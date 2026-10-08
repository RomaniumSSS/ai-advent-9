"""Явное продолжение: прежний 429 не повторяется, резерв и lock сохраняются."""
import contextlib
import fcntl
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import run_openrouter_sample as runner
import resume_openrouter_429 as resume

model, _, filename = runner.MODELS[0]
meta = {'version': 'synthetic'}
cases = [{'case_id': c, 'message_ids': [1]} for c in ['T', 'U']]
jobs = [{'model': model, 'filename': filename, 'case': c, 'body': b'{}', 'reserve': .01} for c in cases]
ledger = {'meta': meta, 'stop_reason': 'http_error', 'attempts': [
    {'model': model, 'case_id': 'T', 'reserve': .01, 'actual_cost': None, 'status': 'error'}]}
failed = {'case_id': 'T', 'error_type': 'http_error', 'http_status': 429, 'reserved_cost': .01, 'actual_cost': None}
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    runner.write(root / filename, {'meta': meta, 'model': model, 'cases': [failed]})
    runner.write(root / 'semantic-openrouter-budget.json', ledger)
    clock = [0.0]; send_times = []
    def sleep(seconds): clock[0] += seconds
    class Reply:
        status_code = 200
        def json(self):
            return {'model': model, 'provider': 'DeepInfra', 'usage': {'cost': .001},
                    'choices': [{'message': {'content': json.dumps({'case_id': 'U',
                      'decisions': {'1': {'decision': 'exclude', 'reason': 'synthetic', 'flags': []}},
                      'document_groups': [], 'review_groups': [], 'missing_context_ids': [], 'notes': ''})},
                      'finish_reason': 'stop'}]}
    def post(*args, **kwargs): send_times.append(clock[0]); return Reply()
    with patch.object(runner, 'PRIVATE', root), patch.object(runner, 'api_key', return_value='test'), \
         patch.object(runner.requests, 'post', post), patch.object(resume.time, 'sleep', sleep), \
         patch.object(resume.time, 'monotonic', lambda: clock[0]), contextlib.redirect_stdout(io.StringIO()):
        attempted, last = resume.inspect(ledger, jobs, meta)
        assert attempted == {(model, 'T')}
        resume.continue_live({'messages': [{'id': 1}]}, jobs, meta, ledger)
    assert send_times == [30.0]
    saved = json.loads((root / 'semantic-openrouter-budget.json').read_text())
    assert len(saved['attempts']) == 2 and saved['attempts'][0] == ledger['attempts'][0]
    assert abs(runner.spent(saved) - .011) < 1e-9
    assert saved['continuations'][0]['no_retry'] and saved['continuations'][0]['last_case'] == 'T'
    results = json.loads((root / filename).read_text())['cases']
    assert results[0] == failed and results[1]['case_id'] == 'U' and results[1]['elapsed_seconds'] == 0
    with patch.object(runner, 'PRIVATE', root):
        try: resume.inspect(saved, jobs, meta)
        except ValueError: pass
        else: raise AssertionError('second continuation allowed')
    lock = root / 'semantic-openrouter-budget.lock'
    with lock.open('a') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with patch.object(runner, 'PRIVATE', root), patch.object(runner, 'prepare', return_value=({}, jobs, meta)), \
             patch.object(sys, 'argv', ['resume', '--live']):
            try: resume.main()
            except ValueError: pass
            else: raise AssertionError('lock ignored')
print('ok: one continuation, 429 skipped/record retained, budget preserved, initial pacing outside elapsed, flock rejects double start')
