"""Синтетические классы качества; вопросы/авторы не из holdout или архива."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_chat_core as chat
from test_full_chat_contract import chunk,V
from test_full_chat_runtime import Client

PRIOR=[{'question':'Что предлагали в обсуждении маяков?', 'status':'done','query':{'intent':'new_topic'},
        'answer':{'answer':'Синтетический ответ.','sources':[{'excerpts':[{'author':'Лев Невский'},{'author':'Ирина Садова'}]}]}}]

class Quality(unittest.TestCase):
    def test_standalone_with_local_pronouns_searches(self):
        for q in ('Какие проблемы обсуждали при переносе библиотеки и как они решались?',
                  'Какие идеи предложила Ирина Садова и что из них успела проверить?',
                  'Участники сравнивали настенные часы и таймеры. Чем они различаются?',
                  'Как Лев Невский описал свою ошибку при ремонте маяка?'):
            for turns in ([],PRIOR):
                with self.subTest(q=q,history=bool(turns)):self.assertEqual(chat.resolve_query(q,turns)['intent'],'new_topic')
    def test_ack_does_not_replace_anchor(self):
        q=chat.resolve_query('Спасибо, понятно',PRIOR);self.assertEqual(q['intent'],'acknowledgement')
        turns=PRIOR+[{'question':'Спасибо, понятно','status':'done','query':q,'answer':{'answer':'Пожалуйста.','sources':[]}}]
        self.assertEqual(chat.resolve_query('А почему?',turns)['anchor'],PRIOR[0]['question'])
    def test_current_named_author_resolves_ambiguous_prior(self):
        q=chat.resolve_query('А что он, Лев Невский, советовал?',PRIOR)
        self.assertNotEqual(q['intent'],'clarification');self.assertIn('Лев Невский',q['search_query'])
    def test_author_coverage_uses_attributed_parts(self):
        corpus=[chunk(str(i),text='Маяк: нерелевантная реплика.',members=[{'id':i,'author':'Ирина Садова'}],source_sections=[{'start_char':0,'end_char':28,'member_ids':[i]}]) for i in range(7)]
        text='Невский предложил проверять лампу маяка.'
        corpus.append(chunk('lev',text=text,members=[{'id':99,'author':'Лев Невский'}],source_sections=[{'start_char':0,'end_char':len(text),'member_ids':[99]}]))
        selected,trace=chat.retrieve_all(corpus,'Сравни предложения Ирины Садовой и Льва Невского о маяке',V)
        self.assertIn('lev',[c['chunk_id'] for c in selected]);self.assertIn('Лев Невский',trace['requested_authors'])
    def test_transliteration_and_inflected_names_match_original_metadata(self):
        text='Синтетическое описание испытаний.'
        c=chunk('lev',text=text,members=[{'id':1,'author':'Lev Nevskii'}],source_sections=[{'start_char':0,'end_char':len(text),'member_ids':[1]}])
        selected,trace=chat.retrieve_all([c],'Какие испытания описал Лев Невский?',V)
        self.assertEqual(trace['requested_authors'],['Lev Nevskii']);self.assertEqual(selected[0]['chunk_id'],'lev')
    def test_ack_runtime_has_zero_provider_calls(self):
        client=Client();r=chat.ChatEngine([],{},client).ask('Спасибо, понятно',PRIOR,'a'*32)
        self.assertEqual(r['status'],'done');self.assertFalse(r['generation_called']);self.assertEqual(client.calls,[])
    def test_ack_inflections_are_zero_calls_and_preserve_topic(self):
        for phrase in ('Понял','Поняла, спасибо','Принято','Спасибо, понял'):
            with self.subTest(phrase=phrase):
                client=Client();r=chat.ChatEngine([],{},client).ask(phrase,PRIOR,'a'*32)
                self.assertEqual(r['query']['intent'],'acknowledgement');self.assertEqual(client.calls,[])
                turns=PRIOR+[{'question':phrase,'query':r['query'],'status':'done','answer':r['answer']}]
                self.assertEqual(chat.resolve_query('А почему?',turns)['anchor'],PRIOR[0]['question'])
    def test_demonstrative_case_forms_keep_topic_without_new_local_subject(self):
        for phrase in ('Можно ли из этих реплик заключить, что опыт уже проверен?',
                       'Можно ли на этой позиции остановиться?',
                       'А что в этом сообщении?', 'Что имелось в виду в этих предложениях?'):
            with self.subTest(phrase=phrase):
                q=chat.resolve_query(phrase,PRIOR);self.assertEqual(q['intent'],'followup')
                self.assertEqual(q['anchor'],PRIOR[0]['question'])
    def test_discussion_author_query_does_not_force_assignment_anchor(self):
        corpus=[chunk('d'+str(i),text='Маяк: выдуманное обсуждение') for i in range(6)]
        a=chunk('a','assignment',13,text='Условие выдуманного задания о маяке');a['vector']=[0.,1.]+[0.]*1022;corpus.append(a)
        selected,trace=chat.retrieve_all(corpus,'Что Лев Невский советовал о маяке в дне13?',V)
        self.assertNotIn('a',[c['chunk_id'] for c in selected])

if __name__=='__main__':unittest.main()
