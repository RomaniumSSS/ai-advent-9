"""Offline exact acknowledgment and quarantine/full-gate tests; no API."""
import copy
from pathlib import Path
import tempfile
from unittest.mock import patch
import resume_selection_reviewed as helper
run=helper.run;prep=helper.prep
rows=run.load();byid={r['case_id']:r for r in rows};pilot=run.pilot_ids(rows)
ledger=run.strict_json((run.ROOT/'ledger.json').read_text());before=copy.deepcopy(ledger)
seen=run.reconcile(ledger,byid)
ack={'request_manifest_sha256':run.EXPECTED,'audit_sha256':prep.file_hash(helper.AUDIT),'case_id':helper.FAILED,
     'raw_sha256':prep.file_hash(run.ROOT/(helper.FAILED+'.json')),'disposition':'review_required','acknowledge':'output_validation'}
review={'acknowledgment':ack}
assert helper.acknowledge(ledger,byid,review)==ack
assert [i for i in pilot if i not in seen] and len([i for i in pilot if i not in seen])==5
assert helper.FAILED in seen and ledger['attempts']==before['attempts']
assert run.bound(ledger)+sum(run.reserve(byid[i]) for i in pilot if i not in seen)<9
for key in ack:
 bad=copy.deepcopy(review);bad['acknowledgment'][key]='tampered'
 try:helper.acknowledge(ledger,byid,bad)
 except ValueError:pass
 else:raise AssertionError('tamper accepted')
for status in ['pending','http_error','incomplete_finish']:
 bad=copy.deepcopy(ledger)
 if status=='pending':bad['attempts'][-1]['status']='pending'
 else:bad['stop_reason']=status
 try:helper.acknowledge(bad,byid,review)
 except ValueError:pass
 else:raise AssertionError('unreviewed accepted')
try:helper.full_gate(ledger,pilot,review)
except ValueError:pass
else:raise AssertionError('incomplete full gate')
with tempfile.TemporaryDirectory() as directory,patch.object(run,'ROOT',Path(directory)):
 for i in pilot:run.write(Path(directory)/(i+'.json'),{'synthetic':i})
 complete={'attempts':[{'case_id':i,'status':'error' if i==helper.FAILED else 'complete'} for i in pilot]}
 gate={'approved':True,'request_manifest_sha256':run.EXPECTED,
       'pilot_evidence_sha256':prep.digest({i:prep.file_hash(Path(directory)/(i+'.json')) for i in pilot}),
       'quarantined_case_id':helper.FAILED,'quarantined_disposition':'review_required','audit_sha256':prep.file_hash(helper.AUDIT)}
 helper.full_gate(complete,pilot,{'full_gate':gate})
 gate['quarantined_disposition']='complete'
 try:helper.full_gate(complete,pilot,{'full_gate':gate})
 except ValueError:pass
 else:raise AssertionError('fake pass')
assert run.strict_json((run.ROOT/'ledger.json').read_text())==before
print('PASS: exact reviewed error, tamper/unreviewed/pending rejection, remaining5 no failed retry, preserved costs/statuses, shared budget, all12 fullgate/quarantine evidence; no API')
