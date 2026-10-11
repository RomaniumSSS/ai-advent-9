import json,sys,unittest
from pathlib import Path
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'day29/core.py').is_file())
sys.path.extend([str(ROOT/'day29'),str(ROOT/'day29/tests')])
import full_chat_core as chat
from test_full_chat_contract import chunk,V
from test_archive_quality_v3 import attributed

class SyntheticCodepointTokenizer:
 # Только fictional test vocabulary: каждый Unicode codepoint — один token.
 # Это не оценка Qwen; production tokenizer/budget остаются прежними.
 def count(self,text):return len(text)

class Refinement(unittest.TestCase):
 def fixture(self,notes=True,explicit=True):
  def make(cid,text,doc='synthetic:prior'):
   c=chunk(cid,'personal_note' if notes else 'discussion',text=text,document_id=doc)
   if not notes:c=attributed(cid,'Ada Vale',text)|{'document_id':doc}
   return c
  intro=make('intro','LEX: общая настройка накопителя и память.')
  distractors=[make('other'+str(i),'LEX: накопитель память и общий отчёт.', 'synthetic:other'+str(i)) for i in range(5)]
  target=make('refinement','Калибровка чувствительности уменьшает задержки. Замена сенсора требует повторной настройки.')
  target['vector']=[0.0,1.0]+[0.0]*1022
  question='Что сказано в личной заметке о LEX?' if notes and explicit else 'Что известно о LEX?'
  prior={'question':question,'status':'done','request_id':'a'*32,'query':{'intent':'new_topic'},
         'answer':{'answer':'UNVERIFIED_FACT_NOT_EVIDENCE','source_refs':['S1'],
                   'sources':[{'source_ref':'S1','chunk_id':'intro','document_id':'synthetic:prior'}]}}
  return [intro]+distractors+[target],[prior]
 def retrieve(self,engine,q,turns):
  query=chat.resolve_query(q,turns)
  return engine.retrieve_sources(q,query,turns,V),query
 def context(self,engine,q,turns):
  (selected,trace),query=self.retrieve(engine,q,turns)
  messages,kept,history,budget=engine.context_builder(q,query,turns,selected,tokenizer=SyntheticCodepointTokenizer())
  return selected,trace,kept,budget
 def test_requested_role_refinement_reaches_actual_five_and_schema(self):
  corpus,turns=self.fixture();engine=chat.EvidenceChatEngine(corpus,{})
  q='А что там сказано про калибровку чувствительности и замену сенсора?'
  selected,trace,kept,budget=self.context(engine,q,turns)
  self.assertIn('refinement',[c['chunk_id'] for c in kept]);self.assertLessEqual(len(kept),5)
  self.assertEqual(trace['eligible_count'],len(corpus))
  u=next(u for u in budget['evidence_units'] if u['chunk_id']=='refinement')
  self.assertIn(u['evidence_id'],budget['response_schema']['properties']['evidence']['items']['properties']['evidence_id']['enum'])
  raw={'evidence':[{'evidence_id':u['evidence_id'],'aspect_ids':['Q1']}],'status':{'Q1':'supported'}}
  answer=engine.decode_answer(raw,kept,'b'*32,budget,{})
  self.assertIn('Замена сенсора требует повторной настройки.',answer['answer'])
 def test_previous_cited_document_refinement_without_requested_role(self):
  corpus,turns=self.fixture(notes=False,explicit=False);engine=chat.EvidenceChatEngine(corpus,{})
  selected,trace,kept,budget=self.context(engine,'А что там сказано про калибровку чувствительности и замену сенсора?',turns)
  self.assertIn('refinement',[c['chunk_id'] for c in kept])
  self.assertEqual(next(c for c in kept if c['chunk_id']=='refinement')['document_id'],'synthetic:prior')
 def test_vague_followup_has_no_current_refinement(self):
  corpus,turns=self.fixture();engine=chat.EvidenceChatEngine(corpus,{})
  for q in ('А почему?', 'А что там?', 'Расскажи подробнее'):
   with self.subTest(q=q):
    (selected,trace),query=self.retrieve(engine,q,turns)
    old,oldtrace=chat.retrieve_all(corpus,query['search_query'],V,engine.lexicon)
    self.assertEqual([c['chunk_id'] for c in selected],[c['chunk_id'] for c in old])
 def test_new_topic_does_not_expand_previous_document(self):
  corpus,turns=self.fixture();engine=chat.EvidenceChatEngine(corpus,{})
  q='Новая тема: какие требования у POL?';(selected,trace),query=self.retrieve(engine,q,turns)
  old,_=chat.retrieve_all(corpus,query['search_query'],V,engine.lexicon)
  self.assertEqual([c['chunk_id'] for c in selected],[c['chunk_id'] for c in old])
 def test_explicit_current_person_does_not_select_foreign_prior_author(self):
  corpus,turns=self.fixture(notes=False,explicit=False)
  corpus.append(attributed('named','Nils Nord','LEX: калибровка чувствительности и замена сенсора пока не проверены.'))
  engine=chat.EvidenceChatEngine(corpus,{})
  selected,trace,kept,budget=self.context(engine,'А что Nils Nord говорил в этой ветке про калибровку чувствительности и замену сенсора?',turns)
  self.assertIn('named',[c['chunk_id'] for c in kept]);self.assertNotIn('refinement',[c['chunk_id'] for c in kept])
 def test_explicit_current_technical_anchor_is_not_replaced(self):
  corpus,turns=self.fixture()
  corpus.append(chunk('current','personal_note',text='POL: калибровка чувствительности и замена сенсора.',vector=[0.0,1.0]+[0.0]*1022))
  engine=chat.EvidenceChatEngine(corpus,{})
  selected,trace,kept,budget=self.context(engine,'А что там сказано про калибровку чувствительности и замену сенсора в POL?',turns)
  self.assertIn('current',[c['chunk_id'] for c in kept]);self.assertNotIn('refinement',[c['chunk_id'] for c in kept])
 def test_incidental_one_term_match_does_not_reserve_source(self):
  corpus,turns=self.fixture();corpus[-1]['text']='Калибровка обсуждалась.';corpus[-1]['end_char']=len(corpus[-1]['text'])
  engine=chat.EvidenceChatEngine(corpus,{})
  (selected,trace),query=self.retrieve(engine,'А что там сказано про калибровку чувствительности и замену сенсора?',turns)
  old,_=chat.retrieve_all(corpus,query['search_query'],V,engine.lexicon)
  self.assertEqual([c['chunk_id'] for c in selected],[c['chunk_id'] for c in old])
 def test_current_named_author_coverage_does_not_protect_all_duplicate_posts(self):
  corpus,turns=self.fixture(notes=False,explicit=False);engine=chat.EvidenceChatEngine(corpus,{})
  q='А что Ada Vale рассказывала в этой ветке про калибровку чувствительности и замену сенсора?'
  selected,trace,kept,budget=self.context(engine,q,turns)
  self.assertIn('refinement',[c['chunk_id'] for c in kept])
  self.assertTrue(any('Ada Vale' in c['author_matches'] for c in kept))
 def test_current_explicit_days_remain_in_actual_five(self):
  corpus,turns=self.fixture()
  corpus.extend(chunk('day'+str(d),'assignment',d,text='Условие: LEX для выдуманной проверки.') for d in (11,12))
  engine=chat.EvidenceChatEngine(corpus,{})
  q='А что там сказано про калибровку чувствительности и замену сенсора в дни 11 и 12?'
  selected,trace,kept,budget=self.context(engine,q,turns)
  self.assertIn('refinement',[c['chunk_id'] for c in kept])
  self.assertEqual({c['day'] for c in kept if c['source']=='assignment'},{11,12})
 def test_current_refinement_survives_budget_removal_of_lower_priority_sources(self):
  corpus,turns=self.fixture();engine=chat.EvidenceChatEngine(corpus,{})
  q='А что там сказано про калибровку чувствительности и замену сенсора?'
  (selected,trace),query=self.retrieve(engine,q,turns)
  _,kept,_,budget=engine.context_builder(q,query,turns,selected,
      options={'temperature':0,'num_ctx':6000,'num_predict':1024},tokenizer=SyntheticCodepointTokenizer())
  self.assertLess(len(kept),5);self.assertIn('refinement',[c['chunk_id'] for c in kept])
  self.assertLessEqual(budget['budget']['input_upper_bound']+1024,6000)
 def test_deictic_plus_generic_refinement_verb_is_not_two_content_terms(self):
  corpus,turns=self.fixture()
  corpus.append(chunk('incidental','personal_note',text='Там поправили опечатку.',document_id='synthetic:unrelated',vector=[0.0,1.0]+[0.0]*1022))
  engine=chat.EvidenceChatEngine(corpus,{})
  (selected,trace),query=self.retrieve(engine,'А что там поправили?',turns)
  old,_=chat.retrieve_all(corpus,query['search_query'],V,engine.lexicon)
  self.assertEqual([c['chunk_id'] for c in selected],[c['chunk_id'] for c in old])
 def test_neighboring_author_cannot_supply_named_author_current_relevance(self):
  corpus,turns=self.fixture(notes=False,explicit=False)
  own='Калибровка сенсора упомянута.'
  neighbor='Ada Vale рассказывала в этой ветке про калибровку чувствительности и замену сенсора.'
  text=own+'\n'+neighbor
  corpus.append(chunk('z_neighbor',text=text,document_id='synthetic:prior',
      members=[{'id':'a','author':'Ada Vale'},{'id':'m','author':'Mira Wren'}],
      source_sections=[{'start_char':0,'end_char':len(own),'member_ids':['a']},
                       {'start_char':len(own)+1,'end_char':len(text),'member_ids':['m']}]))
  engine=chat.EvidenceChatEngine(corpus,{})
  q='А что Ada Vale рассказывала в этой ветке про калибровку чувствительности и замену сенсора?'
  selected,trace,kept,budget=self.context(engine,q,turns)
  self.assertIn('refinement',[c['chunk_id'] for c in kept])
  self.assertEqual(trace['current_refinement']['selected_anchor_ids'],['refinement'])
 def test_acknowledgement_does_not_replace_cited_document_navigation(self):
  corpus,turns=self.fixture(notes=False,explicit=False)
  turns.append({'question':'Понял','status':'done','query':{'intent':'acknowledgement'},
                'answer':{'source_refs':['S1'],'sources':[{'source_ref':'S1','chunk_id':'other0','document_id':'synthetic:other0'}]}})
  engine=chat.EvidenceChatEngine(corpus,{})
  selected,trace,kept,budget=self.context(engine,'А что там сказано про калибровку чувствительности и замену сенсора?',turns)
  self.assertIn('refinement',[c['chunk_id'] for c in kept])
  self.assertEqual(trace['current_refinement']['prior_cited_document_ids'],['synthetic:prior'])
 def test_both_current_named_participants_keep_source_coverage(self):
  corpus,turns=self.fixture(notes=False,explicit=False)
  corpus.append(attributed('second','Nils Nord','LEX: проверка памяти пока не закончена.'))
  engine=chat.EvidenceChatEngine(corpus,{})
  q='А что Ada Vale рассказывала в этой ветке про калибровку чувствительности и замену сенсора и что Nils Nord писал про проверку памяти?'
  selected,trace,kept,budget=self.context(engine,q,turns)
  self.assertIn('refinement',[c['chunk_id'] for c in kept]);self.assertIn('second',[c['chunk_id'] for c in kept])
 def test_current_explicit_day_rejects_conflicting_candidate_day(self):
  corpus,turns=self.fixture();corpus[-1]['day']=9
  corpus.append(chunk('day11','assignment',11,text='LEX: выдуманное условие.'))
  engine=chat.EvidenceChatEngine(corpus,{})
  (selected,trace),query=self.retrieve(engine,'А что там сказано про калибровку чувствительности и замену сенсора в день 11?',turns)
  old,_=chat.retrieve_all(corpus,query['search_query'],V,engine.lexicon)
  self.assertEqual([c['chunk_id'] for c in selected],[c['chunk_id'] for c in old])
 def test_uncited_source_and_stale_document_metadata_do_not_expand_scope(self):
  corpus,turns=self.fixture(notes=False,explicit=False);corpus[-1]['document_id']='synthetic:uncited'
  turns[0]['answer']['sources'][0]['document_id']='synthetic:forged'
  turns[0]['answer']['sources'].append({'source_ref':'S2','chunk_id':'refinement','document_id':'synthetic:uncited'})
  engine=chat.EvidenceChatEngine(corpus,{})
  (selected,trace),query=self.retrieve(engine,'А что там сказано про калибровку чувствительности и замену сенсора?',turns)
  self.assertNotIn('refinement',[c['chunk_id'] for c in selected])
  self.assertEqual(trace['current_refinement']['prior_cited_document_ids'],['synthetic:prior'])
 def test_legacy_engine_keeps_original_selection_and_trace(self):
  corpus,turns=self.fixture();engine=chat.ChatEngine(corpus,{})
  q='А что там сказано про калибровку чувствительности и замену сенсора?'
  (selected,trace),query=self.retrieve(engine,q,turns)
  old,oldtrace=chat.retrieve_all(corpus,query['search_query'],V,engine.lexicon)
  self.assertEqual(selected,old);self.assertEqual(trace,oldtrace)

if __name__=='__main__':unittest.main()
