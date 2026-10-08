"""Точечные mock-проверки budget, resume и провайдера; без API."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import run_openrouter_sample as runner

case = {'case_id': 'T', 'message_ids': [1]}
messages = [{'id': 1}]
model, provider, filename = runner.MODELS[0]
body = runner.request_body(model, provider, case, messages, 'rubric')
assert body['provider'] == {'only': ['deepinfra/fp8'], 'allow_fallbacks': False,
                           'require_parameters': True, 'data_collection': 'deny',
                           'max_price': {'prompt': .20, 'completion': .60}}
assert body['reasoning'] == {'enabled': False} and body['max_tokens'] == 2048
glm = runner.request_body(runner.MODELS[1][0], runner.MODELS[1][1], case, messages, 'rubric')
assert glm['reasoning'] == {'effort': 'low'} and glm['provider']['only'] == ['deepinfra/fp4']
assert body['temperature'] == 0 and body['stream'] is False
assert body['response_format']['json_schema']['strict'] is True
ledger = {'meta': {}, 'attempts': []}
for number in range(3): runner.reserve(ledger, ('M', str(number)), .3)
assert abs(runner.spent(ledger) - .9) < 1e-9
try: runner.reserve(ledger, ('M', '4'), .3)
except ValueError: pass
else: raise AssertionError('cap exceeded')
ledger['attempts'][0]['actual_cost'] = .1
assert abs(runner.spent(ledger) - .7) < 1e-9
try: runner.ensure_ledger({'meta': {}, 'attempts': [dict(ledger['attempts'][0], reserve=0)]}, {}, {('M', '0'): .3})
except ValueError: pass
else: raise AssertionError('unsafe reserve accepted')

valid = {'case_id': 'T', 'decisions': {'1': {'decision': 'exclude', 'reason': 'synthetic', 'flags': []}},
         'document_groups': [], 'review_groups': [], 'missing_context_ids': [], 'notes': ''}
def response(content=None, cost=.001):
    return {'model': model, 'provider': 'DeepInfra', 'usage': {'cost': cost},
            'choices': [{'message': {'content': json.dumps(valid) if content is None else content}, 'finish_reason': 'stop'}]}
record, stop = runner.process_response(case, messages, response(), model)
assert record['valid_coverage'] and not stop
bad = response('{'); record, stop = runner.process_response(case, messages, bad, model)
assert not record['valid_coverage'] and not stop and record['usage']['cost'] == .001
bad = response(); bad['choices'][0]['finish_reason'] = 'length'
record, stop = runner.process_response(case, messages, bad, model)
assert not record['valid_coverage'] and 'truncated_output' in record['validation_errors']
bad = response(); bad['provider'] = 'Other'
assert runner.process_response(case, messages, bad, model)[1] == 'unexpected_provider_or_model'

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory); meta = {'version': 'synthetic'}
    job = {'model': model, 'filename': filename, 'case': case, 'body': b'{}', 'reserve': .01}
    secret = 'TEST_SECRET_MUST_NOT_PRINT'
    env = root / 'key.env'; env.write_text('UNRELATED=x\nOPENROUTER_API_KEY=' + secret + '\n')
    with patch.dict(os.environ, {}, clear=True), patch.object(runner, 'ENV_FILE', env):
        assert runner.api_key() == secret
    class Reply:
        status_code = 200
        def json(self): return response(cost=None)
    output = io.StringIO()
    with patch.object(runner, 'PRIVATE', root), patch.object(runner, 'api_key', return_value=secret), \
         patch.object(runner.requests, 'post', return_value=Reply()) as network, contextlib.redirect_stdout(output):
        runner.live({'messages': messages}, [job], meta)
        assert network.call_count == 1
        kwargs = network.call_args.kwargs
        assert kwargs['verify'] and kwargs['timeout'] == 600
        runner.live({'messages': messages}, [job], meta)
        assert network.call_count == 1
    assert secret not in output.getvalue()
    saved = json.loads((root / 'semantic-openrouter-budget.json').read_text())
    assert runner.spent(saved) == .01 and saved['attempts'][0]['actual_cost'] is None
    saved['attempts'][0]['status'] = 'pending'
    runner.write(root / 'semantic-openrouter-budget.json', saved)
    with patch.object(runner, 'PRIVATE', root), patch.object(runner.requests, 'post') as network:
        try: runner.live({'messages': messages}, [job], meta)
        except ValueError: pass
        else: raise AssertionError('pending restarted')
        network.assert_not_called()

# Первый HTTP/config сбой останавливает весь batch и оставляет reserve.
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    class Failure:
        status_code = 429
    with patch.object(runner, 'PRIVATE', root), patch.object(runner, 'api_key', return_value='test'), \
         patch.object(runner.requests, 'post', return_value=Failure()) as network, contextlib.redirect_stdout(io.StringIO()):
        runner.live({'messages': messages}, [job, dict(job, case={'case_id': 'U', 'message_ids': [1]})], meta)
        assert network.call_count == 1
    saved = json.loads((root / 'semantic-openrouter-budget.json').read_text())
    assert saved['stop_reason'] == 'http_error' and runner.spent(saved) == .01
print('ok: pinned params/TLS, shared budget/unknown cost, no retry/pending, safe checkpoint, key privacy, invalid JSON/length/provider, HTTP stop')

for outcome in ['timeout', 'overspend']:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        class Overspend:
            status_code = 200
            def json(self): return response(cost=.02)
        options = {'side_effect': runner.requests.Timeout()} if outcome == 'timeout' else {'return_value': Overspend()}
        with patch.object(runner, 'PRIVATE', root), patch.object(runner, 'api_key', return_value='test'), \
             patch.object(runner.requests, 'post', **options) as network, contextlib.redirect_stdout(io.StringIO()):
            runner.live({'messages': messages}, [job], meta)
            assert network.call_count == 1
        saved = json.loads((root / 'semantic-openrouter-budget.json').read_text())
        assert saved['stop_reason'] == ('transport_or_response_error' if outcome == 'timeout' else 'actual_exceeds_reserve')
        assert runner.spent(saved) == (.01 if outcome == 'timeout' else .02)
print('ok: mandatory GLM low reasoning, timeout reservation, actual-over-reserve stop')
