"""Выдуманные темы/дни, без corpus, embeddings или model calls."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_chat_core as chat

V=[1.0]+[0.0]*1023
ORTH=[0.0,1.0]+[0.0]*1022

def piece(cid,kind='discussion',day=None,low=False,text='Выдуманное обсуждение каталога.'):
    return {'chunk_id':cid,'document_id':f'assignment:{day}' if kind=='assignment' else 'synthetic:'+cid,
            'source':kind,'day':day,'text':text,'vector':ORTH if low else V,'start_char':0,'end_char':len(text)}

class DayAnchor(unittest.TestCase):
    def corpus(self):return [piece('d'+str(i)) for i in range(6)]+[piece('a13','assignment',13,True,'Условие выдуманного дня.'),piece('note','personal_note',None,False,'В заметке выдуманный каталог.')]
    def test_exact_named_day_survives_low_semantics_without_assignment_keyword(self):
        selected,trace=chat.retrieve_all(self.corpus(),'Как устроен каталог в дне 13?',V)
        self.assertIn('a13',[c['chunk_id'] for c in selected]);self.assertEqual(selected[0]['chunk_id'],'a13')
        self.assertEqual(trace['eligible_count'],8);self.assertFalse(trace['public_day_filter'])
        self.assertLess(next(c['score'] for c in selected if c['chunk_id']=='a13'),chat.THRESHOLD)

    def test_day_anchor_and_explicit_note_preserve_mixed_scope(self):
        selected,_=chat.retrieve_all(self.corpus(),'Как устроен каталог в дне 13 и что сказано об этом в заметке?',V)
        self.assertEqual({c['source'] for c in selected},{'assignment','discussion','personal_note'})
        self.assertIn('a13',[c['chunk_id'] for c in selected]);self.assertLessEqual(len(selected),chat.TOP_K)
        selected,_=chat.retrieve_all(self.corpus(),'Какие требования обсуждали участники в дне 13?',V)
        self.assertIn('a13',[c['chunk_id'] for c in selected]);self.assertIn('discussion',{c['source'] for c in selected})

    def test_pure_discussion_has_no_forced_assignment_or_source_filter(self):
        selected,trace=chat.retrieve_all(self.corpus(),'Что обсуждали участники в дне 13?',V)
        self.assertNotIn('a13',[c['chunk_id'] for c in selected]);self.assertIn('discussion',{c['source'] for c in selected})
        self.assertEqual(trace['eligible_count'],8);self.assertEqual(trace['scope'],'all')

    def test_without_explicit_day_ranking_is_unchanged_and_unknown_day_not_invented(self):
        selected,_=chat.retrieve_all(self.corpus(),'Как устроен каталог?',V)
        # ARCHIVE_QUALITY_SPEC AQ3 разрешает новое нормализованное ranking.
        self.assertEqual(len(selected),chat.TOP_K);self.assertNotIn('a13',[c['chunk_id'] for c in selected])
        selected,_=chat.retrieve_all(self.corpus(),'Как устроен каталог в дне 14?',V)
        self.assertNotIn('a13',[c['chunk_id'] for c in selected])

    def test_whole_budget_guard_retains_anchor_before_large_optional_chunks(self):
        selected,_=chat.retrieve_all(self.corpus(),'Как устроен каталог в дне 13?',V)
        for c in selected:
            if c['chunk_id']!='a13':c['text']='z'*3000;c['end_char']=len(c['text'])
        messages,kept,history,trace=chat.build_context('Как устроен каталог в дне 13?',{'intent':'new_topic'},[],selected)
        self.assertIn('a13',[c['chunk_id'] for c in kept]);self.assertTrue(trace['sources_removed'])
        anchor=next(c for c in kept if c['chunk_id']=='a13');self.assertEqual(anchor['text'],'Условие выдуманного дня.')

    def test_full_day_token_number_boundary_does_not_force_unrelated_assignment(self):
        for question in ('Как устроен каталог в Day130?', 'Сегодня 13 записей о каталоге.',
                         'Как устроен каталог в Day13suffix?', 'Как устроен каталог в midDay13?',
                         'Как устроен каталог в Day130/140?'):
            with self.subTest(question=question):
                selected,trace=chat.retrieve_all(self.corpus(),question,V)
                self.assertEqual(trace['explicit_days'],[])
                self.assertNotIn('a13',[c['chunk_id'] for c in selected])

    def test_complete_day_spellings_and_compact_multiple_days_keep_anchors(self):
        for form in ('Day13','дне13','дня13'):
            with self.subTest(form=form):
                selected,trace=chat.retrieve_all(self.corpus(),'Как устроен каталог в '+form+'?',V)
                self.assertEqual(trace['explicit_days'],[13]);self.assertIn('a13',[c['chunk_id'] for c in selected])
        corpus=self.corpus()+[piece('a14','assignment',14,True,'Другое выдуманное условие.')]
        for form in ('дни13и14','дни 13, 14','Day13/14'):
            with self.subTest(form=form):
                selected,trace=chat.retrieve_all(corpus,'Как устроен каталог в '+form+'?',V)
                self.assertEqual(trace['explicit_days'],[13,14]);self.assertTrue({'a13','a14'}<={c['chunk_id'] for c in selected})
        for form in ('Day130/14','дни130и14','дни 130, 14'):
            with self.subTest(form=form):
                selected,trace=chat.retrieve_all(corpus,'Как устроен каталог в '+form+'?',V)
                self.assertEqual(trace['explicit_days'],[14])
                self.assertIn('a14',[c['chunk_id'] for c in selected]);self.assertNotIn('a13',[c['chunk_id'] for c in selected])

if __name__=='__main__':unittest.main()
