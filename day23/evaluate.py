"""Общий бюджет Day23: резерв каждой попытки и безопасное продолжение."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import time
import requests
from common import API, MODEL, SYSTEM, estimate, key_from_env, packed, payload, refresh_pricing, save, validate_answer

class HTTPFailure(Exception):
    def __init__(self,status):
        self.status=status


def dispatch(url, body, key):
    with requests.Session() as session:
        session.trust_env=False
        response=session.post(url,json=body,headers={'Authorization':'Bearer '+key},timeout=(10,90),allow_redirects=False)
        return {'http_status':response.status_code,'body':response.text}


def pricing_check(pricing):
    if set(pricing) != {'prompt','completion'} or any(type(v) not in (int,float) or not math.isfinite(v) or v < 0 for v in pricing.values()):
        raise ValueError('invalid_pricing')
    if pricing['prompt'] > .14/1e6 or pricing['completion'] > .42/1e6:
        raise ValueError('pricing_exceeds_approved_rates')


def evaluate(prepared, output_dir, key, budget=1.0, pricing=None, dispatch_fn=dispatch,
             max_new_calls=None, max_retries=2, sleep=time.sleep):
    if type(budget) not in (int,float) or not math.isfinite(budget) or not 0 < budget <= 1:
        raise ValueError('invalid_budget')
    if max_retries not in (0,1,2) or (max_new_calls is not None and (type(max_new_calls) is not int or max_new_calls < 1)):
        raise ValueError('invalid_retry_or_call_limit')
    if prepared.get('model') != MODEL:
        raise ValueError('prepared_model_mismatch')
    jobs=[]
    for c in prepared['cases']:
        for mode in prepared.get('modes',c['messages']):
            if not all(isinstance(v,str) and v and all(ch.isalnum() or ch in '_-' for ch in v) for v in (c['id'],mode)):
                raise ValueError('invalid_job_id')
            msgs=c['messages'][mode]
            if not isinstance(msgs,list) or len(msgs) != 2 or any(not isinstance(m,dict) or set(m) != {'role','content'} or not isinstance(m['content'],str) for m in msgs):
                raise ValueError('invalid_messages_schema')
            if msgs[0] != {'role':'system','content':SYSTEM} or msgs[1]['role'] != 'user' or not msgs[1]['content'].startswith('Вопрос: '):
                raise ValueError('generator_prompt_changed')
            if len(packed(msgs)) > 24000:
                raise ValueError('prepared_messages_exceed_budget')
            body=payload(msgs)
            jobs.append((c['id'],mode,body,hashlib.sha256(packed(body)).hexdigest()))
    if len({(i,m) for i,m,_,_ in jobs}) != len(jobs):
        raise ValueError('duplicate_jobs')
    directory=Path(output_dir)
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    directory.chmod(0o700)
    with open(directory/'run.lock','a') as lock:
        os.chmod(directory/'run.lock',0o600)
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('run_already_locked')
        path=directory/'ledger.json'
        ledger=json.loads(path.read_text()) if path.exists() else {'version':1,'budget':budget,'model':MODEL,'entries':[]}
        if ledger.get('budget') != budget or ledger.get('model') != MODEL:
            raise ValueError('resume_configuration_mismatch')
        for e in ledger['entries']:
            if e['status'] in ('inflight','unknown','fatal') and e.get('recovery') not in ('skip','retry'):
                raise ValueError('explicit_recovery_required')
            if e.get('recovery') and (not e.get('recovery_reason') or e.get('charged') != e.get('actual_cost',e['reserve'])):
                raise ValueError('invalid_recovery')
        for ident,mode,_,digest in jobs:
            if any(e['id']==ident and e['mode']==mode and e['payload_sha256'] != digest for e in ledger['entries']):
                raise ValueError('job_payload_changed')
        pricing=refresh_pricing() if pricing is None else pricing
        pricing_check(pricing)
        ledger['pricing']=pricing
        save(path,ledger)
        calls=0
        for ident,mode,body,digest in jobs:
            previous=[e for e in ledger['entries'] if e['id']==ident and e['mode']==mode]
            if any(e['status']=='completed' or e.get('recovery')=='skip' for e in previous):
                continue
            retries=0
            while True:
                if max_new_calls is not None and calls >= max_new_calls:
                    return ledger
                reserve=estimate(body['messages'],pricing)
                spent=sum(e.get('charged',e['reserve']) for e in ledger['entries'])
                if spent+reserve > budget:
                    raise ValueError('budget_exceeded')
                attempt=1+sum(e['id']==ident and e['mode']==mode for e in ledger['entries'])
                e={'id':ident,'mode':mode,'attempt':attempt,'payload_sha256':digest,'reserve':reserve,
                   'charged':reserve,'status':'inflight','started_at':time.time()}
                ledger['entries'].append(e)
                save(path,ledger)  # AICODE-NOTE: резерв предшествует HTTP, включая падение процесса.
                calls+=1
                started=time.monotonic()
                raw_path=directory/f'{ident}-{mode}-attempt-{attempt}.json'
                try:
                    raw=dispatch_fn(API+'/chat/completions',body,key)
                    save(raw_path,raw)
                    if 'http_status' in raw:
                        if not 200 <= raw['http_status'] < 300:
                            raise HTTPFailure(raw['http_status'])
                        result=json.loads(raw['body'])
                    else:
                        result=raw
                    # Даже некорректный ответ может содержать достоверное списание.
                    actual=result.get('usage',{}).get('cost')
                    if type(actual) in (int,float) and math.isfinite(actual) and actual >= 0:
                        e['charged']=actual
                        e['actual_cost']=actual
                    cost=validate_answer(result)
                    e.update(status='completed',actual_cost=cost,response_file=raw_path.name)
                    if cost is None:
                        e['cost_unknown']=True
                    e['elapsed_seconds']=time.monotonic()-started
                    save(path,ledger)
                    if cost is None:
                        raise ValueError('unknown_cost_stop')
                    if sum(x.get('charged',x['reserve']) for x in ledger['entries']) > budget:
                        raise ValueError('actual_cost_exceeds_budget')
                    break
                except Exception as error:
                    if e['status']=='completed':
                        raise
                    transient=isinstance(error,(requests.Timeout,requests.ConnectionError)) or (isinstance(error,HTTPFailure) and (error.status==429 or 500<=error.status<600))
                    e.update(status='transient' if transient else 'fatal',error_type=type(error).__name__,elapsed_seconds=time.monotonic()-started)
                    if not raw_path.exists():
                        save(raw_path,{'error_type':type(error).__name__})
                    save(path,ledger)
                    if not transient or retries >= max_retries:
                        e['status']='unknown' if transient else 'fatal'
                        save(path,ledger)
                        raise ValueError('transient_retries_exhausted' if transient else 'fatal_response_stop') from None
                    retries+=1
                    sleep(2**retries)
        return ledger


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--prepared',required=True)
    p.add_argument('--output-dir',required=True)
    p.add_argument('--env-file')
    p.add_argument('--budget',type=float,default=1)
    p.add_argument('--limit',type=int)
    p.add_argument('--max-retries',type=int,default=2)
    args=p.parse_args()
    try:
        ledger=evaluate(json.loads(Path(args.prepared).read_text()),args.output_dir,key_from_env(args.env_file),args.budget,max_new_calls=args.limit,max_retries=args.max_retries)
        print(json.dumps({'status':'checkpoint','attempts':len(ledger['entries']),'charged':sum(e['charged'] for e in ledger['entries'])}))
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__,'reason':str(error) if isinstance(error,ValueError) else 'request_error'}))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
