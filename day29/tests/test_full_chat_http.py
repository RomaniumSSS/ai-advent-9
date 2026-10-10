import json,sys,tempfile,threading,time,urllib.error,urllib.request,unittest
from unittest.mock import patch
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_chat as web,full_chat_core as chat
class Engine:
    identity={'scope':'all','chunk_count':3,'document_count':3,'source_counts':{'assignment':1,'discussion':1,'personal_note':1},'generation':'synthetic','db_sha256':'synthetic'}
    def __init__(self,hold=False):self.entered=threading.Event();self.release=threading.Event();self.hold=hold
    def ask(self,q,history,cid,request_id,run_id):
        self.entered.set()
        if self.hold:self.release.wait(2)
        return {'conversation_id':cid,'request_id':request_id,'run_id':run_id,'scope':'all','question':q,'status':'unknown','answer':{'answer':'Не знаю по переданному контексту','source_refs':[],'sources':[]},'query':{'intent':'new_topic','search_query':q},'citations_valid':True,'semantic_support':'NOT_CHECKED','times':{'total':.01}}
class HTTP(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=chat.ConversationStore(Path(self.tmp.name)/'chat');self.engine=Engine();self.app=web.Application(self.engine,self.store)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),web.handler_for(self.app));threading.Thread(target=self.server.serve_forever,daemon=True).start()
    def tearDown(self):
        self.engine.release.set()
        for _ in range(100):
            if self.app.active is None:break
            time.sleep(.01)
        self.server.shutdown();self.server.server_close();self.tmp.cleanup()
    def call(self,path,data=None,host='127.0.0.1:8070',origin=None):
        headers={'Host':host,'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req) as r:return r.status,json.loads(r.read())
        except urllib.error.HTTPError as error:
            with error:return error.code,json.loads(error.read())
    def test_host_and_origin_are_rejected(self):
        self.assertEqual(self.call('/api/state',host='evil.example')[0],403);self.assertEqual(self.call('/api/state',origin='http://evil.example')[0],403)
    def test_api_new_ask_poll_reset_and_no_raw_routes(self):
        status,c=self.call('/api/conversations',{});self.assertEqual(status,201);cid=c['conversation_id']
        status,turn=self.call('/api/ask',{'conversation_id':cid,'question':'synthetic question'});self.assertEqual(status,202);rid=turn['request_id']
        for _ in range(100):
            status,job=self.call('/api/requests/'+rid)
            if job['status']!='running':break
            time.sleep(.01)
        self.assertEqual(job['status'],'unknown');self.assertEqual(job['conversation_id'],cid);self.assertEqual(self.call('/api/conversations/'+cid)[1]['turns'][0]['request_id'],rid)
        self.assertEqual(self.call('/api/ask',{'conversation_id':cid,'question':'q','scope':'all'})[0],400);self.assertEqual(self.call('/api/ask',{'conversation_id':'../outside','question':'q'})[0],400)
        self.assertEqual(self.call('/private/full-chat')[0],404);self.assertEqual(self.call('/api/conversations/'+cid+'/../receipts')[0],404)
        self.assertEqual(self.call('/api/reset',{'conversation_id':cid})[1]['turns'],[]);self.assertEqual(self.call('/api/requests/'+rid)[0],404)
    def test_storage_error_is_visible_without_ghost(self):
        cid=self.store.create()['conversation_id']
        with patch('core.save_private',side_effect=OSError('synthetic storage failure')):
            self.assertEqual(self.call('/api/ask',{'conversation_id':cid,'question':'q'})[0],503)
        self.assertEqual(self.store.get(cid)['turns'],[]);self.assertIsNone(self.app.active)
    def test_reset_while_pending_does_not_attach_late_answer(self):
        self.engine.hold=True;cid=self.store.create()['conversation_id'];turn=self.app.submit(cid,'synthetic question');self.assertTrue(self.engine.entered.wait(1))
        self.assertEqual(self.call('/api/reset',{'conversation_id':cid})[0],200);new=self.call('/api/conversations',{})[1]
        self.engine.release.set()
        for _ in range(100):
            if self.app.active is None:break
            time.sleep(.01)
        self.assertEqual(self.store.get(cid)['turns'],[]);self.assertEqual(self.store.get(new['conversation_id'])['turns'],[]);self.assertEqual(self.call('/api/requests/'+turn['request_id'])[0],404)
    def test_second_request_is_busy(self):
        self.engine.hold=True;cid=self.store.create()['conversation_id'];self.app.submit(cid,'synthetic question');self.assertTrue(self.engine.entered.wait(1))
        with self.assertRaisesRegex(ValueError,'busy'):self.app.submit(cid,'second question')
if __name__=='__main__':unittest.main()
