"""Additive scope внутри обычной фразы не зависит от пунктуации."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_archive_quality_v7_mixedfix as mixed

class AdditivePolish(unittest.TestCase):
 def test_unpunctuated_additive_clause_allows_named_condition_role(self):
  for q in ('Что участники обсуждали не только условия задания, но и личный опыт?',
            'Участники обсуждали не только основные требования задания, но и личный опыт.'):
   with self.subTest(q=q):
    _,_,trace,_=mixed.MixedRoleFix().context(q);p=trace['evidence_admissibility']
    self.assertTrue(p['explicit_conditions']);self.assertFalse(p['actor_only'])
    assignment=next(u for u in trace['evidence_units'] if u['source']=='assignment')
    enum=trace['response_schema']['properties']['evidence']['items']['properties']['evidence_id']['enum']
    self.assertIn(assignment['evidence_id'],enum)
 def test_actual_exclusion_and_task_context_stay_actor_only(self):
  for q in ('Что участники обсуждали без условий задания?',
            'Что участники сообщили исключая требования задания?',
            'Какие проблемы участников в задании23?'):
   with self.subTest(q=q):
    _,_,trace,_=mixed.MixedRoleFix().context(q);p=trace['evidence_admissibility']
    self.assertTrue(p['actor_only']);self.assertFalse(p['explicit_conditions'])
    self.assertFalse(any(u['source']=='assignment' and u['evidence_id'] in p['allowed_evidence_ids'] for u in trace['evidence_units']))

if __name__=='__main__':unittest.main()
