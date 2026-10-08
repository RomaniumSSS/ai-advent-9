"""Explicit reviewed continuation; default dry, no retry of paid failures."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import time
import requests
import run_selection_requests as run
import prepare_selection_requests as prep

FAILED='p-0194e3fa84cc0eeef94a'
AUDIT=prep.PRIVATE/'selection-pilot-audit-v1.json'


def acknowledge(ledger, byid, review):
    if ledger.get('stop_reason')!='output_validation':raise ValueError('unexpected_stop')
    errors=[a for a in ledger['attempts'] if a['status']!='complete']
    if len(errors)!=1 or errors[0]['case_id']!=FAILED or errors[0]['status']!='error':raise ValueError('unreviewed_attempt')
    expected={'request_manifest_sha256':run.EXPECTED,'audit_sha256':prep.file_hash(AUDIT),
              'case_id':FAILED,'raw_sha256':prep.file_hash(run.ROOT/(FAILED+'.json')),
              'disposition':'review_required','acknowledge':'output_validation'}
    if review.get('acknowledgment')!=expected:raise ValueError('review_mismatch')
    audit=run.strict_json(AUDIT.read_text())
    case=next(c for c in audit['cases'] if c['case_id']==FAILED)
    if case['model_valid'] or case['local_disposition']!='review_required':raise ValueError('audit_not_quarantined')
    raw=run.strict_json((run.ROOT/(FAILED+'.json')).read_text())
    envelope=run.strict_json(raw['response_text']);choice=envelope['choices'][0]
    if raw['http_status']!=200 or choice['finish_reason']!='stop' or envelope['model']!=prep.MODEL or envelope['provider'].casefold()!='deepinfra':raise ValueError('non_output_error')
    output=run.strict_json(choice['message']['content']);spec=byid[FAILED]
    run.schema_check(output,spec['body']['response_format']['json_schema']['schema'])
    if prep.validate_selection_output(spec,output):raise ValueError('structural_error_not_acknowledgeable')
    if run.context_guard(spec,output)!=['included_reply_unread_parent:4123']:raise ValueError('unexpected_context_error')
    return expected


def full_gate(ledger,pilot,review):
    if not all((run.ROOT/(i+'.json')).exists() for i in pilot):raise ValueError('pilot_incomplete')
    statuses={a['case_id']:a['status'] for a in ledger['attempts']}
    if any(statuses.get(i)!=('error' if i==FAILED else 'complete') for i in pilot):raise ValueError('pilot_status_not_reviewed')
    expected={'approved':True,'request_manifest_sha256':run.EXPECTED,
              'pilot_evidence_sha256':prep.digest({i:prep.file_hash(run.ROOT/(i+'.json')) for i in pilot}),
              'quarantined_case_id':FAILED,'quarantined_disposition':'review_required','audit_sha256':prep.file_hash(AUDIT)}
    if review.get('full_gate')!=expected:raise ValueError('full_review_gate')


def main():
    os.umask(0o077)
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--phase',choices=['pilot','full'],default='pilot');cli.add_argument('--review',type=Path,required=True);cli.add_argument('--live',action='store_true')
    args=cli.parse_args();rows=run.load();byid={r['case_id']:r for r in rows};pilot=run.pilot_ids(rows)
    meta={'version':run.VERSION,'manifest_sha256':run.EXPECTED,'runner_sha256':prep.file_hash(Path(run.__file__)),'cap':run.CAP,'pilot_ids':pilot}
    if run.ROOT.is_symlink() or any(p.is_symlink() for p in run.ROOT.iterdir()):raise ValueError('symlink_state')
    with (run.ROOT/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        path=run.ROOT/'ledger.json';ledger=run.strict_json(path.read_text())
        if ledger['meta']!=meta:raise ValueError('frozen_meta_mismatch')
        seen=run.reconcile(ledger,byid)
        review=run.strict_json(args.review.read_text());ack=acknowledge(ledger,byid,review)
        if args.phase=='full':full_gate(ledger,pilot,review)
        jobs=[byid[i] for i in pilot] if args.phase=='pilot' else rows
        remaining=[r for r in jobs if r['case_id'] not in seen]
        print(json.dumps({'phase':args.phase,'remaining':len(remaining),'spent_bound':run.bound(ledger),
                          'remaining_reserve_upper':sum(run.reserve(r) for r in remaining),'cap':run.CAP,'quarantined':FAILED,'live':args.live}),flush=True)
        if not args.live:return
        ledger.setdefault('reviewed_continuations',[]).append({'utc':datetime.now(timezone.utc).isoformat(),
            'helper_sha256':prep.file_hash(Path(__file__)),'review_sha256':prep.file_hash(args.review),
            'prior_stop_reason':ledger['stop_reason'],'reason':'explicit_review_required_quarantine',
            'acknowledgment':ack,'phase':args.phase,'no_retry':True})
        ledger.pop('stop_reason');run.write(path,ledger)
        key=run.api_key()
        for spec in remaining:
            upper=run.reserve(spec)
            if run.bound(ledger)+upper>run.CAP:raise ValueError('budget_cap')
            ledger['attempts'].append({'case_id':spec['case_id'],'reserve':upper,'actual_cost':None,'status':'pending','phase':args.phase});run.write(path,ledger)
            start=time.monotonic();raw={'body_sha256':spec['body_sha256']}
            try:
                response=run.send(spec,key);raw.update(http_status=response.status_code,response_text=response.text,retry_after=response.headers.get('Retry-After'))
            except requests.RequestException as error:raw.update(http_status=None,response_text='',transport_error=type(error).__name__)
            raw['elapsed_seconds']=time.monotonic()-start;run.write(run.ROOT/(spec['case_id']+'.json'),raw)
            run.reconcile(ledger,byid,only=spec['case_id']);run.write(path,ledger)
            print(json.dumps({'attempts':len(ledger['attempts']),'spent_bound':run.bound(ledger),'stop_reason':ledger.get('stop_reason')}),flush=True)
            if ledger.get('stop_reason'):break

if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'error_type':type(error).__name__}));raise SystemExit(1)
