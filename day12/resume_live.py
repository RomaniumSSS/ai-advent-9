"""Explicit manual repair of the pinned stopped run, via existing owner tunnel."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from live_budget import MAX_COST, decimal
from repair_contract import source_check, require, RUN_ID, REPORT_HASH, audit_check, request_check, short_format
from verify_live import Tunnel, PROFILES, QUESTION


def run(tunnel, source, report, save, approved_by, reason):
    source_check(source)  # Before even opening the tunnel.
    report.update(deepcopy(source))
    report['source_failure'] = {key: report.pop(key) for key in ('error', 'error_type') if key in report}
    report.update(outcome='repair_running', source_report_hash=REPORT_HASH)
    report['cases'][1]['label'] = 'B-failed'
    save()
    require(tunnel.request('evidence') == source['ledger'], 'server ledger differs from original')
    state = tunnel.request('state')['state']
    require(not state['offline'] and state['model'] == 'deepseek-v4-flash', 'real runtime required')
    previous = tunnel.request('resume', {'source_report': source, 'approved_by': approved_by, 'reason': reason})
    audit_check(previous)
    report['ledger'] = previous
    save()
    for index, label in enumerate(('B-resume', 'B-repeat'), 3):
        scope = {'session': f'{RUN_ID}-{label}', 'task': RUN_ID, 'user': RUN_ID}
        current = tunnel.request('scope', scope)['state']
        require(current['scope'] == scope and not current['history'] and not any(current['notes'].values()),
                'fresh empty session required')
        if index == 3:
            tunnel.request('profile', PROFILES[1].to_dict())
        current = tunnel.request('state')['state']
        require(current['scope'] == scope and current['profile'] == PROFILES[1].to_dict()
                and not current['history'] and not any(current['notes'].values())
                and not current['offline'] and current['model'] == 'deepseek-v4-flash', 'runtime state mismatch')
        require(tunnel.request('evidence') == previous, 'concurrent ledger change')
        # Actual context/options are checked under the ledger lock before SDK send.
        reply = tunnel.request('chat', {'text': QUESTION})
        ledger = tunnel.request('evidence')
        report['ledger'] = ledger
        report['cases'].append({'label': label, 'reply': reply})
        save()  # Keep errors/charges even when validation below rejects the result.
        audit_check(ledger)
        require(len(ledger['attempts']) == index and ledger['attempts'][:-1] == previous['attempts'],
                'unexpected attempt mutation/count')
        attempt = ledger['attempts'][-1]
        request_check(previous, attempt['request'])
        require(attempt['status'] == 'complete' and reply['ok'] and reply['saved']
                and not reply.get('state_error') and not reply.get('store_error'), 'incomplete B')
        response = attempt['response']
        require(response.get('id') and response.get('provider')
                and response['model'] == source['ledger']['policy']['model']
                and response['choices'][0]['finish_reason'] == 'stop'
                and response['choices'][0]['message']['content'] == reply['message'], 'provenance mismatch')
        require(short_format(reply['message']), 'B format failed; no further paid calls')
        require(ledger['stopped'] == (None if index == 3 else 'budget reached'), 'unexpected stop')
        report['cases'][-1]['rubric'] = {'format_pass': True, 'household_analogy_human_review': 'pending'}
        previous = ledger
        save()
    require(len(previous['attempts']) == 4 and decimal(previous['reported_cost_usd']) <= MAX_COST,
            'final budget mismatch')
    require(report['cases'][0]['reply']['message'] != report['cases'][2]['reply']['message'], 'A/B identical')
    report.update(outcome='awaiting_human_rubric', automatic_profile_repeat=True)
    save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--approved-by', required=True)
    parser.add_argument('--reason', required=True)
    parser.add_argument('--authorize-same-ledger-repair', action='store_true', required=True)
    args = parser.parse_args()
    source = json.loads(args.source.read_text())
    source_check(source)
    report = {}
    with args.report.open('x') as stream:
        json.dump(report, stream)
    def save():
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    try:
        run(Tunnel(args.url), source, report, save, args.approved_by, args.reason)
    except Exception as error:
        report.update(outcome='fail', error_type=type(error).__name__)
        save()
        raise SystemExit('Repair stopped. Preserve report and ledger; never restart the series.') from None


if __name__ == '__main__':
    main()
