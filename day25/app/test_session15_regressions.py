"""Regression checks for retrieval misses observed in the 15-turn live run."""
import unittest

from conversation import build_context
from temporal import RANGE, interpret


class Session15Regressions(unittest.TestCase):
    def setUp(self):
        self.state = {'version': 2, 'goal': 'Разобраться в RAG по дням 21–24',
                      'clarifications': ['Я новичок'], 'constraints': ['Без кода']}

    def test_course_day_range_is_not_calendar_range(self):
        query = 'А где тут векторы помогают?\nТема продолжения: Разобраться в RAG по дням 21–24\nЯ новичок'
        self.assertIsNone(RANGE.search(query))
        self.assertFalse(interpret(query, [])['enabled'])
        for calendar in ('с 1 по 2 октября', '1–2 октября', '2026-10-01–2026-10-02'):
            with self.subTest(calendar=calendar):
                self.assertIsNotNone(RANGE.search(calendar))

    def test_short_followups_use_current_task_state(self):
        for question in ('И что именно пользователь должен сообщить ему сначала?',
                         'Значит, если я выберу другое время, то нарушу условие?',
                         'Сменим цель: нужен короткий показ работы. Какие три действия продемонстрировать?'):
            with self.subTest(question=question):
                context = build_context(question, self.state, [], 'public')
                self.assertEqual(context['search_rule'], 'task_state_and_substantive_user_question')
                self.assertIn(self.state['goal'], context['search_query'])

    def test_explicit_current_day_keeps_priority(self):
        context = build_context('Что было в задании дня 18?', self.state, [], 'public')
        self.assertEqual(context['search_rule'], 'explicit_current_day_or_period')
        self.assertEqual(context['search_query'], context['original_question'])

    def test_independent_eru_question_does_not_inherit_old_goal(self):
        question = 'Объясни ему индексы PostgreSQL.'
        context = build_context(question, self.state, [], 'public')
        self.assertEqual(context['search_rule'], 'current_question_only')
        self.assertEqual(context['search_query'], question)


if __name__ == '__main__':
    unittest.main()
