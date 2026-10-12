"""Astra regression: synthetic data, mock модели и временный loopback provider."""
import contextlib
import hashlib
import http.server
import io
import json
from pathlib import Path
import select
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evidence,local,server,service
from test_service import Fake,chunk,context_body,embedded_schema

class FocusTests(unittest.TestCase):
    def first(self):
        model=Fake();engine=service.Engine([chunk()],model);answer=engine.answer('Какие условия дня 30?',[])
        answer.update(question='Какие условия дня 30?',request_id='a'*32);return engine,model,answer
    def test_actual_engine_answer_has_focus_in_second_turn(self):
        engine,model,first=self.first();engine.answer('А что именно там нужно проверить?',[first])
        selection=[c for c in model.calls if c[0]=='chat'][2]
        body=context_body(selection[1][-1]['content'])
        self.assertEqual(body['dialogue_focus']['evidence_ids'],['S1.U1'])
    def test_renumbered_span_matches_but_neighbor_and_changed_metadata_do_not(self):
        _,_,first=self.first();source=first['answer']['sources'][0]
        same={**source,'evidence_id':'S4.U7','source_ref':'S4'}
        adjacent={**same,'evidence_id':'S4.U8','start_char':source['end_char'],'end_char':source['end_char']+5,'text':'other','author':'Другой автор'}
        changed={**same,'evidence_id':'S4.U9','date':'другая дата'}
        focus=evidence.dialogue_focus({'intent':'followup'},[first],[same,adjacent,changed])
        self.assertEqual(focus['evidence_ids'],['S4.U7'])
    def test_day30_shape_does_not_fall_back_to_whole_chunk(self):
        _,_,first=self.first();original=first['answer']['sources'][0]
        adjacent={**original,'evidence_id':'S1.U2','text':'Соседняя реплика','start_char':100,'end_char':117,'author':'Другой автор'}
        self.assertEqual(evidence.dialogue_focus({'intent':'followup'},[first],[adjacent])['evidence_ids'],[])
    def test_legacy_fallback_only_legacy_refs(self):
        prior={'status':'done','request_id':'a'*32,'query':{},'answer':{'source_refs':['S1'],'sources':[{'source_ref':'S1','chunk_id':'c'}]}}
        self.assertEqual(evidence.dialogue_focus({'intent':'followup'},[prior],[{'chunk_id':'c','evidence_id':'S8.U1'}])['evidence_ids'],['S8.U1'])

class DiagnosticsTests(unittest.TestCase):
    def test_selection_and_synthesis_failures_keep_raw_phase_and_counts(self):
        for phase,bad in [('selection','ids'),('selection','json'),('synthesis','refs')]:
            with self.subTest(phase=phase,bad=bad):
                model=Fake(bad);engine=service.Engine([chunk()],model)
                try:engine.answer('Какие условия дня 30?',[])
                except Exception as exc:
                    partial=getattr(exc,'partial_result',None)
                    self.assertIsNotNone(partial,'error discarded accumulated trace')
                    self.assertEqual(partial['trace']['last_phase'],phase)
                    self.assertIn(phase+'_raw_response',partial['trace'])
                    self.assertIn(phase+'_prompt',partial['trace']);self.assertIn(phase,partial['trace']['budgets'])
                    self.assertEqual(partial['metrics']['generation_calls'],1 if phase=='selection' else 2)
                    self.assertEqual(partial['status'],'error');self.assertIsNone(partial['answer'])
                else:self.fail('bad response accepted')
    def test_timeout_keeps_attempted_and_completed_counts(self):
        for phase in ('selection','synthesis'):
            class Timeout(Fake):
                def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                    current='selection' if 'sources' in context_body(m[-1]['content']) else 'synthesis'
                    if current==phase:self.calls.append(('chat',m,s));raise TimeoutError('PRIVATE_EXCEPTION_SENTINEL')
                    return super().chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
            model=Timeout()
            with self.subTest(phase=phase):
                try:service.Engine([chunk()],model).answer('Какие условия дня 30?',[])
                except Exception as exc:
                    partial=getattr(exc,'partial_result',None);self.assertIsNotNone(partial)
                    self.assertEqual(partial['trace']['last_phase'],phase)
                    self.assertEqual(partial['metrics']['generation_calls'],1 if phase=='selection' else 2)
                    self.assertEqual(partial['metrics']['generation_completed_calls'],0 if phase=='selection' else 1)
                    self.assertIn(phase,partial['metrics']);self.assertNotIn('PRIVATE_EXCEPTION_SENTINEL',json.dumps(partial))
                else:self.fail('timeout accepted')
    def test_application_persists_private_trace_and_sanitizes_public_and_logs(self):
        with tempfile.TemporaryDirectory() as d:
            app=server.Application(service.Engine([chunk()],Fake('refs')),service.Store(Path(d)/'state'),'fixture-token')
            output=io.StringIO()
            with patch('service.generation_lock',side_effect=contextlib.nullcontext),contextlib.redirect_stdout(output):
                value=app.submit({'question':'Какие условия дня 30?'});app.wait_workers()
            stored=app.store.receipt(value['request_id'],'all');public=service.public_receipt(stored)
            self.assertIn('synthesis_raw_response',stored.get('trace',{}))
            self.assertEqual(stored['trace']['validation_code'],'invalid_point_reference')
            self.assertEqual(public['status'],'error');self.assertEqual(public['metrics']['generation_calls'],2)
            self.assertNotIn('trace',public);self.assertNotIn('invented',json.dumps(public))
            self.assertNotIn('invalid_point_reference',output.getvalue());self.assertNotIn('Автор',output.getvalue())
            self.assertNotIn('fixture-token',output.getvalue());self.assertFalse(app.active)

class ImmediateFixture:
    def __init__(self,body,status=200):
        self.calls=[];owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):self.respond()
            def do_POST(self):self.respond()
            def respond(self):
                raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
                owner.calls.append({'method':self.command,'path':self.path,'body':raw})
                self.send_response(status);self.send_header('Content-Length',str(len(body)))
                if status==302:self.send_header('Location','http://example.invalid/forbidden')
                self.end_headers();self.wfile.write(body)
        self.http=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.http.daemon_threads=True
        self.url=f'http://127.0.0.1:{self.http.server_address[1]}';self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
    def __enter__(self):self.thread.start();return self
    def __exit__(self,*_):self.http.shutdown();self.http.server_close();self.thread.join()

class WireContracts(unittest.TestCase):
    def test_successful_chat_payload_and_close_no_redirect(self):
        response={'model':service.MODEL,'done':True,'done_reason':'stop','message':{'content':'{}'}}
        with ImmediateFixture(json.dumps(response).encode()) as fixture,patch('local.OLLAMA_URL',fixture.url):
            client=local.Ollama(fixture.url)
            result=client.chat([{'role':'user','content':'synthetic question'}],service.SYNTHESIS_SCHEMA)
            self.assertEqual(result,response);self.assertEqual(len(fixture.calls),1)
            sent=json.loads(fixture.calls[0]['body']);self.assertEqual(sent['model'],service.MODEL)
            self.assertFalse(sent['think']);self.assertEqual(sent['options']['num_ctx'],8192)
    def test_redirect_error_body_and_invalid_provider_json_observable_no_retry(self):
        for status,body,code in [(302,b'redirect body','ollama_redirect_forbidden'),(503,b'PRIVATE_ERROR_BODY','ollama_response_error'),(200,b'{broken','Expecting')]:
            with self.subTest(status=status),ImmediateFixture(body,status) as fixture,patch('local.OLLAMA_URL',fixture.url):
                client=local.Ollama(fixture.url)
                try:client.request('/api/tags')
                except ValueError as exc:
                    self.assertIn(code,str(exc));self.assertFalse(hasattr(exc,'response_text'))
                    self.assertEqual(exc.response_metadata['bytecount'],len(body))
                    self.assertEqual(exc.response_metadata['sha256'],hashlib.sha256(body).hexdigest())
                    self.assertTrue(exc.response_complete)
                else:self.fail('invalid provider data accepted')
                self.assertEqual(len(fixture.calls),1);self.assertEqual(len(client.network),1)
    def test_transport_partial_snapshot_is_private_inference_error(self):
        class Hybrid(Fake):
            def chat(self,messages,schema,options=None,think=False,native_format=True,deadline_seconds=None):return wire.chat(messages,schema,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
        with ImmediateFixture(b'{broken') as fixture,patch('local.OLLAMA_URL',fixture.url):
            wire=local.Ollama(fixture.url)
            with self.assertRaises(service.InferenceFailure) as raised:service.Engine([chunk()],Hybrid()).answer('Какие условия дня 30?',[])
            result=raised.exception.partial_result
            self.assertEqual(result['trace']['selection_raw_response']['bytecount'],len(b'{broken'))
            self.assertEqual(result['trace']['selection_raw_response']['sha256'],hashlib.sha256(b'{broken').hexdigest())
            self.assertNotIn('partial_body',result['trace']['selection_raw_response'])
            self.assertTrue(result['trace']['selection_raw_response']['completed'])
            self.assertEqual(result['trace']['validation_code'],'invalid_model_json')
            self.assertEqual(result['metrics']['generation_calls'],1);self.assertEqual(result['metrics']['generation_completed_calls'],0)
            self.assertNotIn('{broken',json.dumps(service.public_receipt(result)))
    def test_synthesis_schema_rejects_bad_status_duplicates_and_extra_fields(self):
        for kind in ('status','duplicates','extra'):
            class Invalid(Fake):
                def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                    response=super().chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
                    if 'originals' in context_body(m[-1]['content']):
                        raw=json.loads(response['message']['content'])
                        if kind=='status':raw['status']='invented'
                        elif kind=='duplicates':raw['c_conclusion']['b_point_refs']*=2
                        else:raw['invented']='extra'
                        response['message']['content']=json.dumps(raw)
                    return response
            with self.subTest(kind=kind),self.assertRaises(service.InferenceFailure) as raised:service.Engine([chunk()],Invalid()).answer('Какие условия дня 30?',[])
            self.assertEqual(raised.exception.partial_result['metrics']['generation_calls'],2)
            self.assertIn('synthesis_raw_response',raised.exception.partial_result['trace'])

class SlowFixture:
    def __init__(self,phase):
        self.phase=phase;self.cancelled=threading.Event();self.calls=0
        owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length','0')))
                self.do_GET()
            def do_GET(self):
                owner.calls+=1
                body=b'{"value":"abcdefghijklm"}'
                header=f'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode()
                try:
                    if owner.phase=='body':self.connection.sendall(header)
                    data=header+body if owner.phase=='headers' else body
                    for byte in data:
                        if select.select([self.connection],[],[],0)[0] and self.connection.recv(1)==b'':owner.cancelled.set();return
                        self.connection.sendall(bytes([byte]));time.sleep(.025)
                except (BrokenPipeError,ConnectionResetError,OSError):owner.cancelled.set()
        self.http=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.http.daemon_threads=True
        self.url=f'http://127.0.0.1:{self.http.server_address[1]}'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
    def __enter__(self):self.thread.start();return self
    def __exit__(self,*_):self.http.shutdown();self.http.server_close();self.thread.join()

class ProviderDeadlineTests(unittest.TestCase):
    def test_partial_headers_and_body_use_absolute_deadline_and_close_socket(self):
        for phase in ('headers','body'):
            with self.subTest(phase=phase),SlowFixture(phase) as fixture:
                with patch('local.OLLAMA_URL',fixture.url),patch('local.TIMEOUT',.12):
                    client=local.Ollama(fixture.url);started=time.monotonic();connections=[]
                    connection_class=local.DeadlineConnection
                    def record(*args,**kwargs):
                        c=connection_class(*args,**kwargs);connections.append(c);return c
                    with patch('local.DeadlineConnection',side_effect=record),self.assertRaises(TimeoutError):client.request('/api/tags')
                    self.assertEqual(connections[0].transport_socket.fileno(),-1)
                    self.assertIsNone(connections[0].sock)
                    self.assertLess(time.monotonic()-started,.3)
                    self.assertTrue(fixture.cancelled.wait(.15),'provider socket remains open after deadline')
                    self.assertEqual(fixture.calls,1);self.assertEqual(len(client.network),1)

if __name__=='__main__':unittest.main()
