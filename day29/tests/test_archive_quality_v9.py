"""Синтетический participant intent: виды/времена и knowledge controls."""
import sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
DAY29=next(p for p in HERE.parents if (p/'core.py').is_file())
sys.path[:0]=[str(HERE),str(DAY29),str(DAY29/'tests')]
import full_chat_core as chat
from test_full_chat_contract import chunk
from test_archive_quality_v3 import attributed

class IntentV9(unittest.TestCase):
 def context(self,q,author_catalog=None):
  sources=[attributed('person','Ada','Я проверил VEX, но пока не получил результата.'),chunk('task','assignment',11,text='Условие: реализуйте проверку.')]
  return chat.build_evidence_context(q,chat.resolve_query(q,[]),[],sources,author_catalog=author_catalog)
 def assert_participant_boundary(self,q,author_catalog=None):
  _,kept,_,trace=self.context(q,author_catalog)
  self.assertTrue(trace['evidence_admissibility']['actor_only'])
  enum=trace['response_schema']['properties']['evidence']['items']['properties']['evidence_id']['enum']
  self.assertEqual(enum,['S1.U1'])
  raw={'evidence':[{'evidence_id':'S2.U1','aspect_ids':['Q1']}],'status':{'Q1':'supported'}}
  with self.assertRaisesRegex(ValueError,'inadmissible_evidence_id'):
   chat.EvidenceChatEngine([],{}).decode_answer(raw,kept,'a'*32,trace,{})
 def test_who_is_person_request_independent_of_predicate_tense(self):
  for q in ('Кто предлагал использовать VEX?', 'Кто рекомендует использовать VEX?',
            'Кто проверит интерфейс ZEL?', 'Кто ранее подключался к ZEL?'):
   with self.subTest(q=q):self.assert_participant_boundary(q)
 def test_speech_families_inflect_without_retrieved_name_dependency(self):
  for q in ('Что рассказывал Nils Nord о VEX?', 'Что рассказывает Nils Nord о ZEL?',
            'Что порекомендовала Mira Vale о ZEL?', 'Почему Nils Nord считает это ограничением?',
            'Что писал Mira Vale о VEX?', 'Что пишет Mira Vale о ZEL?', 'Что предлагала Mira Vale о ZEL?', 'Объясни совет Nils Nord о ZEL.'):
   with self.subTest(q=q):self.assert_participant_boundary(q,{'Ada','Nils Nord','Mira Vale'})
 def test_knowledge_queries_do_not_become_statement_proof_requests(self):
  for q in ('Что такое VEX?', 'Как работает ZEL?', 'Как использовать VEX?',
            'Что такое рекомендация?', 'Что такое совет?', 'Как сформулировать рекомендацию?', 'Что такое ответ?', 'Что сказано в условии задания?'):
   with self.subTest(q=q):
    _,_,_,trace=self.context(q);self.assertFalse(trace['evidence_admissibility']['actor_only'])
    self.assertIn('S2.U1',trace['evidence_admissibility']['allowed_evidence_ids'])
 def test_entity_behavior_keeps_assignment_in_actual_enum_and_decoder(self):
  for q in ('Как используется VEX?', 'Как реализуется VEX?',
            'Что делает программа VEX по заданию?', 'Что делает ZEL?'):
   with self.subTest(q=q):
    _,kept,_,trace=self.context(q);self.assertFalse(trace['evidence_admissibility']['actor_only'])
    enum=trace['response_schema']['properties']['evidence']['items']['properties']['evidence_id']['enum']
    self.assertIn('S2.U1',enum)
    raw={'evidence':[{'evidence_id':'S2.U1','aspect_ids':['Q1']}],'status':{'Q1':'partial'}}
    answer=chat.EvidenceChatEngine([],{}).decode_answer(raw,kept,'a'*32,trace,{})
    self.assertIn('Условие: реализуйте проверку.',answer['answer'])
 def test_explicit_person_attribution_keeps_action_proof_boundary(self):
  for q in ('Что сделал Nils Nord с VEX?', 'Как реализовал проверку автор?',
            'Что проверила Mira Vale в ZEL?'):
   with self.subTest(q=q):self.assert_participant_boundary(q,{'Ada','Nils Nord','Mira Vale'})
 def test_capitalized_entity_and_who_definition_keep_task_evidence(self):
  for q in ('Как используется Silver Loom?', 'Что делает программа Silver Loom в задании?',
            'Кто такой VEX?', 'Что делает Unknown Person?'):
   with self.subTest(q=q):
    _,kept,_,trace=self.context(q,{'Ada','Nils Nord'})
    self.assertFalse(trace['evidence_admissibility']['actor_only'])
    self.assertIn('S2.U1',trace['response_schema']['properties']['evidence']['items']['properties']['evidence_id']['enum'])
    raw={'evidence':[{'evidence_id':'S2.U1','aspect_ids':['Q1']}],'status':{'Q1':'partial'}}
    answer=chat.EvidenceChatEngine([],{}).decode_answer(raw,kept,'a'*32,trace,{})
    self.assertIn('Условие: реализуйте проверку.',answer['answer'])
 def test_unknown_single_handle_speech_and_program_object_keep_participant_boundary(self):
  for q in ('Что сказал Nebulon о VEX?', 'Что рассказывал Nebulon?',
            'Что рекомендовал Nebulon о программе VEX?'):
   with self.subTest(q=q):self.assert_participant_boundary(q,{'Ada','Nils Nord'})
 def test_explicit_nonperson_speech_subject_keeps_task_enum_and_decoder(self):
  for q in ('Что рекомендует программа VEX?', 'Что предлагает приложение ZEL?',
            'Что советует модель VEX?', 'Что сообщает инструмент ZEL?',
            'Программа VEX рекомендует что?', 'Что приложение ZEL предлагает?',
            'Что модель VEX рекомендует?', 'Что инструмент ZEL сообщает?'):
   with self.subTest(q=q):
    _,kept,_,trace=self.context(q,{'Ada','Nils Nord'})
    self.assertFalse(trace['evidence_admissibility']['actor_only'])
    enum=trace['response_schema']['properties']['evidence']['items']['properties']['evidence_id']['enum']
    self.assertIn('S2.U1',enum)
    raw={'evidence':[{'evidence_id':'S2.U1','aspect_ids':['Q1']}],'status':{'Q1':'partial'}}
    answer=chat.EvidenceChatEngine([],{}).decode_answer(raw,kept,'a'*32,trace,{})
    self.assertIn('Условие: реализуйте проверку.',answer['answer'])
 def test_person_speech_about_entity_object_keeps_participant_boundary(self):
  for q in ('Что сказал Nebulon о программе VEX?',
            'Что предлагает Nebulon для приложения ZEL?',
            'Что рассказывал Nebulon про приложение VEX?',
            'Что участники рекомендуют для модели VEX?'):
   with self.subTest(q=q):self.assert_participant_boundary(q,{'Ada','Nils Nord'})
 def test_evidence_engine_uses_full_catalog_without_sending_other_authors_or_text(self):
  sources=[attributed('person','Ada','Я проверил VEX.'),chunk('task','assignment',11,text='Условие: реализуйте проверку.')]
  corpus=sources+[attributed('absent','Nils Nord','CATALOG_PRIVATE_FACT_NOT_IN_PROMPT'),
                  attributed('unused','Secret Catalog Author','ALSO_NOT_IN_PROMPT')]
  engine=chat.EvidenceChatEngine(corpus,{})
  q='Что сделал Nils Nord с VEX?'
  messages,kept,_,trace=engine.context_builder(q,chat.resolve_query(q,[]),[],sources)
  self.assertEqual({c['chunk_id'] for c in kept},{'person','task'})
  self.assertTrue(trace['evidence_admissibility']['actor_only'])
  self.assertEqual(trace['evidence_admissibility']['allowed_evidence_ids'],['S1.U1'])
  self.assertNotIn('CATALOG_PRIVATE_FACT_NOT_IN_PROMPT',messages[1]['content'])
  self.assertNotIn('Secret Catalog Author',messages[1]['content']);self.assertNotIn('author_catalog',messages[1]['content'])
  raw={'evidence':[{'evidence_id':'S2.U1','aspect_ids':['Q1']}],'status':{'Q1':'supported'}}
  with self.assertRaisesRegex(ValueError,'inadmissible_evidence_id'):
   engine.decode_answer(raw,kept,'a'*32,trace,{})
 def test_positive_mixed_condition_and_note_requests_remain_available(self):
  for q in ('Кто рекомендует VEX и каково условие задания?', 'Что рассказывал Nils Nord и каковы требования задания?'):
   with self.subTest(q=q):
    _,_,_,trace=self.context(q);self.assertTrue(trace['evidence_admissibility']['explicit_conditions'])
    self.assertIn('S2.U1',trace['evidence_admissibility']['allowed_evidence_ids'])
  q='Кто предлагал VEX? Сравни с личной заметкой.'
  note=chunk('note','personal_note',text='Планирую измерить результат.')
  _,_,_,trace=chat.build_evidence_context(q,chat.resolve_query(q,[]),[],[note])
  self.assertTrue(trace['evidence_admissibility']['explicit_personal_notes']);self.assertIn('S1.U1',trace['evidence_admissibility']['allowed_evidence_ids'])

if __name__=='__main__':unittest.main()
