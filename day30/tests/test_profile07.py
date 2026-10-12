"""Profile07: actual stage options on loopback wire, budget and private diagnostics."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import local,service
from test_service import Fake,chunk,context_body,embedded_schema
from test_review_regressions import ImmediateFixture

SELECT={'num_ctx':8192,'num_predict':1024,'temperature':0}
SYNTH={'num_ctx':8192,'num_predict':1024,'temperature':0.7,'top_p':0.8}

class Profile07Tests(unittest.TestCase):
    def test_engine_actual_wire_stage_options_and_trace_budget_match(self):
        sent=[]
        class Wire(Fake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(m,s)
                with ImmediateFixture(local.packed(response)) as fixture,patch('local.OLLAMA_URL',fixture.url):
                    received=local.Ollama(fixture.url).chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
                    sent.append(json.loads(fixture.calls[0]['body']));return received
        result=service.Engine([chunk()],Wire()).answer('Какие условия дня 30?',[])
        self.assertEqual([p['options'] for p in sent],[SELECT,SYNTH])
        for phase,payload in zip(('selection','synthesis'),sent):
            self.assertEqual(payload['model'],local.MODEL);self.assertEqual(payload['think'],False)
            self.assertEqual(result['trace']['generation_parameters'][phase],
                {'model':payload['model'],'model_digest':local.GEN_DIGEST,'think':payload['think'],'format_mode':'native','options':payload['options'],'deadline_seconds':300})
            self.assertEqual(result['trace']['budgets'][phase]['options'],payload['options'])
            self.assertEqual(result['trace']['budgets'][phase]['output_reserved'],payload['options']['num_predict'])
            self.assertLessEqual(result['trace']['budgets'][phase]['input_upper_bound']+payload['options']['num_predict'],8192)
        self.assertEqual(result['metrics']['generation_calls'],2);self.assertNotIn('trace',service.public_receipt(result))
    def test_explicit_options_and_default_payload_are_independent_copies(self):
        before=copy.deepcopy(local.GEN_OPTIONS);explicit=dict(SYNTH);calls=[];client=local.Ollama()
        def request(path,payload):
            calls.append(copy.deepcopy(payload));payload['options']['temperature']=99
        client.request=request;client.chat([],{},options=explicit);client.chat([],{})
        self.assertEqual([p['options'] for p in calls],[SYNTH,SELECT])
        self.assertEqual(explicit,SYNTH);self.assertEqual(local.GEN_OPTIONS,before)
    def test_budget_and_observed_count_use_passed_context_and_output(self):
        options={'num_ctx':2000,'num_predict':17,'temperature':0.7,'top_p':0.8}
        messages=[{'role':'user','content':'short synthetic query'}]
        budget=service.budget_for(messages,{},options=options)
        self.assertEqual(budget['options'],options);self.assertEqual(budget['num_ctx'],2000)
        self.assertEqual(budget['output_reserved'],17);self.assertEqual(budget['template_reserve'],512)
        response={'model':local.MODEL,'done':True,'done_reason':'stop','message':{'content':'{}'},'prompt_eval_count':1500}
        self.assertEqual(service.parse_response(response),{})
        with self.assertRaisesRegex(ValueError,'observed_context_overflow_or_missing_count'):
            service.parse_response(response,options=options)
        with self.assertRaises(ValueError):service.budget_for([{'role':'user','content':'x'*1800}],{},options=options)
    def test_completed_invalid_selection_and_synthesis_keep_only_called_parameters(self):
        for bad,phases in (('ids',['selection']),('refs',['selection','synthesis'])):
            with self.subTest(bad=bad),self.assertRaises(service.InferenceFailure) as caught:
                service.Engine([chunk()],Fake(bad)).answer('Какие условия дня 30?',[])
            trace=caught.exception.partial_result['trace']
            self.assertEqual(set(trace['generation_parameters']),set(phases))
            for phase in phases:
                expected=SELECT if phase=='selection' else SYNTH
                self.assertEqual(trace['generation_parameters'][phase]['options'],expected)
                self.assertEqual(trace['budgets'][phase]['options'],expected)
    def test_sent_transport_parse_error_records_selection_options_not_synthesis(self):
        class Wire(Fake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):return provider.chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
        with ImmediateFixture(b'{broken') as fixture,patch('local.OLLAMA_URL',fixture.url):
            provider=local.Ollama(fixture.url)
            with self.assertRaises(service.InferenceFailure) as caught:
                service.Engine([chunk()],Wire()).answer('Какие условия дня 30?',[])
            trace=caught.exception.partial_result['trace'];sent=json.loads(fixture.calls[0]['body'])
            self.assertEqual(trace['generation_parameters']['selection']['options'],sent['options'])
            self.assertEqual(sent['options'],SELECT);self.assertNotIn('synthesis',trace['generation_parameters'])
    def test_unknown_presend_error_no_false_sent_parameters_and_no_shared_default_mutation(self):
        original=copy.deepcopy(local.GEN_OPTIONS)
        with self.assertRaises(service.InferenceTimeout) as caught:
            service.Engine([chunk()],Fake('timeout')).answer('Какие условия дня 30?',[])
        trace=caught.exception.partial_result['trace']
        self.assertNotIn('generation_parameters',trace)
        self.assertEqual(trace['generation_attempt_parameters']['selection'],{'model':local.MODEL,'model_digest':local.GEN_DIGEST,'think':False,'format_mode':'native','options':SELECT,'deadline_seconds':300})
        self.assertNotIn('synthesis',trace['generation_attempt_parameters']);self.assertEqual(local.GEN_OPTIONS,original)

if __name__=='__main__':unittest.main()
