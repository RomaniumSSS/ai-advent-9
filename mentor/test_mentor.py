"""Синтетические проверки: без SSH, приватных данных и облака."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import urllib.request
from unittest.mock import patch
from answers import check_answer
from common import MODEL, messages, packed, save
from retrieval import Config, retrieve
from service import Service, read
from web import make_server

CHUNK={'chunk_id':'c1','document_id':'assignment:18','source':'assignment','text':'Синтетический текст <script>window.pwned=1</script>. Факт: тест.','vector':[1.0,0.0]}
CHUNK.update(start_char=0,end_char=len(CHUNK['text']),members=[{'id':'synthetic-member','message_id':1,'source_key':'synthetic-source','author':'Тестовый автор','date':'2026-09-28T12:00:00+01:00'}],source_sections=[{'start_char':0,'text_start_char':0,'end_char':len(CHUNK['text']),'member_ids':['synthetic-member'],'source_keys':['synthetic-source']}])
def synthetic(q,scope):
    trace=retrieve([CHUNK],q,[1.0,0.0],Config())
    return {'trace':trace,'identity':{'synthetic':True},'backend':'СИНТЕТИЧЕСКИЙ ТЕСТ'}
def auth(root,budget=.1):
    from common import save
    save(root/'authorization.json',{'approved':True,'model':MODEL,'provider':'deepinfra/fp8','retries':0,'scopes':['public'],'questions':['тест','другой тест'],'document_ids':['assignment:18'],'budget':budget,'pricing':{'prompt':.14/1e6,'completion':.42/1e6}})
def raw(content,cost=.0001):
    return {'model':MODEL,'provider':'DeepInfra','usage':{'cost':cost},'choices':[{'finish_reason':'stop','message':{'content':content}}]}
VALID=json.dumps({'answer':'Тестовый ответ','sources':[{'source':'assignment','chunk_id':'c1'}],'quotes':[{'chunk_id':'c1','text':'Факт: тест.'}]},ensure_ascii=False)
def main():
    calls=[]
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);s=Service(root,synthetic,lambda body,key:(calls.append(body) or raw(VALID)),lambda _: 'synthetic-key',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        assert s.ask('a','тест','public')['status']=='not_authorized' and not calls
        auth(root)
        a=read(root/'authorization.json');a.update(question_policy='arbitrary',identity_sha256=hashlib.sha256(packed({'synthetic':True})).hexdigest());save(root/'authorization.json',a)
        assert s.allowed(a,'свободный новый вопрос','public',[CHUNK],{'synthetic':True})
        assert not s.allowed(a,'свободный новый вопрос','public',[CHUNK],{'synthetic':'changed'})
        assert not s.allowed(a,'свободный новый вопрос','public',[dict(CHUNK,document_id='new_document')],{'synthetic':True})
        assert s.ask('b','тест','public')['status']=='verified'
        assert s.ask('b','тест','public')['status']=='verified' and len(calls)==1
        try:s.ask('b','другой тест','public');raise AssertionError('changed id')
        except ValueError:pass
        s.feedback('b',['неверный вывод'],'синтетика')
        restarted=Service(root,synthetic,lambda *_: (_ for _ in ()).throw(AssertionError('unexpected call')))
        assert restarted.get('b')['feedback']['comment']=='синтетика' and len(calls)==1
        assert s.ask('c','тест','all')['status']=='not_authorized'
        auth(root,budget=.00001)
        assert s.ask('d','тест','public')['error']=='budget_exceeded' and len(calls)==1
        auth(root)
        with patch('service.save',side_effect=OSError('synthetic save failure')):
            try:s.ask('e','тест','public');raise AssertionError('must block')
            except OSError:pass
        assert len(calls)==1
        empty=lambda q,scope:{'trace':{'empty':True,'selected':[]},'identity':{}}
        assert Service(root,empty).ask('f','вне темы','all')['status']=='no_context'
        broken=lambda *_: (_ for _ in ()).throw(RuntimeError('synthetic failure'))
        assert Service(root,broken).ask('g','тест','all')['status']=='error'
        s=Service(root,synthetic,lambda *_:raw('{invalid'),lambda _:'synthetic-key',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        assert s.ask('h','тест','public')['status']=='unverified'
        s=Service(root,synthetic,lambda *_:raw(json.dumps({'answer':'Не знаю: уточни тему','sources':[],'quotes':[]},ensure_ascii=False)),lambda _:'synthetic-key',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        assert s.ask('i','тест','public')['status']=='model_refusal'
        truncated=raw(VALID);truncated['choices'][0]['finish_reason']='length'
        s=Service(root,synthetic,lambda *_:truncated,lambda _:'synthetic-key',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        cut=s.ask('truncated','тест','public');assert cut['status']=='unverified' and cut['cost']==.0001 and cut['validation']['errors']==['incomplete_answer']
        assert read(root/'ledger.json')['entries'][-1]['status']=='completed'
        s=Service(root,synthetic,lambda *_:raw(VALID,None),lambda _:'synthetic-key',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        assert s.ask('j','тест','public')['cost'] is None
        assert s.ask('k','тест','public')['error']=='explicit_recovery_required'
        assert not check_answer(VALID.replace('Факт: тест.','выдумка'),[CHUNK])['valid']
        assert not check_answer(VALID.replace('c1','unknown'),[CHUNK])['valid']
        server=make_server(0,service=s);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url='http://'+server.address
        assert json.load(urllib.request.urlopen(url+'/api/state'))['history']
        for route in ('/private/authorization.json','/../day24/private/prepared.json'):
            try:urllib.request.urlopen(url+route);raise AssertionError('private leak')
            except urllib.error.HTTPError as e:assert e.code==404
        req=urllib.request.Request(url+'/api/ask',data=b'{}',headers={'Content-Type':'application/json'})
        try:urllib.request.urlopen(req);raise AssertionError('csrf')
        except urllib.error.HTTPError as e:assert e.code==403
        server.shutdown();server.server_close()
    print('PASS: synthetic validation, authorization, idempotence, budget, persistence, feedback, failures, HTTP privacy/CSRF; cloud calls=0')
if __name__=='__main__':
    with patch('requests.Session.request',side_effect=AssertionError('offline network forbidden')):
        main()
