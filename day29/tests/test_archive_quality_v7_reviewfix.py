"""Исключения source scope и упоминание задания как контекста действия."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_chat_core as chat
import full_chat_evidence as proof
import test_archive_quality_v7 as v7

class ScopeReviewFix(unittest.TestCase):
 def policy(self,q,query=None):
  _,units,parts=v7.QualityV7().fixture()
  return proof.admissibility_policy(q,query or chat.resolve_query(q,[]),units,parts)
 def assert_actor_scope(self,q,query=None):
  p=self.policy(q,query);self.assertTrue(p['actor_only']);self.assertFalse(p['explicit_conditions'])
  self.assertNotIn('S1.U1',p['allowed_evidence_ids']);self.assertNotIn('S2.U1',p['allowed_evidence_ids'])
  self.assertIn('S5.U1',p['allowed_evidence_ids'])
 def test_negative_qualifier_constructions_keep_assignment_background(self):
  for phrase in ('исключая условия задания','за исключением требований задания',
                 'не условия задания','без условий задания','кроме требований задания'):
   with self.subTest(phrase=phrase):self.assert_actor_scope('Что участники обсуждали, '+phrase+'?')
 def test_task_context_is_not_a_request_for_conditions(self):
  for q in ('Какие проблемы участников в задании23?', 'Что Ada сделал в задании?',
            'Какие проблемы с требованиями описали участники?', 'Как участники выполняли условия задания?'):
   with self.subTest(q=q):self.assert_actor_scope(q)
 def test_explicit_task_and_mixed_conditions_are_positive_controls(self):
  for q in ('Объясни задание и позицию Ada.', 'Приведи текст задания и позиции участников.',
            'Что участники обсуждали и каково условие задания?', 'Позиция Ada и условия дня23.',
            'Что участники сообщили и каковы требования задания?', 'Позиция Ada и какое условие задания?'):
   with self.subTest(q=q):
    p=self.policy(q);self.assertFalse(p['actor_only']);self.assertTrue(p['explicit_conditions'])
    self.assertIn('S1.U1',p['allowed_evidence_ids'])
 def test_exclusion_does_not_hide_separate_positive_request(self):
  q='Что участники говорили, исключая требования задания; объясни условие дня7.'
  p=self.policy(q);self.assertTrue(p['explicit_conditions']);self.assertIn('S1.U1',p['allowed_evidence_ids'])
 def test_day_heading_own_reports_and_plans_stay_selectable(self):
  from test_archive_quality_v3 import attributed
  for action in ('Я добавил обработку ошибок и уже запустил пример.',
                 'Я составил отчёт и реализовал проверку.',
                 'Я добавлю обработку ошибок, но пока не сделал её.'):
   with self.subTest(action=action):
    c=attributed('own','Ada','День 9. Задание готово.\n\n'+action)
    units=proof.source_units(c,'S1',chat.attribution_parts(c))
    q='Что сделал участник?'
    p=proof.admissibility_policy(q,chat.resolve_query(q,[]),units,{'own':chat.attribution_parts(c)})
    self.assertEqual(p['allowed_evidence_ids'],['S1.U1'])
    self.assertFalse(chat.evidence_features(chat.attribution_parts(c))['assignment_announcement'])
 def test_day_heading_real_imperatives_and_condition_structure_remain_background(self):
  from test_archive_quality_v3 import attributed
  for instructions in ('Реализуйте поиск. Сравните методы. Добавьте проверки.',
                       'Задание:\nПоиск → ответ\n\nУсиление:\nСравнение методов'):
   with self.subTest(instructions=instructions):
    c=attributed('task','Host','День 9. Поиск\n\n'+instructions)
    units=proof.source_units(c,'S1',chat.attribution_parts(c));q='Что участники сообщили?'
    p=proof.admissibility_policy(q,chat.resolve_query(q,[]),units,{'task':chat.attribution_parts(c)})
    self.assertEqual(p['allowed_evidence_ids'],[])
 def test_current_followup_exclusion_overrides_previous_mixed_scope(self):
  q='Только реплики участников, за исключением условий задания.'
  query={'intent':'followup','search_query':'Позиции участников и условия задания.\nУточнение: '+q}
  self.assert_actor_scope(q,query)

if __name__=='__main__':unittest.main()
