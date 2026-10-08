"""Одно явное продолжение после 429 без повтора ошибочного кейса."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
import time
from unittest.mock import patch
import run_openrouter_sample as runner


def inspect(ledger, jobs, meta):
    keys = {(j['model'], j['case']['case_id']): j['reserve'] for j in jobs}
    attempted = runner.ensure_ledger(ledger, meta, keys)
    if ledger.get('continuations'):
        raise ValueError('continuation_already_used')
    if ledger.get('stop_reason') != 'http_error' or any(a['status'] == 'pending' for a in ledger['attempts']):
        raise ValueError('not_completed_http_stop')
    if not ledger['attempts'] or ledger['attempts'][-1]['status'] != 'error':
        raise ValueError('last_attempt_not_error')
    last = ledger['attempts'][-1]
    found = None
    ledger_records = {(a['model'], a['case_id']): a for a in ledger['attempts']}
    for model, _, filename in runner.MODELS:
        path = runner.PRIVATE / filename
        run = json.loads(path.read_text()) if path.exists() else {'meta': meta, 'model': model, 'cases': []}
        if run.get('meta') != meta or run.get('model') != model or not isinstance(run.get('cases'), list):
            raise ValueError('unsafe_checkpoint')
        ids = [(model, r.get('case_id')) for r in run['cases'] if isinstance(r, dict)]
        if len(ids) != len(run['cases']) or len(ids) != len(set(ids)) or set(ids) != {k for k in attempted if k[0] == model}:
            raise ValueError('checkpoint_ledger_mismatch')
        for record in run['cases']:
            attempt = ledger_records[(model, record['case_id'])]
            if record.get('actual_cost') != attempt['actual_cost'] or record.get('reserved_cost') != attempt['reserve']:
                raise ValueError('checkpoint_cost_mismatch')
        if model == last['model']:
            found = run['cases'][-1] if run['cases'] else None
    if not found or found['case_id'] != last['case_id'] or found.get('http_status') != 429 or found.get('error_type') != 'http_error':
        raise ValueError('last_result_not_429')
    return attempted, last


def continue_live(data, jobs, meta, ledger):
    attempted, last = inspect(ledger, jobs, meta)
    event = {'utc': datetime.now(timezone.utc).isoformat(), 'prior_stop': ledger['stop_reason'],
             'last_case': last['case_id'], 'last_model': last['model'], 'no_retry': True,
             'pacing_seconds': 30, 'remaining_calls': len(jobs) - len(attempted)}
    ledger['continuations'] = [event]
    del ledger['stop_reason']
    runner.write(runner.PRIVATE / 'semantic-openrouter-budget.json', ledger)
    reserve_original, post_original = runner.reserve, runner.requests.post
    last_sent = [time.monotonic()]
    def paced_reserve(*args, **kwargs):
        delay = max(0, last_sent[0] + 30 - time.monotonic())
        if delay: time.sleep(delay)
        return reserve_original(*args, **kwargs)
    def timed_post(*args, **kwargs):
        last_sent[0] = time.monotonic()
        return post_original(*args, **kwargs)
    with patch.object(runner, 'reserve', paced_reserve), patch.object(runner.requests, 'post', timed_post):
        runner.live(data, jobs, meta)


def main():
    os.umask(0o077)
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--live', action='store_true')
    args = cli.parse_args()
    data, jobs, meta = runner.prepare()
    path = runner.PRIVATE / 'semantic-openrouter-budget.json'
    if not args.live:
        ledger = json.loads(path.read_text())
        attempted, last = inspect(ledger, jobs, meta)
        print(json.dumps({'dry_run': True, 'remaining_calls': len(jobs) - len(attempted),
                          'previous_http_status': 429, 'no_retry_case': last['case_id'],
                          'pacing_seconds': 30, 'budget_charged': runner.spent(ledger)}))
        return
    with (runner.PRIVATE / 'semantic-openrouter-budget.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('another_runner_active')
        continue_live(data, jobs, meta, json.loads(path.read_text()))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'error_type': type(error).__name__}), flush=True)
        raise SystemExit(1)
