"""One-case-at-a-time local pilot; all source/output text stays in private/."""
import json,os,time,urllib.request,hashlib
from pilot_validation import validate
from pathlib import Path
os.umask(0o077)
ROOT=Path(__file__).resolve().parents[1]/'private'
BASE='http://127.0.0.1:11435'
MODEL='qwen3:8b'
SYSTEM=(Path(__file__).parent/'semantic-rubric-v2.txt').read_text()
def api(endpoint,payload=None):
 req=urllib.request.Request(BASE+endpoint,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=600) as r:return json.load(r)
def write(path,obj):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');temp.chmod(0o600);temp.replace(path)
data=json.loads((ROOT/'semantic-pilot-v2-input.json').read_text());messages={m['id']:m for m in data['messages']}
show=api('/api/show',{'model':MODEL});tags=api('/api/tags');model=next(m for m in tags['models'] if m['name']==MODEL)
meta={'model':MODEL,'digest':model['digest'],'capabilities':show.get('capabilities'), 'think':False,'num_ctx':8192,'num_predict':2048,'temperature':0,'input_sha256':hashlib.sha256((ROOT/'semantic-pilot-v2-input.json').read_bytes()).hexdigest(),'system_prompt':SYSTEM,'cases':[]}
result_path=ROOT/'semantic-pilot-v2-local.json'
if result_path.exists():
 previous=json.loads(result_path.read_text())
 for key in ['model','digest','think','num_ctx','num_predict','temperature','input_sha256','system_prompt']:
  if previous.get(key)!=meta[key]:
   raise ValueError('Checkpoint incompatible: '+key)
 meta['cases']=previous.get('cases',[])
completed={c['case_id'] for c in meta['cases']}
write(ROOT/'semantic-pilot-v2-local.json',meta)
for case in data['cases']:
 if case['case_id'] in completed:
  continue
 payload={'case':case,'messages':[messages[i] for i in case['message_ids']]}
 start=time.monotonic()
 try:
  response=api('/api/chat',{'model':MODEL,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],'format':'json','stream':False,'think':False,'keep_alive':'60s','options':{'num_ctx':8192,'num_predict':2048,'temperature':0}})
  raw=response.get('message',{}).get('content','');parsed=json.loads(raw)
  ids=[d.get('message_id') for d in parsed.get('decisions',[])]
  errors=validate(case,parsed)
  if response.get('done_reason')=='length': errors.append('truncated_output')
  valid=not errors
  record={'case_id':case['case_id'],'output':parsed,'valid_coverage':valid,'validation_errors':errors,'done_reason':response.get('done_reason'),'elapsed_seconds':round(time.monotonic()-start,3),'usage':{k:response.get(k) for k in ['prompt_eval_count','eval_count','total_duration','load_duration']}}
 except Exception as e:
  record={'case_id':case['case_id'],'error_type':type(e).__name__,'elapsed_seconds':round(time.monotonic()-start,3)}
 meta['cases'].append(record);write(ROOT/'semantic-pilot-v2-local.json',meta)
 print(json.dumps({k:record.get(k) for k in ['case_id','valid_coverage','done_reason','elapsed_seconds','error_type']}),flush=True)
api('/api/generate',{'model':MODEL,'keep_alive':0})
print('Completed local pilot; model unloaded.',flush=True)
