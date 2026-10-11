"""«Не только» расширяет source scope, обычное отрицание его ограничивает."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_archive_quality_v7_mixedfix as mixed

class AdditiveScopeFix(unittest.TestCase):
 def test_additive_conditions_stay_in_actual_schema_allowlist(self):
  for q in ('Что участники обсуждали: не только условия задания, но и личный опыт?',
            'Сравни не только требования задания, но и позиции участников.'):
   with self.subTest(q=q):
    _,_,trace,_=mixed.MixedRoleFix().context(q)
    p=trace['evidence_admissibility'];self.assertTrue(p['explicit_conditions']);self.assertFalse(p['actor_only'])
    assignment=next(u for u in trace['evidence_units'] if u['source']=='assignment')
    enum=trace['response_schema']['properties']['evidence']['items']['properties']['evidence_id']['enum']
    self.assertIn(assignment['evidence_id'],enum)
 def test_additive_notes_stay_separate_from_participant_proof(self):
  for q in ('Сравни не только личные заметки, но и позиции участников.',
            'Не только мои заметки, но и переписка участников.'):
   with self.subTest(q=q):
    _,_,trace,_=mixed.MixedRoleFix().context(q);p=trace['evidence_admissibility']
    self.assertTrue(p['explicit_personal_notes']);self.assertFalse(p['actor_only'])
    allowed=p['allowed_evidence_ids']
    self.assertTrue(any(u['source']=='personal_note' and u['evidence_id'] in allowed for u in trace['evidence_units']))
    self.assertFalse(any(u['source']=='assignment' and u['evidence_id'] in allowed for u in trace['evidence_units']))
 def test_true_negation_controls_still_exclude_unrequested_roles(self):
  for q in ('Что участники обсуждали: не условия задания, а личный опыт?',
            'Что участники сообщили, не из моих заметок?',
            'Что участники сообщили, за исключением требований задания?'):
   with self.subTest(q=q):
    _,_,trace,_=mixed.MixedRoleFix().context(q);p=trace['evidence_admissibility']
    self.assertTrue(p['actor_only']);self.assertFalse(p['explicit_conditions']);self.assertFalse(p['explicit_personal_notes'])
    self.assertFalse(any(u['source'] in ('assignment','personal_note') and u['evidence_id'] in p['allowed_evidence_ids'] for u in trace['evidence_units']))

if __name__=='__main__':unittest.main()
