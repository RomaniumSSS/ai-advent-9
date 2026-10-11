"""Явная тема обсуждения: короткие термины и реальные авторские реплики."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_chat_core as chat
from test_full_chat_contract import chunk,V
from test_archive_quality_v3 import attributed

LOW=[0.,1.]+[0.]*1022

class QualityV6(unittest.TestCase):
 def distractors(self):
  return [attributed('noise'+str(i),'Автор '+str(i),'Я описал конкретную проблему: вопрос обсуждали в переписке вчера.',V) for i in range(7)]
 def test_short_acronym_inflections_reserve_primary_originals(self):
  for term,inflected in [('LUM','луму'),('ZED','зеду'),('TOR','тором')]:
   with self.subTest(term=term):
    c=attributed('topic','Автор темы','Я сравнил поиск по '+inflected+' с исходными данными.',LOW)
    corpus=self.distractors()+[c]
    selected,trace=chat.retrieve_all(corpus,'Обсуждали ли участники '+term+'? Назови проблему из переписки.',V)
    self.assertEqual(selected[0]['chunk_id'],'topic');self.assertEqual(trace['eligible_count'],len(corpus))
    self.assertIn(term.lower(),trace['technical_anchors']);self.assertIn('topic',trace['selected_topic_anchor_ids'])
 def test_topic_assignment_announcement_does_not_outrank_participant(self):
  announcement=attributed('announcement','Ведущий','🔥 День 7. LUM\nРеализуйте функцию. Сравните варианты LUM.',V)
  primary=attributed('primary','Автор ответа','В LUM я встретил конфликт индекса при обновлении.',LOW)
  selected,trace=chat.retrieve_all(self.distractors()+[announcement,primary],'Что участники обсуждали о LUM?',V)
  self.assertEqual(selected[0]['chunk_id'],'primary')
  found=next(c for c in selected if c['chunk_id']=='announcement')
  self.assertTrue(found['evidence_features']['assignment_announcement'])
  self.assertFalse(found['topic_primary_discussion_matches'])
 def test_backtick_anchor_casefolds_without_prefix_false_positive(self):
  primary=attributed('primary','Автор ответа','flexpipe: я встретил конфликт при загрузке.',LOW)
  false=attributed('prefix','Другой автор','FlexPipelined: я обсуждал похожую проблему.',V)
  selected,trace=chat.retrieve_all(self.distractors()+[false,primary],'Что участники писали про `FlexPipe`?',V)
  self.assertEqual(selected[0]['chunk_id'],'primary')
  wrong=next((c for c in selected if c['chunk_id']=='prefix'),None)
  if wrong:self.assertEqual(wrong['topic_anchor_matches'],[])
 def test_multiple_technical_aspects_each_get_navigation_anchor(self):
  corpus=[attributed('lum'+str(i),'Автор '+str(i),'Я проверил LUM на примере.',V) for i in range(7)]
  corpus.append(attributed('zed','Ещё автор','Я проверил ZED и нашёл ошибку.',LOW))
  selected,trace=chat.retrieve_all(corpus,'Какие проблемы участники описали в LUM и ZED?',V)
  self.assertIn('zed',[c['chunk_id'] for c in selected]);self.assertEqual(set(trace['technical_anchors']),{'lum','zed'})
 def test_named_author_and_day_original_survive_topic_navigation(self):
  corpus=[attributed('lum'+str(i),'Автор '+str(i),'Я проверил LUM на примере.',V) for i in range(7)]
  corpus.append(attributed('named','Лев Невский','Я уточнил требования LUM.',LOW))
  corpus.append(chunk('day','assignment',7,text='Официальное условие дня 7 для LUM',vector=LOW))
  selected,trace=chat.retrieve_all(corpus,'Что Лев Невский предложил о LUM и каково условие дня 7?',V)
  self.assertTrue({'named','day'}.issubset({c['chunk_id'] for c in selected}))
 def test_link_only_summary_continuation_is_navigation_not_primary_evidence(self):
  for caption in ('📖 Читать полностью: ', 'Подробнее: ', 'Read more: ', ''):
   with self.subTest(caption=caption):
    link=attributed('link','Публикатор',caption+'https://example.invalid/notes/LUM',V)
    primary=attributed('primary','Автор ответа','Я использую LUM для проверки датчиков. https://example.invalid/docs',LOW)
    selected,trace=chat.retrieve_all(self.distractors()+[link,primary],'Как участники используют LUM?',V)
    self.assertEqual(selected[0]['chunk_id'],'primary')
    nav=next(c for c in selected if c['chunk_id']=='link')
    self.assertTrue(nav['evidence_features']['link_only_navigation'])
    self.assertEqual(nav['topic_primary_discussion_matches'],[])
    self.assertIn('lum',nav['topic_anchor_matches'])
    self.assertNotIn('link',trace['requested_topic_anchor_ids'])
    self.assertFalse(selected[0]['evidence_features']['link_only_navigation'])
 def test_variants_of_use_request_widens_distinct_primary_authors(self):
  corpus=[attributed('summary'+str(i),'Сводчик','Что обсуждали: LUM для разных задач.',V) for i in range(6)]
  corpus.extend(attributed('report'+str(i),'Участник '+str(i),'Я использую LUM для датчика '+str(i)+'.',LOW) for i in range(3))
  for noun in ('варианта использования','способа применения','сценария использования'):
   with self.subTest(noun=noun):
    selected,trace=chat.retrieve_all(corpus,'Приведи три разных '+noun+' LUM участниками.',V)
    self.assertTrue(trace['multiple_examples']);self.assertEqual(trace['top_k'],8)
    self.assertEqual({c['chunk_id'] for c in selected[:3]},{'report0','report1','report2'})
    self.assertEqual(trace['eligible_count'],9)
 def test_distinct_participants_survive_actual_five_source_context_limit(self):
  corpus=[attributed('a'+str(i),'Ada','Я LUM: датчик.',V) for i in range(7)]
  corpus.extend([attributed('b','Bex','Я LUM: каталог.',LOW),
                 attributed('c','Cyra','Я LUM: календарь.',LOW)])
  corpus.append(chunk('day','assignment',7,text='Day 7 LUM',vector=LOW))
  for noun in ('варианта использования','примера использования'):
   with self.subTest(noun=noun):
    question='Три разных '+noun+' LUM и условие дня7.'
    selected,retrieval=chat.retrieve_all(corpus,question,V)
    _,kept,_,trace=chat.build_evidence_context(question,chat.resolve_query(question,[]),[],selected)
    authors={u['author'] for u in trace['evidence_units'] if u['author']}
    self.assertTrue({'Ada','Bex','Cyra'}.issubset(authors))
    self.assertIn('day',{c['chunk_id'] for c in kept});self.assertLessEqual(len(kept),5)
    self.assertEqual(trace['selected_count'],len(kept))
 def test_no_anchor_keeps_mixed_scope_and_no_term_whitelist(self):
  corpus=[chunk('a','assignment',7),chunk('d'),chunk('n','personal_note')]
  selected,trace=chat.retrieve_all(corpus,'Что обсуждали о библиотеке?',V)
  self.assertEqual({c['chunk_id'] for c in selected},{'a','d','n'})
  self.assertEqual(trace['technical_anchors'],[]);self.assertEqual(trace['eligible_count'],3)

if __name__=='__main__':unittest.main()
