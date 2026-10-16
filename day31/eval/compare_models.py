"""Явное сравнение трёх профилей: общий контекст, один ledger, без автоподбора."""
from __future__ import annotations
import argparse
import copy
import datetime
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import dotenv_values
from day31.assistant import Assistant
from day31.config import ROOT
from day31.mcp_client import GitMcpClient
from day31.provider import ANSWER_SCHEMA, BudgetLedger, OpenRouterProvider, ProviderError, ProviderProfile, build_request, check_endpoint, request_reserve
from day31.retrieval import RetrievalIndex

LEDGER_PATH=ROOT/'.runtime/live-20261016/budget.sqlite3'
SYSTEM_PATH=ROOT/'results/prompt-diagnostic-20261016/tested-system.txt'
QUESTIONS=(
    ('Q6','Откуда помощник Day17 понимает, какие действия доступны у сервера и какие данные нужно передать для выбранного действия?'),
    ('P1','Как клиент MCP узнаёт, какие операции предлагает сервер и какие параметры они принимают в Day17?'),
    ('T3','Покажи короткий JSON-пример описания MCP-инструмента Day17 с полями type и function и объясни их.'),
)


def serialized(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def fingerprint(value):
    return hashlib.sha256(serialized(value).encode()).hexdigest()


def load_profiles(path: Path):
    value=json.loads(path.read_text())
    if not isinstance(value,dict) or set(value)!={'profiles'} or not isinstance(value['profiles'],list) or len(value['profiles'])!=3:
        raise ValueError('Нужен profiles JSON с тремя явными профилями')
    profiles={}
    for row in value['profiles']:
        if not isinstance(row,dict): raise ValueError('Профиль должен быть объектом')
        row=dict(row); name=row.pop('id',None)
        if not isinstance(name,str) or not name or len(name)>60 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name) or name in profiles:
            raise ValueError('Нужны уникальные короткие id профилей без путей')
        profiles[name]=ProviderProfile.from_dict(row)
    return profiles


class ContextSnapshot:
    """Одни реальные observations переиспользуются общим Assistant всех кандидатов."""
    def __init__(self,chunks,git_context,discovery):
        self.chunks=tuple(chunks)
        self.git_context=copy.deepcopy(git_context)
        self.last_discovery=copy.deepcopy(discovery)

    def search(self,question):
        return list(self.chunks)

    def read(self):
        return copy.deepcopy(self.git_context)


def corpus_manifest(index):
    if not isinstance(index,RetrievalIndex):
        return {'scope':'test_double'}
    return {'scope':'README+docs allowlist','files':[{'path':path,'sha256':hashlib.sha256(text.encode()).hexdigest()} for path,text in index._snapshot()]}


def run_comparison(profiles,index,mcp,ledger,system,output,*,execute=False,key=None,client_factory=None,preflight=None):
    """Офлайн plan по умолчанию. Генерация — только execute=True после общего pre-check."""
    if len(profiles)!=3: raise ValueError('Нужны ровно три профиля, сокращение pilot не допускается')
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    summary={'status':'preparing','execute':execute,'planned_calls':len(QUESTIONS)*len(profiles),'calls':[],'execution':{'mode':'parallel_by_profile','max_workers':3,'questions_within_profile':'sequential'},
        'profiles':{name:profile.to_dict() for name,profile in profiles.items()},'system_sha256':hashlib.sha256(system.encode()).hexdigest(),'schema_sha256':fingerprint(ANSWER_SCHEMA)}
    def save(): (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    event_lock=threading.Lock()
    def event(phase,**data):
        with event_lock, (output/'events.jsonl').open('a') as file:
            file.write(json.dumps({'time':datetime.datetime.now(datetime.UTC).isoformat(),'phase':phase,**data},ensure_ascii=False)+'\n')
    def write(name,value): (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    try:
        preflight=preflight or (lambda profile:check_endpoint(profile=profile))
        summary['preflight']={name:preflight(profile) for name,profile in profiles.items()}
        event('preflight_passed',profiles=list(profiles))
        corpus=corpus_manifest(index)
        summary['corpus_sha256']=fingerprint(corpus)
        write('corpus-manifest.json',corpus)
        snapshots={};requests={};total=0
        summary['planned_requests']=[]
        for case_id,question in QUESTIONS:
            chunks=index.search(question)
            if not chunks: raise ValueError('Нет контекста: полный pilot не может быть подготовлен')
            git_context=mcp.read()
            snapshot=ContextSnapshot(chunks,git_context,mcp.last_discovery)
            snapshots[case_id]=snapshot
            context={'question':question,'sources':[c.to_dict() for c in chunks],'git_context':git_context}
            write(case_id+'-context.json',{'context':context,'context_sha256':fingerprint(context),'discovery':mcp.last_discovery,'provenance':'один реальный поиск и один реальный MCP для всех кандидатов'})
            for name,profile in profiles.items():
                request=build_request(profile,system,**context)
                requests[case_id,name]=request
                amount=request_reserve(profile,request);total+=amount
                summary['planned_requests'].append({'case_id':case_id,'profile':name,'reserve_ceiling_usd':amount,'messages_sha256':fingerprint(request['messages']),'input_sha256':fingerprint(request)})
        if corpus_manifest(index)!=corpus: raise ValueError('Корпус изменился во время подготовки: pilot остановлен')
        summary['total_reserve_ceiling_usd']=total
        summary['budget_before']=ledger.budget_state()
        if total>summary['budget_before']['remaining_usd']:
            summary['status']='stopped_budget';event('stopped_budget',ceiling_usd=total,remaining_usd=summary['budget_before']['remaining_usd']);return summary
        summary['status']='plan_ready';save()
        if not execute: return summary
        if not key: raise ValueError('Для execute нужен OPENROUTER_API_KEY')
        # AICODE-NOTE: общий pre-check не блокирует бюджет; каждый вызов сохраняет
        # прежний ledger.reserve. Конкурентный расход может честно остановить серию.
        budget_stop=threading.Event()
        for name in profiles:
            (output/name).mkdir()
        def worker(name,profile):
            # У каждого профиля свой provider/client. Ledger открывает отдельное
            # SQLite-соединение в каждом reserve/finish; общей connection нет.
            provider=OpenRouterProvider(key,ledger,profile=profile,system=system,client=None if client_factory is None else client_factory(profile))
            rows=[]
            for case_id,question in QUESTIONS:
                if budget_stop.is_set(): break
                snapshot=snapshots[case_id]
                request=requests[case_id,name]
                event('call_started',case_id=case_id,profile=name)
                answer=Assistant(snapshot,snapshot,provider).answer(question)
                call=provider.last_call or {}
                content=call.get('content')
                final_json=None;parse_error=None
                if isinstance(content,str):
                    try: final_json=json.loads(content)
                    except json.JSONDecodeError as error: parse_error={'type':'JSONDecodeError','position':error.pos,'message':error.msg}
                record={'case_id':case_id,'profile_id':name,'profile':provider.profile.to_dict(),'trace_id':answer.trace_id,
                    'corpus_sha256':summary['corpus_sha256'],'system_sha256':summary['system_sha256'],'schema_sha256':summary['schema_sha256'],
                    'actual_input':request,'input_sha256':fingerprint(request),'messages_sha256':fingerprint(request['messages']),
                    'final_json':final_json,'final_json_parse_error':parse_error,'provider_final':call,'answer':answer.to_dict(),
                    'context_provenance':'Общий снимок реального retrieval/MCP, без повторного чтения для кандидата'}
                filename=f'{name}/{case_id}.json';write(filename,record)
                error_code=(call.get('error') or {}).get('code')
                rows.append({'case_id':case_id,'profile':name,'trace_id':answer.trace_id,'status':answer.status,'error_code':error_code,'usage':answer.usage,'file':filename})
                event('call_finished',case_id=case_id,profile=name,trace_id=answer.trace_id,status=answer.status,error_code=error_code,usage=answer.usage)
                if error_code=='budget_exceeded':
                    budget_stop.set()
                    break
            return rows
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(worker,name,profile) for name,profile in profiles.items()]
        # Сводку пишет только главный поток после завершения всех workers.
        for future in futures:
            summary['calls'].extend(future.result())
        summary['budget_after']=ledger.budget_state()
        if budget_stop.is_set():
            summary['status']='partial_budget'
            return summary
        summary['status']='complete_with_errors' if any(c['status']=='error' for c in summary['calls']) else 'complete'
        return summary
    except Exception as error:
        summary['status']='stopped_preflight' if 'preflight' not in summary else 'failed'
        summary['error']={'type':type(error).__name__,'message':str(error) if isinstance(error,(ValueError,ProviderError)) else 'Ошибка подготовки или сохранения сравнения'}
        event('stopped',status=summary['status'],error=summary['error'])
        raise
    finally:
        save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profiles',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='Новый каталог, не перезаписывать предыдущий')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--execute',action='store_true',help='Отправить 9 новых платных запросов после общего pre-check')
    mode.add_argument('--plan',action='store_true',help='Только бесплатные metadata/retrieval/MCP и общий расчёт бюджета')
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--budget-usd',type=float)
    args=parser.parse_args()
    if args.execute and args.budget_usd!=0.50: parser.error('Для execute нужен явно разрешённый --budget-usd 0.50')
    if not LEDGER_PATH.is_file(): parser.error('Общий существующий ledger не найден; новый ledger не создаётся')
    try:
        profiles=load_profiles(args.profiles)
        system=SYSTEM_PATH.read_text()
        ledger=BudgetLedger(LEDGER_PATH,0.50)
        index=RetrievalIndex(ROOT,ROOT/'.runtime/compare-index.sqlite3')
        mcp=GitMcpClient(ROOT.parent)
        key=None
        if args.execute:
            key=(dotenv_values(args.env_file).get('OPENROUTER_API_KEY') if args.env_file else os.environ.get('OPENROUTER_API_KEY'))
            if not key: raise ValueError('OPENROUTER_API_KEY не настроен')
        summary=run_comparison(profiles,index,mcp,ledger,system,args.output,execute=args.execute,key=key)
    except (OSError,ValueError,ProviderError) as error:
        parser.error(str(error))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if summary['status'] in ('complete','plan_ready') else 1


if __name__=='__main__': raise SystemExit(main())
