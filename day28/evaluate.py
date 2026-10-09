"""Новые последовательные E2E/replay прогоны; рубрика не заменяется автопроверкой цитат."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from core import Engine, GEN_OPTIONS, check_budget, load_index, packed, save_private, sha

HERE=Path(__file__).resolve().parent

def assess(result,expected):
    answer=result.get('answer') or {}
    docs={s['source'] for s in answer.get('sources',[])}
    unknown=bool(expected.get('unknown'))
    return {'transport_ok':result['status']!='error','citations_valid':result['citations_valid'],
        'required_sources_present':set(expected.get('required_document_ids',[]))<=docs if not unknown else None,
        'unknown_without_sources':result['status']=='unknown' and not docs if unknown else None,
        'supported_facts':'requires_human_review','completeness':'requires_human_review',
        'groundedness_semantic':None,'human_verdict':None}

def run(args):
    suite=json.loads(args.suite.read_text());run_id=uuid.uuid4().hex
    output=args.output or HERE/'private'/'runs'/run_id
    if HERE/'private' not in output.resolve().parents:raise ValueError('evaluation_output_must_be_private')
    output.mkdir(parents=True,exist_ok=False,mode=0o700);output.chmod(0o700)
    identity,chunks=load_index(args.index_root);engine=Engine(chunks,identity)
    receipt={'run_id':run_id,'mode':args.mode,'suite_id':suite['suite_id'],'suite_sha256':sha(suite),
        'started_at':datetime.now(timezone.utc).isoformat(),'generation_options':GEN_OPTIONS,'index':identity,
        'rubric':suite.get('rubric'),'status':'running','requests':[]}
    save_private(output/'suite-frozen.json',suite)
    try:
        for case in suite['cases']:
            for repeat in range(1,args.repeats+1):
                kwargs={}
                if args.mode=='replay':
                    if sha(case['messages'])!=case['hashes']['messages_sha256']:raise ValueError('frozen_messages_hash_mismatch')
                    kwargs={'replay_messages':case['messages'],'replay_selected':case['selected']}
                result=engine.ask(case['question'],'all' if args.mode=='replay' else 'public',run_id=run_id,**kwargs)
                result.update(case_id=case['case_id'],repeat=repeat,assessment=assess(result,case.get('expected',{})))
                if args.mode=='replay':
                    result.update(historical_response=case['historical_response'],historical_metrics=case['historical_metrics'],
                                  frozen_input_hashes=case['hashes'],messages_identical=result['messages']==case['messages'])
                save_private(output/(result['request_id']+'.json'),result)
                receipt['requests'].append({'case_id':case['case_id'],'repeat':repeat,'request_id':result['request_id'],
                    'status':result['status'],'times':result['times'],'metrics':result['metrics'],
                    'assessment':result['assessment'],'answer_sha256':sha(result['answer']),
                    'receipt':result['request_id']+'.json'})
                save_private(output/'run.json',receipt)
                print(f"{case['case_id']} #{repeat}: {result['status']} · request {result['request_id']} · {result['times']['total']:.2f}s",flush=True)
        receipt['stability']=[]
        for case in suite['cases']:
            group=[r for r in receipt['requests'] if r['case_id']==case['case_id']]
            receipt['stability'].append({'case_id':case['case_id'],'repeats':len(group),
                'identical_answer_json':len({r['answer_sha256'] for r in group})==1,
                'statuses':[r['status'] for r in group],'semantic_comparison':'requires_human_review'})
        receipt['status']='completed_with_errors' if any(r['status']=='error' for r in receipt['requests']) else 'completed'
    except Exception as error:
        receipt.update(status='error',error={'type':type(error).__name__,'message':str(error)})
        raise
    finally:
        receipt['finished_at']=datetime.now(timezone.utc).isoformat();save_private(output/'run.json',receipt)
    print(f'run {run_id} · {output}',flush=True)
    return 1 if receipt['status']!='completed' else 0

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Day28: frozen E2E или точный replay исторических messages')
    p.add_argument('--suite',type=Path,required=True);p.add_argument('--mode',choices=('e2e','replay'),required=True)
    p.add_argument('--index-root',type=Path,default=HERE/'private'/'index-release-v1')
    p.add_argument('--repeats',type=int,default=2);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if not 1<=a.repeats<=3:p.error('число повторов должно быть 1–3')
    raise SystemExit(run(a))
