"""Синтетические RED для независимых A1–A5 и нового контекста, не holdout."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_chat_core as chat
from test_full_chat_contract import chunk,V


def prior(question='Что предлагали о маяках?',authors=()):
    return {'question':question,'status':'done','query':{'intent':'new_topic'},
            'answer':{'answer':'UNVERIFIED_ASSISTANT_FACT_DO_NOT_REUSE',
                      'sources':[{'excerpts':[{'author':a} for a in authors]}]}}


def attributed(cid,author,text,vector=V):
    return chunk(cid,text=text,vector=vector,members=[{'id':cid,'author':author}],
                 source_sections=[{'start_char':0,'end_char':len(text),'member_ids':[cid]}])


class QualityV3(unittest.TestCase):
    def test_a1_one_named_subject_overrides_foreign_topic(self):
        for question in ('QuantaX — почему его выбирали?', 'Реестр — зачем это проверять?',
                         'Veloria: какие у него ограничения?'):
            for history in ([],[prior()]):
                with self.subTest(question=question,history=bool(history)):
                    q=chat.resolve_query(question,history)
                    self.assertEqual(q['intent'],'new_topic');self.assertIsNone(q['anchor'])
                    self.assertEqual(q['search_query'],question)
    def test_a2_pronoun_cases_preserve_object_topic(self):
        for question in ('Какие у него ограничения?', 'Как к нему обращаться?',
                         'А что в ней сохраняют?', 'Какие у неё ограничения?'):
            with self.subTest(question=question):
                q=chat.resolve_query(question,[prior()])
                self.assertEqual(q['intent'],'followup');self.assertEqual(q['anchor'],prior()['question'])
    def test_a3_chain_keeps_intermediate_constraint_and_skips_ack(self):
        history=[prior()]
        question='Что они советовали именно о проверке лампы?'
        q=chat.resolve_query(question,history);history.append({**prior(question),'query':q})
        ack=chat.resolve_query('Понял, спасибо',history);history.append({**prior('Понял, спасибо'),'query':ack})
        q=chat.resolve_query('Почему это предлагали?',history)
        self.assertIn('проверке лампы',q['search_query']);self.assertNotIn('Понял, спасибо',q['search_query'])
        self.assertNotIn('UNVERIFIED_ASSISTANT',q['search_query'])
        switch=chat.resolve_query('Новая тема: что обсуждали о библиотеке?',history)
        self.assertNotIn('лампы',switch['search_query']);self.assertIsNone(switch['anchor'])
    def test_a4_explicit_fullname_resolves_shared_firstname(self):
        h=[prior('Что предлагали участники о маяках?',('Иван Петров','Иван Сидоров'))]
        q=chat.resolve_query('А что он, Иван Петров, советовал?',h)
        self.assertNotEqual(q['intent'],'clarification');self.assertIn('Иван Петров',q['search_query'])
    def test_a5_inflected_surnames_and_cross_script_shared_names(self):
        corpus=[attributed('p','Иван Петров','Петров предложил лампу.'),attributed('s','Иван Сидоров','Сидоров предложил датчик.')]
        self.assertEqual(set(chat.requested_authors(corpus,'Сравни советы Ивана Петрова и Ивана Сидорова')),{'Иван Петров','Иван Сидоров'})
        corpus=[attributed('n','Lev Nevskii','Невский предложил лампу.'),attributed('p','Lev Petrovskii','Петровский предложил датчик.')]
        self.assertEqual(chat.requested_authors(corpus,'Что предложил Лев Невский?'),['Lev Nevskii'])
    def test_fullname_does_not_select_nested_short_name(self):
        corpus=[attributed('a','Иван','Привет.'),attributed('b','Ivan Petrov','Привет.'),attributed('c','Иван Сидоров','Привет.')]
        self.assertEqual(chat.requested_authors(corpus,'Что предложил Иван Петров?'),['Ivan Petrov'])
    def test_prompt_uses_only_topic_user_questions_not_assistant_facts(self):
        history=[prior()];question='Что именно предложили?';q=chat.resolve_query(question,history)
        messages,selected,sent,trace=chat.build_evidence_context(question,q,history,[chunk('d')])
        body=json.loads(messages[1]['content'])
        self.assertNotIn('UNVERIFIED_ASSISTANT',messages[1]['content'])
        self.assertTrue(sent);self.assertIn(history[0]['question'],messages[1]['content'])
        self.assertTrue(all('answer' not in t for t in sent))
    def test_ack_does_not_take_one_of_three_topic_history_slots(self):
        history=[prior()]
        for question in ('Что они советовали о лампе?','Понял','Как проверить это?','Спасибо'):
            q=chat.resolve_query(question,history);history.append({**prior(question),'query':q})
        question='А почему?';q=chat.resolve_query(question,history)
        messages,selected,sent,trace=chat.build_evidence_context(question,q,history,[chunk('d')])
        self.assertEqual([t['question'] for t in sent],[history[0]['question'],history[1]['question'],history[3]['question']])
    def test_author_subclause_prioritizes_rare_evidence_over_generic_topic(self):
        low=[.7]+[0.0]*1023;low[1]=(1-.7**2)**.5
        corpus=[attributed('p'+str(i),'Иван Петров','Общие советы о памяти и лампах в архиве.') for i in range(6)]
        corpus.append(attributed('rare','Иван Петров','Предложил контрольную проверку первоисточника.',low))
        corpus.append(attributed('s','Иван Сидоров','Описал трудности с памятью.',V))
        selected,trace=chat.retrieve_all(corpus,'Какую трудность с памятью описал Иван Сидоров и какую проверку по первоисточнику предложил Иван Петров?',V)
        self.assertIn('rare',[c['chunk_id'] for c in selected]);self.assertIn('s',[c['chunk_id'] for c in selected])
    def test_name_case_variants_do_not_survive_as_topical_terms(self):
        corpus=[attributed('p','Иван Петров','Петров предложил лампу.'),attributed('s','Иван Сидоров','Сидоров предложил датчик.')]
        selected,trace=chat.retrieve_all(corpus,'Сравни советы Ивана Петрова и Ивана Сидорова о лампах',V)
        self.assertIn('query_terms',trace)
        self.assertFalse(any(t.startswith(('ivan','pet','sidor')) for t in trace['query_terms']))
    def test_multiple_examples_widen_primary_author_coverage(self):
        corpus=[attributed('summary'+str(i),'Сводчик','Что обсуждали: ZETA инструменты. Назови разные примеры использования.',V) for i in range(6)]
        low=[.78]+[0.0]*1023;low[1]=(1-.78**2)**.5
        corpus.extend(attributed('report'+str(i),'Участник '+str(i),'Недавно использовал ZETA для выдуманной задачи '+str(i)+'.',low) for i in range(4))
        selected,trace=chat.retrieve_all(corpus,'Назови три разных примера использования ZETA участниками.',V)
        self.assertGreater(len(selected),5)
        self.assertGreaterEqual(sum(c['chunk_id'].startswith('report') for c in selected),3)
        self.assertEqual(trace['eligible_count'],len(corpus))
    def test_named_current_participant_keeps_explicit_branch_reference(self):
        history=[prior('Что спрашивал Никита о доступе через сетевой шлюз?',('Никита','Майя Климова'))]
        q=chat.resolve_query('А что Майя ответила в этой ветке насчёт API ZETA?',history)
        self.assertEqual(q['intent'],'followup');self.assertIn('сетевой шлюз',q['search_query'])
        self.assertIn('Майя',q['search_query']);self.assertNotIn('UNVERIFIED_ASSISTANT',q['search_query'])
    def test_wider_input_keeps_output_reference_limit_and_scope(self):
        corpus=[attributed('s'+str(i),'Участник '+str(i),'Выдуманный текст '+str(i)) for i in range(8)]
        answer=chat.materialize({'answer':'Синтетический подтверждённый ответ','source_refs':['S8']},corpus,'a'*32)
        self.assertEqual(answer['sources'][0]['chunk_id'],'s7')
        with self.assertRaises(ValueError):
            chat.materialize({'answer':'Синтетический ответ','source_refs':['S'+str(i) for i in range(1,7)]},corpus,'a'*32)

if __name__=='__main__':unittest.main()
