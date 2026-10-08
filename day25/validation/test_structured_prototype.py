"""Saved evidence tests; no application mutation and no external calls."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from structured_prototype import reference_errors,comparison_errors,metadata_for_reference,narrative_errors

PRIVATE=Path(__file__).parents[1]/'private/live-run-04'


class StructuredPrototypeTest(unittest.TestCase):
    def saved(self,turn):
        if not PRIVATE.exists():self.skipTest('private evidence unavailable')
        return json.loads((PRIVATE/('rag-course-review-'+str(turn).zfill(2)+'.json')).read_text())

    def ref(self,chunk):
        part=next(m for m in chunk['message_parts'] if m.get('attribution')=='single_member')
        return {'chunk_id':chunk['chunk_id'],'message_id':part['message_id'],'day':chunk.get('day')}

    def test_all7_existing_id_from_other_day_does_not_authorize_binding(self):
        item=self.saved(7);original=copy.deepcopy(item);chunks=item['generation']['transmitted_chunks']
        day22=next(c for c in chunks if c['document_id']=='assignment:22')
        day21=next(c for c in chunks if c['document_id']=='assignment:21')
        correct=self.ref(day22);wrong=dict(correct,message_id=self.ref(day21)['message_id'])
        self.assertEqual((correct['message_id'],wrong['message_id']),(4154,4082))
        self.assertEqual(reference_errors(wrong,chunks),['reference_message_not_in_chunk'])
        self.assertEqual(reference_errors(correct,chunks),[])
        self.assertEqual(metadata_for_reference(correct,chunks)['day'],22)
        self.assertEqual(metadata_for_reference(correct,chunks)['message_id'],4154)
        self.assertEqual(narrative_errors(item['answer']['answer']),['unstructured_message_id'])
        self.assertEqual(narrative_errors('Источник отображается из validated metadata'),[])
        self.assertEqual(item,original)

    def test_all10_requires_two_typed_evidence_sides_without_same_day(self):
        item=self.saved(10);original=copy.deepcopy(item);chunks=item['generation']['transmitted_chunks']
        self.assertEqual(comparison_errors([],chunks),['comparison_rows_required'])
        requirement=next(c for c in chunks if c['document_id']=='assignment:24')
        discussion=next(c for c in chunks if c.get('source')=='discussion' and c.get('day')==22)
        def quoted(c):return dict(self.ref(c),quote=c['message_parts'][0]['text'])
        row={'aspect':'SYNTHETIC STRUCTURE TEST','requirement':quoted(requirement),'discussion':quoted(discussion),
             'relationship':'supplements','analysis':'SYNTHETIC, NOT A SEMANTIC CLAIM'}
        self.assertEqual(comparison_errors([row],chunks),[])
        broken=copy.deepcopy(row);broken['discussion']['quote']='SYNTHETIC_ABSENT_QUOTE'
        self.assertIn('reference_quote_not_in_message',comparison_errors([broken],chunks))
        broken=copy.deepcopy(row);broken['discussion']=quoted(requirement)
        self.assertIn('comparison_wrong_source_role',comparison_errors([broken],chunks))
        self.assertEqual(item,original)

    def synthetic_pair(self):
        chunks=[{'chunk_id':'a','source':'assignment','day':24,'message_parts':[{'message_id':1,'attribution':'single_member','text':'Requirement','date':'VALID_A'}]},
                {'chunk_id':'d','source':'discussion','day':22,'message_parts':[{'message_id':2,'attribution':'single_member','text':'Discussion','date':'VALID_D'}]}]
        row={'aspect':'Sources','requirement':{'chunk_id':'a','message_id':1,'day':24,'quote':'Requirement'},
             'discussion':{'chunk_id':'d','message_id':2,'day':22,'quote':'Discussion'},
             'relationship':'supplements','analysis':'Synthetic analysis'}
        return chunks,row

    def test_free_ids_rejected_in_every_model_display_field(self):
        chunks,row=self.synthetic_pair()
        for field in ('aspect','analysis'):
            bad=copy.deepcopy(row);bad[field]='**message_id** 99'
            self.assertIn('unstructured_message_id',comparison_errors([bad],chunks))
        chunks[0]['message_parts'][0]['text']='message_id 99'
        bad=copy.deepcopy(row);bad['requirement']['quote']='message_id 99'
        self.assertIn('unstructured_message_id',comparison_errors([bad],chunks))
        insufficient={'status':'insufficient_context','aspect':'Sources','available_evidence':[],
                      'missing_sides':['requirement','discussion'],'reason':'Limited context'}
        for field in ('aspect','reason'):
            bad=copy.deepcopy(insufficient);bad[field]='ID 99'
            self.assertIn('unstructured_message_id',comparison_errors([bad],chunks))

    def test_day_and_message_types_are_strict(self):
        chunks,row=self.synthetic_pair();ref={k:row['requirement'][k] for k in ('chunk_id','message_id','day')}
        for day in (True,24.0,'24',0,-1):
            self.assertEqual(reference_errors(dict(ref,day=day),chunks),['reference_day_invalid'])
        for message in (True,1.0,'1',0,-1):
            self.assertEqual(reference_errors(dict(ref,message_id=message),chunks),['reference_message_id_invalid'])
        self.assertEqual(reference_errors(dict(ref,day=None),chunks),['reference_day_mismatch'])
        chunks[0]['day']=None
        self.assertEqual(reference_errors(dict(ref,day=None),chunks),[])

    def test_renderer_uses_same_validated_single_member_quote_part(self):
        chunks,row=self.synthetic_pair();ref=row['requirement']
        chunks[0]['message_parts'].insert(0,{'message_id':1,'attribution':'ambiguous_or_missing','text':'Requirement','date':'WRONG'})
        chunks[0]['message_parts'].insert(1,{'message_id':1,'attribution':'single_member','text':'Other content','date':'OTHER'})
        self.assertEqual(reference_errors(ref,chunks,require_quote=True),[])
        self.assertEqual(metadata_for_reference(ref,chunks)['date'],'VALID_A')
        bad=dict(ref,quote='Other content')
        self.assertEqual(metadata_for_reference(bad,chunks)['date'],'OTHER')
        chunks[0]['message_parts']=chunks[0]['message_parts'][:1]
        with self.assertRaises(ValueError):metadata_for_reference(ref,chunks)

    def test_insufficient_context_needs_no_invented_second_side(self):
        chunks,row=self.synthetic_pair()
        partial={'status':'insufficient_context','aspect':'Sources',
                 'available_evidence':[{'role':'requirement','reference':row['requirement']}],
                 'missing_sides':['discussion'],'reason':'No relevant discussion evidence for this aspect in the provided context'}
        self.assertEqual(comparison_errors([partial],[chunks[0]]),[])
        empty=dict(partial,available_evidence=[],missing_sides=['requirement','discussion'])
        self.assertEqual(comparison_errors([empty],[]),[])
        conflict=dict(partial,missing_sides=['requirement'])
        self.assertIn('insufficient_context_sides',comparison_errors([conflict],chunks))
        both=dict(partial,missing_sides=[])
        self.assertIn('insufficient_context_schema',comparison_errors([both],chunks))
        invalid=copy.deepcopy(partial);invalid['available_evidence'][0]['reference']['message_id']=999
        self.assertIn('reference_message_not_in_chunk',comparison_errors([invalid],chunks))

    def test_missing_ambiguous_and_foreign_refs_fail_closed(self):
        chunk={'chunk_id':'a','source':'assignment','day':22,'message_parts':[{'message_id':1,'attribution':'ambiguous_or_missing','text':'test'}]}
        ref={'chunk_id':'a','message_id':1,'day':22}
        self.assertEqual(reference_errors(ref,[chunk]),['reference_message_not_in_chunk'])
        self.assertEqual(reference_errors(dict(ref,chunk_id='foreign'),[chunk]),['reference_chunk_not_transmitted'])
        self.assertEqual(reference_errors(dict(ref,day=21),[chunk]),['reference_day_mismatch'])
        self.assertEqual(reference_errors(dict(ref,message_id=True),[chunk]),['reference_message_id_invalid'])


if __name__=='__main__':
    with patch('requests.Session.request',side_effect=AssertionError('network forbidden')),patch('subprocess.run',side_effect=AssertionError('SSH forbidden')):
        unittest.main()
