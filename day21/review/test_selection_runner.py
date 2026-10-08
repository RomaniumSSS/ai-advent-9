"""Offline targeted recovery, cost, strict output and context-only tests."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import run_selection_requests as runner
import prepare_selection_requests as prep

rows=runner.load();pilot=runner.pilot_ids(rows)
assert len(pilot)==12
assert set(pilot[:4])=={'p-4265ce3dd6da0964a616','p-e7b7548dcfafa17e7f55','p-6c1b8eda0210859d71b0','p-c0b02517064ab894ada5'}
assert sum(runner.reserve(r) for r in rows)<9
for raw in ['{"a":1,"a":2}','{"a":NaN}']:
 try:runner.strict_json(raw)
 except ValueError:pass
 else:raise AssertionError('malformed accepted')
spec={'body':{'messages':[{}, {'content':json.dumps({'owned_messages':[{'id':2,'reply_to':1}], 'context_messages':[{'id':1,'attachment_presence':True,'content_read':False}]})}]}}
output={'decisions':{'2':{'decision':'include','flags':[]}},'document_groups':[{'message_ids':[2],'context_ids':[]}]}
assert runner.context_guard(spec,output)
output['decisions']['2']['flags']=['incomplete_context'];output['document_groups'][0]['context_ids']=[1]
assert not runner.context_guard(spec,output)
try:runner.schema_check({'x':True},{'type':'object','properties':{'x':{'type':'integer'}},'required':['x'],'additionalProperties':False})
except ValueError:pass
else:raise AssertionError('bool accepted as integer')
row=rows[0];ident=row['case_id'];ledger={'attempts':[{'case_id':ident,'reserve':runner.reserve(row),'status':'pending','actual_cost':None}]}
with tempfile.TemporaryDirectory() as directory,patch.object(runner,'ROOT',Path(directory)):
 runner.reconcile(ledger,{ident:row});assert ledger['stop_reason']=='pending_without_response'
 del ledger['stop_reason']
 raw={'body_sha256':row['body_sha256'],'http_status':429,'response_text':'{"usage":{"cost":0.001}}'}
 runner.write(Path(directory)/(ident+'.json'),raw)
 runner.reconcile(ledger,{ident:row});assert ledger['attempts'][0]['status']=='error' and ledger['stop_reason']=='http_error'
 assert ledger['attempts'][0]['actual_cost']==.001
 before=copy.deepcopy(ledger);runner.reconcile(ledger,{ident:row});assert ledger==before
 duplicate=copy.deepcopy(ledger);duplicate['attempts']*=2
 try:runner.reconcile(duplicate,{ident:row})
 except ValueError:pass
 else:raise AssertionError('duplicate reservation')
 raw['response_text']='invalid';runner.write(Path(directory)/(ident+'.json'),raw);runner.reconcile(ledger,{ident:row})
 assert ledger['attempts'][0]['actual_cost'] is None and runner.bound(ledger)==runner.reserve(row)
assert 'api_key()' not in Path(runner.__file__).read_text().split('if not args.live:return')[0]
print('PASS: deterministic12pilot, budget, duplicates, malformed JSON/types, context-only unread guard, durable429/unknown reservation/reconciliation/no-repeat; no API')

with patch.object(runner.requests,'post') as post:
 runner.send(row,'SYNTHETIC_SECRET')
 kwargs=post.call_args.kwargs
 assert kwargs['data']==prep.encoded(row['body'])
 assert len(kwargs['data'])==row['full_utf8_bytes']
 assert prep.digest(row['body'])==row['body_sha256']
 assert kwargs['headers']['Content-Type']=='application/json' and kwargs['verify']
for value,schema in [('',{'type':'string','minLength':1}),([] ,{'type':'array','minItems':1})]:
 try:runner.schema_check(value,schema)
 except ValueError:pass
 else:raise AssertionError('schema minimum ignored')
print('PASS: exact frozen UTF8 sent bytes, TLS enabled, schema minima')
output={'case_id':ident,'decisions':{str(i):{'decision':'exclude','reason':'synthetic','flags':[]} for i in row['owned_ids']},'document_groups':[],'review_groups':[],'missing_context_ids':[],'notes':''}
envelope={'model':prep.MODEL,'provider':'DeepInfra','usage':{'cost':.001},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(output)}}]}
raw={'body_sha256':row['body_sha256'],'http_status':200,'response_text':json.dumps(envelope)}
assert runner.process(row,raw)==output
for change in ['length','duplicate','provider']:
 bad=copy.deepcopy(envelope)
 if change=='length':bad['choices'][0]['finish_reason']='length'
 elif change=='duplicate':bad['choices'][0]['message']['content']='{"case_id":"a","case_id":"b"}'
 else:bad['provider']='Other'
 try:runner.process(row,dict(raw,response_text=json.dumps(bad)))
 except Exception:pass
 else:raise AssertionError('invalid accepted')
with tempfile.TemporaryDirectory() as directory,patch.object(runner,'ROOT',Path(directory)):
 pending={'attempts':[{'case_id':ident,'reserve':runner.reserve(row),'status':'pending','actual_cost':None}]}
 runner.write(Path(directory)/(ident+'.json'),raw)
 seen=runner.reconcile(pending,{ident:row})
 assert seen=={ident} and pending['attempts'][0]['status']=='complete'
 assert pending['attempts'][0]['actual_cost']==.001
print('PASS: saved-response interruption reconciles without API; length/duplicate/provider stops')
