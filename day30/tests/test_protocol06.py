"""Protocol06: synthetic full-unit projection/provenance and backend-derived missing."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import protocol,service
from test_protocol03 import UNIT,ASPECTS,metadata
from test_service import Fake,chunk,context_body,embedded_schema


def output():
    return {'points':[{'aspect_ids':['Q1'],'evidence_id':'S1.U1','text':'Предложено сравнить варианты.'}],
            'doubtful_aspect_ids':[],
            'conclusion':{'text':'Вывод: сравните варианты; результат нужно проверить.','point_refs':['P1']}}

class Protocol06Tests(unittest.TestCase):
    def test_projection_full_text_exact_metadata_and_stage_local_context(self):
        for text in (' Короткая фраза.\n\nСледующая фраза!  ', '🙂е́\t'*150, 'z'*401):
            unit={**UNIT,'text':text,'attribution':None,'context_ids':['S9.U1','S2.U1']}
            other={**UNIT,'evidence_id':'S2.U1'};before=copy.deepcopy([unit,other])
            for phase in ('selection','synthesis'):
                projected=protocol.model_projection([unit,other],phase)[0]
                fields={'evidence_id','source','author','date','attribution','context_ids','text'}
                if phase=='synthesis':fields.add('evidence_role')
                self.assertEqual(set(projected),fields);self.assertEqual(projected['text'].encode(),text.encode())
                self.assertIsNone(projected['attribution']);self.assertEqual(projected['context_ids'],['S2.U1'])
                self.assertEqual(protocol.model_projection([unit],phase)[0]['context_ids'],[])
            self.assertEqual([unit,other],before)
    def test_point_derives_full_private_quote_original_span_and_metadata(self):
        unit={**UNIT,'text':' Первое.\n\n Второе.  ','start_char':50,'end_char':69,'attribution':None}
        before=copy.deepcopy(unit);diagnostic={};answer=protocol.materialize_synthesis(output(),ASPECTS,[unit],metadata(),diagnostic)
        span=diagnostic['point_source_spans'][0]
        self.assertEqual(span['quote'].encode(),unit['text'].encode())
        self.assertEqual((span['start_char'],span['end_char']),(unit['start_char'],unit['end_char']))
        self.assertEqual((span['evidence_id'],span['source_ref']),('S1.U1','S1'))
        self.assertEqual(diagnostic['derived_missing_aspect_ids'],['Q2'])
        self.assertEqual(answer['sources'][0]['text'],unit['text']);self.assertIsNone(answer['sources'][0]['attribution'])
        self.assertNotIn('point_source_spans',answer);self.assertEqual(unit,before)
    def test_point_unknown_background_cross_aspect_and_removed_ids_rejected(self):
        for change in ({'evidence_id':'invented'},{'evidence_id':'S2.U1'},{'aspect_ids':['Q2']}):
            raw=output();raw['points'][0].update(change)
            with self.assertRaisesRegex(ValueError,'invalid_point_reference'):protocol.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
        background={**UNIT,'evidence_role':'background_context'}
        with self.assertRaisesRegex(ValueError,'invalid_point_reference'):protocol.materialize_synthesis(output(),ASPECTS,[background],metadata())
        cov=metadata();cov['proof_ids']=[]
        with self.assertRaisesRegex(ValueError,'invalid_point_reference'):protocol.materialize_synthesis(output(),ASPECTS,[UNIT],cov)
    def test_model_cannot_supply_quote_anchor_ids_or_offsets(self):
        for key,value in (('anchor','copied text'),('anchor_ids',['S1.U1.A1']),('start_char',0),('quote',UNIT['text'])):
            raw=output();raw['points'][0][key]=value
            with self.assertRaisesRegex(ValueError,'invalid_synthesis_points'):protocol.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
    def test_code_missing_cannot_drop_partial_none_or_uncovered_full(self):
        for status in ('full','partial'):
            cov=metadata();cov['coverage']['Q1']=status;diagnostic={}
            answer=protocol.materialize_synthesis(output(),ASPECTS,[UNIT],cov,diagnostic)
            self.assertEqual(diagnostic['derived_missing_aspect_ids'],['Q2'] if status=='full' else ['Q1','Q2'])
            self.assertEqual(answer['status'],'partial');self.assertIn(ASPECTS[1]['text'],answer['summary'])
        cov=metadata();cov['coverage']['Q2']='full';cov['aspect_evidence_ids']['Q2']=['S1.U1']
        diagnostic={};protocol.materialize_synthesis(output(),ASPECTS,[UNIT],cov,diagnostic)
        self.assertEqual(diagnostic['derived_missing_aspect_ids'],['Q2'])
    def test_doubtful_only_effective_full_and_never_upgrade(self):
        raw=output();raw['doubtful_aspect_ids']=['Q1'];diagnostic={}
        answer=protocol.materialize_synthesis(raw,ASPECTS,[UNIT],metadata(),diagnostic)
        self.assertEqual(diagnostic['derived_missing_aspect_ids'],['Q1','Q2']);self.assertEqual(answer['status'],'partial')
        for doubtful in (['Q2'],['Q9'],['Q1','Q1'], 'Q1'):
            raw=output();raw['doubtful_aspect_ids']=doubtful
            with self.assertRaisesRegex(ValueError,'invalid_doubtful_aspects'):protocol.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
        cov=metadata();cov['coverage']['Q1']='partial';raw=output();raw['doubtful_aspect_ids']=['Q1']
        with self.assertRaisesRegex(ValueError,'invalid_doubtful_aspects'):protocol.materialize_synthesis(raw,ASPECTS,[UNIT],cov)
    def test_schema_only_retained_proof_and_full_doubts_no_empty_enum(self):
        background={**UNIT,'evidence_id':'S2.U1','evidence_role':'background_context'}
        schema=protocol.synthesis_schema(ASPECTS,[UNIT,background],metadata());props=schema['properties']
        point=props['points']['items']['properties']
        self.assertEqual(set(point),{'aspect_ids','evidence_id','text'})
        self.assertEqual(point['evidence_id']['enum'],['S1.U1']);self.assertEqual(props['doubtful_aspect_ids']['items']['enum'],['Q1'])
        cov=metadata();cov['coverage']['Q1']='partial';schema=protocol.synthesis_schema(ASPECTS,[UNIT],cov)
        self.assertEqual(schema['properties']['doubtful_aspect_ids']['maxItems'],0)
        self.assertNotIn('enum',schema['properties']['doubtful_aspect_ids']['items'])
    def test_empty_points_local_unknown_without_model_missing(self):
        raw={'points':[],'doubtful_aspect_ids':[],'conclusion':{'text':protocol.UNKNOWN_CONCLUSION,'point_refs':[]}}
        diagnostic={};answer=protocol.materialize_synthesis(raw,ASPECTS,[UNIT],metadata(),diagnostic)
        self.assertEqual(answer['status'],'unknown');self.assertEqual(answer['sources'],[])
        self.assertEqual(diagnostic['derived_missing_aspect_ids'],['Q1','Q2'])
        raw['missing_aspect_ids']=[]
        with self.assertRaisesRegex(ValueError,'invalid_synthesis_points'):protocol.materialize_synthesis(raw,ASPECTS,[UNIT],metadata())
    def test_fit_uses_projected_bytes_and_prunes_only_whole_units(self):
        first={**UNIT,'text':'x'*1500,'chunk_id':'opaque'*3000,'context_ids':['S2.U1']}
        second={**UNIT,'evidence_id':'S2.U1','text':'low '*3000}
        for phase,key in (('selection','sources'),('synthesis','originals')):
            before=copy.deepcopy([first,second])
            messages,kept,_,budget=service.fit_prompt('synthetic system','current question',[],before,
                service.SYNTHESIS_SCHEMA,phase=phase)
            self.assertEqual(kept,[first]);self.assertEqual(before,[first,second])
            projected=context_body(messages[-1]['content'])[key]
            self.assertEqual(projected[0]['context_ids'],[]);self.assertNotIn('chunk_id',projected[0])
            self.assertEqual(projected[0]['text'],first['text']);self.assertLessEqual(budget['input_upper_bound']+budget['output_reserved'],8192)
    def test_engine_trace_projection_and_budget_actual_sent_body(self):
        result=service.Engine([chunk()],Fake()).answer('Какие условия дня 30?',[]);trace=result['trace']
        self.assertEqual(trace['protocol_version'],'protocol06')
        for stage,key in (('selection','sources'),('synthesis','originals')):
            body=context_body(trace[stage+'_prompt'][-1]['content'])
            self.assertEqual(trace[stage+'_projection'],body[key])
            counted=service.budget_for(trace[stage+'_prompt'],trace[stage+'_wire_schema'],options=trace['generation_parameters'][stage]['options'],deadline_seconds=trace['generation_parameters'][stage]['deadline_seconds'])
            self.assertEqual(trace['budgets'][stage],counted)
        self.assertEqual(trace['derived_missing_aspect_ids'],[]);self.assertTrue(trace['point_source_spans'])
        self.assertEqual(result['metrics']['generation_calls'],2)

if __name__=='__main__':unittest.main()
