"""Синтетический focus/order/coverage UX, без eval-вопросов и inference."""
import json,sys,unittest
from pathlib import Path
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'core.py').is_file() and (p/'full_chat_core.py').is_file())
sys.path.append(str(ROOT));sys.path.append(str(ROOT/'tests'))
import core,full_chat_core as chat,full_chat_evidence as proof
from test_full_chat_contract import chunk

class QualityV5(unittest.TestCase):
 def fixture(self):
  alpha=chunk('alpha',text='Планирую проверить лампы завтра.',members=[{'id':1,'author':'Автор А'}],source_sections=[{'start_char':0,'end_char':31,'member_ids':[1]}])
  beta=chunk('beta',text='В прежнем эпизоде говорил о настройке часов.')
  unit=proof.source_units(alpha,'S1',chat.attribution_parts(alpha))[0]
  turn={'request_id':'prior','question':'Что предложил автор о лампах?','status':'done','query':{'intent':'new_topic'},
        'answer':{'answer':'FORBIDDEN_PRIOR_ASSISTANT_FACT','source_refs':['S1'],'sources':[{'source_ref':'S1','chunk_id':'alpha'}],'evidence_units':[unit]}}
  return alpha,beta,turn
 def test_followup_focus_remaps_fresh_ids_not_previous_ref_position(self):
  alpha,beta,turn=self.fixture();q=chat.resolve_query('Можно ли из этих реплик считать проверку завершённой?',[turn])
  messages,kept,history,trace=chat.build_evidence_context('Можно ли из этих реплик считать проверку завершённой?',q,[turn],[beta,alpha])
  body=json.loads(messages[1]['content']);self.assertEqual(body['dialogue_focus']['evidence_ids'],['S2.U1'])
  self.assertEqual(trace['dialogue_focus']['prior_request_id'],'prior');self.assertNotIn('FORBIDDEN_PRIOR_ASSISTANT_FACT',messages[1]['content'])
 def test_focus_ignores_ack_and_new_topic_clears_focus(self):
  alpha,beta,turn=self.fixture();ack={'request_id':'ack','question':'Понял','status':'done','query':{'intent':'acknowledgement'},'answer':{'answer':'Пожалуйста','sources':[]}}
  turns=[turn,ack];q=chat.resolve_query('А почему?',turns)
  messages,_,_,trace=chat.build_evidence_context('А почему?',q,turns,[alpha])
  self.assertTrue(trace['dialogue_focus']['evidence_ids'])
  q=chat.resolve_query('Новая тема: что описано в каталоге?',turns)
  messages,_,_,trace=chat.build_evidence_context('Новая тема: что описано в каталоге?',q,turns,[alpha])
  self.assertEqual(trace['dialogue_focus']['evidence_ids'],[])
 def test_prior_unit_must_match_actual_fresh_immutable_text(self):
  alpha,beta,turn=self.fixture();turn['answer']['evidence_units'][0]['text']='Подменённый старый текст'
  q=chat.resolve_query('А почему?',[turn]);messages,_,_,trace=chat.build_evidence_context('А почему?',q,[turn],[alpha])
  self.assertEqual(trace['dialogue_focus']['evidence_ids'],[]);self.assertNotIn('Подменённый',messages[1]['content'])
 def test_output_schema_serializes_evidence_before_status(self):
  alpha,_,_=self.fixture();units=proof.source_units(alpha,'S1',chat.attribution_parts(alpha));aspects=proof.question_aspects('Что предложено?')
  schema=proof.response_schema(aspects,units);props=schema['properties'];self.assertEqual(set(props),{'evidence','status'})
  packed=core.packed(schema).decode();self.assertLess(packed.index('"evidence":'),packed.index('"status":'))
 def test_visible_quote_does_not_get_false_missing_answer_message(self):
  c=chunk('reply',text='Предложили проверку.\n\nЯ сделал проверку за две минуты.')
  units=proof.source_units(c,'S1',chat.attribution_parts(c));aspects=proof.question_aspects('Кто сделал проверку? Какой интервал назван?')
  raw={'evidence':[{'evidence_id':units[0]['evidence_id'],'aspect_ids':['Q1']}],'status':{'Q1':'supported','Q2':'not_found'}}
  answer,trace=proof.render_selection(raw,aspects,units)
  self.assertIn('две минуты',answer['answer']);self.assertNotIn('Прямой ответ',answer['answer'])
  self.assertIn('полнота ответа не проверена',answer['answer'])
  self.assertEqual(trace['semantic_support'],'NOT_CHECKED')

if __name__=='__main__':unittest.main()
