"""Profile08: actual wire, single schema accounting and reasoning-free persistence."""
import contextlib
import hashlib
import http.server
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import local,service,server
from test_service import Fake,chunk
from test_review_regressions import ImmediateFixture

REASON='SYNTHETIC_PRIVATE_REASONING_SENTINEL'

def parts(messages):
    text=messages[-1]['content'];body,end=json.JSONDecoder().raw_decode(text)
    rest=text[end:];return body,json.loads(rest) if rest.strip() else None

class ThinkingFake(Fake):
    def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
        response=super().chat(m,s,options=options)
        if think:response['message']['thinking']=REASON
        return response

class PartialFixture:
    def __init__(self,prefix):
        self.cancelled=threading.Event();owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200);self.send_header('Content-Length',str(len(prefix)+4096));self.end_headers()
                self.wfile.write(prefix);self.wfile.flush();self.connection.settimeout(1)
                if self.connection.recv(1)==b'':owner.cancelled.set()
        self.http=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.http.daemon_threads=True
        self.url=f'http://127.0.0.1:{self.http.server_address[1]}'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
    def __enter__(self):self.thread.start();return self
    def __exit__(self,*args):self.http.shutdown();self.http.server_close();self.thread.join()

class Profile08Tests(unittest.TestCase):
    def no_reason(self,value):
        self.assertTrue(REASON not in json.dumps(value,ensure_ascii=False),'reasoning leaked')
    def test_actual_engine_wire_both_native_false_schema_once(self):
        captured=[]
        class Wire(ThinkingFake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(m,s,options,think,native_format,deadline_seconds)
                with ImmediateFixture(local.packed(response)) as fixture,patch('local.OLLAMA_URL',fixture.url):
                    value=local.Ollama(fixture.url).chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
                    captured.append(json.loads(fixture.calls[0]['body']));return value
        result=service.Engine([chunk()],Wire()).answer('Какие условия дня 30?',[])
        for phase,sent in zip(('selection','synthesis'),captured):
            self.assertFalse(sent['think']);self.assertEqual(sent['format'],result['trace'][phase+'_wire_schema']);self.assertFalse(sent['stream'])
            self.assertEqual([m['role'] for m in sent['messages']],['system','user']);self.assertIsNone(parts(sent['messages'])[1])
            self.assertEqual(result['trace']['generation_parameters'][phase]['format_mode'],'native')
        self.assertEqual(captured[1]['options'],{'num_ctx':8192,'num_predict':1024,'temperature':0.7,'top_p':0.8})
        schema=captured[1]['format']
        self.assertEqual(list(schema['properties']),['a_points','b_doubtful_aspect_ids','c_conclusion'])
        self.assertEqual(list(schema['properties']['a_points']['items']['properties']),['aspect_ids','evidence_id','text'])
        self.assertEqual(list(schema['properties']['c_conclusion']['properties']),['a_text','b_point_refs'])
        self.assertEqual(result['metrics']['generation_calls'],2);self.no_reason(result)
    def test_budget_counts_actual_native_schema_once_and_keeps_reserves(self):
        result=service.Engine([chunk()],ThinkingFake()).answer('Какие условия дня 30?',[]);trace=result['trace']
        for phase in ('selection','synthesis'):
            b=trace['budgets'][phase];options=trace['generation_parameters'][phase]['options']
            expected=service.budget_for(trace[phase+'_prompt'],trace[phase+'_wire_schema'],options=options,deadline_seconds=trace['generation_parameters'][phase]['deadline_seconds'])
            self.assertEqual(b,expected);self.assertEqual(b['template_reserve'],512);self.assertEqual(b['output_reserved'],options['num_predict'])
            self.assertLessEqual(b['input_upper_bound']+options['num_predict'],8192);self.assertGreater(b['schema_tokens'],0)
            self.assertIsNone(parts(trace[phase+'_prompt'])[1])
    def test_think_true_accepts_final_but_false_phase_still_rejects_without_leaking(self):
        valid={'model':local.MODEL,'done':True,'done_reason':'stop','prompt_eval_count':1,
               'message':{'thinking':REASON,'content':'{}'}}
        self.assertEqual(service.parse_response(valid,think=True),{})
        with self.assertRaisesRegex(ValueError,'unexpected_model_thinking'):service.parse_response(valid,think=False)
        class Wrong(ThinkingFake):
            def chat(self,*args,**kwargs):
                response=super().chat(*args,**kwargs);response['message']['thinking']=REASON;return response
        with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],Wrong()).answer('Какие условия дня 30?',[])
        self.assertEqual(caught.exception.partial_result['trace']['validation_code'],'unexpected_model_thinking')
        self.no_reason(caught.exception.partial_result)
    def test_success_and_schema_error_private_files_logs_and_api_never_contain_reasoning(self):
        for bad in (None,'refs'):
            with tempfile.TemporaryDirectory() as d:
                app=server.Application(service.Engine([chunk()],ThinkingFake(bad)),service.Store(Path(d)/'state'),'test-token')
                log=io.StringIO()
                with patch('service.generation_lock',side_effect=contextlib.nullcontext),contextlib.redirect_stdout(log):
                    accepted=app.submit({'question':'Какие условия дня 30?'});app.wait_workers()
                receipt=app.store.receipt(accepted['request_id'],'all');self.no_reason(receipt)
                self.no_reason(service.public_receipt(receipt));self.assertTrue(REASON not in log.getvalue(),'reasoning logged')
                for p in Path(d).rglob('*.json'):self.assertTrue(REASON not in p.read_text(),'reasoning persisted')
                raw=receipt['trace']['synthesis_raw_response'];self.assertNotIn('thinking',raw['message'])
                self.assertTrue(raw['message']['content']);self.assertEqual(raw['eval_count'],50)
                self.assertEqual(receipt['status'],'error' if bad else 'done')
    def test_bad_final_empty_length_duplicate_and_think_tags_remain_fail_no_retry(self):
        cases=[('', 'invalid_model_json'),('{broken','invalid_model_json'),
               ('{"points":[],"points":[]}','duplicate_json_key'),
               ('<think>'+REASON+'</think>{}','invalid_model_json')]
        for content,code in cases:
            class Bad(ThinkingFake):
                def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                    response=super().chat(m,s,options,think,native_format,deadline_seconds)
                    if 'originals' in parts(m)[0]:response['message']['content']=content
                    return response
            model=Bad()
            with self.subTest(code=code),self.assertRaises(service.InferenceFailure) as caught:
                service.Engine([chunk()],model).answer('Какие условия дня 30?',[])
            result=caught.exception.partial_result;self.assertEqual(result['trace']['validation_code'],code)
            self.assertEqual(result['metrics']['generation_calls'],2);self.no_reason(result)
            self.assertNotIn('content',result['trace']['synthesis_raw_response']['message'])
        class Length(ThinkingFake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(m,s,options,think,native_format,deadline_seconds)
                if 'originals' in parts(m)[0]:response['done_reason']='length'
                return response
        with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],Length()).answer('Какие условия дня 30?',[])
        self.assertEqual(caught.exception.partial_result['trace']['validation_code'],'incomplete_model_response')
        self.assertEqual(caught.exception.partial_result['metrics']['generation_calls'],2);self.no_reason(caught.exception.partial_result)
    def test_malformed_outer_transport_only_hash_count_stage_no_prefix(self):
        body=b'{"message":{"thinking":"'+REASON.encode()
        class Wire(Fake):
            def chat(self,*args,**kwargs):return provider.chat(*args,**kwargs)
        with ImmediateFixture(body) as fixture,patch('local.OLLAMA_URL',fixture.url):
            provider=local.Ollama(fixture.url)
            with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],Wire()).answer('Какие условия дня 30?',[])
            raw=caught.exception.partial_result['trace']['selection_raw_response'];self.no_reason(raw)
            self.assertEqual(raw['bytecount'],len(body));self.assertEqual(raw['sha256'],hashlib.sha256(body).hexdigest())
            self.assertEqual(raw['transport_stage'],'body');self.assertNotIn('partial_body',raw)
    def test_partial_timeout_hash_count_synchronous_cancellation_no_reasoning(self):
        prefix=b'{"message":{"thinking":"'+REASON.encode()+b'"'
        with PartialFixture(prefix) as fixture,patch('local.OLLAMA_URL',fixture.url),patch('local.TIMEOUT',.1):
            client=local.Ollama(fixture.url)
            with self.assertRaises(local.ProviderTimeout) as caught:client.request('/api/chat',{'model':local.MODEL})
            error=caught.exception;self.assertFalse(hasattr(error,'response_text'))
            self.assertEqual(error.response_metadata['bytecount'],len(prefix))
            self.assertEqual(error.response_metadata['sha256'],hashlib.sha256(prefix).hexdigest());self.no_reason(error.response_metadata)
            self.assertTrue(fixture.cancelled.wait(.2),'provider socket not cancelled')
    def test_response_data_and_legacy_text_error_paths_sanitize_before_snapshot(self):
        class Error(Fake):
            def chat(self,*args,**kwargs):
                exc=ValueError('ollama_response_error');exc.transport_stage='body'
                exc.response_text='{broken '+REASON
                exc.response_data={'message':{'thinking':REASON,'content':'{"a_evidence":{"S1.U1":["Q1"]},"b_coverage":{"Q1":"full"}}'},'eval_count':4}
                raise exc
        with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],Error()).answer('Какие условия дня 30?',[])
        result=caught.exception.partial_result;self.no_reason(result)
        raw=result['trace']['selection_raw_response'];self.assertNotIn('thinking',raw['message'])
        self.assertEqual(raw['message']['content'],'{"a_evidence":{"S1.U1":["Q1"]},"b_coverage":{"Q1":"full"}}')
        self.assertEqual(raw['transport_metadata']['bytecount'],len(('{broken '+REASON).encode()))
    def test_actual_parsed_provider_error_sanitizes_response_data_and_hashes_body(self):
        response={'error':'fixture error','message':{'thinking':REASON,'content':'{"a_evidence":{"S1.U1":["Q1"]},"b_coverage":{"Q1":"full"}}'},'eval_count':4}
        body=local.packed(response)
        class Wire(Fake):
            def chat(self,*args,**kwargs):return provider.chat(*args,**kwargs)
        with ImmediateFixture(body) as fixture,patch('local.OLLAMA_URL',fixture.url):
            provider=local.Ollama(fixture.url)
            with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],Wire()).answer('Какие условия дня 30?',[])
            result=caught.exception.partial_result;self.no_reason(result)
            raw=result['trace']['selection_raw_response'];self.assertEqual(raw['message']['content'],'{"a_evidence":{"S1.U1":["Q1"]},"b_coverage":{"Q1":"full"}}')
            self.assertNotIn('thinking',raw['message']);self.assertNotIn('error',raw)
            self.assertEqual(raw['transport_metadata']['sha256'],hashlib.sha256(body).hexdigest())
            self.assertEqual(result['trace']['validation_code'],'ollama_response_error')
    def test_parseable_bad_final_with_reasoning_field_is_opaque_in_snapshot(self):
        class Labelled(ThinkingFake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(m,s,options,think,native_format,deadline_seconds)
                if 'originals' in parts(m)[0]:response['message']['content']=json.dumps({'points':[],'thinking':REASON,
                    'doubtful_aspect_ids':[],'conclusion':{'text':service.UNKNOWN_CONCLUSION,'point_refs':[]}})
                return response
        with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],Labelled()).answer('Какие условия дня 30?',[])
        result=caught.exception.partial_result
        self.assertEqual(result['trace']['validation_code'],'invalid_wire_shape');self.no_reason(result)
        self.assertNotIn('content',result['trace']['synthesis_raw_response']['message'])

if __name__=='__main__':unittest.main()
