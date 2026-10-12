"""Selection03: один ID покрывает несколько аспектов, дубли строго отклоняются."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evidence,service
from test_service import Fake,chunk,context_body,embedded_schema

class Selection03Tests(unittest.TestCase):
    def test_provider_schema_has_keyed_mapping_constraint(self):
        schema=evidence.response_schema([{'id':'Q1'}],[{'evidence_id':'S1.U1','source_ref':'S1'}])
        self.assertEqual(schema['properties']['evidence']['type'],'object');self.assertFalse(schema['properties']['evidence']['additionalProperties'])
        self.assertEqual(schema['properties']['evidence']['maxProperties'],8)
    def test_one_evidence_id_supports_two_requested_aspects_in_two_calls(self):
        class MultiAspect(Fake):
            def chat(self,messages,schema,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(messages,schema,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
                body=context_body(messages[-1]['content'])
                if 'sources' in body:
                    eid=next(iter(schema['properties']['a_evidence']['properties']))
                    aspects=[a['id'] for a in body['question_aspects']]
                    self_aspects={qid:'full' for qid in aspects}
                    value={'a_evidence':{eid:aspects},'b_coverage':self_aspects}
                    response['message']['content']=json.dumps(value)
                return response
        original='Помощник предложил добавить журнал. Участник спросил, хранить ли сообщения или достаточно выполнить 7 проверок.'
        model=MultiAspect();engine=service.Engine([chunk(source='discussion',text=original)],model)
        result=engine.answer('Какое предложение было сделано; какой вопрос был задан?',[])
        self.assertEqual(result['status'],'done');self.assertEqual(result['metrics']['generation_calls'],2)
        self.assertEqual(result['trace']['coverage']['coverage'],{'Q1':'full','Q2':'full'})
        self.assertEqual(result['trace']['coverage']['aspect_evidence_ids'],{'Q1':['S1.U1'],'Q2':['S1.U1']})
        self.assertEqual(result['trace']['coverage']['proof_ids'],['S1.U1'])
        self.assertEqual(result['trace']['synthesis_originals'][0]['text'],original)
        self.assertEqual(len(result['answer']['sources']),1)
    def test_duplicate_same_id_rejected_without_synthesis_even_different_aspects(self):
        for split in (False,True):
            class Duplicate(Fake):
                def chat(self,messages,schema,options=None,think=False,native_format=True,deadline_seconds=None):
                    response=super().chat(messages,schema,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds);body=context_body(messages[-1]['content'])
                    if 'sources' in body:
                        eid=next(iter(schema['properties']['a_evidence']['properties']))
                        groups=[['Q1'],['Q2']] if split else [['Q1','Q2'],['Q1','Q2']]
                        response['message']['content']='{"a_evidence":{'+json.dumps(eid)+':'+json.dumps(groups[0])+','+json.dumps(eid)+':'+json.dumps(groups[1])+'},"b_coverage":{"Q1":"full","Q2":"full"}}'
                    return response
            model=Duplicate()
            with self.subTest(split=split),self.assertRaises(service.InferenceFailure) as caught:
                service.Engine([chunk()],model).answer('Какие условия дня 30; какие проверки нужны?',[])
            failure=caught.exception.partial_result
            self.assertEqual(failure['trace']['validation_code'],'duplicate_json_key')
            self.assertEqual(failure['metrics']['generation_calls'],1)
            self.assertNotIn('synthesis_raw_response',failure['trace'])
            metadata=failure['trace']['selection_raw_response']['message']['content_metadata']
            self.assertGreater(metadata['bytecount'],0);self.assertEqual(len(metadata['sha256']),64)
            self.assertNotIn('content',failure['trace']['selection_raw_response']['message'])

if __name__=='__main__':unittest.main()
