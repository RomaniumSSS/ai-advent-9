"""Синтетические проверки ошибок формата и сохранения, без переписки и сети."""
import copy
import json
import tempfile
from pathlib import Path
from pilot_validation import validate
from run_local_sample import normalized, output_schema, parse_output, resume, write

case = {'case_id': 'T', 'message_ids': [1, 2]}
good = {'case_id': 'T', 'decisions': [
    {'message_id': i, 'decision': 'include', 'reason': 'причина', 'flags': []} for i in [1, 2]],
    'document_groups': [{'message_ids': [1, 2], 'context_ids': [], 'reason': 'связь'}],
    'review_groups': [], 'missing_context_ids': [], 'notes': ''}
assert not validate(case, good)
for bad in [None, [], 1, 'x']:
    assert validate(case, bad)
for field in good:
    bad = copy.deepcopy(good); del bad[field]
    assert validate(case, bad), field
for field in ['decisions', 'document_groups', 'review_groups', 'missing_context_ids']:
    for value in [None, {}, 'x', [None], [[1]]]:
        bad = copy.deepcopy(good); bad[field] = value
        assert validate(case, bad), (field, value)
for field, value in [('flags', None), ('flags', {}), ('flags', ['unknown']),
                     ('message_id', True), ('message_id', []), ('decision', []), ('reason', '')]:
    bad = copy.deepcopy(good); bad['decisions'][0][field] = value
    assert validate(case, bad)
for rows in [[good['decisions'][0]], [good['decisions'][0]] * 2]:
    bad = copy.deepcopy(good); bad['decisions'] = rows
    assert 'decision_coverage' in validate(case, bad)
bad = copy.deepcopy(good); bad['decisions'][0]['decision'] = 'review'
assert 'document_groups_membership' in validate(case, bad)
assert output_schema(case)['properties']['decisions']['required'] == ['1', '2']
converted = copy.deepcopy(good)
converted['decisions'] = {str(d['message_id']): {k: v for k, v in d.items() if k != 'message_id'} for d in good['decisions']}
assert normalized(converted) == good
for raw in ['{', '{"1": {}, "1": {}}']:
    try: parse_output(raw)
    except ValueError: pass
    else: raise AssertionError('malformed JSON accepted')
meta = {'case_ids': ['T'], 'digest': 'x', 'cases': []}
record = {'case_id': 'T', 'valid_coverage': False, 'raw_output': 'broken'}
previous = dict(meta, cases=[record])
assert resume(previous, meta) == [record]
for bad in [dict(previous, digest='y'), dict(previous, cases=[record, record]), dict(previous, cases=None)]:
    try: resume(bad, meta)
    except ValueError: pass
    else: raise AssertionError('invalid checkpoint accepted')
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'result.json'
    write(path, previous)
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == previous
    assert list(Path(directory).iterdir()) == [path]
print('ok: required fields, hostile types, IDs/groups, schema normalization, duplicate JSON, checkpoint, atomic 0600')

# Проверяем весь пакет: malformed и length не останавливают следующий кейс;
# повторный запуск сохраняет даже невалидный завершённый ответ.
import contextlib
import io
import sys
from unittest.mock import patch
import run_local_sample as runner
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    sample = {'cases': [{'case_id': c, 'message_ids': [1]} for c in ['T1', 'T2', 'T3']],
              'messages': [{'id': 1, 'text': 'синтетика'}]}
    (root / 'input.json').write_text(json.dumps(sample))
    rubric = root / 'rubric.txt'; rubric.write_text('синтетическая рубрика')
    calls = []
    def fake_api(endpoint, payload=None):
        if endpoint == '/api/tags':
            return {'models': [{'name': runner.MODEL, 'digest': 'test'}]}
        if endpoint == '/api/generate': return {}
        calls.append(payload)
        number = len(calls)
        output = copy.deepcopy(good)
        output['case_id'] = 'T' + str(number)
        output['decisions'] = output['decisions'][:1]
        output['document_groups'][0]['message_ids'] = [1]
        return {'message': {'content': '{' if number == 1 else json.dumps(output)},
                'done_reason': 'length' if number == 2 else 'stop', 'eval_count': 12}
    argv = ['runner', '--input', 'input.json', '--output', 'output.json']
    with patch.object(runner, 'PRIVATE', root), patch.object(runner, 'RUBRIC', rubric), \
            patch.object(runner, 'api', fake_api), patch.object(sys, 'argv', argv), \
            contextlib.redirect_stdout(io.StringIO()):
        runner.main()
        saved = (root / 'output.json').read_bytes()
        runner.main()
    records = json.loads(saved)['cases']
    assert len(calls) == 3
    assert records[0]['validation_errors'] == ['malformed_output']
    assert records[0]['usage']['eval_count'] == 12
    assert 'truncated_output' in records[1]['validation_errors']
    assert records[1]['valid_coverage'] is False
    assert records[2]['valid_coverage'] is True
    assert (root / 'output.json').read_bytes() == saved
print('ok: malformed/length batch isolation, usage preservation, invalid checkpoint record retained without rerun')
