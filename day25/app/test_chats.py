"""T1: local storage and HTTP boundaries; no provider or SSH calls."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from service import Service
from common import save
from web import make_server


def empty_search(question, scope):
    return {'trace': {'empty': True, 'selected': []}}


class ChatsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / 'private'
        self.calls = []
        def search(question, scope):
            self.calls.append((question, scope))
            return empty_search(question, scope)
        self.service = Service(self.directory, search_fn=search,
                               generate_fn=lambda *_: self.fail('provider called'))
        self.a = self.service.create_chat('A')['chat_id']
        self.b = self.service.create_chat('B')['chat_id']

    def tearDown(self):
        self.tmp.cleanup()

    def test_archive_restart_isolation_and_idempotency(self):
        first = self.service.ask(self.a, 'r1', 'Question', 'all')
        self.assertEqual(first, self.service.ask(self.a, 'r1', 'Question', 'all'))
        self.assertEqual(len(self.calls), 1)
        with self.assertRaisesRegex(ValueError, 'id_chat_changed'):
            self.service.ask(self.b, 'r1', 'Question', 'all')
        with self.assertRaisesRegex(ValueError, 'id_payload_changed'):
            self.service.ask(self.a, 'r1', 'Different', 'all')
        for action in (lambda: self.service.get(self.b, 'r1'),
                       lambda: self.service.feedback(self.b, 'r1', [], 'bad')):
            with self.assertRaisesRegex(ValueError, 'result_not_found'): action()
        self.assertEqual(self.service.history(self.b), [])
        self.assertEqual(self.service.messages(self.b), [])
        self.assertEqual([m['role'] for m in self.service.messages(self.a)], ['user', 'assistant'])
        restarted = Service(self.directory, search_fn=empty_search)
        self.assertEqual(restarted.get(self.a, 'r1'), first)
        self.assertEqual(len(restarted.chats()), 2)
        self.assertEqual(restarted.messages(self.a), self.service.messages(self.a))
        restarted.feedback(self.a, 'r1', ['неполный ответ'], 'review')
        self.assertEqual(restarted.get(self.a, 'r1')['feedback']['comment'], 'review')

    def test_task_state_versions_delete_and_snapshot(self):
        state = {'goal': 'Learn RAG', 'clarifications': ['Python'], 'constraints': ['Short']}
        updated = self.service.update_task_state(self.a, state, 0)
        self.assertEqual(updated['task_state']['version'], 1)
        item = self.service.ask(self.a, 'r1', 'Question', 'all')
        self.service.clear_task_state(self.a, 1)
        restarted = Service(self.directory, search_fn=empty_search)
        self.assertEqual(restarted.chat(self.a)['task_state'],
                         {'version': 2, 'goal': '', 'clarifications': [], 'constraints': []})
        self.assertEqual(restarted.get(self.a, 'r1')['task_state']['goal'], 'Learn RAG')
        self.assertEqual(item['task_state_version'], 1)
        self.assertEqual(restarted.chat(self.b)['task_state']['version'], 0)
        with self.assertRaisesRegex(ValueError, 'version_conflict'):
            restarted.update_task_state(self.a, state, 1)
        for invalid in ({}, {'goal': 'x', 'clarifications': 'x', 'constraints': []}):
            with self.assertRaisesRegex(ValueError, 'invalid_task_state'):
                restarted.update_task_state(self.a, invalid, 2)

    def test_permissions_scope_and_no_automatic_migration(self):
        self.service.ask(self.a, 'r1', 'Question', 'all')
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        for path in self.directory.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(ValueError, 'chat_scope_changed'):
            self.service.ask(self.a, 'r2', 'Question', 'public')
        for ident in ('../escape', '', None):
            with self.assertRaises(ValueError): self.service.chat(ident)
        save(self.directory / 'result-legacy.json', {'id': 'legacy', 'status': 'no_context'})
        restarted = Service(self.directory, search_fn=empty_search)
        self.assertEqual(len(restarted.history(self.a)), 1)
        with self.assertRaisesRegex(ValueError, 'result_not_found'): restarted.get(self.a, 'legacy')

    def test_http_public_and_foreign_chat_boundaries(self):
        public = self.service.create_chat('public', 'public')['chat_id']
        self.service.ask(public, 'pub', 'Public question', 'public')
        self.service.ask(self.a, 'private', 'Private question', 'all')
        contaminated = self.service.ask(public, 'contaminated', 'Private archive question', 'public')
        contaminated['search']['trace']['selected'] = [{'document_id':'private:note','text':'Private archive text'}]
        contaminated['answer']['answer'] = 'Private archive answer'
        save(self.service.path('contaminated'), contaminated)
        server = make_server(0, service=self.service, public_only=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def call(route, data=None):
            headers = {'Host': server.address, 'Origin': 'http://' + server.address,
                       'X-Mentor-Token': server.token, 'Content-Type': 'application/json'}
            req = Request('http://' + server.address + route,
                          data=json.dumps(data).encode() if data is not None else None, headers=headers)
            try:
                with urlopen(req) as response: return response.status, json.load(response)
            except HTTPError as error:
                with error: return error.code, json.load(error)
        try:
            code, chats = call('/api/chats')
            self.assertEqual(code, 200)
            self.assertEqual([c['chat_id'] for c in chats], [public])
            self.assertEqual(call('/api/chat/' + self.a)[0], 404)
            self.assertEqual(call('/api/result/private?chat_id=' + self.a)[0], 404)
            self.assertEqual(call('/api/result/private?chat_id=' + public)[0], 400)
            self.assertEqual(call('/api/result/pub?chat_id=' + public)[0], 200)
            self.assertEqual(call('/api/result/contaminated?chat_id=' + public)[0], 404)
            code, archive = call('/api/chat/' + public)
            self.assertEqual(code, 200)
            self.assertEqual([item['id'] for item in archive['history']], ['pub'])
            self.assertEqual({message['request_id'] for message in archive['messages']}, {'pub'})
            self.assertNotIn('Private archive', json.dumps(archive))
            self.assertEqual(call('/api/result/pub')[0], 400)
            self.assertEqual(call('/api/task-state', {'chat_id':self.a, 'state':{}, 'expected_version':0})[0],400)
            self.assertEqual(call('/api/chats', {'title':'private', 'scope':'all'})[0],400)
            self.assertEqual(call('/api/ask', {'chat_id':public,'id':'private','question':'Private question','scope':'public'})[0],400)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_day24_snapshot_unchanged(self):
        here = Path(__file__).parent
        baseline = json.loads((here / 'BASELINE.json').read_text())
        for name, digest in baseline.items():
            path = here.parents[1] / 'day24' / 'app' / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)


if __name__ == '__main__':
    unittest.main()
