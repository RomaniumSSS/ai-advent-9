"""Exact paid transport deferral only; offline/no retries."""
import copy
from pathlib import Path
from unittest.mock import patch
import run_selection_context_review as h
run=h.run;prep=h.prep
rows=run.load();byid={r['case_id']:r for r in rows};p=run.ROOT/'ledger.json';before=p.read_bytes();ledger=run.strict_json(before);ident='p-5a5999733c18a92cba0b';a=next(a for a in ledger['attempts'] if a['case_id']==ident);rawpath=run.ROOT/(ident+'.json');raw_before=rawpath.read_bytes()
artifact={'case_id':ident,'request_manifest_sha256':run.EXPECTED,'raw_sha256':prep.file_hash(rawpath),'transport_error':'ConnectionError','http_status':None,'disposition':'transport_unresolved','no_retry':True}
assert h.transport_ack(a,byid[ident],artifact)
assert a['status']=='error' and a['actual_cost'] is None and a['reserve']==.0046946
for key in artifact:
 bad=copy.deepcopy(artifact);bad[key]='tampered'
 try:h.transport_ack(a,byid[ident],bad)
 except ValueError:pass
 else:raise AssertionError('tamper accepted')
for raw in [dict(run.strict_json(raw_before),transport_error='Timeout'),dict(run.strict_json(raw_before),http_status=429)]:
 with patch.object(run,'strict_json',return_value=raw):
  try:h.transport_ack(a,byid[ident],artifact)
  except ValueError:pass
  else:raise AssertionError('wrong transport accepted')
queue=run.strict_json(h.QUEUE.read_text());seen=set()
for attempt in ledger['attempts']:
 seen.add(attempt['case_id'])
 if h.transport_ack(attempt,byid[attempt['case_id']],artifact):continue
 h.reconcile_one(attempt,byid[attempt['case_id']],queue)
assert len(rows)-len(seen)==1035
assert run.strict_json(before)['attempts']==ledger['attempts']
assert p.read_bytes()==before and rawpath.read_bytes()==raw_before
print('PASS:exactack/tamper/wrongerror rejection,reserve.0046946 retained,errornotretried,1035remaining,allotherrecords reconciled,ledger/raw unchanged;no API')
