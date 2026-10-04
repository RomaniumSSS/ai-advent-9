"""T4: API paths used by real frontend and negative HTTP boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from common import save
from preview_fixture import fixture
from web import make_server
from service import Service


class WebChatTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.directory=Path(self.tmp.name)
        self.service,self.metrics=fixture(self.directory)
        self.server=make_server(0,service=self.service)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def call(self,path,data=None,headers=None):
        fields={'Host':self.server.address,'Origin':'http://'+self.server.address,
                'X-Mentor-Token':self.server.token,'Content-Type':'application/json'}
        if headers:fields.update(headers)
        request=Request('http://'+self.server.address+path,
                        data=json.dumps(data).encode() if data is not None else None,headers=fields)
        try:
            with urlopen(request) as response:
                body=response.read().decode();return response.status, json.loads(body) if response.headers.get_content_type()=='application/json' else body
        except HTTPError as error:
            with error:return error.code,json.load(error)

    def test_frontend_paths_create_memory_ask_archive_feedback_restart(self):
        _,a=self.call('/api/chats',{'title':'A','scope':'all'})
        _,b=self.call('/api/chats',{'title':'B','scope':'all'})
        chat=a['chat_id']
        state={'goal':'RAG','clarifications':['Python'],'constraints':['Кратко']}
        code,changed=self.call('/api/task-state',{'chat_id':chat,'state':state,'expected_version':0})
        self.assertEqual(code,200);self.assertEqual(changed['task_state']['version'],1)
        self.assertEqual(self.call('/api/task-state',{'chat_id':chat,'state':state,'expected_version':0})[0],400)
        code,item=self.call('/api/ask',{'chat_id':chat,'id':'r1','question':'Объясни RAG','scope':'all'})
        self.assertEqual(code,200);self.assertEqual(item['status'],'verified')
        self.assertEqual(item['task_state_version'],1)
        before=self.metrics()
        code,archive=self.call('/api/chat/'+chat)
        self.assertEqual(code,200);self.assertEqual(len(archive['history']),1)
        self.assertEqual(len(archive['messages']),2)
        self.assertEqual(self.call('/api/chat/'+b['chat_id'])[1]['history'],[])
        self.call('/api/result/r1?chat_id='+chat)
        self.assertEqual(self.metrics(),before)
        self.assertEqual(self.call('/api/feedback',{'chat_id':chat,'id':'r1','marks':['неполный ответ'],'comment':'UI test'})[0],200)
        self.assertEqual(self.call('/api/task-state/clear',{'chat_id':chat,'expected_version':1})[1]['task_state']['version'],2)
        self.server.service=Service(self.directory,generate_fn=lambda *_:self.fail('restart generated'))
        archive=self.call('/api/chat/'+chat)[1]
        self.assertEqual(archive['chat']['task_state']['goal'],'')
        self.assertEqual(archive['history'][0]['feedback']['comment'],'UI test')
        self.assertEqual(archive['history'][0]['task_state']['goal'],'RAG')

    def test_http_auth_static_and_missing_chat_id(self):
        code,state=self.call('/api/state')
        self.assertEqual(code,200)
        self.assertEqual(state['cloud']['identity_sha256'],json.loads((self.directory/'authorization.json').read_text())['identity_sha256'])
        self.assertNotIn('authorization_id',state['cloud'])
        code,html=self.call('/')
        self.assertEqual(code,200)
        for ident in ('chats','messages','memory','goal','constraints','clarifications'):self.assertIn('id="'+ident+'"',html)
        self.assertNotIn('Каждый вопрос самостоятельный',html)
        for headers in ({'X-Mentor-Token':'wrong'},{'Origin':'http://evil.invalid'},{'Host':'evil.invalid'}):
            self.assertEqual(self.call('/api/chats',{'title':'x','scope':'all'},headers)[0],403)
        self.assertEqual(self.call('/api/ask',{'id':'x','question':'x','scope':'all'})[0],400)
        for path in ('/private/authorization.json','/../private/ledger.json','/test_web_chat.py'):
            self.assertEqual(self.call(path)[0],404)

    def test_typed_http_uses_snapshot_metadata_and_private_transmission_is_hidden(self):
        from preview_fixture import IDENTITY
        chunk={'chunk_id':'http-typed','document_id':'assignment:18','source':'assignment','day':18,
               'text':'Факт о планировщике.','message_parts':[{'message_id':1,'attribution':'single_member',
               'text':'Факт о планировщике.','member_id':'synthetic','source_key':'assignment:18','author':'<script>unsafe</script>','date':'2026-09-25'}]}
        calls=[]
        self.service.search_fn=lambda *_:{'identity':IDENTITY,'trace':{'selected':[copy.deepcopy(chunk)],'candidates':[copy.deepcopy(chunk)],'removed':[],'empty':False}}
        response={'answer':'<img src=x onerror=window.pwned=1>','sources':[{'source':'assignment','chunk_id':'http-typed'}],
                  'quotes':[{'chunk_id':'http-typed','text':chunk['text']}],
                  'attributions':[{'chunk_id':'http-typed','message_id':1,'day':18}]}
        def generate(*_):
            calls.append(1)
            return {'model':__import__('common').MODEL,'provider':'DeepInfra','usage':{'cost':.00001},
                    'choices':[{'finish_reason':'stop','message':{'content':json.dumps(response)}}]}
        self.service.generate_fn=generate
        _,chat=self.call('/api/chats',{'title':'Typed HTTP','scope':'public'})
        code,item=self.call('/api/ask',{'chat_id':chat['chat_id'],'id':'typed-http','question':'Что возвращает инструмент?','scope':'public'})
        self.assertEqual(code,200);self.assertEqual(item['status'],'verified')
        meta=item['structured_evidence']['attributions'][0];self.assertEqual((meta['day'],meta['message_id']),(18,1))
        tampered=copy.deepcopy(item);tampered['structured_evidence']['attributions'][0]['message_id']=999
        save(self.service.path('typed-http'),tampered)
        self.server.public_only=True
        result=self.call('/api/result/typed-http?chat_id='+chat['chat_id'])[1]
        self.assertEqual(result['structured_evidence']['attributions'][0]['message_id'],1)
        self.assertEqual(len(calls),1)
        contaminated=copy.deepcopy(item);contaminated['id']='private-transmission'
        contaminated['generation']['transmitted_chunks'][0]['document_id']='private:note'
        save(self.service.path('private-transmission'),contaminated)
        self.assertEqual(self.call('/api/result/private-transmission?chat_id='+chat['chat_id'])[0],404)
        archive=self.call('/api/chat/'+chat['chat_id'])[1]
        self.assertEqual([x['id'] for x in archive['history']],['typed-http'])

    def test_public_only_archive_sources_and_trace_do_not_leak(self):
        private=self.service.create_chat('PRIVATE_TITLE','all')['chat_id']
        self.service.update_task_state(private,{'goal':'PRIVATE_GOAL','clarifications':[],'constraints':[]},0)
        public=self.service.create_chat('Public','public')['chat_id']
        item=self.service.ask(public,'public','Объясни RAG','public')
        contaminated=copy.deepcopy(item)
        contaminated.update(id='contaminated',question='PRIVATE_QUESTION')
        contaminated['answer']['answer']='PRIVATE_ANSWER'
        contaminated['search']['trace']['candidates'].append({'document_id':'private:note','text':'PRIVATE_TRACE'})
        save(self.service.path('contaminated'),contaminated)
        self.server.public_only=True
        code,html=self.call('/')
        self.assertEqual(code,200)
        self.assertNotIn('<option value="all">',html)
        self.assertIn('Публичный корпус',html)
        for path in ('/api/state','/api/chats','/api/chat/'+public,'/api/result/public?chat_id='+public):
            code,data=self.call(path);self.assertEqual(code,200)
            self.assertNotIn('PRIVATE_',json.dumps(data))
        self.assertEqual(self.call('/api/chat/'+private)[0],404)
        self.assertEqual(self.call('/api/result/contaminated?chat_id='+public)[0],404)
        for path,data in (('/api/task-state',{'chat_id':private,'state':{},'expected_version':1}),
                          ('/api/feedback',{'chat_id':public,'id':'contaminated','marks':[],'comment':'x'}),
                          ('/api/ask',{'chat_id':public,'id':'contaminated','question':'PRIVATE_QUESTION','scope':'public'})):
            self.assertEqual(self.call(path,data)[0],400)
        self.assertEqual(self.call('/api/chats',{'scope':'all'})[0],400)


if __name__=='__main__':unittest.main()
