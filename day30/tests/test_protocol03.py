"""Repair03: strict JSON, per-aspect mapping, anchors, renderer и budgets; synthetic only."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from test_service import Fake,chunk,context_body,embedded_schema
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evidence,service

ASPECTS=[{'id':'Q1','text':'Что предложили?'},{'id':'Q2','text':'Есть ли подтверждение выполнения?'}]
UNIT={'evidence_id':'S1.U1','source_ref':'S1','chunk_id':'c','document_id':'d','source':'discussion','author':'Участник',
      'date':'2026-01-01','attribution':'original','start_char':0,'end_char':76,
      'text':'Помощник предложил использовать журнал или сравнить 7 проверок; завершение неизвестно.','context_ids':[],'evidence_role':'proof'}

def selection():return {'evidence':{'S1.U1':['Q1']},'coverage':{'Q1':'full','Q2':'none'}}
def synthesis():return {'points':[{'aspect_ids':['Q1'],'evidence_id':'S1.U1',
                          'text':'Предложено использовать журнал либо сравнить 7 проверок.'}],
                        'doubtful_aspect_ids':[],'conclusion':{'text':'Вывод: сравните предложенные варианты; результат пока не подтверждён.','point_refs':['P1']}}

def metadata():return {'coverage':{'Q1':'full','Q2':'none'},'aspect_evidence_ids':{'Q1':['S1.U1'],'Q2':[]},
                      'proof_ids':['S1.U1'],'evidence_to_aspect_ids':{'S1.U1':['Q1']}}

class Protocol03Tests(unittest.TestCase):
    def test_split_proposal_and_explicit_completion_grammar(self):
        for connector in ('есть ли','было ли','удалось ли'):
            result=evidence.question_aspects('Что предложили сделать и '+connector+' подтверждение выполнения?')
            self.assertEqual(len(result),2);self.assertTrue(result[1]['text'].startswith(connector))
        self.assertEqual(len(evidence.question_aspects('Что известно о данных и обработке?')),1)
    def test_duplicate_json_keys_every_level_and_escaped_key(self):
        for raw in ('{"evidence":{},"evidence":{},"coverage":{}}','{"evidence":{"S1.U1":["Q1"],"S1.U1":["Q2"]},"coverage":{}}',
                    '{"points":[],"conclusion":{"text":"x","text":"y"}}','{"a":1,"\\u0061":2}'):
            response={'model':service.MODEL,'done':True,'done_reason':'stop','message':{'content':raw},'prompt_eval_count':1}
            with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'duplicate_json_key'):service.parse_response(response)
    def test_selection_object_one_id_many_aspects_and_consistency(self):
        selected,coverage=service.validate_selection({'evidence':{'S1.U1':['Q1','Q2']},'coverage':{'Q1':'full','Q2':'partial'}},ASPECTS,[UNIT],{'S1.U1'})
        self.assertEqual(len(selected),1);self.assertEqual(coverage['aspect_evidence_ids'],{'Q1':['S1.U1'],'Q2':['S1.U1']})
        for raw in ({'evidence':{'S1.U1':['Q1']},'coverage':{'Q1':'full','Q2':'full'}},
                    {'evidence':{'S1.U1':['Q1','Q1']},'coverage':{'Q1':'full','Q2':'none'}},
                    {'evidence':{'invented':['Q1']},'coverage':{'Q1':'full','Q2':'none'}},
                    {'evidence':{},'coverage':{'Q1':'partial','Q2':'none'}}):
            with self.assertRaises(ValueError):service.validate_selection(raw,ASPECTS,[UNIT],{'S1.U1'})
    def test_renderer_preserves_known_proposal_and_names_missing_result(self):
        raw=synthesis();answer=service.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
        self.assertTrue(answer['summary'].startswith(raw['points'][0]['text']))
        self.assertIn(ASPECTS[1]['text'],answer['summary']);self.assertEqual(answer['conclusion'],raw['conclusion']['text'])
        self.assertEqual(answer['status'],'partial');self.assertEqual(answer['source_refs'],['S1.U1'])
        self.assertNotIn('points',answer);self.assertNotIn('anchor',answer);self.assertEqual(answer['sources'][0]['text'],UNIT['text'])
    def test_full_can_be_conservatively_missing_partial_cannot_be_hidden(self):
        raw=synthesis();raw['doubtful_aspect_ids']=['Q1']
        self.assertEqual(service.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())['status'],'partial')
        coverage=metadata();coverage['coverage']['Q1']='partial'
        with self.assertRaisesRegex(ValueError,'invalid_doubtful_aspects'):service.materialize_synthesis(raw,ASPECTS,[UNIT],coverage)
        raw['doubtful_aspect_ids']=[];answer=service.materialize_synthesis(raw,ASPECTS,[UNIT],coverage)
        self.assertEqual(answer['status'],'partial');self.assertIn(ASPECTS[0]['text'],answer['summary'])
    def test_invalid_anchor_mapping_background_or_doubtful_or_conclusion(self):
        for field,value,code in [('evidence_id','S9.U1','invalid_point_reference'),
                                ('aspect_ids',['Q2'],'invalid_point_reference')]:
            raw=synthesis();raw['points'][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,code):service.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
        raw=synthesis();raw['doubtful_aspect_ids']=['Q2']
        with self.assertRaisesRegex(ValueError,'invalid_doubtful_aspects'):service.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
        raw=synthesis();raw['conclusion']['point_refs']=['P2']
        with self.assertRaisesRegex(ValueError,'invalid_conclusion_refs'):service.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
        background={**UNIT,'evidence_role':'background_context'};cov=metadata();cov['proof_ids']=[]
        with self.assertRaisesRegex(ValueError,'invalid_point_reference'):service.materialize_synthesis(synthesis(),ASPECTS,[background],cov)
    def test_unknown_points_exact_local_contract(self):
        raw={'points':[],'doubtful_aspect_ids':[],'conclusion':{'text':'Вывод: уточните вопрос или нужный источник.','point_refs':[]}}
        answer=service.materialize_synthesis(raw,ASPECTS,[UNIT],metadata());self.assertEqual(answer['status'],'unknown')
        self.assertTrue(answer['summary'].startswith('Не знаю по переданному контексту'));self.assertEqual(answer['sources'],[])
        raw['conclusion']['text']='Вывод: свободная догадка.'
        with self.assertRaisesRegex(ValueError,'invalid_unknown_points'):service.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
    def test_no_point_output_truncation_and_summary_limit(self):
        raw=synthesis();raw['points'][0]['text']='x'*301
        with self.assertRaisesRegex(ValueError,'invalid_synthesis_points'):service.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
        raw=synthesis();raw['points']=[copy.deepcopy(raw['points'][0])]*5
        with self.assertRaisesRegex(ValueError,'invalid_synthesis_points'):service.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
        raw=synthesis();raw['points']=[{**raw['points'][0],'text':'x'*300}]*4
        long_aspects=[{'id':'Q1','text':'known'},{'id':'Q2','text':'y'*800}]
        with self.assertRaisesRegex(ValueError,'rendered_summary_too_long'):service.materialize_synthesis(raw,long_aspects,[UNIT],metadata())
    def test_pruning_rebuilds_mapping_and_downgrades_coverage(self):
        cov={'coverage':{'Q1':'full','Q2':'partial'},'aspect_evidence_ids':{'Q1':['S1.U1','S2.U1'],'Q2':['S2.U1']},
             'proof_ids':['S1.U1','S2.U1'],'evidence_to_aspect_ids':{'S1.U1':['Q1'],'S2.U1':['Q1','Q2']}}
        kept=service.retain_coverage(cov,[UNIT])
        self.assertEqual(kept['coverage'],{'Q1':'partial','Q2':'none'});self.assertEqual(kept['proof_ids'],['S1.U1'])
        self.assertEqual(kept['evidence_to_aspect_ids'],{'S1.U1':['Q1']})
        schema=service.synthesis_schema(ASPECTS,[UNIT],kept)
        self.assertEqual(schema['properties']['points']['items']['properties']['evidence_id']['enum'],['S1.U1'])
        for system in (service.SELECTION_SYSTEM,service.SYNTHESIS_SYSTEM):
            messages,units,history,b=service.fit_prompt(system,'current question',['old'*1000],
                [UNIT,{**UNIT,'evidence_id':'S2.U1','text':'low'*3000}],schema)
            self.assertLessEqual(b['input_upper_bound']+b['output_reserved'],8192);self.assertEqual(b['template_reserve'],512)
            self.assertIn('current question',messages[-1]['content'])

class EnginePruningTests(unittest.TestCase):
    def test_multi_iteration_pruning_counts_all_history_and_rebuilds_final_mapping(self):
        class AllProof(Fake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds);body=context_body(m[-1]['content'])
                if 'sources' in body:
                    response['message']['content']=json.dumps({'a_evidence':{eid:['Q1'] for eid in s['properties']['a_evidence']['properties']},'b_coverage':{'Q1':'full'}})
                return response
        client=AllProof();chunks=[chunk('c'+str(i),text='original '+str(i)+' '+('x'*180)) for i in range(3)]
        prior={'status':'done','question':'Какие условия дня 30?', 'query':{'intent':'new_topic',
            'anchor':'Какие условия дня 30?','topic_questions':['Какие условия дня 30?','Какие проверки нужны?','Какие ограничения есть?']},'answer':{}}
        actual_budget=service.budget_for;synthesis_calls=[]
        def bounded_budget(messages,schema,*args,**kwargs):
            body=context_body(messages[-1]['content'])
            if 'originals' in body:
                history=body['history_for_dialogue_only'];units=body['originals']
                synthesis_calls.append((len(history),len(units)))
                if history or len(units)>1:raise ValueError('input_exceeds_frozen_context_budget')
            return actual_budget(messages,schema,*args,**kwargs)
        with patch('service.budget_for',side_effect=bounded_budget):result=service.Engine(chunks,client).answer('А что именно там нужно проверить?',[prior])
        body=context_body(result['trace']['synthesis_prompt'][-1]['content'])
        self.assertGreaterEqual(len(synthesis_calls),3)
        self.assertEqual(result['trace']['pruning']['synthesis']['history_questions_removed'],3-len(body['history_for_dialogue_only']))
        self.assertEqual(body['coverage'],{'Q1':'partial'})
        kept={u['evidence_id'] for u in body['originals']}
        self.assertEqual(set(body['evidence_to_aspect_ids']),kept)
        self.assertEqual(set(result['trace']['synthesis_schema']['properties']['points']['items']['properties']['evidence_id']['enum']),kept)
        self.assertEqual(result['metrics']['generation_calls'],2);self.assertEqual(result['answer']['status'],'partial')
        self.assertIn('Не полностью подтверждены аспекты',result['answer']['summary'])

if __name__=='__main__':unittest.main()
