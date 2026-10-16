"""HTTP API: общий handler, локальная граница, секреты и произвольные пути."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from day31.web import make_server
from day31.assistant import Assistant
from day31.retrieval import RetrievalIndex
from day31.tests.test_assistant import FakeMcp, FakeProvider


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name); (root/'README.md').write_text('# MCP\n\nДокументация запуска MCP.\n')
        app=Assistant(RetrievalIndex(root,root/'index.db'),FakeMcp(),FakeProvider())
        app.mcp.repo=root
        self.app=app
        self.server=make_server(app,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.addCleanup(self.stop)
        self.port=self.server.server_address[1]
        _,config=self.request('GET','/api/config')
        self.token=config['token']

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)

    def request(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_address[1],timeout=3)
        conn.request(method,path,body,headers or {})
        response=conn.getresponse(); raw=response.read(); status=response.status; conn.close()
        try: value=json.loads(raw)
        except ValueError: value=raw.decode()
        return status,value

    def post(self,question,extra=None):
        headers={'Content-Type':'application/json','X-DevHelper-Token':self.token}
        headers.update(extra or {})
        return self.request('POST','/api/answer',json.dumps({'question':question}),headers)

    def test_same_handler_trace_and_no_key(self):
        status,value=self.post('/help MCP')
        self.assertEqual(status,200); self.assertEqual(value['status'],'ok')
        direct=self.app.answer('/help MCP').to_dict()
        self.assertEqual(value['text'],direct['text']); self.assertEqual(value['source_ids'],direct['source_ids'])
        self.assertNotEqual(value['trace_id'],direct['trace_id'])
        self.assertNotIn('api_key',json.dumps(value).lower())

    def test_bad_request_boundary(self):
        self.assertEqual(self.post('MCP',{'Origin':'https://attacker.invalid'})[0],403)
        self.assertEqual(self.post('MCP',{'Host':'attacker.invalid'})[0],403)
        self.assertEqual(self.post('MCP',{'X-DevHelper-Token':'bad'})[0],403)
        self.assertEqual(self.post('MCP',{'Content-Type':'text/plain'})[0],415)
        status,_=self.request('POST','/api/answer','{',{'Content-Type':'application/json','X-DevHelper-Token':self.token})
        self.assertEqual(status,400)
        for path in ('/.env','/api/source?path=../../.env','/docs/../../.env','/api/history'):
            self.assertEqual(self.request('GET',path)[0],404)

    def test_static_content_security(self):
        status,html=self.request('GET','/')
        self.assertEqual(status,200); self.assertIn('DevHelper',html)
        status,js=self.request('GET','/app.js')
        self.assertEqual(status,200); self.assertNotIn('innerHTML',js)
        self.assertNotIn('OPENROUTER_API_KEY',html+js)


if __name__=='__main__': unittest.main()
