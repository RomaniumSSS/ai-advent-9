"""Синтетические source-role границы и bounded multiset без semantic verifier."""
import sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
DAY29=next(p for p in HERE.parents if (p/'core.py').is_file())
sys.path[:0]=[str(HERE),str(DAY29),str(DAY29/'tests')]
import full_chat_core as chat
import full_chat_evidence as proof
from test_full_chat_contract import chunk
from test_archive_quality_v3 import attributed

class BoundaryV8(unittest.TestCase):
 def context(self,q,sources):return chat.build_evidence_context(q,chat.resolve_query(q,[]),[],sources)
 def test_who_statement_advice_intent_does_not_depend_on_fresh_author(self):
  sources=[attributed('report','Ada','Я проверил LUM, но результата пока нет.'),chunk('task','assignment',9,text='Условие: реализуйте поиск.')]
  for q in ('Кто предложил использовать LUM?', 'Что сказал Nils Nord о LUM?', 'Какие советы давали по LUM?'):
   with self.subTest(q=q):
    _,kept,_,trace=self.context(q,sources);p=trace['evidence_admissibility'];self.assertTrue(p['actor_only'])
    ids=trace['response_schema']['properties']['evidence']['items']['properties']['evidence_id']['enum']
    self.assertEqual(ids,['S1.U1'])
    raw={'evidence':[{'evidence_id':'S2.U1','aspect_ids':['Q1']}],'status':{'Q1':'supported'}}
    with self.assertRaisesRegex(ValueError,'inadmissible_evidence_id'):
     chat.EvidenceChatEngine([],{}).decode_answer(raw,kept,'a'*32,trace,{})
 def test_absent_participant_original_does_not_open_assignment_proof(self):
  _,_,_,trace=self.context('Что сказал Nils Nord?', [chunk('task','assignment',9,text='Условие: реализуйте поиск.')])
  self.assertTrue(trace['evidence_admissibility']['actor_only']);self.assertEqual(trace['evidence_admissibility']['allowed_evidence_ids'],[])
  self.assertEqual(trace['response_schema']['properties']['evidence']['maxItems'],0)
 def test_explicit_conditions_still_allow_mixed_statement_request(self):
  _,_,_,trace=self.context('Что сказал Nils Nord и каково условие задания?', [chunk('task','assignment',9,text='Условие: реализуйте поиск.')])
  self.assertTrue(trace['evidence_admissibility']['explicit_conditions']);self.assertIn('S1.U1',trace['evidence_admissibility']['allowed_evidence_ids'])
 def test_own_headed_report_and_plan_invite_are_selectable_and_render_original(self):
  for report in ('Я реализовал поиск и уже проверил результаты.', 'Я добавил проверку, но пока не запустил.', 'Я планирую сделать проверку, пока результата нет.'):
   with self.subTest(report=report):
    text='День 9. '+report+'\n\nПопробуйте мой пример и проверьте ответы на своих данных.'
    c=attributed('own','Ada',text);_,kept,_,trace=self.context('Что сделал участник?', [c])
    self.assertFalse(chat.evidence_features(chat.attribution_parts(c))['assignment_announcement'])
    self.assertEqual(trace['evidence_admissibility']['allowed_evidence_ids'],['S1.U1'])
    raw={'evidence':[{'evidence_id':'S1.U1','aspect_ids':['Q1']}],'status':{'Q1':'partial'}}
    answer=chat.EvidenceChatEngine([],{}).decode_answer(raw,kept,'a'*32,trace,{})
    self.assertIn(text,answer['answer']);self.assertIn('Ada:',answer['answer'])
 def test_task_instruction_before_own_example_stays_background(self):
  for text in ('День 9. Реализуйте поиск.\n\nЯ покажу пример работы.',
               'День 9. Поиск\n\nЗадание:\nЯ реализовал поиск в примере. Проверьте ответы.'):
   with self.subTest(text=text):
    c=attributed('task','Host',text);_,_,_,trace=self.context('Что сделал участник?', [c])
    self.assertTrue(chat.evidence_features(chat.attribution_parts(c))['assignment_announcement'])
    self.assertEqual(trace['evidence_admissibility']['allowed_evidence_ids'],[])
 def test_statement_words_in_source_do_not_change_question_scope(self):
  c=attributed('report','Ada','Я сказал: реализуйте поиск.')
  _,_,_,trace=self.context('Какие характеристики указаны?', [c,chunk('task','assignment',9,text='Условие: реализуйте поиск.')])
  self.assertFalse(trace['evidence_admissibility']['actor_only']);self.assertIn('S2.U1',trace['evidence_admissibility']['allowed_evidence_ids'])

class IdempotentSelectionV8(unittest.TestCase):
 def fixture(self):
  c=attributed('quote','Ada','Я предложил проверку, но ещё не выполнил её.')
  return c,proof.source_units(c,'S1',chat.attribution_parts(c)),proof.question_aspects('Какой статус указан?')
 def test_bounded_multiset_schema_and_identical_items_render_once(self):
  c,units,aspects=self.fixture();item={'evidence_id':'S1.U1','aspect_ids':['Q1']}
  raw={'evidence':[dict(item) for _ in range(8)],'status':{'Q1':'not_proven'}}
  schema=proof.response_schema(aspects,units);self.assertNotIn('uniqueItems',schema['properties']['evidence'])
  self.assertTrue(schema['properties']['evidence']['items']['properties']['aspect_ids']['uniqueItems'])
  answer,trace=proof.render_selection(raw,aspects,units)
  self.assertEqual(answer['answer'].count(c['text']),1);self.assertEqual(answer['source_refs'],['S1'])
  self.assertEqual(trace['aspects'][0]['evidence_ids'],['S1.U1']);self.assertEqual(trace['selected_evidence_ids'],['S1.U1'])
  self.assertEqual(sum(n['reason']=='deduplicated_valid_selection' for n in trace['normalizations']),7)
  self.assertEqual(trace['semantic_support'],'NOT_CHECKED')
 def test_duplicates_do_not_relax_raw_size_type_domain_role_or_extra_field_guards(self):
  _,units,aspects=self.fixture();item={'evidence_id':'S1.U1','aspect_ids':['Q1']}
  def raw(items):return {'evidence':items,'status':{'Q1':'partial'}}
  with self.assertRaisesRegex(ValueError,'too_many_selected'):
   proof.render_selection(raw([item]*9),aspects,units)
  for bad in ({'evidence_id':'BAD','aspect_ids':['Q1']}, {'evidence_id':3,'aspect_ids':['Q1']},
              {'evidence_id':'S1.U1','aspect_ids':['Q1','Q1']}, {'evidence_id':'S1.U1','aspect_ids':['Q99']},
              {'evidence_id':'S1.U1','aspect_ids':[]}, {'evidence_id':'S1.U1','aspect_ids':['Q1'],'extra':True}):
   with self.subTest(bad=bad):
    with self.assertRaises(ValueError):proof.render_selection(raw([item,bad,bad]),aspects,units)
  with self.assertRaisesRegex(ValueError,'inadmissible_evidence_id'):
   proof.render_selection(raw([item,item]),aspects,units,[])
 def test_decoder_preserves_coverage_and_one_quote_for_repeated_valid_selection(self):
  c,units,aspects=self.fixture();q='Какой статус указан?'
  _,kept,_,trace=chat.build_evidence_context(q,chat.resolve_query(q,[]),[],[c])
  raw={'evidence':[{'evidence_id':'S1.U1','aspect_ids':['Q1']}]*4,'status':{'Q1':'not_proven'}}
  result={};answer=chat.EvidenceChatEngine([],{}).decode_answer(raw,kept,'a'*32,trace,result)
  self.assertEqual(answer['answer'].count(c['text']),1);self.assertEqual(len(answer['evidence_units']),1)
  self.assertEqual(answer['coverage'][0]['selection_status'],'not_proven')
  self.assertEqual(result['evidence_selection']['selected_evidence_ids'],['S1.U1'])

if __name__=='__main__':unittest.main()
