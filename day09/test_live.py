"""Парные реальные прогоны с общим бюджетом и отчётом после каждого хода.

uv run day09/test_live.py --env-file /путь/.env --repeats 1
Затем --start 2 --repeats 2. Существующие результаты не перезаписываются.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from agent import Agent, AgentConfig, CompressionConfig, SUMMARY_PROMPT
from experiment import BudgetLedger, MeasuredClient, real_client, DEFAULT_LEDGER, PROVIDER
from scenarios import SCENARIOS
from store import SqliteStore

OUT = Path(__file__).parent/'results'/'final'

def write(path, data):
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    tmp.replace(path)

def run_pair(scenario, repeat, ledger, resume=False):
    name=f'{scenario}-r{repeat}'
    target=OUT/(name+'.json')
    config=AgentConfig(temperature=0, max_tokens=4000)
    report={'scenario':scenario,'repeat':repeat,'started':datetime.now(timezone.utc).isoformat(),
            'config':asdict(config),'compression':asdict(CompressionConfig()),
            'provider':PROVIDER, 'summary_prompt':SUMMARY_PROMPT, 'reasoning_enabled':False,
            'facts':SCENARIOS[scenario]['facts'],'turns':[], 'complete':False}
    old_turn=None
    if target.exists():
        if not resume:raise RuntimeError(f'{target} существует; используйте --resume')
        saved=json.loads(target.read_text())
        if saved.get('complete'):return saved
        if saved.get('summary_prompt') != SUMMARY_PROMPT:
            raise RuntimeError('промпт изменён: старый эксперимент нельзя незаметно продолжить')
        report=saved
        report.setdefault('stops',[]).append(report.pop('stop_reason','прерванный процесс'))
        if report['turns']:
            last=report['turns'][-1]
            if any(d['reply']['store_error'] or d['reply']['finish_reason']=='length' for d in last['sides'].values()):
                raise RuntimeError('обрезанный ответ или сбой сохранения требует разбора; автоматический повтор запрещён')
            if any(d['reply']['error'] or d['reply']['store_error'] or not d['reply']['text'].strip()
                   or d['reply']['finish_reason']=='length' for d in last['sides'].values()):
                old_turn=report['turns'].pop()
    agents={}
    for side in ['full','compressed']:
        agents[side]=Agent(config=config,compression=CompressionConfig(enabled=side=='compressed'),
            store=SqliteStore(OUT/(name+'.db'),side),
            client=MeasuredClient(real_client(),ledger,name+':'+side,OUT/(name+'-'+side+'-calls.json')))
        expected=len(report['turns'])
        if old_turn:
            r=old_turn['sides'][side]['reply']
            expected+=int(not r['error'] and bool(r['text'].strip()))
        if agents[side].turns != expected:raise RuntimeError('архив не совпадает с checkpoint; нужен разбор')
    write(target,report)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for i in range(len(report['turns'])+1,len(SCENARIOS[scenario]['questions'])+1):
            question=SCENARIOS[scenario]['questions'][i-1]
            turn={'number':i,'question':question,'sides':{}}
            previous={}
            if old_turn and old_turn['number']==i:
                previous=old_turn['sides']
                for side,data in previous.items():
                    r=data['reply']
                    if not r['error'] and not r['store_error'] and r['text'].strip() and r['finish_reason']!='length':
                        turn['sides'][side]=data
            futures={pool.submit(agent.ask,question):side for side,agent in agents.items() if side not in turn['sides']}
            for future in as_completed(futures):
                side=futures[future];agent=agents[side];reply=future.result()
                attempts=list(previous.get(side,{}).get('attempts',[]))
                if side in previous:attempts.append(previous[side]['reply'])
                for retry in range(2):
                    if not reply.error or not any(code in reply.error for code in ('429','502','503','504')):break
                    attempts.append(asdict(reply))
                    print(f'{name} {i} {side}: временная ошибка, повтор {retry+1}/2 через 15 секунд',flush=True)
                    time.sleep(15)
                    reply=agent.ask(question)
                turn['sides'][side]={'attempts':attempts,'reply':asdict(reply),'event':agent.compression_event,
                    'summary':agent.summary,'covered':agent.covered,'usage':agent.store.usage_by_kind()}
                write(target,{**report,'pending_turn':turn})
            report['turns'].append(turn);report.pop('pending_turn',None)
            write(target,report)
            print(name,f'{i}/16:',{s:(d['reply']['prompt_tokens'],d['reply']['completion_tokens']) for s,d in turn['sides'].items()},flush=True)
            for side,data in turn['sides'].items():
                r=data['reply']
                if r['error'] or r['store_error'] or not r['text'].strip() or r['finish_reason']=='length':
                    report['stop_reason']=f'{side}: '+str(r['error'] or r['store_error'] or 'пустой/обрезанный ответ')
                    write(target,report);return report
    report['complete']=True
    report['failed_attempts_without_usage']=sum('error' in record for agent in agents.values() for record in agent.client.records)
    report['totals']={side:a.store.usage_by_kind() for side,a in agents.items()}
    write(target,report)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--scenario',choices=list(SCENARIOS))
    parser.add_argument('--start',type=int,default=1)
    parser.add_argument('--repeats',type=int,default=1)
    parser.add_argument('--ledger',type=Path,default=DEFAULT_LEDGER)
    parser.add_argument('--budget',type=float,default=0.50)
    args=parser.parse_args()
    if args.repeats<1 or args.start<1: parser.error('номера прогонов должны быть положительными')
    load_dotenv(args.env_file) if args.env_file else load_dotenv()
    OUT.mkdir(parents=True,exist_ok=True)
    ledger=BudgetLedger(args.ledger,args.budget)
    tasks=[(s,r) for r in range(args.start,args.start+args.repeats) for s in SCENARIOS if args.scenario is None or s==args.scenario]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(run_pair,s,r,ledger,args.resume) for s,r in tasks]
        outcomes=[f.result() for f in futures]
    write(OUT/'budget-report.json',ledger.report())
    print(json.dumps({k:v for k,v in ledger.report().items() if k!='reservations'}),flush=True)
    if not all(r['complete'] for r in outcomes): raise SystemExit('есть незавершённый прогон, см. отчёты')
if __name__=='__main__': main()
