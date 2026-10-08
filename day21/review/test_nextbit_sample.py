"""NextBit adapter: отдельный provider, общий bound и безопасное сохранение."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import run_nextbit_sample as runner

case = {'case_id': 'T', 'message_ids': [1]}
messages = [{'id': 1}]
output = {'case_id': 'T', 'decisions': {'1': {'decision': 'exclude', 'reason': 'synthetic', 'flags': []}},
          'document_groups': [], 'review_groups': [], 'missing_context_ids': [], 'notes': ''}
def response(provider='NextBit', text=None):
    return {'model': runner.MODEL, 'provider': provider, 'usage': {'cost': None},
            'choices': [{'message': {'content': json.dumps(output) if text is None else text}, 'finish_reason': 'stop'}]}
record, stop = runner.process_response(case, messages, response())
assert record['provider'] == 'NextBit' and record['valid_coverage'] and stop is None
record, stop = runner.process_response(case, messages, response('DeepInfra'))
assert record['provider'] == 'DeepInfra' and stop == 'unexpected_provider_or_model'
record, stop = runner.process_response(case, messages, response(text='{'))
assert not record['valid_coverage'] and stop is None
assert runner.process_response(case, messages, {'model': runner.MODEL, 'provider': 'NextBit', 'choices': []})[1] == 'response_envelope'

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    prior = {'stop_reason': 'http_error', 'attempts': [{'model': 'prior', 'case_id': 'P', 'reserve': .02, 'actual_cost': None, 'status': 'error'}]}
    runner.shared.write(root / runner.PRIOR, prior)
    with patch.object(runner, 'PRIVATE', root):
        digest, bound = runner.prior_snapshot()
        meta = {'prior_ledger_sha256': digest, 'prior_bound': bound}
        job = {'model': runner.MODEL, 'case': case, 'body': b'{}', 'reserve': .01}
        ledger = {'meta': meta, 'attempts': []}
        runner.reserve(ledger, job)
        assert runner.shared.spent(ledger) == .01
        try: runner.reserve(ledger, job)
        except ValueError: pass
        else: raise AssertionError('duplicate reservation')
        expensive = {'meta': meta, 'attempts': []}
        try: runner.reserve(expensive, dict(job, reserve=.99))
        except ValueError: pass
        else: raise AssertionError('combined cap exceeded')
        old_bytes = (root / runner.PRIOR).read_bytes()
        (root / runner.PRIOR).write_bytes(old_bytes + b' ')
        try: runner.reserve({'meta': meta, 'attempts': []}, job)
        except ValueError: pass
        else: raise AssertionError('prior SHA change ignored')
        (root / runner.PRIOR).write_bytes(old_bytes)
        class Reply:
            status_code = 200
            def json(self): return response()
        stdout = io.StringIO()
        with patch.object(runner.shared, 'api_key', return_value='SECRET_NOT_IN_STDOUT'), \
             patch.object(runner.requests, 'post', return_value=Reply()) as network, contextlib.redirect_stdout(stdout):
            runner.live({'messages': messages}, [job], meta)
            runner.live({'messages': messages}, [job], meta)
            assert network.call_count == 1
        assert 'SECRET_NOT_IN_STDOUT' not in stdout.getvalue()
        assert (root / runner.PRIOR).read_bytes() == old_bytes
        own = json.loads((root / runner.LEDGER).read_text())
        assert runner.shared.spent(own) == .01 and own['attempts'][0]['actual_cost'] is None
        own['attempts'][0]['status'] = 'pending'; runner.shared.write(root / runner.LEDGER, own)
        with patch.object(runner.requests, 'post') as network:
            try: runner.live({'messages': messages}, [job], meta)
            except ValueError: pass
            else: raise AssertionError('pending repeated')
            network.assert_not_called()
print('ok: explicit NextBit guard, prior SHA/frozen bound, combined cap, duplicate/pending/no-retry, unknown reserve, old ledger unchanged, no secret output, malformed envelope/JSON')
