"""Реальная регрессия 24 условий на VPS: локальный эмбеддер, облачных ответов нет."""
import base64
import json
from pathlib import Path
import subprocess
from common import packed, save

def check():
    here=Path(__file__).parent
    sources={n:(here/(n+'.py')).read_text() for n in ('common','temporal','retrieval')}
    job=base64.b64encode(packed({'sources':sources})).decode()
    script='''import base64,json,sys,types
job=json.loads(base64.b64decode(%r))
for name in ('common','temporal','retrieval'):
 m=types.ModuleType(name);sys.modules[name]=m;exec(compile(job['sources'][name],name+'.py','exec'),m.__dict__)
from common import *
from retrieval import *
identity,chunks=load_index('/opt/day21/private/index-release-v1','structure')
url='http://127.0.0.1:11434'
tags=request(url+'/api/tags')['models']
match=next((m for m in tags if m.get('name')==EMBED_MODEL or m.get('model')==EMBED_MODEL),None)
if not match or match['digest']!=identity['config']['model']['digest']:raise ValueError('embedding_digest_mismatch')
show=request(url+'/api/show',{'model':EMBED_MODEL})
if show.get('remote_host') or show.get('remote_model'):raise ValueError('remote_embedding_forbidden')
questions=['дай условие дня '+str(n) for n in range(1,25)]
vectors=[]
for offset in range(0,len(questions),8):
 response=request(url+'/api/embed',{'model':EMBED_MODEL,'input':[query_input(q) for q in questions[offset:offset+8]],'truncate':False,'options':OPTIONS})
 vectors.extend(vector(v) for v in response['embeddings'])
rows=[]
for day,q,v in zip(range(1,25),questions,vectors):
 trace=retrieve(chunks,q,v,Config())
 expected={c['chunk_id'] for c in chunks if c['source']=='assignment' and c.get('day')==day}
 selected={c['chunk_id'] for c in trace['selected'] if c['source']=='assignment' and c.get('day')==day}
 rows.append({'day':day,'expected_chunks':len(expected),'selected_assignment_chunks':len(selected),'all_assignment_chunks_selected':expected==selected and bool(expected),'selected_chunk_ids':sorted(selected),'below_threshold_selected':sum(c['score']<.35 for c in trace['selected'] if c['chunk_id'] in selected),'missing_reasons':[c['removal_reason'] for c in trace['removed'] if c['chunk_id'] in expected-selected],'context_bytes':trace['context_bytes']})
print(json.dumps({'rows':rows,'identity':identity,'cloud_calls':0,'passed':all(r['all_assignment_chunks_selected'] for r in rows)},ensure_ascii=False))
''' % job
    result=subprocess.run(['ssh','-o','ConnectTimeout=10','crm-agent','/opt/day21/pipeline-venv/bin/python -'],input=script.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=360)
    if result.returncode:raise RuntimeError('assignment_regression_failed_exit_'+str(result.returncode))
    return json.loads(result.stdout)

def main():
    result=check();save(Path(__file__).parent/'private/assignment-regression.json',result)
    print(json.dumps({'passed':result['passed'],'days':len(result['rows']),'selected_assignment_chunks':sum(r['selected_assignment_chunks'] for r in result['rows']),'below_threshold_selected':sum(r['below_threshold_selected'] for r in result['rows']),'failed_days':[r['day'] for r in result['rows'] if not r['all_assignment_chunks_selected']],'cloud_calls':0}))
if __name__=='__main__':main()
