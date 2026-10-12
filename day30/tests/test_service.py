"""Офлайн контракты Day30: подставная модель и настоящий локальный HTTP handler."""
import contextlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import service
import protocol
import server

VEC = [1.0] + [0.0] * 1023

def chunk(cid='c1', source='assignment', text='Реализуйте API и чат. Проверьте лимиты и сетевой доступ.', day=30):
    return dict(chunk_id=cid, document_id=cid, source=source, day=day, text=text,
                start_char=0, end_char=len(text), vector=VEC, members=[dict(id='m', author='Автор', date='2026-10-11')],
                source_sections=[dict(start_char=0, text_start_char=0, end_char=len(text), member_ids=['m'])])

def context_body(raw):
    return json.JSONDecoder().raw_decode(raw)[0]

def embedded_schema(raw):
    _,end=json.JSONDecoder().raw_decode(raw)
    rest=raw[end:]
    return json.loads(rest) if rest.strip() else None

class Fake:
    def __init__(self, bad=None): self.calls=[]; self.bad=bad
    def embed(self, question,deadline_seconds=None): self.calls.append(('embedding',question)); return VEC
    def chat(self, messages, schema,options=None,think=False,native_format=True,deadline_seconds=None):
        self.calls.append(('chat',messages,schema))
        body=context_body(messages[-1]['content'])
        if 'sources' in body:
            rule=schema['properties']['a_evidence'];ids=list(rule.get('properties',{})) if 'oneOf' not in rule else [node['required'][0] for node in rule['oneOf'][1:]];qids=[a['id'] for a in body['question_aspects']]
            value={'evidence':{ids[0]:qids},'coverage':{qid:'full' for qid in qids}}
        else:
            eid=next(iter(body['evidence_to_aspect_ids']));unit=next(u for u in body['originals'] if u['evidence_id']==eid)
            groups=body['evidence_to_aspect_ids'][eid]
            value={'points':[{'aspect_ids':groups,'evidence_id':eid,
                'text':'Задание требует API и чат. Нужна проверка лимитов.'}],
                'doubtful_aspect_ids':[],
                'conclusion':{'text':'Вывод: проверьте ограничения перед использованием.','point_refs':['P1']}}
        if self.bad == 'ids' and 'sources' in body:value['evidence']={'invented':qids}
        if self.bad == 'refs' and 'originals' in body:value['points'][0]['evidence_id']='invented'
        if self.bad == 'unknown' and 'sources' in body:value={'evidence':{},'coverage':{qid:'none' for qid in qids}}
        if self.bad == 'timeout': raise TimeoutError('sensitive provider traceback')
        return dict(model=service.MODEL, done=True, done_reason='length' if self.bad=='length' else 'stop',
                    message={'content':'{' if self.bad=='json' else json.dumps(protocol.wire_value('selection' if 'sources' in body else 'synthesis',value), ensure_ascii=False)},
                    prompt_eval_count=300, eval_count=50, total_duration=100000000)

class CoreTests(unittest.TestCase):
    def engine(self,bad=None,chunks=None):
        model=Fake(bad); return service.Engine(chunks or [chunk()], model),model
    def test_two_calls_and_original_metadata(self):
        engine,model=self.engine(); result=engine.answer('Какие условия задания дня 30?',[])
        self.assertEqual([x[0] for x in model.calls],['embedding','chat','chat'])
        self.assertEqual(result['status'],'done'); self.assertEqual(result['answer']['sources'][0]['author'],'Автор')
        self.assertIn(result['answer']['sources'][0]['text'],chunk()['text'])
        self.assertEqual(context_body(model.calls[-1][1][-1]['content'])['originals'][0]['text'],result['answer']['sources'][0]['text'])
        for phase in ('selection','synthesis'):
            b=result['trace']['budgets'][phase]; self.assertLessEqual(b['input_upper_bound']+b['output_reserved'],8192)
    def test_bad_ids_no_synthesis(self):
        engine,model=self.engine('ids')
        with self.assertRaises(ValueError): engine.answer('Какие условия дня 30?',[])
        self.assertEqual(len([c for c in model.calls if c[0]=='chat']),1)
    def test_bad_refs(self):
        engine,_=self.engine('refs')
        with self.assertRaises(ValueError):engine.answer('Какие условия дня 30?',[])
    def test_invalid_json_length_timeout_no_retry(self):
        for bad in ('json','length','timeout'):
            with self.subTest(bad=bad):
                engine,model=self.engine(bad)
                with self.assertRaises((ValueError,TimeoutError)):engine.answer('Какие условия дня 30?',[])
                self.assertLessEqual(len([c for c in model.calls if c[0]=='chat']),1)
    def test_unknown_no_synthesis(self):
        engine,model=self.engine('unknown'); result=engine.answer('Какие условия дня 30?',[])
        self.assertEqual(result['status'],'unknown');self.assertEqual(result['answer']['sources'],[])
        self.assertEqual(len([c for c in model.calls if c[0]=='chat']),1)
    def test_question_limits(self):
        for q in ('',' ',None,'a'*501):
            with self.assertRaises(ValueError):service.validate_question(q)
    def test_demo_before_retrieval_and_prompt(self):
        secret='PRIVATE_SENTINEL'; engine,model=self.engine(chunks=[chunk(),chunk('private','discussion',secret)])
        result=engine.answer('Какие условия дня 30?',[],scope='assignment')
        self.assertNotIn(secret,json.dumps(model.calls,ensure_ascii=False)); self.assertTrue(all(s['source']=='assignment' for s in result['answer']['sources']))
    def test_history_budget_drops_questions_before_whole_sources(self):
        units=[dict(evidence_id='S1.U1',text='x'*2000,author=None,date=None)]
        messages,kept,history,budget=service.fit_prompt('s','q'*500,['h'*3000]*3,units,service.SYNTHESIS_SCHEMA)
        self.assertEqual(len(kept),1); self.assertLess(len(history),3)
        self.assertIn('q'*500,messages[-1]['content']);self.assertLessEqual(budget['input_upper_bound']+budget['output_reserved'],8192)
    def test_current_question_never_truncated(self):
        with self.assertRaises(ValueError):service.fit_prompt('s'*9000,'q'*500,[],[],service.SYNTHESIS_SCHEMA)
    def test_new_topic_does_not_use_prior_assistant_fact(self):
        engine,model=self.engine();engine.answer('Какие условия дня 30?',[{'question':'Старый вопрос','status':'done','query':{'intent':'new_topic'},'answer':{'summary':'PRIVATE_ASSISTANT_SENTINEL'}}])
        self.assertNotIn('PRIVATE_ASSISTANT_SENTINEL',json.dumps(model.calls))
    def test_private_modes_restart_and_scope(self):
        with tempfile.TemporaryDirectory() as d:
            store=service.Store(Path(d)/'state'); cid,rid=store.start('вопрос',None,'all')
            store2=service.Store(Path(d)/'state');self.assertEqual(store2.receipt(rid,'all')['status'],'interrupted')
            with self.assertRaises(ValueError):store2.conversation(cid,'assignment')
            self.assertEqual((Path(d)/'state').stat().st_mode & 0o777,0o700)
            self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in (Path(d)/'state').glob('*.json')))
            cid2,rid2=store2.start('следующий',cid,'all'); store2.finish(rid2,{'status':'done','answer':{'summary':'готово'}})
            self.assertEqual(service.Store(Path(d)/'state').receipt(rid2,'all')['status'],'done')
    def test_lock_release_after_error(self):
        with self.assertRaises(RuntimeError):
            with service.generation_lock():raise RuntimeError()
        with service.generation_lock():pass
    def test_shared_lock_busy(self):
        with service.generation_lock():
            with self.assertRaises(ValueError):
                with service.generation_lock():pass

class StubEngine:
    def answer(self,q,turns,scope='all',phase=None):
        if phase:phase('embedding')
        if q=='slow':time.sleep(.3)
        if q=='failure':raise TimeoutError('SECRET_EXCEPTION')
        return {'status':'done','answer':{'summary':'ответ','conclusion':'вывод','sources':[]},'metrics':{}}

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=server.Application(StubEngine(),service.Store(Path(self.tmp.name)/'state'),'test-secret')
        self.http=server.make_server('127.0.0.1',0,self.app);self.port=self.http.server_address[1]
        self.app.hosts={f'127.0.0.1:{self.port}'};self.app.origins={f'https://127.0.0.1:{self.port}'}
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.http.shutdown();self.http.server_close();self.thread.join();self.app.wait_workers();self.tmp.cleanup()
    def request(self,method='POST',path='/api/chat',body=None,headers=None):
        h={'Authorization':'Bearer test-secret','Content-Type':'application/json'};h.update(headers or {})
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3)
        c.request(method,path,json.dumps({'question':'вопрос'} if body is None else body) if method=='POST' else None,h)
        r=c.getresponse();data=r.read();result=(r.status,dict(r.getheaders()),json.loads(data) if 'json' in r.getheader('Content-Type','') else data.decode());c.close();return result
    def await_done(self,rid,path='/api/requests/'):
        for _ in range(40):
            status,_,value=self.request('GET',path+rid)
            if value.get('status') not in ('running','accepted'):return value
            time.sleep(.025)
        self.fail('request did not finish')
    def test_auth_private_and_static(self):
        self.assertEqual(self.request(headers={'Authorization':''})[0],401)
        self.assertEqual(self.request('GET','/api/state',headers={'Authorization':''})[0],401)
        self.assertEqual(self.request('GET','/',headers={'Authorization':''})[0],200)
    def test_host_origin(self):
        self.assertEqual(self.request(headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request(headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request(headers={'Origin':f'https://127.0.0.1:{self.port}'})[0],202)
    def test_body_question_scope_no_bypass(self):
        for body in ({'question':''},{'question':'a'*501},{'question':'q','scope':'all'},{'question':'q','conversation_id':'../x'},[]):
            with self.subTest(body=body):self.assertEqual(self.request(body=body)[0],400)
        c=http.client.HTTPConnection('127.0.0.1',self.port)
        c.request('POST','/api/chat',b'x'*65537,{'Authorization':'Bearer test-secret','Content-Type':'application/json'})
        self.assertEqual(c.getresponse().status,413);c.close()
    def test_invalid_json_and_content_type(self):
        c=http.client.HTTPConnection('127.0.0.1',self.port)
        c.request('POST','/api/chat','{',{'Authorization':'Bearer test-secret','Content-Type':'application/json'});self.assertEqual(c.getresponse().status,400);c.close()
        self.assertEqual(self.request(headers={'Content-Type':'text/plain'})[0],415)
    def test_async_receipt_history(self):
        code,_,value=self.request();self.assertEqual(code,202);result=self.await_done(value['request_id'])
        self.assertEqual(result['status'],'done');self.assertEqual(result['conversation_id'],value['conversation_id'])
        self.assertEqual(self.request('GET','/api/conversations/'+value['conversation_id'])[0],200)
    def test_busy_no_queue(self):
        code,_,value=self.request(body={'question':'slow'});self.assertEqual(code,202)
        self.assertEqual(self.request()[0],409);self.await_done(value['request_id'])
    def test_rate_six_accepted(self):
        for _ in range(6):
            code,_,value=self.request();self.assertEqual(code,202);self.await_done(value['request_id'])
        code,headers,_=self.request();self.assertEqual(code,429);self.assertGreater(int(headers['Retry-After']),0)
    def test_failure_sanitized_and_unlock(self):
        _,_,v=self.request(body={'question':'failure'});result=self.await_done(v['request_id']);self.assertEqual(result['status'],'error')
        self.assertNotIn('SECRET_EXCEPTION',json.dumps(result));self.assertEqual(self.request()[0],202)
    def test_demo_store_isolation(self):
        _,_,v=self.request(path='/api/demo/chat');result=self.await_done(v['request_id'],'/api/demo/requests/');self.assertEqual(result['scope'],'assignment')
        self.assertEqual(self.request('GET','/api/requests/'+v['request_id'])[0],404)
    def test_headers_safe_dom(self):
        code,headers,html=self.request('GET','/');self.assertEqual(code,200)
        self.assertIn("default-src 'self'",headers['Content-Security-Policy']);self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
        _,_,js=self.request('GET','/app.js');self.assertNotIn('innerHTML',js);self.assertNotIn('localStorage',js)

if __name__=='__main__':unittest.main()
