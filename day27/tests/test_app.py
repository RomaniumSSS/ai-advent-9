"""Офлайн-проверки контракта: провайдер заменён локальным тестовым сервером."""
import importlib.util
import io
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SPEC = importlib.util.spec_from_file_location('day27_app', Path(__file__).parents[1] / 'app.py')
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)

class Contracts(unittest.TestCase):
    def test_validation(self):
        good = {'messages': [{'role': 'user', 'content': 'Привет'}]}
        self.assertEqual(app.validate_request(good), good['messages'])
        for bad in [{}, {'messages': []}, {'messages': [{'role':'system','content':'x'}]},
                    {'messages':[{'role':'user','content':' '}]},
                    {'messages':[{'role':'assistant','content':'x'}]},
                    {'messages':[{'role':'user','content':'x'*12001}]}]:
            with self.subTest(bad=str(bad)[:80]), self.assertRaises(ValueError):
                app.validate_request(bad)

    def test_payload_and_completed_stream(self):
        messages = [{'role':'user','content':'Тест'}]
        payload = app.provider_payload(messages)
        self.assertEqual(payload['messages'], messages)
        self.assertFalse(payload['think'])
        self.assertTrue(payload['stream'])
        self.assertEqual(payload['model'], 'qwen3:8b')
        self.assertEqual(payload['options']['num_ctx'], 4096)
        stream = io.BytesIO(b'{"message":{"content":"hello"},"done":false}\n'
                            b'{"message":{"content":"!"},"done":true,"done_reason":"stop","eval_count":2,"total_duration":2000000000}\n')
        events = list(app.parse_provider_stream(stream))
        self.assertEqual([e['content'] for e in events if e['type']=='delta'], ['hello','!'])
        self.assertEqual(events[-1]['type'], 'done')
        self.assertEqual(events[-1]['eval_count'], 2)
        self.assertEqual(events[-1]['total_duration'], 2000000000)
        self.assertIsNone(events[-1]['prompt_eval_count'])

    def test_interrupted_and_invalid_stream(self):
        for raw in [b'{"message":{"content":"partial"},"done":false}\n', b'not json\n',
                    b'{"error":"model missing"}\n', b'{"done":true}\n',
                    b'{"message":{"content":55},"done":false}\n']:
            with self.subTest(raw=raw), self.assertRaises(app.ProviderError):
                list(app.parse_provider_stream(io.BytesIO(raw)))

    def test_no_proxy_and_no_redirects(self):
        handlers = app.local_opener().handlers
        self.assertFalse(any(isinstance(h, urllib.request.ProxyHandler) and h.proxies for h in handlers))
        handler = next(h for h in handlers if isinstance(h, app.NoRedirect))
        with self.assertRaises(app.ProviderError):
            handler.redirect_request(None, None, 302, '', {}, 'https://example.com')

class HttpContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.make_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self, path, data=None, headers=None):
        request = urllib.request.Request(self.base+path, data=data, headers=headers or {})
        try:
            return urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            return error

    def test_html_and_validation(self):
        with self.request('/') as result:
            self.assertEqual(result.status, 200)
            self.assertIn('Локальный чат', result.read().decode())
        for data, headers, code in [(b'{}', {'Content-Type':'application/json'},400),
                                     (b'{}', {'Content-Type':'text/plain'},415),
                                     (b'{}', {'Content-Type':'application/json','Origin':'https://evil.example'},403),
                                     (b'{', {'Content-Type':'application/json'},400)]:
            with self.request('/api/chat', data, headers) as result:
                self.assertEqual(result.status, code)
                self.assertIn('error', json.load(result))

    def test_chat_forwards_history_and_final_event(self):
        history = [{'role':'user','content':'Проект Маяк'},
                   {'role':'assistant','content':'Запомнил'},
                   {'role':'user','content':'Название?'}]
        received = []
        def fake_events(messages):
            received.append(messages)
            yield {'type':'delta','content':'Маяк'}
            yield {'type':'done','done_reason':'stop','eval_count':2}
        with patch.object(app, 'chat_events', fake_events):
            with self.request('/api/chat', json.dumps({'messages':history}).encode(),
                              {'Content-Type':'application/json'}) as result:
                events = [json.loads(line) for line in result]
        self.assertEqual(received, [history])
        self.assertEqual(events[-1]['type'], 'done')
        self.assertEqual(events[0]['content'], 'Маяк')

    def test_provider_failure_is_stream_error_and_releases_lock(self):
        def fake_events(messages):
            yield {'type':'delta','content':'Часть'}
            raise app.ProviderError('Поток оборвался')
        with patch.object(app, 'chat_events', fake_events):
            with self.request('/api/chat', b'{"messages":[{"role":"user","content":"x"}]}',
                              {'Content-Type':'application/json'}) as result:
                events = [json.loads(line) for line in result]
        self.assertEqual([e['type'] for e in events], ['delta', 'error'])
        self.assertFalse(app.GENERATION_LOCK.locked())

    def test_unavailable_model_and_payload_without_network(self):
        opener = unittest.mock.MagicMock()
        opener.open.side_effect = urllib.error.URLError('offline')
        history = [{'role':'user','content':'x'}]
        with patch.object(app, 'local_opener', return_value=opener):
            with self.assertRaises(app.ProviderError):
                list(app.chat_events(history))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:11434/api/chat')
        self.assertEqual(json.loads(request.data)['messages'], history)
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 300)

    def test_unknown_path(self):
        with self.request('/../../CLAUDE.md') as result:
            self.assertEqual(result.status, 404)

if __name__ == '__main__':
    unittest.main(verbosity=2)
