"""Синтетическое сравнение: partial/malformed/unknown measurement без сети."""
import copy
from compare_holdout import analyze, compare
case = {'case_id': 'T', 'message_ids': [1, 2]}
sample = {'cases': [case], 'messages': [{'id': 1}, {'id': 2}]}
output = {'case_id': 'T', 'decisions': [{'message_id': i, 'decision': 'include', 'reason': 'synthetic', 'flags': []} for i in [1, 2]],
          'document_groups': [{'message_ids': [1], 'context_ids': [], 'reason': 'synthetic'},
                              {'message_ids': [2], 'context_ids': [1], 'reason': 'synthetic'}],
          'review_groups': [], 'missing_context_ids': [], 'notes': ''}
expect = {'decisions': [{'message_id': 1, 'allowed_decisions': ['include'], 'if_include_flags': ['needs_fact_check']}],
          'required_relations': [{'case_id': 'T', 'ids': [1, 2]}]}
full, rows = analyze(sample, {'cases': [output]}, expect)
assert full['valid_ids'] == 2 and full['elapsed_seconds']['reported_sum'] is None
assert full['required_relations'][0]['status'] == 'pass'
assert len(full['parent_flag_diagnostics']) == 1
partial = copy.deepcopy(output); partial['decisions'] = partial['decisions'][:1]
result, rows = analyze(sample, {'cases': [{'case_id': 'T', 'output': partial, 'elapsed_seconds': 2.5}]}, expect)
assert result['valid_ids'] == 0 and result['missing_observed_ids'] == [2]
assert result['elapsed_seconds']['reported_sum'] == 2.5
assert result['required_relations'][0]['status'] == 'not_observed_valid_case'
for malformed in [None, {}, {'cases': None}, {'cases': [None, {'case_id': []}]}]:
    analyze(sample, malformed, expect)
dup, _ = analyze(sample, {'cases': [output, output, {'case_id': 'unknown'}]}, expect)
assert dup['duplicate_cases'] == ['T'] and dup['unknown_cases'] == ['unknown'] and dup['valid_ids'] == 0
unknown = copy.deepcopy(output); unknown['decisions'][1]['message_id'] = 99
result, _ = analyze(sample, {'cases': [unknown]}, expect)
assert result['checks'][0]['unknown_message_ids'] == [99]
api, _ = analyze(sample, {'cases': [{'case_id': 'T', 'http_status': 429, 'error_type': 'http_error'}]}, expect)
assert api['api_error_cases'] == 1 and api['missing_output_cases'] == 1
report = compare(sample, {'direct': {'cases': [output]}, 'wrapped': {'cases': [{'case_id': 'T', 'output': output}]}, 'partial': {'cases': []}}, expect,
                 {'attempts': [{'actual_cost': None, 'reserve': .1, 'status': 'pending'}]})
assert report['agreement']['direct:wrapped']['common_valid_ids'] == 2
assert report['agreement']['direct:partial']['not_common_expected_ids'] == 2
assert report['budget']['reported_actual_cost'] is None and report['budget']['unknown_reserved_cost'] == .1
review = copy.deepcopy(output); review['decisions'][1]['decision'] = 'review'
review['document_groups'] = review['document_groups'][:1]; review['review_groups'] = [{'message_ids': [2], 'context_ids': [], 'reason': 'synthetic'}]
result, _ = analyze(sample, {'cases': [review]}, expect)
assert result['required_relations'][0]['status'] == 'not_applicable_non_include'
print('ok: direct/wrapped, partial/malformed/unknown IDs, API error separate, unknown elapsed/cost, explicit denominators, relations conditional on include')

from compare_holdout import run_hash_errors
assert not run_hash_errors({'input_sha256': 'i', 'rubric_sha256': 'r'}, 'i', 'r')
assert not run_hash_errors({'meta': {'input_sha256': 'i', 'rubric_sha256': 'r'}}, 'i', 'r')
assert run_hash_errors({'meta': {'input_sha256': 'wrong', 'rubric_sha256': 'r'}}, 'i', 'r') == ['input_hash_mismatch']
result, rows = analyze(sample, {'invalid_run_errors': ['input_hash_mismatch']}, expect)
assert result['status'] == 'invalid_run' and not rows
parsed, _ = analyze(sample, {'cases': [{'case_id': 'T', 'error_type': 'ValueError'}]}, expect)
assert parsed['api_error_cases'] == 0 and parsed['output_parse_error_cases'] == 1
print('ok: per-run hash rejection, parse error separate from API reliability')

report = compare(sample, {'a': {'cases': [output]}}, expect,
    {'attempts': [{'actual_cost': .1, 'reserve': .2, 'status': 'complete'}, {'actual_cost': None, 'reserve': .2, 'status': 'error'}]},
    {'meta': {'prior_bound': .3}, 'attempts': [{'actual_cost': .05, 'reserve': .1, 'status': 'complete'}, {'actual_cost': None, 'reserve': .1, 'status': 'pending'}]})
assert abs(report['combined_budget']['combined_bound'] - .45) < 1e-9
assert abs(report['combined_budget']['reported_actual_total'] - .15) < 1e-9
assert report['combined_budget']['nextbit_unknown_reserved_cost'] == .1
print('ok: NextBit separate row/budget, frozen prior counted exactly once')
