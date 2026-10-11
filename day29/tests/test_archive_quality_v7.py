"""Цельность коротких originals и authority-boundary без смыслового verifier."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_chat_core as chat
import full_chat_evidence as proof
from test_full_chat_contract import chunk,V
from test_archive_quality_v3 import attributed

class QualityV7(unittest.TestCase):
 def test_short_authored_part_retains_action_condition_and_literal_offsets(self):
  text='Я предложил библиотеку.\n\nНо пока не внедрил её: сначала нужна проверка.'
  c=attributed('original','Ada',text);c['start_char']=40;c['end_char']=40+len(text)
  c['source_sections']=[{'start_char':40,'end_char':40+len(text),'member_ids':['original']}]
  units=proof.source_units(c,'S1',chat.attribution_parts(c))
  self.assertEqual(len(units),1);self.assertEqual(units[0]['text'],text)
  self.assertEqual((units[0]['start_char'],units[0]['end_char']),(40,40+len(text)))
  answer,_=proof.render_selection({'evidence':[{'evidence_id':'S1.U1','aspect_ids':['Q1']}],'status':{'Q1':'not_proven'}},proof.question_aspects('Завершено ли внедрение?'),units)
  self.assertIn(text,answer['answer'])
 def test_parts_never_merge_author_date_or_attribution(self):
  c=chunk('parts',text='AAA\n\nBBB\n\nCCC')
  parts=[{'text':'AAA','start_char':0,'author':'Ada','date':'date1','attribution':'original'},
         {'text':'BBB','start_char':5,'author':'Ada','date':'date2','attribution':'original'},
         {'text':'CCC','start_char':10,'author':'Bex','date':'date2','attribution':'ambiguous'}]
  units=proof.source_units(c,'S1',parts)
  self.assertEqual([u['text'] for u in units],['AAA','BBB','CCC']);self.assertEqual(len({u['part_index'] for u in units}),3)
  self.assertEqual([u['date'] for u in units],['date1','date2','date2'])
 def test_long_parts_keep_original_paragraph_sentence_offsets(self):
  text=('Сначала описано наблюдение. '+'Потом условие без изменения смысла. '*25)+'\n\nНо результат ещё не проверен.'
  c=attributed('long','Ada',text);units=proof.source_units(c,'S1',chat.attribution_parts(c))
  self.assertGreater(len(units),1)
  for u in units:self.assertEqual(text[u['start_char']:u['end_char']],u['text'])
  self.assertTrue(any(u['text']=='Но результат ещё не проверен.' for u in units))
 def fixture(self):
  sources=[chunk('assignment','assignment',7,text='Условие LUM: реализуйте поиск.'),
           attributed('announcement','Host','🔥 День 7. LUM\nРеализуйте поиск.'),
           attributed('summary','Publisher','Что обсуждали: участники применили LUM.'),
           attributed('link','Publisher','Читать полностью: https://example.invalid/LUM'),
           attributed('primary','Ada','Я проверил LUM.\n\nНо пока не получил результата.')]
  units=[u for i,c in enumerate(sources,1) for u in proof.source_units(c,'S'+str(i),chat.attribution_parts(c))]
  parts={c['chunk_id']:chat.attribution_parts(c) for c in sources}
  return sources,units,parts
 def test_actor_only_enum_excludes_background_without_dropping_source_units(self):
  sources,units,parts=self.fixture();q='Что участники сообщили в исходной переписке о LUM?'
  policy=proof.admissibility_policy(q,chat.resolve_query(q,[]),units,parts)
  self.assertTrue(policy['actor_only']);self.assertEqual(policy['allowed_evidence_ids'],['S5.U1'])
  self.assertEqual(len(policy['excluded_evidence_units']),4)
  schema=proof.response_schema(proof.question_aspects(q),units,policy['allowed_evidence_ids'])
  self.assertEqual(schema['properties']['evidence']['items']['properties']['evidence_id']['enum'],['S5.U1'])
  self.assertEqual(len(units),5)
 def test_explicit_requirements_and_mixed_scope_keep_assignment_selectable(self):
  _,units,parts=self.fixture()
  for q in ('Каково условие задания дня 7?', 'Что участники сообщили и каково условие задания?'):
   with self.subTest(q=q):
    policy=proof.admissibility_policy(q,chat.resolve_query(q,[]),units,parts)
    self.assertFalse(policy['actor_only']);self.assertIn('S1.U1',policy['allowed_evidence_ids'])
 def test_decoder_rejects_inadmissible_selected_id_without_retry(self):
  _,units,parts=self.fixture();q='Что участники сообщили в переписке?'
  policy=proof.admissibility_policy(q,chat.resolve_query(q,[]),units,parts)
  raw={'evidence':[{'evidence_id':'S1.U1','aspect_ids':['Q1']}],'status':{'Q1':'supported'}}
  with self.assertRaisesRegex(ValueError,'inadmissible_evidence_id'):
   proof.render_selection(raw,proof.question_aspects(q),units,policy['allowed_evidence_ids'])
 def test_short_reply_context_is_explicit_background_with_own_author(self):
  text='🔥 День 7. Реализуйте поиск.\n\nЯ проверил, но не завершил.'
  c=chunk('thread',text=text)
  parts=[{'text':'🔥 День 7. Реализуйте поиск.','start_char':0,'author':'Host','attribution':'original'},
         {'text':'Я проверил, но не завершил.','start_char':len('🔥 День 7. Реализуйте поиск.\n\n'),'author':'Ada','attribution':'original'}]
  units=proof.source_units(c,'S1',parts);q='Что участники сообщили в переписке?'
  policy=proof.admissibility_policy(q,chat.resolve_query(q,[]),units,{'thread':parts})
  self.assertEqual(policy['allowed_evidence_ids'],['S1.U2'])
  raw={'evidence':[{'evidence_id':'S1.U2','aspect_ids':['Q1']}],'status':{'Q1':'partial'}}
  answer,trace=proof.render_selection(raw,proof.question_aspects(q),units,policy['allowed_evidence_ids'])
  self.assertIn('Host (фоновый контекст, не доказательство действий участников)',answer['answer'])
  self.assertIn('Ada: «Я проверил, но не завершил.»',answer['answer'])
  self.assertEqual(trace['background_context_evidence_ids'],['S1.U1'])
 def test_actual_prompt_preserves_background_unit_shape_and_decoder_enforcement(self):
  sources,_,_=self.fixture();sources=[sources[4],sources[0]];q='Что участники сообщили о LUM?'
  messages,kept,_,trace=chat.build_evidence_context(q,chat.resolve_query(q,[]),[],sources)
  body=json.loads(messages[1]['content']);self.assertEqual(len(body['sources']),2)
  self.assertEqual(body['sources'][1]['units'][0]['text'],sources[1]['text'])
  self.assertEqual(set(body['sources'][1]['units'][0]),{'evidence_id','part_index','author','date','attribution','text','context_ids'})
  self.assertEqual(trace['evidence_admissibility']['allowed_evidence_ids'],['S1.U1'])
  raw={'evidence':[{'evidence_id':'S2.U1','aspect_ids':['Q1']}],'status':{'Q1':'supported'}}
  with self.assertRaisesRegex(ValueError,'inadmissible_evidence_id'):
   chat.EvidenceChatEngine([],{}).decode_answer(raw,kept,'a'*32,trace,{})
 def test_runtime_inadmissible_provider_selection_fails_closed_one_generation(self):
  from test_full_chat_runtime import Client
  class BackgroundClient(Client):
   def request(self,path,payload):
    body=json.loads(payload['messages'][1]['content'])
    eid=next(s['units'][0]['evidence_id'] for s in body['sources'] if s['source']=='assignment')
    self.answer={'evidence':[{'evidence_id':eid,'aspect_ids':['Q1']}],'status':{'Q1':'supported'}}
    return super().request(path,payload)
  sources,_,_=self.fixture();client=BackgroundClient()
  r=chat.EvidenceChatEngine([sources[4],sources[0]],{},client).ask('Что участники сообщили о LUM?',[],'a'*32)
  self.assertEqual(r['status'],'error');self.assertEqual(r['error']['message'],'inadmissible_evidence_id')
  self.assertEqual(sum(route=='/api/chat' for route,_ in client.calls),1)
  self.assertIsNone(r.get('answer'))
 def test_empty_allowlist_schema_requires_empty_selection(self):
  sources,units,parts=self.fixture();units=units[:1];q='Что участники сообщили о LUM?'
  policy=proof.admissibility_policy(q,chat.resolve_query(q,[]),units,parts)
  schema=proof.response_schema(proof.question_aspects(q),units,policy['allowed_evidence_ids'])
  self.assertEqual(schema['properties']['evidence']['maxItems'],0)
  answer,_=proof.render_selection({'evidence':[],'status':{'Q1':'not_found'}},proof.question_aspects(q),units,[])
  self.assertEqual(answer['source_refs'],[])

if __name__=='__main__':unittest.main()
