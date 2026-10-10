"""Выдуманные грамматические аналоги, не corpus/gold questions."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_chat_core as chat

PRIOR=[{'question':'Как устроена выдуманная библиотека?','status':'done','query':{'intent':'new_topic'},
        'answer':{'answer':'Синтетический прежний ответ.','sources':[]}}]

class LocalAntecedents(unittest.TestCase):
    def test_numbered_local_object_is_self_contained_not_previous_anchor(self):
        question='Какой порядок описан в разделе 37 и нужна ли для этого раздела отдельная схема?'
        for history in ([],PRIOR):
            with self.subTest(has_history=bool(history)):
                query=chat.resolve_query(question,history)
                self.assertEqual(query['intent'],'new_topic');self.assertIsNone(query['anchor'])
                self.assertEqual(query['search_query'],question)

    def test_named_definition_is_self_contained_despite_это_их(self):
        question='В инструкции куб, шар и конус — это три детали одной фигуры? Объясни их различие по описанию.'
        for history in ([],PRIOR):
            with self.subTest(has_history=bool(history)):
                query=chat.resolve_query(question,history)
                self.assertEqual(query['intent'],'new_topic');self.assertIsNone(query['anchor'])
                self.assertEqual(query['search_query'],question)

    def test_true_deictic_ellipsis_and_unrelated_number_keep_history(self):
        for question in ('А почему?', 'Что именно фиксируется в этот момент?', 'Как за 5 минут проверить его?',
                         'А он — это кто?', 'Какая схема нужна для этого раздела?'):
            for history in ([],PRIOR):
                with self.subTest(question=question,has_history=bool(history)):
                    query=chat.resolve_query(question,history)
                    self.assertEqual(query['intent'],'followup' if history else 'clarification')
                    if history:self.assertEqual(query['anchor'],PRIOR[0]['question'])

    def test_multi_author_followup_does_not_become_local_definition(self):
        turns=[{**PRIOR[0],'answer':{'answer':'Синтетический ответ.','sources':[{'excerpts':[{'author':'Автор А'},{'author':'Автор Б'}]}]}}]
        self.assertEqual(chat.resolve_query('А он — это кто?',turns)['intent'],'clarification')
        self.assertEqual(chat.resolve_query('Новая тема: какие формы описаны?',turns)['intent'],'new_topic')

    def test_common_demonstrative_inflections_keep_history_or_clarify(self):
        for question in ('А что в том разделе?', 'А что в той части?', 'Как действовать в таком случае?',
                         'Расскажи о той схеме', 'Как работает эта схема?', 'Расскажи про такие фигуры'):
            for history in ([],PRIOR):
                with self.subTest(question=question,has_history=bool(history)):
                    query=chat.resolve_query(question,history)
                    self.assertEqual(query['intent'],'followup' if history else 'clarification')
                    if history:self.assertEqual(query['anchor'],PRIOR[0]['question'])

    def test_demonstrative_local_reference_still_overrides_previous_topic(self):
        for determiner in ('этого','того','такого'):
            question=f'Что показано в разделе 37 и нужна ли для {determiner} раздела отдельная схема?'
            for history in ([],PRIOR):
                with self.subTest(determiner=determiner,has_history=bool(history)):
                    query=chat.resolve_query(question,history)
                    self.assertEqual(query['intent'],'new_topic');self.assertIsNone(query['anchor'])
                    self.assertEqual(query['search_query'],question)
        question='В разделе Z описан порядок. Что проверяют в таком разделе?'
        for history in ([],PRIOR):
            query=chat.resolve_query(question,history)
            self.assertEqual(query['intent'],'new_topic');self.assertEqual(query['search_query'],question)

    def test_volume_noun_and_conditional_particle_are_not_bare_anaphora(self):
        for question in ('Сколько страниц содержит том 3?', 'Если файл пустой, то как записать новый текст?'):
            for history in ([],PRIOR):
                with self.subTest(question=question,has_history=bool(history)):
                    query=chat.resolve_query(question,history)
                    self.assertEqual(query['intent'],'new_topic');self.assertIsNone(query['anchor'])
                    self.assertEqual(query['search_query'],question)

    def test_collective_plural_and_object_reference_preserve_whole_topic(self):
        for authors in ([],['Нина'],['Нина','Вера']):
            sources=[{'excerpts':[{'author':author} for author in authors]}]
            for anchor,question in (('Сравни предложения Нины и Веры','Что они предложили?'),
                                    ('Сравни предложения Нины и Веры','Какие из их предложений описаны?'),
                                    ('Сравни выдуманные детали A и B','Что из них применили?'),
                                    ('Сравни выдуманные детали A и B','Как пользоваться ими?'),
                                    ('Сравни выдуманные детали A и B','Что делают с ними?')):
                with self.subTest(authors=len(authors),anchor=anchor,question=question):
                    prior=[{**PRIOR[0],'question':anchor,'answer':{'answer':'Синтетический ответ.','sources':sources}}]
                    query=chat.resolve_query(question,prior)
                    self.assertEqual(query['intent'],'followup');self.assertEqual(query['anchor'],anchor)
                    self.assertIn(anchor,query['search_query'])
                    self.assertEqual(chat.resolve_query(question,[])['intent'],'clarification')

    def test_singular_unspecified_participant_still_clarifies_multiple_authors(self):
        prior=[{**PRIOR[0],'answer':{'answer':'Синтетический ответ.','sources':[{'excerpts':[{'author':'Нина'},{'author':'Вера'}]}]}}]
        self.assertEqual(chat.resolve_query('Что он предложил?',prior)['intent'],'clarification')

if __name__=='__main__':unittest.main()
