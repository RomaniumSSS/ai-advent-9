"""Офлайн HTTP: явное поднятие изолированного fixture, никакой Ollama."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from contextlib import nullcontext
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Application, handler_for, public_result
from core import Engine
import core
from test_core import Fake, chunk

class HttpContract(unittest.TestCase):
    def setUp(self):
        self.lock_patch=patch.object(core,'generation_lock',return_value=nullcontext())
        self.lock_patch.start();self.addCleanup(self.lock_patch.stop)
        self.temp=tempfile.TemporaryDirectory()
        self.app=Application(Engine([chunk(),chunk('private','discussion')],{},Fake()),self.temp.name)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.app));self.app.port=self.server.server_port
        self.url='http://127.0.0.1:'+str(self.app.port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,data=None,headers=None):
        req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,
            headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with self.client.open(req) as r:return json.loads(r.read())
        except urllib.error.HTTPError as error:
            error.close();raise
    def test_real_terminal_id_and_no_private(self):
        job=self.request('/api/ask',{'question':'Что требуется в задании дня 18?'})
        for _ in range(100):
            r=self.request('/api/requests/'+job['request_id'])
            if r['status']!='running':break
            time.sleep(.01)
        self.assertEqual(r['status'],'done');self.assertEqual(r['request_id'],job['request_id'])
        self.assertNotIn('discussion',json.dumps(r));self.assertNotIn('messages',r);self.assertNotIn('raw_response',r)
        self.assertTrue(list(Path(self.temp.name).rglob('*.json')))
    def test_private_routes_and_scope_rejected(self):
        for path in ('/private/index-release-v1/current.json','/../core.py','/api/requests/missing'):
            with self.assertRaises(urllib.error.HTTPError):self.request(path)
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/ask',{'question':'x','scope':'all'})
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/ask',{'question':'x'}, {'Origin':'https://external'})
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/state',headers={'Host':'external'})
    def test_projection_rejects_private_context(self):
        with self.assertRaises(ValueError):public_result({'scope':'public','selected':[chunk(source='discussion')]})

if __name__=='__main__':unittest.main()
