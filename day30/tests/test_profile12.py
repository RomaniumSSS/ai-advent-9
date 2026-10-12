"""Profile12: alias wire/Go sort, lossless gates, identity и приватность без inference."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import local,protocol,service
from test_service import Fake,chunk,context_body
from test_protocol03 import ASPECTS,UNIT,metadata,synthesis
from test_review_regressions import ImmediateFixture

MODEL='qwen3:8b-q8_0';DIGEST='e56358ca25dd14db6853a9f68a92d717aaa6f0a94250a72d1a0f3d86a9f30130'

class Profile12Tests(unittest.TestCase):
    def test_lossless_stage_specific_aliases_and_strict_unknown_mixed_missing(self):
        canonical=synthesis();canonical['points'][0]['text']='a_evidence и c_conclusion остаются текстом.'
        wire=protocol.wire_value('synthesis',canonical)
        self.assertEqual(list(wire),['a_points','b_doubtful_aspect_ids','c_conclusion'])
        self.assertEqual(list(wire['c_conclusion']),['a_text','b_point_refs'])
        self.assertEqual(protocol.normalize_wire('synthesis',wire),canonical);self.assertEqual(wire['a_points'],canonical['points'])
        for bad in (canonical,{**wire,'points':[]},{**wire,'analysis':'opaque'},
                    {k:v for k,v in wire.items() if k!='b_doubtful_aspect_ids'},
                    {**wire,'c_conclusion':canonical['conclusion']}, {**wire,'c_conclusion':{**wire['c_conclusion'],'analysis':'opaque'}}):
            with self.assertRaisesRegex(ValueError,'invalid_wire_shape'):protocol.normalize_wire('synthesis',bad)
        with self.assertRaisesRegex(ValueError,'invalid_wire_shape'):protocol.normalize_wire('selection',wire)
        raw='{"a_evidence":{},"a_evidence":{},"b_coverage":{}}'
        with self.assertRaisesRegex(ValueError,'duplicate_json_key'):protocol.normalize_wire('selection',protocol.strict_json(raw))
    def test_duplicate_alias_keys_all_levels_before_normalization(self):
        for raw in ('{"a_evidence":{},"\u0061_evidence":{},"b_coverage":{}}',
                    '{"a_evidence":{"S1.U1":[],"S1.U1":[]},"b_coverage":{}}',
                    '{"a_points":[],"b_doubtful_aspect_ids":[],"c_conclusion":{"a_text":"x","a_text":"y","b_point_refs":[]}}'):
            response={'model':MODEL,'done':True,'done_reason':'stop','message':{'content':raw},'prompt_eval_count':1}
            with self.assertRaisesRegex(ValueError,'duplicate_json_key'):service.parse_response(response)
    def test_previous_model_response_rejected_without_retry(self):
        class Wrong(Fake):
            def chat(self,*args,**kwargs):
                response=super().chat(*args,**kwargs);response['model']='qwen3.5:9b-q4_K_M';return response
        with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],Wrong()).answer('Какие условия дня 30?',[])
        self.assertEqual(caught.exception.partial_result['trace']['validation_code'],'incomplete_model_response')
        self.assertEqual(caught.exception.partial_result['metrics']['generation_calls'],1)
    def test_actual_wire_sorted_provider_order_budget_identity_and_raw_final(self):
        sent=[];returned=[]
        class Wire(Fake):
            def chat(self,m,s,**kwargs):
                response=super().chat(m,s,**kwargs)
                with ImmediateFixture(local.packed(response)) as fixture,patch('local.OLLAMA_URL',fixture.url):
                    result=local.Ollama(fixture.url).chat(m,s,**kwargs);sent.append(json.loads(fixture.calls[0]['body']));returned.append(response['message']['content']);return result
        result=service.Engine([chunk()],Wire()).answer('Назови один пример в задании дня 30',[])
        self.assertEqual(local.MODEL,MODEL);self.assertEqual(local.GEN_DIGEST,DIGEST)
        self.assertEqual(result['trace']['wire_schema_version'],'profile12_aliases')
        roots=(['a_evidence','b_coverage'],['a_points','b_doubtful_aspect_ids','c_conclusion'])
        for phase,payload,root,raw in zip(('selection','synthesis'),sent,roots,returned):
            schema=payload['format'];sorted_schema=json.loads(json.dumps(schema,sort_keys=True))
            self.assertEqual(list(sorted_schema['properties']),root)
            self.assertEqual(payload['model'],MODEL);self.assertFalse(payload['think'])
            self.assertEqual(schema,result['trace'][phase+'_wire_schema'])
            self.assertEqual(result['trace'][phase+'_raw_response']['message']['content'],raw)
            self.assertEqual(result['trace'][phase+'_response'],protocol.normalize_wire(phase,protocol.strict_json(raw)))
            self.assertEqual(result['trace']['budgets'][phase],service.budget_for(payload['messages'],schema,options=payload['options'],deadline_seconds=300))
            self.assertEqual(result['trace']['generation_parameters'][phase]['model_digest'],DIGEST)
        props=json.loads(json.dumps(sent[1]['format'],sort_keys=True))['properties']
        self.assertEqual(list(props['a_points']['items']['properties']),['aspect_ids','evidence_id','text'])
        self.assertEqual(list(props['c_conclusion']['properties']),['a_text','b_point_refs'])
        self.assertEqual(result['metrics']['generation_calls'],2);self.assertEqual(len(result['answer']['sources']),1)
    def test_safe_wire_raw_is_exact_unknown_reasoning_shapes_opaque(self):
        wire=protocol.wire_value('synthesis',synthesis());wire['a_points'][0]['evidence_id']='invalid-reference'
        raw=json.dumps(wire,ensure_ascii=False,indent=2)
        response={'message':{'content':raw,'thinking':'SYNTHETIC_REASON_ONLY_RAM'}}
        saved=local.sanitized_response(response)
        self.assertEqual(saved['message']['content'],raw);self.assertNotIn('thinking',saved['message'])
        for bad in ({**wire,'analysis':'SYNTHETIC_REASON_ONLY_RAM'}, {**wire,'c_conclusion':{**wire['c_conclusion'],'analysis':'SYNTHETIC_REASON_ONLY_RAM'}},synthesis()):
            value=local.sanitized_response({'message':{'content':json.dumps(bad)}})
            self.assertNotIn('content',value['message']);self.assertNotIn('SYNTHETIC_REASON_ONLY_RAM',json.dumps(value))
    def test_normalized_invalid_refs_quantity_and_no_canonical_fallback(self):
        for bad,code in (('refs','invalid_point_reference'),('canonical','invalid_wire_shape')):
            class Bad(Fake):
                def chat(self,m,s,**kwargs):
                    response=super().chat(m,s,**kwargs)
                    if bad=='canonical':response['message']['content']=json.dumps({'evidence':{},'coverage':{'Q1':'none'}})
                    return response
            with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],Bad('refs' if bad=='refs' else None)).answer('Какие условия дня 30?',[])
            self.assertEqual(caught.exception.partial_result['trace']['validation_code'],code)
            self.assertEqual(caught.exception.partial_result['metrics']['generation_calls'],2 if bad=='refs' else 1)
        raw={'evidence':{'S1.U1':['Q1'],'S2.U1':['Q2']},'coverage':{'Q1':'full','Q2':'full'}}
        decoded=protocol.normalize_wire('selection',protocol.wire_value('selection',raw))
        with self.assertRaisesRegex(ValueError,'invalid_selection_quantity'):protocol.validate_selection(decoded,ASPECTS,[UNIT,{**UNIT,'evidence_id':'S2.U1','source_ref':'S2'}],{'S1.U1','S2.U1'},answer_limits={'max_proof_units':1,'max_points':1})

if __name__=='__main__':unittest.main()
