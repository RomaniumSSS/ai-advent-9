"""Явно запрошенная личная заметка — самостоятельная роль, не чужая реплика."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_chat_core as chat
from test_full_chat_contract import chunk,V
from test_archive_quality_v3 import attributed

class MixedRoleFix(unittest.TestCase):
 def fixture(self):
  return [attributed('d','Ada','Я сравнил результаты проверки.'),
          chunk('n','personal_note',text='Мой план: сначала проверить условие, затем измерить результат.'),
          chunk('a','assignment',7,text='Условие: реализуйте проверку.')]
 def context(self,q,query=None):
  sources=self.fixture();selected,retrieval=chat.retrieve_all(sources,(query or {}).get('search_query') or q,V)
  messages,kept,_,trace=chat.build_evidence_context(q,query or chat.resolve_query(q,[]),[],selected)
  return json.loads(messages[1]['content']),kept,trace,retrieval
 def test_requested_note_reaches_actual_schema_decoder_with_separate_unknown_author_label(self):
  q='Сравни позицию участников с моей личной заметкой.'
  body,kept,trace,retrieval=self.context(q)
  self.assertEqual(retrieval['eligible_count'],3);self.assertEqual(set(retrieval['source_counts']),{'discussion','personal_note','assignment'})
  self.assertEqual({c['source'] for c in kept},{'discussion','personal_note','assignment'})
  units=trace['evidence_units'];note=next(u for u in units if u['source']=='personal_note');participant=next(u for u in units if u['source']=='discussion');assignment=next(u for u in units if u['source']=='assignment')
  enum=trace['response_schema']['properties']['evidence']['items']['properties']['evidence_id']['enum']
  self.assertIn(note['evidence_id'],enum);self.assertIn(participant['evidence_id'],enum);self.assertNotIn(assignment['evidence_id'],enum)
  self.assertIsNone(note['author']);self.assertEqual(note['attribution'],'unknown')
  raw={'evidence':[{'evidence_id':u['evidence_id'],'aspect_ids':['Q1']} for u in (participant,note)],'status':{'Q1':'partial'}}
  answer=chat.EvidenceChatEngine([],{}).decode_answer(raw,kept,'a'*32,trace,{})
  self.assertIn('Заметка: «'+note['text']+'»',answer['answer']);self.assertIn('Ada: «'+participant['text']+'»',answer['answer'])
  self.assertNotIn('Ada: «'+note['text'],answer['answer'])
  self.assertEqual(sum(len(s['units']) for s in body['sources']),len(units))
 def test_negative_note_scope_keeps_notes_inadmissible(self):
  for phrase in ('без заметок','не из моих заметок','исключая личную заметку','за исключением моих заметок'):
   with self.subTest(phrase=phrase):
    q='Что участники сообщили, '+phrase+'?';_,_,trace,_=self.context(q)
    self.assertTrue(trace['evidence_admissibility']['actor_only'])
    ids=trace['evidence_admissibility']['allowed_evidence_ids']
    self.assertFalse(any(u['source']=='personal_note' and u['evidence_id'] in ids for u in trace['evidence_units']))
 def test_prior_note_scope_and_incidental_source_word_do_not_override_current_scope(self):
  q='Что участники сообщили, не из моих заметок?'
  query={'intent':'followup','search_query':'Позиции участников и моя заметка.\nУточнение: '+q}
  _,_,trace,_=self.context(q,query)
  self.assertTrue(trace['evidence_admissibility']['actor_only'])
  self.assertFalse(trace['evidence_admissibility']['explicit_personal_notes'])
  _,_,trace,_=self.context('Что участники сообщили?')
  self.assertFalse(trace['evidence_admissibility']['explicit_personal_notes'])
 def test_explicit_note_exclusion_applies_to_condition_request_too(self):
  _,_,trace,_=self.context('Объясни условие задания, без заметок.')
  allowed=trace['evidence_admissibility']['allowed_evidence_ids']
  self.assertTrue(any(u['source']=='assignment' and u['evidence_id'] in allowed for u in trace['evidence_units']))
  self.assertFalse(any(u['source']=='personal_note' and u['evidence_id'] in allowed for u in trace['evidence_units']))

if __name__=='__main__':unittest.main()
