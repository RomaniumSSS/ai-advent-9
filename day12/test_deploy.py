"""Настоящий локальный HTTP; временная БД, без провайдера."""
import http.client
import json
import socket
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import base_agent
import web
from agent import AgentConfig


def request(server, method, path, body=None, host=None, origin=None):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    headers = {'Host': host or f'127.0.0.1:{server.server_port}'}
    if origin is not None:
        headers['Origin'] = origin
    if body is not None:
        headers['Content-Type'] = 'application/json'
        body = json.dumps(body)
    try:
        conn.request(method, path, body, headers)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def main():
    with tempfile.TemporaryDirectory() as directory, patch.object(base_agent, 'get_client', side_effect=AssertionError('API forbidden')):
        web.STATE.update(db=Path(directory)/'test.db', config=AgentConfig(), recent_turns=2, offline=True)
        web.STATE['agent'] = web.make_agent('smoke', 'smoke', 'smoke')
        servers = web.bind_servers(read_port=0, run_port=0)
        public, local = servers
        assert public.server_address[0] == '127.0.0.1'
        assert local.server_address[0] == '127.0.0.1'
        threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
        for thread in threads:
            thread.start()
        try:
            for path in ['/', '/app.js', '/api/state']:
                assert request(public, 'GET', path, host='external.example')[0] == 200
            assert request(public, 'GET', '/api/evidence')[0] == 404
            assert request(local, 'GET', '/api/evidence')[0] == 409
            before = web.state()
            with patch.object(web, 'act', side_effect=AssertionError('public mutation')):
                for path in ['profile', 'demo-user', 'save', 'forget', 'scope', 'reset', 'chat', 'unknown']:
                    for host in ['external.example', f'localhost:{public.server_port}']:
                        assert request(public, 'POST', '/api/'+path, {}, host)[0] == 403
            assert before == web.state()
            for method in ['PUT', 'PATCH', 'DELETE']:
                assert request(public, method, '/api/reset', {})[0] == 501
            assert request(local, 'POST', '/api/reset', {}, 'evil.example')[0] == 403
            for origin in ['http://evil.example', 'null', f'http://localhost:{local.server_port}', f'http://evil@127.0.0.1:{local.server_port}']:
                assert request(local, 'POST', '/api/reset', {}, origin=origin)[0] == 403
            # Tokenizer and client must remain offline during the action.
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
                web.act('/api/chat', {'text': 'Проверка'})
            assert request(local, 'POST', '/api/save', {'layer':'working', 'key':'smoke', 'value':'ok'}, origin=f'http://127.0.0.1:{local.server_port}')[0] == 200
            data = json.loads(request(public, 'GET', '/api/state')[1])
            assert data['read_only'] and data['state']['offline']
            assert b'smoke' in request(public, 'GET', '/api/state')[1]
            assert not json.loads(request(local, 'GET', '/api/state')[1])['read_only']
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join()
        # A failed second bind releases the first socket.
        first = web.ThreadingHTTPServer(('127.0.0.1', 0), web.Handler)
        with patch.object(web, 'ThreadingHTTPServer', side_effect=[first, OSError('occupied')]):
            try:
                web.bind_servers(read_port=0, run_port=0)
            except OSError:
                pass
            else:
                raise AssertionError('bind failure hidden')
        assert first.socket.fileno() == -1
    unit = (Path(__file__).parent/'deploy/day12.service').read_text()
    assert '--offline' not in unit and '--read-port 8035 --run-port 8036' in unit
    assert 'EnvironmentFile=/etc/ai-advent-day12/openrouter.env' in unit
    assert 'UnsetEnvironment=OPENROUTER_API_KEY' not in unit
    assert '--live-policy' in unit and '--live-ledger' in unit
    assert 'load_dotenv' not in Path('base_agent.py').read_text()
    print('ok: real local HTTP, public denial, loopback actions, offline, bind cleanup, unit')


if __name__ == '__main__':
    main()
