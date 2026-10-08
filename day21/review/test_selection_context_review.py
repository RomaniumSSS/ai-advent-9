"""Offline tests; paid state immutable, no calls."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import run_selection_context_review as h
run=h.run;prep=h.prep
rows=run.load();byid={r['case_id']:r for r in rows}
ledger=run.strict_json((run.ROOT/'ledger.json').read_text());before=copy.deepcopy(ledger)
queue={'cases':{}}
for attempt in ledger['attempts']:h.reconcile_one(attempt,byid[attempt['case_id']],queue)
assert set(queue['cases'])=={'p-0194e3fa84cc0eeef94a','p-31d10a3f512db9ccd685'}
assert all(v['whole_case'] and v['disposition']=='review_required' for v in queue['cases'].values())
assert ledger['attempts']==before['attempts'] and len(rows)-len(ledger['attempts'])==1698
spec=byid[ledger['attempts'][0]['case_id']]
raw=run.strict_json((run.ROOT/(spec['case_id']+'.json')).read_text())
for kind in ['http','length','schema','duplicate','unknown_context']:
 bad=copy.deepcopy(raw)
 if kind=='http':bad['http_status']=429
 else:
  envelope=run.strict_json(bad['response_text'])
  if kind=='length':envelope['choices'][0]['finish_reason']='length'
  elif kind=='schema':envelope['choices'][0]['message']['content']='{}'
  elif kind=='duplicate':envelope['choices'][0]['message']['content']='{"a":1,"a":2}'
  bad['response_text']=json.dumps(envelope)
 try:
  with patch.object(run,'context_guard',return_value=['unknown:1']) if kind=='unknown_context' else patch.object(run,'context_guard',wraps=run.context_guard):h.classify(spec,bad)
 except Exception:pass
 else:raise AssertionError('fatal accepted')
with tempfile.TemporaryDirectory() as directory,patch.object(run,'ROOT',Path(directory)):
 attempt={'case_id':spec['case_id'],'reserve':run.reserve(spec),'actual_cost':None,'status':'pending'}
 try:h.reconcile_one(attempt,spec,{'cases':{}})
 except ValueError:pass
 else:raise AssertionError('unknown pending')
 run.write(Path(directory)/(spec['case_id']+'.json'),raw)
 h.reconcile_one(attempt,spec,{'cases':{}});assert attempt['status']=='complete'
 envelope=run.strict_json(raw['response_text']);envelope['usage']['cost']=10
 run.write(Path(directory)/(spec['case_id']+'.json'),dict(raw,response_text=json.dumps(envelope)))
 try:h.reconcile_one(attempt,spec,{'cases':{}})
 except ValueError:pass
 else:raise AssertionError('cost cap')
assert run.strict_json((run.ROOT/'ledger.json').read_text())==before
print('PASS: two whole-case context quarantines, unchanged charged statuses/costs,1698 remaining/no repeats,API/length/schema/duplicate/unknowncontext/pending fatal,cost reserve,recovery; no API')

context_id='p-0194e3fa84cc0eeef94a'
context_spec=byid[context_id]
context_raw=run.strict_json((run.ROOT/(context_id+'.json')).read_text())
with tempfile.TemporaryDirectory() as directory,patch.object(run,'ROOT',Path(directory)):
 run.write(Path(directory)/(context_id+'.json'),context_raw)
 run.write(Path(directory)/(spec['case_id']+'.json'),dict(raw,http_status=429))
 for ids in [[context_id,spec['case_id']],[spec['case_id'],context_id]]:
  try:
   for ident in ids:h.reconcile_one({'case_id':ident,'reserve':run.reserve(byid[ident]),'actual_cost':None,'status':'pending'},byid[ident],{'cases':{}})
  except ValueError as error:assert str(error)=='http_error'
  else:raise AssertionError('context masked fatal')
 run.write(Path(directory)/(spec['case_id']+'.json'),raw)
 try:h.reconcile_one({'case_id':spec['case_id'],'reserve':run.reserve(spec),'actual_cost':None,'status':'pending'},spec,{'cases':{spec['case_id']:{}}})
 except ValueError as error:assert str(error)=='review_queue_mismatch'
 else:raise AssertionError('stale queue accepted')
print('PASS: fatal first/last cannot be masked by context; complete case stale queue rejected')
