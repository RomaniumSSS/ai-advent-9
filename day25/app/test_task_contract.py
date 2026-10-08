"""Day25 goal-execution spec: answer_requirements распознаёт вопрос об исполнении цели."""
import unittest
from task_contract import answer_requirements


class GoalExecutionTest(unittest.TestCase):
    def setUp(self):
        self.goal_state={'goal':'Разобраться в RAG по дням 21–24','clarifications':[],'constraints':[]}
        self.empty_state={'goal':'','clarifications':[],'constraints':[]}

    def test_steps_question_with_goal_sets_flag_and_guidance(self):
        for question in ('Какие шаги мне сделать дальше?','С чего мне начать?',
                         'Что мне делать по этому заданию?','Какой план действий?'):
            requirements=answer_requirements(question,self.goal_state)
            self.assertTrue(requirements['goal_execution_requested'],question)
            self.assertIn('task_state.goal',requirements['guidance'])
            self.assertIn('конкретные действия пользователя',requirements['guidance'])

    def test_same_question_without_goal_keeps_flag_false_and_guidance_unchanged(self):
        with_goal=answer_requirements('Какие шаги мне сделать дальше?',self.goal_state)
        without_goal=answer_requirements('Какие шаги мне сделать дальше?',self.empty_state)
        self.assertFalse(without_goal['goal_execution_requested'])
        self.assertNotIn('конкретные действия пользователя',without_goal['guidance'])
        self.assertNotEqual(with_goal['guidance'],without_goal['guidance'])

    def test_non_execution_question_with_goal_keeps_flag_false(self):
        requirements=answer_requirements('Что такое чанк?',self.goal_state)
        self.assertFalse(requirements['goal_execution_requested'])
        self.assertNotIn('конкретные действия пользователя',requirements['guidance'])

    def test_sentence_and_point_limits_survive_goal_execution_guidance(self):
        state=dict(self.goal_state,constraints=['Не более двух предложений','Не более трёх пунктов'])
        requirements=answer_requirements('Какие шаги мне сделать дальше?',state)
        self.assertTrue(requirements['goal_execution_requested'])
        self.assertEqual(requirements['max_sentences'],2)
        self.assertEqual(requirements['max_points'],3)
        self.assertIn('не более 2 предложений',requirements['guidance'])
        self.assertIn('нумерованный список',requirements['guidance'])
        self.assertIn('конкретные действия пользователя',requirements['guidance'])


if __name__=='__main__':unittest.main()
