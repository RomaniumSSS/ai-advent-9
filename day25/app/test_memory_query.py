"""N1: ordered query analysis and actual fake Service transmission, no provider."""
import json
import unittest
from conversation import build_context, analyze_question, SEARCH_ADDITION_BYTES
import test_context as fixture


class QueryAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.state={'version':2,'goal':'Проверить RAG по дням 21–24',
                    'clarifications':['На Python'],'constraints':['Без кода']}

    def test_modes_precedence_and_ambiguity(self):
        for question in ('И что именно пользователь должен сообщить ему сначала?',
                         'Значит, если я выберу другое время, то нарушу условие?',
                         'Что мы сами выбрали для показа?', 'Подробнее'):
            c=build_context(question,self.state,[],'all')
            self.assertEqual(c['query_analysis']['mode'],'continuation')
            self.assertIn(self.state['goal'],c['search_query'])
            self.assertEqual(c['query_analysis']['task_state_version'],2)
            self.assertEqual(c['query_analysis']['used_fields'],
                             ['task_state.goal','task_state.clarifications[0]','task_state.constraints[0]'])
        for question in ('Составь итоговый план изучения PostgreSQL с нуля',
                         'Составь итоговый план переезда в Берлин',
                         'Найди обсуждения курса о размере чанков'):
            c=build_context(question,self.state,[],'all')
            self.assertEqual(c['query_analysis']['mode'],'new_topic')
            self.assertEqual(c['search_query'],question)
            self.assertEqual(c['query_analysis']['used_fields'],[])
        for question in ('Для нашей текущей цели, но только день 18',
                         'Для нашей текущей цели за 01.10.2026.',
                         'Для нашей текущей цели только обсуждения'):
            c=build_context(question,self.state,[],'all')
            self.assertEqual(c['query_analysis']['mode'],'explicit_filter')
            self.assertEqual(c['search_query'],question)
        empty=dict(self.state,goal='',clarifications=[],constraints=[])
        c=build_context('А это?',empty,[],'public')
        self.assertEqual(c['query_analysis']['mode'],'ambiguous')
        self.assertTrue(c['query_analysis']['clarification_needed'])
        self.assertEqual(c['search_query'],'А это?')
        c=build_context('А это?',dict(empty,constraints=['Без кода']),[],'public')
        self.assertEqual(c['query_analysis']['mode'],'ambiguous')
        self.assertEqual(c['query_analysis']['used_fields'],[])

    def test_new_topic_followup_does_not_reintroduce_old_task(self):
        state=dict(self.state,goal='Напоминалка по заданию дня 18',clarifications=['SQLite'])
        anchor={'id':'postgres','scope':'public','status':'verified','task_state_version':2,
                'question':'Что такое PostgreSQL?','answer':{'answer':'ASSISTANT_ONLY'}}
        c=build_context('Подробнее о его индексах.',state,[anchor],'public')
        self.assertIn('PostgreSQL',c['search_query'])
        self.assertNotIn('дня 18',c['search_query'])
        self.assertNotIn('SQLite',c['search_query'])
        self.assertEqual(c['query_analysis']['used_fields'],['user_anchor.question'])
        self.assertEqual(c['query_analysis']['state_policy'],'independent_user_anchor_only')
        c=build_context('Подробнее для нашей текущей цели.',state,[anchor],'public')
        self.assertIn(state['goal'],c['search_query'])
        self.assertNotIn('PostgreSQL',c['search_query'])
        self.assertIsNone(c['search_anchor_request_id'])
        anchor.update(id='day22',question='Что требуется в задании дня 22?')
        c=build_context('А дальше?',state,[anchor],'public')
        self.assertIn('дня 22',c['search_query'])
        self.assertNotIn('дня 18',c['search_query'])
        self.assertNotIn('SQLite',c['search_query'])
        c=build_context('Для нашей текущей цели?',state,[anchor],'public')
        self.assertIn('дня 18',c['search_query'])
        self.assertNotIn('дня 22',c['search_query'])

    def test_anchor_filter_conflicts_cover_day_date_and_scope(self):
        anchor={'id':'anchor','scope':'public','status':'verified','task_state_version':2,
                'question':'Что требуется в задании дня 22?'}
        for goal in ('Обсуждения от 30.09.2026','Задание дня 18','Только публичные задания'):
            c=build_context('Подробнее.',dict(self.state,goal=goal),[anchor],'public')
            self.assertEqual(c['query_analysis']['used_fields'],['user_anchor.question'])
            self.assertNotIn(goal,c['search_query'])
        state=dict(self.state,goal='Задание дня 22',clarifications=[],constraints=['Без кода'])
        c=build_context('Подробнее.',state,[anchor],'public')
        self.assertIn(state['goal'],c['search_query'])
        self.assertIn('Без кода',c['search_query'])
        anchor['question']='Обсуждения за 01.10.2026.'
        c=build_context('Подробнее.',state,[anchor],'public')
        self.assertNotIn(state['goal'],c['search_query'])
        anchor['question']='Только обсуждения курса'
        c=build_context('Подробнее.',dict(state,goal='Только публичные задания'),[anchor],'public')
        self.assertNotIn('публичные',c['search_query'])

    def test_field_diagnostics_match_budget_and_allowed_state(self):
        state=dict(self.state,goal='г'*500,clarifications=['ц'*500,'д'*500],constraints=['к'*500])
        c=build_context('Подробнее',state,[],'public')
        self.assertLessEqual(len(c['search_query'].split('Тема продолжения: ',1)[1].encode()),SEARCH_ADDITION_BYTES)
        for field in c['query_analysis']['used_fields']:
            if field.endswith('goal'):self.assertIn(state['goal'],c['search_query'])
        self.assertNotIn('task_state.clarifications[1]',c['query_analysis']['used_fields'])
        old={'id':'old','scope':'all','status':'verified','task_state_version':1,
             'question':'OLD 29.09.2026','answer':{'answer':'ASSISTANT_ONLY'}}
        c=build_context('Подробнее',self.state,[old],'public')
        self.assertNotIn('OLD',c['search_query'])
        self.assertNotIn('ASSISTANT_ONLY',c['search_query'])


class QueryServiceTest(unittest.TestCase):
    setUp=fixture.ContextTest.setUp
    tearDown=fixture.ContextTest.tearDown

    def test_fresh_search_snapshot_transmission_and_cancelled_constraint(self):
        self.service.update_task_state(self.a,{'goal':'План задания дня 18',
            'clarifications':['SQLite'],'constraints':['Без кода']},0)
        first=self.service.ask(self.a,'n1-first','Подробнее','public')
        self.assertEqual(first['status'],'verified')
        self.service.update_task_state(self.a,{'goal':'Изучить RAG',
            'clarifications':[],'constraints':[]},1)
        second=self.service.ask(self.a,'n1-second','А это?','public')
        self.assertEqual(second['status'],'verified')
        self.assertEqual(len(self.search_calls),2)
        self.assertNotIn('SQLite',self.search_calls[-1][0])
        self.assertNotIn('Без кода',self.search_calls[-1][0])
        c=second['conversation']
        self.assertEqual(c['query_analysis']['task_state_version'],second['task_state_version'])
        self.assertIsNone(c['search_anchor_request_id'])
        envelope=json.loads(self.generate_calls[-1]['messages'][1]['content'])
        self.assertEqual(envelope['query_analysis'],c['query_analysis'])
        self.assertEqual(envelope['task_state'],second['task_state'])
        self.assertEqual(second['generation']['transmitted_chunk_ids'],['c1'])
        self.assertIn(fixture.CHUNK['text'],envelope['fresh_rag_context'])
        other=self.service.ask(self.b,'n1-other','А это?','public')
        self.assertEqual(other['conversation']['query_analysis']['mode'],'ambiguous')
        self.assertNotIn('Изучить RAG',self.search_calls[-1][0])


if __name__=='__main__':unittest.main()
