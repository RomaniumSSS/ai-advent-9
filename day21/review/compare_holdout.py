"""Структура, контекст и parent diagnostics holdout; agreement не accuracy."""
import collections
import hashlib
import itertools
import json
import math
from pathlib import Path
from pilot_validation import validate, diagnose_context
from run_local_sample import PRIVATE, write

RESULTS = {'cloud': 'semantic-expanded-v3-holdout-cloud.json',
           'local': 'semantic-expanded-v3-holdout-local.json',
           'deepseek': 'semantic-holdout-deepseek.json', 'glm': 'semantic-holdout-glm.json', 'glm_nextbit': 'semantic-holdout-glm-nextbit.json'}


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def measured_sum(rows, field):
    values = [row.get(field) for row in rows if isinstance(row, dict)]
    known = [value for value in values if number(value)]
    return {'reported_sum': round(sum(known), 9) if known else None,
            'reported_count': len(known), 'missing_count': len(values) - len(known)}


def is_api_error(check):
    status = check.get('http_status')
    return (type(status) is int and status >= 400) or check.get('error_type') in {
        'http_error', 'Timeout', 'ReadTimeout', 'ConnectTimeout', 'ConnectionError',
        'HTTPError', 'SSLError', 'URLError', 'TimeoutError', 'OSError', 'RequestException'}


def run_hash_errors(run, input_hash, rubric_hash):
    if not isinstance(run, dict): return ['result_container']
    meta = run.get('meta', run)
    if not isinstance(meta, dict): return ['result_metadata']
    errors = []
    if meta.get('input_sha256') != input_hash: errors.append('input_hash_mismatch')
    if meta.get('rubric_sha256') != rubric_hash: errors.append('rubric_hash_mismatch')
    return errors


def connected(ids, groups):
    graph = collections.defaultdict(set)
    for group in groups:
        members = group['message_ids'] + group['context_ids']
        for ident in members:
            graph[ident].update(members)
    visited, pending = set(), [ids[0]]
    while pending:
        ident = pending.pop()
        if ident in visited: continue
        visited.add(ident); pending.extend(graph[ident] - visited)
    return set(ids) <= visited


def analyze(sample, run, expectations):
    cases = {c['case_id']: c for c in sample['cases']}
    expected_ids = {i for c in cases.values() for i in c['message_ids']}
    if run is None:
        return {'status': 'missing', 'completed_cases': 0, 'expected_cases': len(cases),
                'valid_ids': 0, 'expected_ids': len(expected_ids)}, {}
    if isinstance(run, dict) and run.get('invalid_run_errors'):
        return {'status': 'invalid_run', 'errors': run['invalid_run_errors']}, {}
    if not isinstance(run, dict) or not isinstance(run.get('cases'), list):
        return {'status': 'malformed', 'error': 'result_container'}, {}
    rows = run['cases']
    counts = collections.Counter(r.get('case_id') for r in rows if isinstance(r, dict) and isinstance(r.get('case_id'), str))
    unknown = sorted(set(counts) - cases.keys())
    duplicate = sorted(k for k, n in counts.items() if n > 1)
    checks, decisions, outputs = [], {}, {}
    observed_ids = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('case_id'), str) or row['case_id'] not in cases:
            continue
        case_id = row['case_id']; output = row.get('output', row)
        errors = validate(cases[case_id], output)
        if row.get('done_reason') == 'length' or row.get('finish_reason') == 'length': errors.append('truncated_output')
        if counts[case_id] > 1: errors.append('duplicate_case')
        context = diagnose_context(cases[case_id], sample['messages'], output)
        checks.append({'case_id': case_id, 'structural_errors': sorted(set(errors)), 'context_diagnostics': context,
                       'error_type': row.get('error_type'), 'http_status': row.get('http_status'),
                       'output_missing': 'output' not in row and 'decisions' not in row})
        entries = output.get('decisions', []) if isinstance(output, dict) else []
        if isinstance(entries, list):
            row_ids = [d['message_id'] for d in entries if isinstance(d, dict) and type(d.get('message_id')) is int]
            checks[-1]['unknown_message_ids'] = sorted(set(row_ids) - set(cases[case_id]['message_ids']))
            checks[-1]['duplicate_message_ids'] = sorted(i for i, n in collections.Counter(row_ids).items() if n > 1)
            observed_ids.update(d['message_id'] for d in entries if isinstance(d, dict) and type(d.get('message_id')) is int and d['message_id'] in cases[case_id]['message_ids'])
        if errors: continue
        outputs[case_id] = output
        decisions.update({(case_id, d['message_id']): d for d in output['decisions']})
    deviations, flags, missing_expectations = [], [], []
    id_to_case = {i: c['case_id'] for c in cases.values() for i in c['message_ids']}
    for item in expectations.get('decisions', []):
        ident = item['message_id']; case_id = id_to_case.get(ident)
        decision = decisions.get((case_id, ident))
        if decision is None:
            missing_expectations.append({'case_id': case_id, 'message_id': ident}); continue
        actual = decision['decision']
        if actual not in item['allowed_decisions']:
            deviations.append({'case_id': case_id, 'message_id': ident, 'actual': actual, 'allowed': item['allowed_decisions']})
        required = item.get('if_include_flags', [])
        if actual == 'include' and set(required) - set(decision['flags']):
            flags.append({'case_id': case_id, 'message_id': ident, 'missing_flags': sorted(set(required) - set(decision['flags']))})
    relations = []
    for relation in expectations.get('required_relations', []):
        case_id, ids = relation['case_id'], relation['ids']; output = outputs.get(case_id)
        if output is None:
            status = 'not_observed_valid_case'
        elif any(decisions[(case_id, i)]['decision'] != 'include' for i in ids):
            status = 'not_applicable_non_include'
        else:
            status = 'pass' if connected(ids, output['document_groups']) else 'diagnostic_gap'
        relations.append({'case_id': case_id, 'ids': ids, 'status': status})
    usage_rows = [r['usage'] for r in rows if isinstance(r, dict) and isinstance(r.get('usage'), dict)]
    usage = {field: measured_sum(usage_rows, field) for field in
             ['cost', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'prompt_eval_count', 'eval_count']}
    return {'status': 'complete' if set(counts) == cases.keys() and not duplicate and len(rows) == len(cases) else 'partial_or_invalid',
            'completed_cases': len(set(counts) & cases.keys()), 'expected_cases': len(cases),
            'unknown_cases': unknown, 'duplicate_cases': duplicate,
            'malformed_case_records': sum(not isinstance(r, dict) or not isinstance(r.get('case_id'), str) for r in rows),
            'missing_cases': sorted(cases.keys() - counts.keys()),
            'structurally_valid_cases': len(outputs), 'checks': checks,
            'api_error_cases': sum(is_api_error(c) for c in checks),
            'output_parse_error_cases': sum(bool(c['error_type']) and not is_api_error(c) for c in checks),
            'missing_output_cases': sum(c['output_missing'] for c in checks),
            'observed_known_ids': len(observed_ids), 'missing_observed_ids': sorted(expected_ids - observed_ids),
            'valid_ids': len(decisions), 'expected_ids': len(expected_ids),
            'valid_decision_totals': dict(collections.Counter(d['decision'] for d in decisions.values())),
            'elapsed_seconds': measured_sum(rows, 'elapsed_seconds'), 'usage': usage,
            'usage_missing_case_count': len(rows) - len(usage_rows),
            'parent_diagnostic_deviations': deviations, 'parent_flag_diagnostics': flags,
            'parent_unobserved_decisions': missing_expectations, 'required_relations': relations}, decisions


def compare(sample, runs, expectations, ledger=None, nextbit_ledger=None):
    report = {'scope': 'Agreement on structurally valid cases; parent diagnostics are not human gold or accuracy.',
              'models': {}, 'agreement': {}}
    maps = {}
    expected = sum(len(c['message_ids']) for c in sample['cases'])
    for name, run in runs.items():
        report['models'][name], maps[name] = analyze(sample, run, expectations)
    for left, right in itertools.combinations(maps, 2):
        a, b = maps[left], maps[right]; common = a.keys() & b.keys()
        report['agreement'][left + ':' + right] = {'common_valid_ids': len(common), 'expected_ids': expected,
            'same': sum(a[k]['decision'] == b[k]['decision'] for k in common),
            'different': sum(a[k]['decision'] != b[k]['decision'] for k in common),
            'left_valid_not_common': len(a.keys() - common), 'right_valid_not_common': len(b.keys() - common),
            'not_common_expected_ids': expected - len(common)}
    if ledger is not None:
        rows = ledger.get('attempts', [])
        actual = [a.get('actual_cost') for a in rows if isinstance(a, dict)]
        known = [c for c in actual if number(c)]
        reserves = [a['reserve'] for a in rows if isinstance(a, dict) and a.get('actual_cost') is None and number(a.get('reserve'))]
        report['budget'] = {'reported_actual_cost': sum(known) if known else None,
                            'reported_cost_count': len(known), 'unknown_reserved_cost': sum(reserves),
                            'unknown_cost_count': len(reserves), 'pending_count': sum(isinstance(a, dict) and a.get('status') == 'pending' for a in rows),
                            'stop_reason': ledger.get('stop_reason')}
    if nextbit_ledger is not None:
        if nextbit_ledger.get('invalid_budget_errors'):
            report['combined_budget'] = {'status': 'invalid', 'errors': nextbit_ledger['invalid_budget_errors']}
        else:
            own = nextbit_ledger.get('attempts', [])
            known = [a['actual_cost'] for a in own if isinstance(a, dict) and number(a.get('actual_cost'))]
            unknown = [a['reserve'] for a in own if isinstance(a, dict) and a.get('actual_cost') is None and number(a.get('reserve'))]
            prior = report.get('budget', {})
            prior_known = prior.get('reported_actual_cost')
            report['combined_budget'] = {
                'prior_reported_actual_cost': prior_known,
                'prior_unknown_reserved_cost': prior.get('unknown_reserved_cost'),
                'nextbit_reported_actual_cost': sum(known) if known else None,
                'nextbit_unknown_reserved_cost': sum(unknown),
                'nextbit_unknown_cost_count': len(unknown),
                'reported_actual_total': (prior_known or 0) + sum(known) if prior_known is not None or known else None,
                'combined_bound': nextbit_ledger['meta']['prior_bound'] + sum(known) + sum(unknown),
                'nextbit_pending_count': sum(isinstance(a, dict) and a.get('status') == 'pending' for a in own),
                'nextbit_stop_reason': nextbit_ledger.get('stop_reason')}
    return report


def main():
    source = PRIVATE / 'semantic-expanded-v3-holdout-input.json'
    raw = source.read_bytes(); sample = json.loads(raw)
    expectations = json.loads((PRIVATE / 'semantic-holdout-review-expectations.json').read_text())
    if expectations['input_sha256'] != hashlib.sha256(raw).hexdigest(): raise ValueError('expectation_input_hash')
    if expectations['rubric_sha256'] != sample['rubric_sha256']: raise ValueError('expectation_rubric_hash')
    runs = {}
    for name, filename in RESULTS.items():
        path = PRIVATE / filename
        try: runs[name] = json.loads(path.read_text()) if path.exists() else None
        except (ValueError, OSError): runs[name] = {'cases': None}
        if runs[name] is not None:
            errors = run_hash_errors(runs[name], hashlib.sha256(raw).hexdigest(), sample['rubric_sha256'])
            if errors: runs[name] = {'invalid_run_errors': errors}
    path = PRIVATE / 'semantic-openrouter-budget.json'
    ledger = json.loads(path.read_text()) if path.exists() else None
    next_path = PRIVATE / 'semantic-nextbit-budget.json'
    nextbit = json.loads(next_path.read_text()) if next_path.exists() else None
    if nextbit is not None:
        if not path.exists() or nextbit.get('meta', {}).get('prior_ledger_sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
            nextbit = {'invalid_budget_errors': ['prior_ledger_hash_mismatch']}
    report = compare(sample, runs, expectations, ledger, nextbit)
    write(PRIVATE / 'semantic-holdout-comparison.json', report)
    print(json.dumps({'models': {name: {k: result.get(k) for k in
          ['status', 'completed_cases', 'structurally_valid_cases', 'valid_ids', 'expected_ids', 'elapsed_seconds']}
          for name, result in report['models'].items()}, 'agreement': report['agreement'], 'budget': report.get('budget'), 'combined_budget': report.get('combined_budget')}, ensure_ascii=False))


if __name__ == '__main__': main()
