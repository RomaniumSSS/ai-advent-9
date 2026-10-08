"""Report structural checks and explicit regression expectations, without quoting chat."""
import collections
import json
from pathlib import Path
from pilot_validation import validate

PRIVATE = Path(__file__).resolve().parents[1] / 'private'
source = json.loads((PRIVATE / 'semantic-pilot-v2-input.json').read_text())
inputs = {c['case_id']: c for c in source['cases']}

# Reviewer expectations for concrete failures in v1, established before v2 review.
# These are regression checks, not a gold label for the complete corpus.
EXPECTATIONS = {
    ('C02', 2640): 'exclude', ('C02', 2694): 'exclude',
    ('C02', 2641): 'include', ('C02', 2695): 'include',
    ('C02', 2642): 'include', ('C02', 2696): 'include',
    ('C04', 4144): 'include', ('C04', 4163): 'include', ('C04', 4164): 'include',
    ('C03', 1585): 'exclude',
    ('C07', 723): 'exclude', ('C07', 726): 'exclude',
    ('C09', 1145): 'exclude', ('C09', 1150): 'exclude',
}
report = {'scope': 'Partial results allowed. Agreement is not accuracy.', 'models': {}}
decisions_by_model = {}
for name in ['cloud', 'local']:
    path = PRIVATE / f'semantic-pilot-v2-{name}.json'
    if not path.exists():
        report['models'][name] = {'completed': 0}
        continue
    run = json.loads(path.read_text())
    decisions, checks, outcomes = {}, [], []
    for item in run.get('cases', []):
        case_id = item['case_id']
        output = item.get('output', item)
        errors = validate(inputs[case_id], output)
        if item.get('done_reason') == 'length':
            errors.append('truncated_output')
        checks.append({'case_id': case_id, 'errors': errors})
        rows = output.get('decisions', []) if isinstance(output, dict) else []
        for decision in rows if isinstance(rows, list) else []:
            if not isinstance(decision, dict) or type(decision.get('message_id')) is not int or decision.get('decision') not in ('include', 'exclude', 'review'):
                continue
            key = (case_id, decision['message_id'])
            decisions[key] = decision['decision']
        for key, expected in EXPECTATIONS.items():
            if key[0] == case_id:
                actual = decisions.get(key)
                outcomes.append({'case_id': case_id, 'message_id': key[1],
                                 'expected': expected, 'actual': actual,
                                 'pass': actual == expected})
    decisions_by_model[name] = decisions
    report['models'][name] = {
        'completed': len(checks), 'structurally_valid': sum(not c['errors'] for c in checks),
        'checks': checks, 'regressions': outcomes,
        'regression_passes': sum(r['pass'] for r in outcomes),
        'regression_total_observed': len(outcomes),
        'seconds': round(sum(c.get('elapsed_seconds', 0) for c in run.get('cases', [])), 3),
    }
if len(decisions_by_model) == 2:
    cloud, local = decisions_by_model['cloud'], decisions_by_model['local']
    common = cloud.keys() & local.keys()
    report['agreement'] = {'compared': len(common), 'same': sum(cloud[k] == local[k] for k in common),
                           'different': sum(cloud[k] != local[k] for k in common),
                           'transitions': dict(collections.Counter(cloud[k] + ' -> ' + local[k]
                                                                   for k in common if cloud[k] != local[k]))}
path = PRIVATE / 'semantic-pilot-v2-analysis.json'
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
path.chmod(0o600)
print(json.dumps(report, ensure_ascii=False, indent=2))
