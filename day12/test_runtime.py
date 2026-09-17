"""Runtime wiring and listener contracts without opening a socket."""
import io
import os
import stat
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import base_agent
import web
from deploy.check_secret import check_secret
from test_memory import FakeClient


def main():
    with patch.object(base_agent, '_client', None), patch.object(base_agent, '_live_budget', None), patch.dict(os.environ, {'OPENROUTER_API_KEY':'test-only'}), patch.object(base_agent, 'OpenAI') as factory:
        client = base_agent.get_client()
        assert client is factory.return_value
        assert factory.call_args.kwargs['max_retries'] == 0
        assert factory.call_args.kwargs['base_url'] == 'https://openrouter.ai/api/v1'
    with tempfile.TemporaryDirectory() as tmp:
        web.STATE.update(db=Path(tmp)/'db', config=base_agent.AgentConfig(), recent_turns=2, offline=False)
        client = FakeClient()
        with patch.object(base_agent, 'get_client', return_value=client):
            web.STATE['agent'] = web.make_agent('real-wire', 'task', 'user')
            assert web.STATE['agent'].client is None, 'production must select real client'
            assert web.act('/api/chat', {'text':'test'})['ok']
            assert len(client.requests) == 1
    # Exercise actual handler dispatch, stopping before body reads and act().
    for path in ('/api/chat', '/api/profile', '/api/resume', '/anything'):
        handler = object.__new__(web.ReadHandler)
        handler.path = path
        handler.rfile = NS(read=lambda *args: (_ for _ in ()).throw(AssertionError('body read')))
        results = []
        handler.send_json = lambda body, status=200: results.append(status)
        with patch.object(web, 'act', side_effect=AssertionError('mutation')):
            handler.do_POST()
        assert results == [403]
    addresses = []
    def server(address, handler):
        addresses.append((address, handler))
        return NS(server_close=lambda: None)
    with patch.object(web, 'ThreadingHTTPServer', side_effect=server):
        web.bind_servers(read_port=8035, run_port=8036)
    assert addresses == [(('127.0.0.1',8035), web.ReadHandler), (('127.0.0.1',8036), web.Handler)]
    for mode, uid, gid, valid in [(stat.S_IFREG|0o600,0,0,True), (stat.S_IFREG|0o644,0,0,False), (stat.S_IFREG|0o600,501,0,False), (stat.S_IFLNK|0o600,0,0,False)]:
        file = NS(lstat=lambda: NS(st_mode=mode, st_uid=uid, st_gid=gid))
        with patch.dict(os.environ, {'OPENROUTER_API_KEY':'test-only'}):
            try: check_secret(file)
            except RuntimeError: assert not valid
            else: assert valid
    unit = Path('deploy/day12.service').read_text()
    assert '--offline' not in unit and 'UnsetEnvironment=OPENROUTER_API_KEY' not in unit
    assert 'EnvironmentFile=/etc/ai-advent-day12/openrouter.env' in unit
    assert 'check_secret.py' in unit and '--live-policy' in unit and '--live-ledger' in unit
    assert 'load_dotenv' not in Path('base_agent.py').read_text()
    # Empty choices still expose reported usage to callers; ledger is authoritative.
    with tempfile.TemporaryDirectory() as tmp:
        from test_memory import agent
        a = agent(Path(tmp)/'db', 'empty')
        reply = a._record(NS(choices=[], usage=NS(prompt_tokens=4, completion_tokens=2, cost=0.001)), 0, None)
        assert reply.cost_reported == 0.001 and reply.prompt_tokens == 4
    print('ok: production SDK wiring, public POST before body, loopback bind contract, secret metadata, unit, empty usage (no socket opened)')


if __name__ == '__main__':
    with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
        main()
