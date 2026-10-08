"""Full continuation: only unread-parent context failures enter whole-case review."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import time
import requests
import run_selection_requests as run
import prepare_selection_requests as prep
import resume_selection_reviewed as reviewed

GATE=prep.PRIVATE/'selection-full-review.json'
QUEUE=run.ROOT/'context-review-queue.json'
ALLOWED='included_reply_unread_parent'


def classify(spec, raw):
    if raw.get('http_status')!=200:raise ValueError('http_error')
    envelope=run.strict_json(raw['response_text'])
    if envelope.get('model')!=prep.MODEL or envelope.get('provider','').casefold()!='deepinfra':raise ValueError('provider_model_mismatch')
    choice=envelope['choices'][0]
    if choice['finish_reason']!='stop':raise ValueError('incomplete_finish')
    output=run.strict_json(choice['message']['content'])
    run.schema_check(output,spec['body']['response_format']['json_schema']['schema'])
    if prep.validate_selection_output(spec,output):raise ValueError('structural_validation')
    errors=run.context_guard(spec,output)
    if any(not e.startswith(ALLOWED+':') for e in errors):raise ValueError('unknown_context_error')
    return errors


def reconcile_one(attempt,spec,queue):
    path=run.ROOT/(spec['case_id']+'.json')
    if not path.exists():raise ValueError('pending_without_response')
    raw=run.strict_json(path.read_text())
    if raw['body_sha256']!=spec['body_sha256']:raise ValueError('raw_body_mismatch')
    try:cost=run.strict_json(raw['response_text']).get('usage',{}).get('cost')
    except (ValueError,TypeError):cost=None
    if cost is not None and (type(cost) not in (int,float) or not math.isfinite(cost) or cost<0):cost=None
    attempt['actual_cost']=cost
    try:errors=classify(spec,raw)
    except Exception:
        attempt['status']='error';raise
    if cost is not None and cost>attempt['reserve']:
        attempt['status']='error';raise ValueError('actual_over_reserve')
    if errors:
        attempt['status']='error'
        entry={'case_id':spec['case_id'],'disposition':'review_required','whole_case':True,
               'raw_sha256':prep.file_hash(path),'request_sha256':spec['body_sha256'],
               'owned_ids':spec['owned_ids'],'error_codes':errors}
        prior=queue['cases'].get(spec['case_id'])
        if prior is not None and prior!=entry:raise ValueError('review_queue_mismatch')
        queue['cases'][spec['case_id']]=entry
    else:
        if spec['case_id'] in queue['cases']:raise ValueError('review_queue_mismatch')
        if attempt['status']=='error':raise ValueError('unexplained_prior_error')
        attempt['status']='complete'


def check_policy(policy):
    expected={'allowed_context_error':ALLOWED,'cap':run.CAP,'request_manifest_sha256':run.EXPECTED,
              'root_full_gate_sha256':prep.file_hash(GATE)}
    if policy!=expected:raise ValueError('policy_mismatch')
    gate=run.strict_json(GATE.read_text())
    if gate['full_gate']['audit_sha256']!=prep.file_hash(reviewed.AUDIT):raise ValueError('pilot_audit_changed')
    evidence=prep.digest({i:prep.file_hash(run.ROOT/(i+'.json')) for i in run.pilot_ids(run.load())})
    if gate['full_gate']['pilot_evidence_sha256']!=evidence:raise ValueError('pilot_evidence_changed')
    if gate['full_gate']['approved'] is not True or gate['full_gate']['request_manifest_sha256']!=run.EXPECTED:raise ValueError('full_gate_invalid')


def main():
    os.umask(0o077)
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--policy',type=Path,required=True);cli.add_argument('--live',action='store_true');args=cli.parse_args()
    rows=run.load();byid={r['case_id']:r for r in rows};pilot=run.pilot_ids(rows)
    meta={'version':run.VERSION,'manifest_sha256':run.EXPECTED,'runner_sha256':prep.file_hash(Path(run.__file__)),'cap':run.CAP,'pilot_ids':pilot}
    if run.ROOT.is_symlink() or any(p.is_symlink() for p in run.ROOT.iterdir()):raise ValueError('symlink_state')
    with (run.ROOT/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        policy=run.strict_json(args.policy.read_text());check_policy(policy)
        path=run.ROOT/'ledger.json';oldsha=prep.file_hash(path);ledger=run.strict_json(path.read_text())
        if ledger['meta']!=meta:raise ValueError('frozen_meta_mismatch')
        policysha=prep.file_hash(args.policy)
        queue=run.strict_json(QUEUE.read_text()) if QUEUE.exists() else {'policy_sha256':policysha,'cases':{}}
        if queue['policy_sha256']!=policysha:raise ValueError('queue_policy_changed')
        seen=set()
        for attempt in ledger['attempts']:
            ident=attempt['case_id']
            if ident in seen or ident not in byid or attempt['reserve']!=run.reserve(byid[ident]) or attempt['status'] not in ['pending','error','complete']:raise ValueError('ledger_consistency')
            seen.add(ident);reconcile_one(attempt,byid[ident],queue)
        if set(queue['cases'])-seen:raise ValueError('orphan_review_queue')
        if ledger.get('stop_reason') not in [None,'output_validation']:raise ValueError('prior_fatal_stop')
        if ledger.get('stop_reason')=='output_validation' and not queue['cases']:raise ValueError('unexplained_prior_stop')
        if run.bound(ledger)>run.CAP:raise ValueError('budget_exceeded')
        remaining=[r for r in rows if r['case_id'] not in seen]
        print(json.dumps({'attempts':len(seen),'remaining':len(remaining),'quarantined':len(queue['cases']),'spent_bound':run.bound(ledger),'live':args.live}),flush=True)
        if not args.live:return
        run.write(QUEUE,queue)
        ledger.setdefault('context_policy_events',[]).append({'utc':datetime.now(timezone.utc).isoformat(),'old_ledger_sha256':oldsha,'policy_sha256':policysha,'helper_sha256':prep.file_hash(Path(__file__)),'prior_stop_reason':ledger.get('stop_reason'),'allowed_error':ALLOWED})
        ledger.pop('stop_reason',None);run.write(path,ledger);key=run.api_key()
        for spec in remaining:
            upper=run.reserve(spec)
            if run.bound(ledger)+upper>run.CAP:
                ledger['stop_reason']='budget_cap';run.write(path,ledger);break
            attempt={'case_id':spec['case_id'],'reserve':upper,'actual_cost':None,'status':'pending','phase':'full'}
            ledger['attempts'].append(attempt);run.write(path,ledger)
            raw={'body_sha256':spec['body_sha256']};start=time.monotonic()
            try:
                response=run.send(spec,key);raw.update(http_status=response.status_code,response_text=response.text,retry_after=response.headers.get('Retry-After'))
            except requests.RequestException as error:raw.update(http_status=None,response_text='',transport_error=type(error).__name__)
            raw['elapsed_seconds']=time.monotonic()-start;run.write(run.ROOT/(spec['case_id']+'.json'),raw)
            try:reconcile_one(attempt,spec,queue)
            except Exception as error:ledger['stop_reason']=str(error) if isinstance(error,ValueError) else type(error).__name__
            run.write(QUEUE,queue);run.write(path,ledger)
            print(json.dumps({'attempts':len(ledger['attempts']),'quarantined':len(queue['cases']),'spent_bound':run.bound(ledger),'stop_reason':ledger.get('stop_reason')}),flush=True)
            if ledger.get('stop_reason'):break

if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'error_type':type(error).__name__}));raise SystemExit(1)
