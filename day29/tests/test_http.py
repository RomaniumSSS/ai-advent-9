import json,sys,threading,urllib.error,urllib.request,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
class Engine:
    identity={'generation':'fixture','db_sha256':'fixture'}
    def ask(self,question,profile_id,run_id,request_id):
        return {'run_id':run_id,'request_id':request_id,'question':question,'profile_id':profile_id,'scope':'public','status':'unknown','selected':[],'answer':{'answer':'Не знаю','sources':[],'quotes':[]},'times':{'total':1}}
class HTTP(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp=tempfile.TemporaryDirectory();self.application=app.Application(Engine(),self.tmp.name,8069)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),app.handler_for(self.application));self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()
    def call(self,path,data=None,host='127.0.0.1:8069',origin=None):
        headers={'Host':host,'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req) as r:return r.status,json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:return e.code,json.loads(e.read())
    def test_host_origin_and_routes(self):
        self.assertEqual(self.call('/api/state',host='evil.example')[0],403)
        self.assertEqual(self.call('/api/state',origin='http://evil.example')[0],403)
        self.assertEqual(self.call('/private/runs')[0],404)
        self.assertEqual(self.call('/api/state')[0],200)
    def test_question_profile_and_request_id(self):
        a=self.call('/api/ask',{'question':'q','profile_id':'baseline'});self.assertEqual(a[0],202)
        for _ in range(100):
            import time
            job=self.call('/api/requests/'+a[1]['request_id'])[1]
            if job['status']!='running':break
            time.sleep(.01)
        self.assertEqual(job['question'],'q');self.assertEqual(job['profile_id'],'baseline')
        b=self.call('/api/ask',{'question':'q','profile_id':'prompt'});self.assertEqual(b[0],202);self.assertNotEqual(a[1]['request_id'],b[1]['request_id'])
        self.assertEqual(self.call('/api/ask',{'question':'q','profile_id':'evil'})[0],400)
        self.assertEqual(self.call('/api/ask',{'question':'q','profile_id':'baseline','index_root':'/private'})[0],400)
if __name__=='__main__':unittest.main()
