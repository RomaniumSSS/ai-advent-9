"""Offline repair tests: real captured source, synthetic new responses, zero network."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch

from live_budget import LiveBudget, BudgetStop, digest
from repair_contract import source_check, RUN_ID, short_format
from resume_live import run
from verify_live import PROFILES

SOURCE = json.loads((Path(__file__).parent/'results/live-deepseek.json').read_text())
ANSWER = 'Резервная копия похожа на запасной ключ: регулярно сохраняй данные отдельно.\n\nДля проверки восстанови файлы в другую папку и открой их.'


def ns(value):
    if isinstance(value, dict): return NS(**{k: ns(v) for k,v in value.items()})
    if isinstance(value, list): return [ns(v) for v in value]
    return value


class LocalTunnel:
    def __init__(self, root):
        self.path = root/'ledger.json'
        self.path.write_text(json.dumps(SOURCE['ledger']))
        self.budget = LiveBudget(self.path, SOURCE['ledger']['policy'])
        self.state = {'offline': False, 'model': 'deepseek-v4-flash', 'scope': {},
                      'history': [], 'notes': {}, 'profile': {}}
        self.saves = 0
        self.sends = 0
        self.answer = ANSWER
        self.fail = False
        self.request_edit = lambda request: None

    def send(self, **kwargs):
        self.sends += 1
        if self.fail: raise RuntimeError('synthetic provider error')
        result = deepcopy(SOURCE['ledger']['attempts'][0]['response'])
        result['choices'][0]['message']['content'] = self.answer
        result['usage']['cost'] = 0.00001
        return ns(result)

    def request(self, path, body=None):
        if path == 'evidence': return self.budget.snapshot()
        if path == 'state': return {'state': deepcopy(self.state)}
        if path == 'resume': return self.budget.authorize_resume(body['source_report'], body['approved_by'], body['reason'])
        if path == 'scope':
            self.state['scope'] = body
            self.state['history'] = []
            return {'state': deepcopy(self.state)}
        if path == 'profile':
            self.saves += 1
            self.state['profile'] = body
            return {}
        if path == 'chat':
            assert set(body) == {'text'}
            if self.sends: assert self.saves == 1
            request = deepcopy(SOURCE['ledger']['attempts'][0]['request'])
            request['messages'][1] = PROFILES[1].message()
            self.request_edit(request)
            try:
                result = self.budget.create(self.send, **request)
                return {'ok': True, 'saved': True, 'message': result.choices[0].message.content}
            except BudgetStop:
                return {'ok': False, 'saved': False, 'message': 'stopped'}
        raise AssertionError(path)


def rejected(call):
    try: call()
    except (BudgetStop, ValueError): return
    raise AssertionError('expected rejection')


def main():
    original_hash = digest(SOURCE)
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        tunnel = LocalTunnel(root)
        report = {}
        run(tunnel, SOURCE, report, lambda: None, 'offline tester', 'fixture analysis')
        assert tunnel.sends == 2 and tunnel.saves == 1
        ledger = tunnel.budget.snapshot()
        assert ledger['attempts'][:2] == SOURCE['ledger']['attempts']
        assert ledger['reported_cost_usd'] == '0.00012041'
        assert ledger['stopped'] == 'budget reached'
        assert report['outcome'] == 'awaiting_human_rubric' and len(report['cases']) == 4
        assert report['automatic_profile_repeat']
        rejected(lambda: tunnel.budget.authorize_resume(SOURCE, 'tester', 'again'))
        rejected(lambda: run(tunnel, SOURCE, {}, lambda: None, 'tester', 'again'))
        request = ledger['attempts'][-1]['request']
        rejected(lambda: LiveBudget(tunnel.path, ledger['policy']).create(tunnel.send, **request))
        assert tunnel.sends == 2
        for field in ('run_id', 'cost', 'status', 'policy', 'attempt', 'audit'):
            changed = deepcopy(SOURCE)
            if field == 'run_id': changed['run_id'] = 'other'
            if field == 'cost': changed['ledger']['reported_cost_usd'] = '0'
            if field == 'status': changed['ledger']['stopped'] = None
            if field == 'policy': changed['ledger']['policy']['max_tokens'] = 1024
            if field == 'attempt': changed['ledger']['attempts'].pop()
            if field == 'audit': changed['ledger']['manual_resume'] = {}
            rejected(lambda: source_check(changed))
            tunnel = LocalTunnel(root)
            if field != 'run_id':
                tunnel.path.write_text(json.dumps(changed['ledger']))
                rejected(lambda: tunnel.budget.authorize_resume(SOURCE, 'tester', 'analysis'))
                assert tunnel.sends == 0
        for case in ('tokens', 'reasoning', 'temperature', 'context', 'profile', 'bad_format', 'error', 'audit', 'cost'):
            tunnel = LocalTunnel(root)
            def edit(request):
                if case == 'tokens': request['max_tokens'] = 256
                if case == 'reasoning': request['extra_body']['reasoning'] = {'effort':'low'}
                if case == 'temperature': request['temperature'] = 0
                if case == 'context': request['messages'][-1]['content'] = 'other'
                if case == 'profile': request['messages'][1] = PROFILES[0].message()
                if case in ('audit', 'cost'):
                    state = tunnel.budget.snapshot()
                    if case == 'audit': state['manual_resume']['run_id'] = 'other'
                    else: state['reported_cost_usd'] = '0'
                    with tunnel.budget.locked(): tunnel.budget.write(state)
            tunnel.request_edit = edit
            if case == 'bad_format': tunnel.answer = 'bad format'
            if case == 'error': tunnel.fail = True
            report = {}
            rejected(lambda: run(tunnel, SOURCE, report, lambda: None, 'tester', 'analysis'))
            assert tunnel.sends == (1 if case in ('bad_format', 'error') else 0), case
            if case == 'bad_format':
                # B-repeat remains denied even if a caller bypasses runner rubric.
                req = tunnel.budget.snapshot()['attempts'][-1]['request']
                rejected(lambda: tunnel.budget.create(tunnel.send, **req))
                assert tunnel.sends == 1
        assert digest(SOURCE) == original_hash
        assert short_format(ANSWER)
        assert not short_format('One. Two.\n\nThree.')
        assert not short_format(' '.join(['word']*61) + '.\n\nEnd.')
        # Actual private action dispatcher + SQLite + agent context builder.
        import base_agent
        import web
        tunnel = LocalTunnel(root)
        web.STATE.update(db=root/'runtime.db', config=base_agent.AgentConfig(max_tokens=512),
                         recent_turns=6, offline=False)
        client = NS(chat=NS(completions=NS(create=tunnel.send)))
        class WebTunnel:
            saves = 0
            def request(self, path, body=None):
                if path == 'evidence': return tunnel.budget.snapshot()
                if path == 'state': return {'state': web.state()}
                if path == 'profile': self.saves += 1
                return web.act('/api/' + path, body)
        with patch.object(base_agent, '_client', client), patch.object(base_agent, '_live_budget', tunnel.budget):
            web.STATE['agent'] = web.make_agent('initial', RUN_ID, RUN_ID)
            transport = WebTunnel()
            run(transport, SOURCE, {}, lambda: None, 'offline tester', 'integration')
            assert transport.saves == 1 and tunnel.sends == 2
            web.act('/api/scope', {'session':'wrong', 'task':RUN_ID, 'user':RUN_ID})
            rejected(lambda: web.act('/api/chat', {'text':'test'}))
            assert tunnel.sends == 2
    print('ok: pinned source, immutable failed attempt/cost, audit, two remaining calls, B repeat without save, request guards, no retry, consolidated report')


if __name__ == '__main__':
    with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
        main()
