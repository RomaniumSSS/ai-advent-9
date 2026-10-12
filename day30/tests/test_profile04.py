"""Profile04: только identity/payload и существующий qwen35 byte-bound fallback, без Ollama."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import local,service
from tokenizer import Qwen2Tokenizer
from test_service import Fake,chunk,context_body,embedded_schema
from test_review_regressions import ImmediateFixture

MODEL='qwen3:8b-q8_0'
DIGEST='e56358ca25dd14db6853a9f68a92d717aaa6f0a94250a72d1a0f3d86a9f30130'
OLD_DIGEST='500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41'
INFO={'tokenizer.ggml.model':'gpt2','tokenizer.ggml.pre':'qwen35','qwen35.context_length':262144}

class Profile04Tests(unittest.TestCase):
    def test_pinned_generator_identity(self):
        self.assertEqual(local.MODEL,MODEL);self.assertEqual(service.MODEL,MODEL)
        self.assertEqual(local.GEN_DIGEST,DIGEST);self.assertEqual(service.GEN_DIGEST,DIGEST)
    def test_wire_model_identity_and_options_without_package_default_overrides(self):
        response={'model':MODEL,'done':True,'done_reason':'stop','message':{'content':'{}'},'prompt_eval_count':1}
        with ImmediateFixture(json.dumps(response).encode()) as fixture,patch('local.OLLAMA_URL',fixture.url):
            client=local.Ollama(fixture.url);received=client.chat([{'role':'user','content':'synthetic question'}],service.SYNTHESIS_SCHEMA)
            self.assertEqual(service.parse_response(received),{});self.assertEqual(len(fixture.calls),1)
            sent=json.loads(fixture.calls[0]['body']);self.assertEqual(sent['model'],MODEL);self.assertFalse(sent['think'])
            self.assertEqual(sent['options'],{'num_ctx':8192,'num_predict':1024,'temperature':0})
            self.assertTrue({'presence_penalty','top_p','top_k'}.isdisjoint(sent['options']))
    def test_old_model_response_rejected_before_second_call_without_retry(self):
        class Wrong(Fake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds);response['model']='qwen3:8b';return response
        client=Wrong()
        with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],client).answer('Какие условия дня 30?',[])
        self.assertEqual(caught.exception.partial_result['trace']['validation_code'],'incomplete_model_response')
        self.assertEqual(caught.exception.partial_result['metrics']['generation_calls'],1)
        self.assertEqual(len([c for c in client.calls if c[0]=='chat']),1)
    def test_verify_accepts_frozen_9b_and_rejects_old_digest(self):
        for digest,valid in ((DIGEST,True),(OLD_DIGEST,False)):
            calls=[];client=local.Ollama()
            def request(path,payload=None):
                calls.append((path,payload))
                if path=='/api/tags':return {'models':[{'name':MODEL,'digest':digest},{'name':local.EMBED_MODEL,'digest':local.EMBED_DIGEST}]}
                return {'model_info':INFO if payload['model']==MODEL else {'qwen3.context_length':2048}}
            client.request=request
            if valid:
                verified=client.verify();self.assertEqual(verified['generator_digest'],DIGEST)
                self.assertEqual(verified['embedding_digest'],local.EMBED_DIGEST)
            else:
                with self.assertRaisesRegex(ValueError,'model_digest_mismatch'):client.verify()
            self.assertFalse(any(path in ('/api/embed','/api/chat') for path,_ in calls))
    def test_qwen35_is_unsupported_and_real_factory_keeps_byte_bound_before_both_calls(self):
        with self.assertRaisesRegex(ValueError,'unsupported_local_tokenizer'):Qwen2Tokenizer(INFO)
        class Client(Fake):
            def verify(self):return {'generator_show':{'model_info':INFO}}
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                budget=service.budget_for(m,s if native_format else None,options=options,deadline_seconds=deadline_seconds)
                self.checked.append(budget);self.assert_budget(budget)
                return super().chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
            def assert_budget(self,b):
                if b['input_upper_bound']+b['output_reserved']>b['num_ctx']:raise AssertionError('provider called before budget check')
        client=Client();client.checked=[]
        with patch('service.load_full_index',return_value=({},[chunk()])),patch('service.Ollama',return_value=client):engine=service.Engine.real('fixture-readonly-index')
        self.assertIsNone(engine.tokenizer);result=engine.answer('Какие условия дня 30?',[])
        self.assertEqual(result['metrics']['generation_calls'],2);self.assertEqual(len(client.checked),2)
        for phase in ('selection','synthesis'):
            b=result['trace']['budgets'][phase];self.assertEqual(b['method'],'conservative_utf8_byte_bound_with_reserves')
            self.assertEqual(b['template_reserve'],512);self.assertEqual(b['num_ctx'],8192);self.assertEqual(b['output_reserved'],1024 if phase=='selection' else 1024)
    def test_observed_context_overflow_rejected_without_retry(self):
        class Overflow(Fake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds);response['prompt_eval_count']=8000;return response
        client=Overflow()
        with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],client).answer('Какие условия дня 30?',[])
        self.assertEqual(caught.exception.partial_result['trace']['validation_code'],'observed_context_overflow_or_missing_count')
        self.assertEqual(caught.exception.partial_result['metrics']['generation_calls'],1)
        self.assertEqual(len([c for c in client.calls if c[0]=='chat']),1)

if __name__=='__main__':unittest.main()
