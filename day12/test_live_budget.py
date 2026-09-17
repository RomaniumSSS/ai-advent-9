"""Deterministic doubles only: no API, no prices claimed as current."""
import json
import multiprocessing
import os
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from live_budget import LiveBudget, BudgetStop, MODEL
from profile import UserProfile

POLICY = dict(model=MODEL, provider='test-provider', price_source='test fixture',
              verified_at='test only', prompt_usd_per_million='0.1',
              completion_usd_per_million='0.2', max_prompt_tokens=8192, max_tokens=256)
REQUEST = dict(model=MODEL, max_tokens=256, messages=[UserProfile().message(), {'role':'user','content':'test'}])


def response(cost='0.0001'):
    return NS(id='test-id', provider='test-provider', model=MODEL,
              usage=NS(prompt_tokens=100, completion_tokens=20, cost=cost),
              choices=[NS(message=NS(content='answer'), finish_reason='stop')])


def stopped(call):
    try:
        call()
    except BudgetStop:
        return
    raise AssertionError('not stopped')


def crash(path):
    b = LiveBudget(path, POLICY)
    b.create(lambda **kw: os._exit(9), **REQUEST)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        count = []
        def send(**kw):
            count.append(kw)
            assert kw['extra_body']['provider']['allow_fallbacks'] is False
            assert kw['extra_body']['provider']['only'] == ['test-provider']
            return response()
        b = LiveBudget(root/'limits.json', POLICY)
        for _ in range(4):
            b.create(send, **REQUEST)
        stopped(lambda: b.create(send, **REQUEST))
        stopped(lambda: LiveBudget(b.path, POLICY).create(send, **REQUEST))
        assert len(count) == 4
        for index, bad in enumerate([None, NS(prompt_tokens=1, completion_tokens=1),
                                     NS(prompt_tokens=None, completion_tokens=1, cost='0.001'),
                                     NS(prompt_tokens=1, completion_tokens=1, cost='NaN'),
                                     NS(prompt_tokens=1, completion_tokens=1, cost='-1')]):
            b = LiveBudget(root/f'missing-{index}', POLICY)
            r = response(); r.usage = bad
            stopped(lambda: b.create(lambda **kw: r, **REQUEST))
            stopped(lambda: LiveBudget(b.path, POLICY).create(send, **REQUEST))
            assert len(b.snapshot()['attempts']) == 1
            if index == 2:
                assert b.snapshot()['reported_cost_usd'] == '0.001'
        b = LiveBudget(root/'error', POLICY)
        def error(**kw):
            raise RuntimeError('secret must not enter ledger')
        stopped(lambda: b.create(error, **REQUEST))
        stopped(lambda: b.create(send, **REQUEST))
        assert 'secret must not' not in b.path.read_text()
        for label, r in [('empty', response()), ('truncated', response()), ('expensive', response('0.03'))]:
            if label == 'empty': r.choices = []
            if label == 'truncated': r.choices[0].finish_reason = 'length'
            b = LiveBudget(root/label, POLICY)
            stopped(lambda: b.create(lambda **kw: r, **REQUEST))
            assert b.snapshot()['reported_cost_usd'] == ('0.03' if label == 'expensive' else '0.0001')
            stopped(lambda: b.create(send, **REQUEST))
        b = LiveBudget(root/'reserve', {**POLICY, 'prompt_usd_per_million':'10'})
        stopped(lambda: b.create(send, **REQUEST))
        assert not b.snapshot()['attempts']
        b = LiveBudget(root/'remaining', POLICY)
        for _ in range(1):
            s = b.snapshot(); s['reported_cost_usd'] = '0.0199'
            with b.locked(): b.write(s)
        stopped(lambda: b.create(send, **REQUEST))
        assert not b.snapshot()['attempts']
        b = LiveBudget(root/'parallel', POLICY)
        count.clear()
        def worker():
            stopped_or_result = lambda: LiveBudget(b.path, POLICY).create(send, **REQUEST)
            try: stopped_or_result()
            except BudgetStop: pass
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert len(count) == 4 and len(b.snapshot()['attempts']) == 4
        ctx = multiprocessing.get_context('spawn')
        p = ctx.Process(target=crash, args=(root/'crash',)); p.start(); p.join(10)
        assert p.exitcode == 9
        b = LiveBudget(root/'crash', POLICY)
        stopped(lambda: b.create(send, **REQUEST))
        assert len(b.snapshot()['attempts']) == 1 and 'unknown outcome' in b.snapshot()['stopped']
        stopped(lambda: LiveBudget(root/'limits.json', {**POLICY, 'provider':'changed'}))
        b = LiveBudget(root/'oversized', POLICY)
        stopped(lambda: b.create(send, **{**REQUEST, 'messages':[UserProfile().message(), {'role':'user','content':'x'*9000}]}))
        assert not b.snapshot()['attempts']
        # Integration: default runtime client is wrapped, profile remains automatic.
        import base_agent
        from test_memory import agent
        b = LiveBudget(root/'integration', POLICY)
        client = NS(chat=NS(completions=NS(create=send)))
        with patch.object(base_agent, '_client', client), patch.object(base_agent, '_live_budget', b):
            current = agent(root/'integration.db', 'one')
            current.store.save_profile(UserProfile('brief', 'list', 'three items'))
            assert current.ask('test').ok
            repeated = agent(root/'integration.db', 'two')
            assert repeated.ask('test').ok
            attempts = b.snapshot()['attempts']
            assert len(attempts) == 2
            assert attempts[0]['profile'] == attempts[1]['profile']
            assert attempts[0]['context_without_profile_hash'] == attempts[1]['context_without_profile_hash']
    print('ok: 4-call limit, restart, unknown usage, errors, cost overrun, empty/truncated, reserve, concurrency, crash, policy and input bounds')


if __name__ == '__main__':
    with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
        main()
