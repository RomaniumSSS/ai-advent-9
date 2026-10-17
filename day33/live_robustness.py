"""Операторский прогон holdout: только явный --live и существующий ledger."""
import argparse
import copy
import json
import hashlib
import math
from pathlib import Path
from unittest.mock import patch
from app import Application
from budget import Budget
from domain import ROOT, retrieve, validate_context
from mcp_client import read_context
from model import ModelResponseError

class SessionBudget:
    def __init__(self, ledger, ceiling):
        if type(ceiling) not in (int, float) or not math.isfinite(ceiling) or not 0 < ceiling <= 1:
            raise ValueError('Потолок accounted должен быть конечным числом в (0, 1]')
        self.budget = Budget(ledger)
        self.ceiling = ceiling
    def reserve(self, run_id, maximum):
        # Оператор запускает оба дня последовательно; исходный ledger не меняется.
        with self.budget.connect() as db:
            accounted = db.execute('SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM reservations').fetchone()[0]
        if accounted + maximum > self.ceiling: raise RuntimeError('Исчерпан операторский лимит robustness')
        return self.budget.reserve(run_id, maximum)
    def settle(self, reservation, actual):self.budget.settle(reservation, actual)

def run_case(case, application):
    context, trace = read_context(case['user_id'], case['ticket_id'])
    context = copy.deepcopy(context)
    if 'events' in case: context['ticket']['events'] = case['events']
    if 'subject' in case: context['ticket']['subject'] = case['subject']
    context = validate_context(context, case['user_id'], case['ticket_id'])
    corpus=json.loads((ROOT/'data/knowledge.json').read_text())
    for source in corpus:
        if source['id'] in case.get('faq_overrides',{}):source['text']=case['faq_overrides'][source['id']]
    if case.get('empty_corpus'):corpus=[]
    with patch('app.read_context',return_value=(context,trace)), patch('app.retrieve',side_effect=lambda q,t:retrieve(q,t,corpus)):
        return application.ask(case['user_id'],{'ticket_id':case['ticket_id'],'question':case['question']})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true',required=True)
    parser.add_argument('--ledger',required=True);parser.add_argument('--manifest',default=str(ROOT/'data/robustness/live-cases.json'))
    parser.add_argument('--output',required=True);parser.add_argument('--case',required=True)
    parser.add_argument('--accounted-ceiling',type=float,default=.767852)
    args=parser.parse_args()
    cases=json.loads(Path(args.manifest).read_text())
    case=next(c for c in cases if c['id']==args.case)
    output=Path(args.output)
    if output.exists():raise ValueError('Файл evidence уже существует')
    result={'case':case,'mode':'live','semantic_verdict':'REQUIRES_INDEPENDENT_REVIEW',
            'sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (ROOT/'app.py',ROOT/'domain.py',ROOT/'model.py',ROOT/'transport.py',ROOT/'data/knowledge.json',ROOT/'data/crm.json')},
            'manifest_sha256':hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
            'fixture_injection':'Synthetic overrides are injected AFTER real MCP scope read; probes application/retrieval/model, not MCP fixture delivery.'}
    try:result['response']=run_case(case,Application('live',SessionBudget(args.ledger,args.accounted_ceiling)))
    except ModelResponseError as exc:result['error']=exc.evidence
    except Exception as exc:result['error']={'type':type(exc).__name__,'message':str(exc)}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
