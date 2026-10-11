"""Синтетические A1/A2 и fidelity-unit boundary, не вопросы eval."""
import sys,unittest
from pathlib import Path
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'core.py').is_file() and (p/'full_chat_core.py').is_file())
sys.path.append(str(ROOT));sys.path.append(str(ROOT/'tests'))
import full_chat_core as chat
from full_chat_retrieval import matching_authors
from test_full_chat_contract import chunk
import full_chat_evidence as proof

AUTHORS=['Иван Петров','Алексей Сидоров','Иван Сидоров','Алексей Петров']

def prior(q='Что обсуждали участники о маяках?'):
 return {'question':q,'status':'done','query':{'intent':'new_topic'},'answer':{'answer':'UNVERIFIED',
 'sources':[{'excerpts':[{'author':'Иван Петров'},{'author':'Алексей Сидоров'}]}]}}

class QualityV4(unittest.TestCase):
 def test_fullname_mentions_do_not_cross_people(self):
  q='Сравни советы Ивана Петрова и Алексея Сидорова о лампах'
  self.assertEqual(matching_authors(AUTHORS,q),['Алексей Сидоров','Иван Петров'])
  self.assertEqual(matching_authors(['Иван Сидоров','Алексей Петров'],q),[])
  self.assertEqual(matching_authors(AUTHORS,'Что предложил Петров Иван?'),['Иван Петров'])
 def test_latest_named_user_antecedent_wins_over_random_source_authors(self):
  history=[prior()];q='А что он, Иван Петров, советовал?';resolved=chat.resolve_query(q,history)
  history.append({**prior(q),'query':resolved})
  resolved=chat.resolve_query('А почему он это предложил?',history)
  self.assertEqual(resolved['intent'],'followup');self.assertIn('Иван Петров',resolved['search_query'])
  self.assertNotIn('UNVERIFIED',resolved['search_query'])
 def fixture(self):
  text='Я не отправил нужную карточку.\n\nПредложил проверить её завтра, но пока не проверил.'
  c=chunk('p',text=text,members=[{'id':1,'author':'Автор А','date':'2026-01-02'}],source_sections=[{'start_char':0,'end_char':len(text),'member_ids':[1]}])
  return c,proof.source_units(c,'S1',chat.attribution_parts(c))
 def test_units_preserve_whole_negation_status_and_offsets(self):
  c,units=self.fixture();self.assertEqual([u['text'] for u in units],[c['text']])
  for u in units:self.assertEqual(c['text'][u['start_char']:u['end_char']],u['text'])
  self.assertEqual(units[0]['author'],'Автор А')
 def test_verified_renderer_keeps_literal_direction_and_status(self):
  c,units=self.fixture();aspects=proof.question_aspects('Какую ошибку описал автор? Что успел проверить?')
  raw={'evidence':[{'evidence_id':u['evidence_id'],'aspect_ids':[a['id'] for a in aspects]} for u in units],'status':{a['id']:'partial' for a in aspects}}
  answer,trace=proof.render_selection(raw,aspects,units)
  self.assertIn('не отправил нужную карточку',answer['answer']);self.assertIn('пока не проверил',answer['answer'])
  self.assertNotIn('лишнее',answer['answer']);self.assertEqual(answer['source_refs'],['S1'])
  self.assertEqual(trace['verification'],'exact_immutable_evidence_ids_only');self.assertEqual(trace['semantic_support'],'NOT_CHECKED')
 def test_unknown_id_and_free_factual_prose_are_rejected(self):
  c,units=self.fixture();aspects=proof.question_aspects('Что сделал автор?')
  for raw in ({'evidence':[{'evidence_id':'FORGED','aspect_ids':['Q1']}],'status':{'Q1':'supported'}},
              {'answer':'Придуманный успех','evidence':[{'evidence_id':units[0]['evidence_id'],'aspect_ids':['Q1']}],'status':{'Q1':'supported'}}):
   with self.subTest(raw=raw):
    with self.assertRaises(ValueError):proof.render_selection(raw,aspects,units)
 def test_every_aspect_present_and_partial_evidence_survives_unknown(self):
  c,units=self.fixture();aspects=proof.question_aspects('Какая ошибка описана? Измерен ли эффект?')
  raw={'evidence':[{'evidence_id':units[0]['evidence_id'],'aspect_ids':['Q1']}],'status':{'Q1':'supported','Q2':'not_found'}}
  answer,trace=proof.render_selection(raw,aspects,units)
  self.assertTrue(answer['source_refs']);self.assertIn(units[0]['text'],answer['answer']);self.assertIn('Измерен ли эффект',answer['answer'])
  with self.assertRaises(ValueError):proof.render_selection({'evidence':raw['evidence'],'status':{'Q1':'supported'}},aspects,units)
 def test_shared_chunk_does_not_inherit_neighbor_author(self):
  text='Не проверил.\n\nПроверила.';c=chunk('mixed',text=text,members=[{'id':1,'author':'Автор А'},{'id':2,'author':'Автор Б'}],source_sections=[{'start_char':0,'end_char':12,'member_ids':[1]},{'start_char':14,'end_char':24,'member_ids':[2]}])
  units=proof.source_units(c,'S1',chat.attribution_parts(c));self.assertEqual([u['author'] for u in units],['Автор А','Автор Б'])
  a=proof.question_aspects('Кто проверил?');ans,_=proof.render_selection({'evidence':[{'evidence_id':units[1]['evidence_id'],'aspect_ids':['Q1']}],'status':{'Q1':'supported'}},a,units)
  self.assertIn('Автор Б: «Проверила.»',ans['answer']);self.assertIn('Автор А (контекст реплики): «Не проверил.»',ans['answer'])
 def test_aspect_schema_selects_ids_instead_of_generated_quote_or_offsets(self):
  c,units=self.fixture();aspects=proof.question_aspects('Какая ошибка описана и что предложено проверить?')
  schema=proof.response_schema(aspects,units)
  self.assertEqual(set(schema['properties']['status']['required']),{a['id'] for a in aspects})
  self.assertNotIn('quote',str(schema));self.assertNotIn('offset',str(schema));self.assertIn(units[0]['evidence_id'],str(schema))
 def test_runtime_uses_one_call_selector_and_actual_schema_budget(self):
  from test_full_chat_runtime import Client
  class SelectorClient(Client):
   def request(self,path,payload):
    body=__import__('json').loads(payload['messages'][1]['content'])
    ids=[u['evidence_id'] for source in body['sources'] for u in source['units']]
    self.answer={'evidence':[{'evidence_id':eid,'aspect_ids':[a['id'] for a in body['question_aspects']]} for eid in ids[:2]],'status':{a['id']:'partial' for a in body['question_aspects']}}
    return super().request(path,payload)
  c,units=self.fixture();client=SelectorClient()
  r=chat.EvidenceChatEngine([c],{},client).ask('Какую ошибку описал автор? Что успел проверить?',[],'a'*32)
  self.assertEqual(r['status'],'done');self.assertIn('не отправил нужную карточку',r['answer']['answer'])
  self.assertEqual(sum(route=='/api/chat' for route,_ in client.calls),1)
  self.assertEqual(r['payload']['format'],r['context_trace']['response_schema'])
  self.assertGreater(r['context_trace']['budget']['schema_bytes'],0)
  self.assertEqual(r['semantic_support'],'NOT_CHECKED');self.assertTrue(r['citations_valid'])
 def test_no_arbitrary_character_failure_for_faithful_long_evidence(self):
  c=chunk('long',text='Длинная исходная формулировка без скрытой обрезки '*100)
  units=proof.source_units(c,'S1',chat.attribution_parts(c));aspects=proof.question_aspects('Что записано?')
  raw={'evidence':[{'evidence_id':units[0]['evidence_id'],'aspect_ids':['Q1']}],'status':{'Q1':'supported'}}
  ans,trace=proof.render_selection(raw,aspects,units)
  self.assertIn(c['text'].strip(),ans['answer']);self.assertGreater(trace['rendered_characters'],4000)
 def test_schema_and_local_guards_bound_units_and_source_refs(self):
  c=chunk('many',text='\n\n'.join('Исходный параграф '+str(i)+' содержит подробное наблюдение без пропуска отрицаний и условий. ' for i in range(9)))
  units=proof.source_units(c,'S1',chat.attribution_parts(c));aspects=proof.question_aspects('Какие параграфы?')
  self.assertEqual(proof.response_schema(aspects,units)['properties']['evidence']['maxItems'],8)
  def selection(us):return {'evidence':[{'evidence_id':u['evidence_id'],'aspect_ids':['Q1']} for u in us],'status':{'Q1':'supported'}}
  with self.assertRaisesRegex(ValueError,'too_many_selected'):proof.render_selection(selection(units),aspects,units)
  sources=[u for i in range(6) for u in proof.source_units(chunk(str(i)),f'S{i+1}',chat.attribution_parts(chunk(str(i))))]
  with self.assertRaisesRegex(ValueError,'too_many_output_source'):proof.render_selection(selection(sources),aspects,sources)
 def test_not_proven_preserves_hope_and_proposal_and_requires_evidence(self):
  c=chunk('hope',text='Жду возможности проверить эффект.\n\nПредлагаю сравнить контрольные результаты, измерений пока нет.')
  units=proof.source_units(c,'S1',chat.attribution_parts(c));aspects=proof.question_aspects('Доказан ли положительный эффект?')
  raw={'evidence':[{'evidence_id':u['evidence_id'],'aspect_ids':['Q1']} for u in units],'status':{'Q1':'not_proven'}}
  ans,trace=proof.render_selection(raw,aspects,units)
  self.assertIn('Жду возможности',ans['answer']);self.assertIn('измерений пока нет',ans['answer']);self.assertTrue(ans['source_refs'])
  missing,trace=proof.render_selection({'evidence':[],'status':{'Q1':'not_proven'}},aspects,units)
  self.assertEqual(missing['source_refs'],[]);self.assertEqual(trace['aspects'][0]['selection_status'],'not_found')
 def test_numbers_survive_future_uncertainty_without_free_interpretation(self):
  c=chunk('numbers',text='4 GB DDR4\n700 GB HDD\n\nПредполагаю, что хватит для будущей задачи.')
  units=proof.source_units(c,'S1',chat.attribution_parts(c));aspects=proof.question_aspects('Какие память и диск указаны?')
  raw={'evidence':[{'evidence_id':units[0]['evidence_id'],'aspect_ids':['Q1']}],'status':{'Q1':'supported'}}
  ans,_=proof.render_selection(raw,aspects,units)
  self.assertIn('4 GB DDR4',ans['answer']);self.assertIn('700 GB HDD',ans['answer']);self.assertNotIn('гарантирован',ans['answer'])
 def test_schema_valid_duplicate_groups_and_coverage_are_renderable(self):
  c,units=self.fixture();aspects=proof.question_aspects('Какая ошибка? Что проверил?')
  raw={'evidence':[{'evidence_id':units[0]['evidence_id'],'aspect_ids':['Q1']},{'evidence_id':units[0]['evidence_id'],'aspect_ids':['Q2']}],'status':{'Q1':'not_found','Q2':'supported'}}
  ans,trace=proof.render_selection(raw,aspects,units)
  self.assertEqual(trace['selected_evidence_ids'],[units[0]['evidence_id']]);self.assertIn(units[0]['text'],ans['answer'])
  self.assertEqual(trace['aspects'][0]['selection_status'],'partial')
  for status in ('supported','partial','not_proven','not_found'):
   raw={'evidence':[],'status':{a['id']:status for a in aspects}}
   ans,trace=proof.render_selection(raw,aspects,units)
   self.assertEqual(ans['source_refs'],[]);self.assertTrue(all(a['selection_status']=='not_found' for a in trace['aspects']))
 def test_actual_evidence_prompt_caps_sources_before_generation(self):
  selected=[chunk('d'+str(i)) for i in range(8)]
  messages,kept,history,trace=chat.build_evidence_context('Какие сведения описаны?',{'intent':'new_topic'},[],selected)
  self.assertLessEqual(len(kept),5);self.assertEqual(len(selected),8)
  self.assertTrue(any(x['reason']=='evidence_protocol_input_source_limit' for x in trace['sources_removed']))
  self.assertLessEqual(len({u['source_ref'] for u in trace['evidence_units']}),5)

if __name__=='__main__':unittest.main()
