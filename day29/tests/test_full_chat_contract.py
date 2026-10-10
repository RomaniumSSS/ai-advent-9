import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,full_chat_core as chat
V=[1.0]+[0.0]*1023
def chunk(cid,source='discussion',day=None,text='Синтетическое обсуждение SQLite',**extra):
    return {'chunk_id':cid,'document_id':'synthetic:'+cid,'source':source,'day':day,'text':text,'vector':V,'start_char':0,'end_char':len(text),**extra}
class FullContracts(unittest.TestCase):
    def test_all_sources_participate_even_without_day(self):
        chunks=[chunk('a','assignment',18),chunk('d'),chunk('n','personal_note')]
        selected,trace=chat.retrieve_all(chunks,'Что обсуждали о SQLite в день18?',V)
        self.assertEqual({c['chunk_id'] for c in selected},{'a','d','n'});self.assertEqual(trace['eligible_count'],3)
    def test_offsets_do_not_assign_other_author(self):
        text='AAA\nBBB';c=chunk('d',text=text,members=[{'id':1,'author':'Автор A','date':'dateA'},{'id':2,'author':'Автор B','date':'dateB'}],source_sections=[{'start_char':0,'end_char':3,'text_start_char':0,'member_ids':[1]},{'start_char':4,'end_char':7,'text_start_char':4,'member_ids':[2]}])
        parts=chat.attribution_parts(c)
        self.assertEqual(''.join(p['text'] for p in parts),text)
        self.assertEqual([p['author'] for p in parts if p['text'] in ('AAA','BBB')],['Автор A','Автор B'])
    def test_followup_is_anchored_in_user_question(self):
        turns=[{'question':'Что обсуждали о SQLite?','status':'done','answer':{'answer':'Историческое утверждение не является источником.','sources':[]},'query':{'intent':'new_topic','search_query':'Что обсуждали о SQLite?'}}]
        q=chat.resolve_query('Расскажи подробнее',turns)
        self.assertEqual(q['intent'],'followup');self.assertIn('SQLite',q['search_query']);self.assertEqual(q['anchor'],'Что обсуждали о SQLite?')
    def test_self_contained_new_subject_overrides_pronoun(self):
        turns=[{'question':'Что обсуждали о SQLite?','status':'done','answer':{'answer':'synthetic prior','sources':[]},'query':{'intent':'new_topic','search_query':'SQLite'}}]
        q=chat.resolve_query('Что такое MCP и зачем это нужно?',turns)
        self.assertEqual(q['intent'],'new_topic');self.assertIsNone(q['anchor']);self.assertNotIn('SQLite',q['search_query'])
    def test_common_elliptical_followups_keep_user_anchor(self):
        turns=[{'question':'Что обсуждали о SQLite?','status':'done','answer':{'answer':'synthetic prior','sources':[]},'query':{'intent':'new_topic','search_query':'SQLite'}}]
        for question in ('А почему?','А почему так?','Что дальше?','А что дальше?'):
            with self.subTest(question=question):
                q=chat.resolve_query(question,turns);self.assertEqual(q['intent'],'followup');self.assertEqual(q['anchor'],turns[0]['question']);self.assertIn('SQLite',q['search_query'])
    def test_history_budget_never_silently_overflows(self):
        turns=[{'question':'synthetic question','status':'done','answer':{'answer':'x'*2000,'sources':[]},'request_id':str(i)} for i in range(6)]
        messages,selected,history,trace=chat.build_context('Что обсуждали о SQLite?',{'search_query':'SQLite'},turns,[chunk('d')])
        self.assertLessEqual(len(history),3);self.assertTrue(trace['history_removed']);self.assertEqual(selected[0]['chunk_id'],'d')
        core.check_budget(messages)
if __name__=='__main__':unittest.main()
