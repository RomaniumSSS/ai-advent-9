"""General model-output quarantine tests, offline only."""
import copy,json,tempfile
from pathlib import Path
from unittest.mock import patch
import run_selection_context_review as h
run=h.run;prep=h.prep
rows=run.load();byid={r['case_id']:r for r in rows};ledger=run.strict_json((run.ROOT/'ledger.json').read_text());before=copy.deepcopy(ledger)
queue=run.strict_json(h.QUEUE.read_text());old=copy.deepcopy(queue)
for a in ledger['attempts']:h.reconcile_one(a,byid[a['case_id']],queue)
assert len(queue['cases'])==5 and ledger['attempts']==before['attempts']
assert all(queue['cases'][k]==v for k,v in old['cases'].items())
spec=byid[ledger['attempts'][0]['case_id']];raw=run.strict_json((run.ROOT/(spec['case_id']+'.json')).read_text());env=run.strict_json(raw['response_text'])
for category in ['parse','schema','coverage','group','length','refusal','context']:
 e=copy.deepcopy(env);choice=e['choices'][0]
 if category=='length':choice['finish_reason']='length'
 elif category=='refusal':choice['message']['refusal']='synthetic'
 elif category=='parse':choice['message']['content']='bad'
 elif category=='schema':choice['message']['content']='{}'
 elif category in ['coverage','group']:
  out=run.strict_json(choice['message']['content']);out['decisions'].pop(next(iter(out['decisions']))) if category=='coverage' else out['document_groups'].append({'message_ids':[],'context_ids':[],'reason':''});choice['message']['content']=json.dumps(out)
 with patch.object(run,'context_guard',return_value=['included_reply_unread_parent:1']) if category=='context' else patch.object(run,'context_guard',wraps=run.context_guard):
  assert h.classify(spec,dict(raw,response_text=json.dumps(e)))
for category in ['429','401','provider','usage','cost','envelope']:
 e=copy.deepcopy(env);bad=copy.deepcopy(raw)
 if category in ['429','401']:bad['http_status']=int(category)
 elif category=='provider':e['provider']='Other'
 elif category=='usage':e['usage']={}
 elif category=='cost':e['usage']['cost']=float('inf')
 else:e['choices']=[]
 bad['response_text']=json.dumps(e)
 try:h.classify(spec,bad)
 except Exception:pass
 else:raise AssertionError('fatal accepted')
with tempfile.TemporaryDirectory() as d,patch.object(run,'ROOT',Path(d)):
 a={'case_id':spec['case_id'],'reserve':run.reserve(spec),'actual_cost':None,'status':'pending'}
 try:h.reconcile_one(a,spec,{'cases':{}})
 except ValueError:pass
 else:raise AssertionError('pending accepted')
 run.write(Path(d)/(spec['case_id']+'.json'),dict(raw,body_sha256='wrong'))
 try:h.reconcile_one(a,spec,{'cases':{}})
 except ValueError:pass
 else:raise AssertionError('identity accepted')
assert run.strict_json((run.ROOT/'ledger.json').read_text())==before
print('PASS:81paid unchanged,5review packets,oldqueue unchanged;parse/schema/coverage/group/context/length/refusal review;HTTP/auth/provider/envelope/usage/nonfinitecost/pending/rawidentity fatal;no API/retries')
with tempfile.TemporaryDirectory() as d,patch.object(run,'ROOT',Path(d)):
 review_id='p-bd9e6d80963ea487c634';review_spec=byid[review_id]
 review_raw=run.strict_json((Path(__file__).resolve().parents[1]/'private/selection-run-v1'/(review_id+'.json')).read_text())
 run.write(Path(d)/(review_id+'.json'),review_raw)
 run.write(Path(d)/(spec['case_id']+'.json'),dict(raw,http_status=429))
 for ids in [[review_id,spec['case_id']],[spec['case_id'],review_id]]:
  try:
   for ident in ids:h.reconcile_one({'case_id':ident,'reserve':run.reserve(byid[ident]),'actual_cost':None,'status':'pending'},byid[ident],{'cases':{}})
  except ValueError as error:assert str(error)=='http_error'
  else:raise AssertionError('review masked fatal')
 e=copy.deepcopy(env);e['usage']['cost']=10
 run.write(Path(d)/(spec['case_id']+'.json'),dict(raw,response_text=json.dumps(e)))
 try:h.reconcile_one({'case_id':spec['case_id'],'reserve':run.reserve(spec),'actual_cost':None,'status':'pending'},spec,{'cases':{}})
 except ValueError as error:assert str(error)=='actual_over_reserve'
 else:raise AssertionError('reserve exceeded')
print('PASS:review cannot mask fatal first/last;costoverreserve fatal')
