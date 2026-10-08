"""Отдельный явно разрешённый GLM/NextBit holdout-run; dry-run по умолчанию."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import time
import requests
import certifi
import run_openrouter_sample as shared
from pilot_validation import validate, diagnose_context

PRIVATE = shared.PRIVATE
MODEL = 'z-ai/glm-5.3-flash'
PROVIDER = 'nextbit/fp8'
OUTPUT = 'semantic-holdout-glm-nextbit.json'
LEDGER = 'semantic-nextbit-budget.json'
PRIOR = 'semantic-openrouter-budget.json'


def prior_snapshot():
    raw = (PRIVATE / PRIOR).read_bytes()
    ledger = json.loads(raw)
    if not ledger.get('stop_reason') or any(a.get('status') == 'pending' for a in ledger['attempts']):
        raise ValueError('prior_ledger_not_frozen')
    for attempt in ledger['attempts']:
        if not shared.money(attempt.get('reserve')) or attempt.get('actual_cost') is not None and not shared.money(attempt['actual_cost']):
            raise ValueError('invalid_prior_cost')
    return shared.digest(raw), shared.spent(ledger)


def prepare():
    data, original, _ = shared.prepare()
    prior_hash, bound = prior_snapshot()
    jobs = []
    for job in original:
        if job['model'] != MODEL: continue
        payload = json.loads(job['body'])
        payload['provider']['only'] = [PROVIDER]
        body = shared.serialize(payload)
        jobs.append({'model': MODEL, 'case': job['case'], 'body': body, 'reserve': shared.reserve_upper(body)})
    meta = {'version': 1, 'code_sha256': shared.digest(Path(__file__).read_bytes()),
            'input_sha256': shared.EXPECTED_INPUT, 'rubric_sha256': data['rubric_sha256'],
            'request_sha256': [shared.digest(j['body']) for j in jobs],
            'prior_ledger_sha256': prior_hash, 'prior_bound': bound, 'cap': 1.0}
    return data, jobs, meta


def reserve(ledger, job):
    current_hash, bound = prior_snapshot()
    if current_hash != ledger['meta']['prior_ledger_sha256'] or bound != ledger['meta']['prior_bound']:
        raise ValueError('prior_ledger_changed')
    if bound + shared.spent(ledger) + job['reserve'] > 1.0:
        raise ValueError('shared_budget_cap')
    return shared.reserve(ledger, (MODEL, job['case']['case_id']), job['reserve'])


def process_response(case, messages, response):
    record = {'case_id': case['case_id'], 'valid_coverage': False}
    if not isinstance(response, dict): return dict(record, error_type='response_type'), 'response_type'
    record.update(usage=response.get('usage'), provider=response.get('provider'), model=response.get('model'))
    provider = response.get('provider')
    stop = None if response.get('model') == MODEL and isinstance(provider, str) and provider.casefold() == 'nextbit' else 'unexpected_provider_or_model'
    choices = response.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict) or not isinstance(choices[0].get('message'), dict):
        return dict(record, error_type='response_envelope'), stop or 'response_envelope'
    choice = choices[0]
    record['finish_reason'] = choice.get('finish_reason')
    record['raw_output'] = choice['message'].get('content')
    try:
        output = shared.normalized(shared.parse_output(record['raw_output']))
        errors = validate(case, output)
        if record['finish_reason'] == 'length': errors.append('truncated_output')
        record.update(output=output, validation_errors=errors, valid_coverage=not errors,
                      context_diagnostics=diagnose_context(case, messages, output))
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        record.update(error_type=type(error).__name__, validation_errors=['malformed_output'])
        if record['finish_reason'] == 'length': record['validation_errors'].append('truncated_output')
    return record, stop


def safe_code(value):
    if type(value) is int: return value
    if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}', value): return value
    return None


def live(data, jobs, meta):
    path = PRIVATE / LEDGER
    ledger = json.loads(path.read_text()) if path.exists() else {'meta': meta, 'attempts': []}
    keys = {(MODEL, j['case']['case_id']): j['reserve'] for j in jobs}
    attempted = shared.ensure_ledger(ledger, meta, keys)
    if ledger.get('stop_reason') or any(a['status'] == 'pending' for a in ledger['attempts']):
        raise ValueError('stopped_or_pending_requires_review')
    target = PRIVATE / OUTPUT
    run = json.loads(target.read_text()) if target.exists() else {'meta': meta, 'model': MODEL, 'cases': []}
    if run.get('meta') != meta or run.get('model') != MODEL or not isinstance(run.get('cases'), list):
        raise ValueError('unsafe_checkpoint')
    records = run['cases']
    ids = [(MODEL, r.get('case_id')) for r in records if isinstance(r, dict)]
    if len(ids) != len(records) or len(ids) != len(set(ids)) or set(ids) != attempted:
        raise ValueError('checkpoint_ledger_mismatch')
    costs = {(a['model'], a['case_id']): a for a in ledger['attempts']}
    for record in records:
        attempt = costs[(MODEL, record['case_id'])]
        if record.get('actual_cost') != attempt['actual_cost'] or record.get('reserved_cost') != attempt['reserve']:
            raise ValueError('checkpoint_cost_mismatch')
    key = shared.api_key()
    for job in jobs:
        ident = (MODEL, job['case']['case_id'])
        if ident in attempted: continue
        attempt = reserve(ledger, job)
        shared.write(path, ledger)
        started = time.monotonic()
        record, stop = {'case_id': ident[1], 'valid_coverage': False}, None
        try:
            response = requests.post(shared.ENDPOINT, data=job['body'],
                headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                timeout=600, verify=certifi.where())
            record['http_status'] = response.status_code
            if response.status_code != 200:
                record['error_type'] = 'http_error'; stop = 'http_error'
                record['retry_after'] = response.headers.get('Retry-After')
                try:
                    error = response.json().get('error', {})
                    if isinstance(error, dict):
                        record['error_code'] = safe_code(error.get('code'))
                        record['provider_error_type'] = safe_code(error.get('type'))
                except (ValueError, AttributeError): pass
            else:
                record, stop = process_response(job['case'], data['messages'], response.json())
                record['http_status'] = response.status_code
        except (requests.RequestException, ValueError) as error:
            record['error_type'] = type(error).__name__; stop = 'transport_or_response_error'
        record['elapsed_seconds'] = round(time.monotonic() - started, 3)
        usage = record.get('usage'); actual = usage.get('cost') if isinstance(usage, dict) else None
        if actual is not None and not shared.money(actual): actual = None; stop = stop or 'invalid_usage_cost'
        record.update(actual_cost=actual, reserved_cost=attempt['reserve'])
        attempt.update(actual_cost=actual, status='error' if stop else 'complete')
        if actual is not None and actual > attempt['reserve']: stop = 'actual_exceeds_reserve'
        records.append(record); shared.write(target, run)
        if stop: ledger['stop_reason'] = stop
        shared.write(path, ledger)
        print(json.dumps({'case_id': ident[1], 'valid_coverage': record.get('valid_coverage'),
                          'http_status': record.get('http_status'), 'stop_reason': stop,
                          'seconds': record['elapsed_seconds'],
                          'combined_budget_bound': meta['prior_bound'] + shared.spent(ledger)}), flush=True)
        if stop: return


def main():
    os.umask(0o077)
    cli = argparse.ArgumentParser(description=__doc__); cli.add_argument('--live', action='store_true')
    args = cli.parse_args(); data, jobs, meta = prepare()
    if not args.live:
        print(json.dumps({'dry_run': True, 'calls': len(jobs), 'model': MODEL, 'provider': PROVIDER,
                          'prior_bound': meta['prior_bound'], 'own_reserve_upper': sum(j['reserve'] for j in jobs),
                          'combined_upper': meta['prior_bound'] + sum(j['reserve'] for j in jobs), 'cap': 1.0}))
        return
    with (PRIVATE / 'semantic-openrouter-budget.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('another_runner_active')
        live(data, jobs, meta)


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'error_type': type(error).__name__}), flush=True)
        raise SystemExit(1)
