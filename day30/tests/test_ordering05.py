"""Repair05: actual Ollama.request wire capture; состояние остаётся canonical."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evidence,local,service
from test_service import Fake,chunk,context_body,embedded_schema
from test_review_regressions import ImmediateFixture
from test_protocol03 import ASPECTS,UNIT,metadata

EXPECTED={'selection_root':['evidence','coverage'],
          'synthesis_root':['points','doubtful_aspect_ids','conclusion'],
          'point':['aspect_ids','evidence_id','text'],'conclusion':['text','point_refs']}

def orders(selection,synthesis):
    point='a_points' if 'a_points' in synthesis['properties'] else 'points';conclusion='c_conclusion' if point=='a_points' else 'conclusion'
    return {'selection_root':list(selection['properties']), 'synthesis_root':list(synthesis['properties']),
            'point':list(synthesis['properties'][point]['items']['properties']),
            'conclusion':list(synthesis['properties'][conclusion]['properties'])}

class Ordering05Tests(unittest.TestCase):
    def test_real_wire_preserves_all_four_schema_orders_and_payload_semantics(self):
        selection=evidence.response_schema(ASPECTS,[{**UNIT,'evidence_id':'S2.U1','source_ref':'S2'},UNIT]);synthesis=service.synthesis_schema(ASPECTS,[UNIT],metadata())
        response={'model':local.MODEL,'done':True,'done_reason':'stop','message':{'content':'{}'},'prompt_eval_count':1}
        captured=[]
        for schema in (selection,synthesis):
            messages=[{'role':'system','content':'Синтетический system'},{'role':'user','content':'Синтетический вопрос'}]
            with ImmediateFixture(local.packed(response)) as fixture,patch('local.OLLAMA_URL',fixture.url):
                client=local.Ollama(fixture.url);client.chat(messages,schema)
                raw=fixture.calls[0]['body'];sent=json.loads(raw)
                expected={'model':local.MODEL,'messages':messages,'stream':False,'think':False,'format':schema,'options':local.GEN_OPTIONS,'keep_alive':'5m'}
                self.assertEqual(sent,expected);self.assertEqual(len(raw),len(local.packed(expected)))
                captured.append(sent['format'])
        self.assertEqual(orders(*captured),EXPECTED)
        self.assertEqual(list(captured[0]['properties']['evidence']['properties']),['S2.U1','S1.U1'])
    def test_trace_order_arrays_survive_canonical_private_save_and_match_actual_wire(self):
        captured=[]
        class WireFake(Fake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
                with ImmediateFixture(local.packed(response)) as fixture,patch('local.OLLAMA_URL',fixture.url):
                    value=local.Ollama(fixture.url).chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds);captured.append(json.loads(fixture.calls[0]['body']).get('format') if native_format else embedded_schema(m[-1]['content']));return value
        result=service.Engine([chunk()],WireFake()).answer('Какие условия дня 30?',[])
        self.assertEqual(result['trace'].get('schema_property_order'),orders(*captured))
        actual_expected={'selection_root':['a_evidence','b_coverage'],'synthesis_root':['a_points','b_doubtful_aspect_ids','c_conclusion'],'point':['aspect_ids','evidence_id','text'],'conclusion':['a_text','b_point_refs']}
        self.assertEqual(result['trace']['schema_property_order'],actual_expected)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'receipt.json';local.save_private(path,result)
            stored=json.loads(path.read_text());self.assertEqual(stored['trace']['schema_property_order'],actual_expected)
            self.assertEqual(path.read_bytes(),local.packed(result))
    def test_failed_selection_does_not_claim_synthesis_order(self):
        with self.assertRaises(service.InferenceFailure) as caught:service.Engine([chunk()],Fake('ids')).answer('Какие условия дня 30?',[])
        recorded=caught.exception.partial_result['trace'].get('schema_property_order',{})
        self.assertEqual(recorded.get('selection_root'),['a_evidence','b_coverage'])
        self.assertNotIn('synthesis_root',recorded);self.assertNotIn('point',recorded);self.assertNotIn('conclusion',recorded)
    def test_failure_before_known_send_does_not_claim_wire_schema_order(self):
        with self.assertRaises(service.InferenceTimeout) as caught:service.Engine([chunk()],Fake('timeout')).answer('Какие условия дня 30?',[])
        self.assertNotIn('schema_property_order',caught.exception.partial_result['trace'])
    def test_canonical_packed_and_prompt_body_remain_sorted(self):
        self.assertEqual(local.packed({'z':1,'a':'пример'}),json.dumps({'z':1,'a':'пример'},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
        messages,_,_,_=service.fit_prompt('synthetic system','current question',[],[],service.SYNTHESIS_SCHEMA,native_format=False)
        body=messages[-1]['content'];context,end=json.JSONDecoder().raw_decode(body)
        self.assertEqual(body[:end],local.packed(context).decode())
        self.assertEqual(body[end:],'\n'+local.provider_body(service.SYNTHESIS_SCHEMA).decode())

if __name__=='__main__':unittest.main()
