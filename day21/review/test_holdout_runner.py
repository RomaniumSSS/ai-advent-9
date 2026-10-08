"""Офлайн-проверки holdout-интерфейса; тексты не выводятся."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import run_local_sample as runner
from pilot_validation import diagnose_context
from prepare_development_context import PRIVATE

case = {'case_id': 'T', 'message_ids': [1]}
for value, error in [({}, 'context_input_container'), ([None], 'context_input_message_type'),
                     ([], 'context_input_missing_case_id'), ([{'id': 1}, {'id': 1}], 'context_input_duplicate_id')]:
    assert diagnose_context(case, value, {}) == [error]
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / 'input.json'
    source.write_text(json.dumps({'cases': [case], 'messages': [{'id': 1}]}))
    rubric = root / 'default.txt'; rubric.write_text('default synthetic')
    def fake_api(endpoint, payload=None):
        if endpoint == '/api/tags': return {'models': [{'name': runner.MODEL, 'digest': 'test'}]}
        if endpoint == '/api/generate': return {}
        return {'message': {'content': '{'}, 'done_reason': 'stop'}
    with patch.object(runner, 'PRIVATE', root), patch.object(runner, 'RUBRIC', rubric), \
         patch.object(runner, 'api', fake_api), contextlib.redirect_stdout(io.StringIO()):
        with patch.object(sys, 'argv', ['x', '--input', 'input.json', '--output', 'default.json']): runner.main()
        default = json.loads((root / 'default.json').read_text())
        assert default['rubric_sha256'] == hashlib.sha256(rubric.read_bytes()).hexdigest()
        assert default['system_prompt'] == 'default synthetic' and not default['schema_mode']
        argv = ['x', '--input', 'input.json', '--output', 'v3.json', '--rubric', 'semantic-rubric-v3.txt', '--schema']
        with patch.object(sys, 'argv', argv): runner.main()
        saved = json.loads((root / 'v3.json').read_text())
        real_rubric = Path(runner.__file__).with_name('semantic-rubric-v3.txt')
        assert saved['rubric_sha256'] == hashlib.sha256(real_rubric.read_bytes()).hexdigest()
        for key, value in [('rubric_sha256', 'different'), ('schema_mode', False)]:
            meta = dict(saved); meta[key] = value
            try: runner.resume(saved, meta)
            except ValueError: pass
            else: raise AssertionError('checkpoint mismatch accepted')
        source.write_text(json.dumps({'cases': [case], 'messages': {}}))
        with patch.object(sys, 'argv', argv), patch.object(runner, 'api') as network:
            try: runner.main()
            except ValueError: pass
            else: raise AssertionError('malformed inputs accepted')
            network.assert_not_called()

full = json.loads((PRIVATE / 'semantic-expanded-v2-input.json').read_text())
holdout = json.loads((PRIVATE / 'semantic-expanded-v3-holdout-input.json').read_text())
ids = {m['id'] for m in holdout['messages']}
original = {m['id']: m for m in full['messages']}
expected_cases = [c for c in full['cases'] if c['split'] == 'holdout']
assert holdout['cases'] == expected_cases and len(expected_cases) == 20 and len(ids) == 51
assert ids == {i for c in expected_cases for i in c['message_ids']}
for m in holdout['messages']:
    assert all(m[k] == v for k, v in original[m['id']].items())
    assert m['text'].encode() == original[m['id']]['text'].encode()
    assert m['content_read'] is False
for name in ['semantic-expanded-v2-development-input.json', 'semantic-pilot-v2-input.json']:
    other = json.loads((PRIVATE / name).read_text())
    assert not ids & {m['id'] for m in other['messages']}
assert holdout['parent_input_sha256'] == hashlib.sha256((PRIVATE / 'semantic-expanded-v2-input.json').read_bytes()).hexdigest()
assert (PRIVATE / 'semantic-expanded-v3-holdout-input.json').stat().st_mode & 0o777 == 0o600
print('ok: default/v3 rubric, checkpoint mismatch, context containers, before-API failure, holdout 20/51 unchanged/disjoint/0600')
