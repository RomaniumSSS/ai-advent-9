"""Целевые бесплатные проверки нового eval-runner; модель не вызывается."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from day31.eval import qwen_quality as q
from day31.eval.compare_models import QUESTIONS
from day31.provider import OpenRouterProvider

PLAN_DIR = Path(__file__).resolve().parent/'final-reviewed'


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.cases = q.load_cases()
        self.plan = json.loads((PLAN_DIR/'plan.json').read_text())
        self.rows = [json.loads((PLAN_DIR/(c['id']+'-input.json')).read_text()) for c in self.cases]

    def test_ten_unique_and_literal_paired_questions(self):
        self.assertEqual(len(self.cases), 10)
        questions = {c['id']: c['question'] for c in self.cases}
        for case_id, question in QUESTIONS:
            if case_id in ('Q6', 'T3'):
                self.assertEqual(questions[case_id], question)
        self.assertNotIn('P1', questions)
        original = json.loads((q.ROOT/'eval/cases.json').read_text())['cases']
        for case in original:
            self.assertEqual(questions[case['id']], case['question'])

    def test_actual_input_has_no_rubric_and_preserves_system_and_profile(self):
        for case, row in zip(self.cases, self.rows):
            request = row['actual_input']
            context = json.loads(request['messages'][1]['content'])
            self.assertEqual(set(context), {'question', 'sources', 'git_context'})
            self.assertEqual(context, row['context'])
            self.assertEqual(request['messages'][0]['content'], q.SYSTEM)
            self.assertNotIn('rubric', context)
            self.assertNotIn(case['rubric'][0], request['messages'][1]['content'])
            self.assertEqual(request['model'], 'qwen/qwen3.8-max-0902')
            self.assertEqual(request['max_tokens'], 4096)
            self.assertEqual(request['extra_body'], {'provider': {'only': ['alibaba/us-east-1'], 'allow_fallbacks': False, 'require_parameters': True}, 'reasoning': {'effort': 'low', 'exclude': True}})
            self.assertEqual(q.request_reserve(q.PROFILE, request), row['request_reserve_usd'])

    def test_top5_and_empty_rag_are_not_replaced(self):
        class Index:
            def search(_, question, limit):
                self.assertEqual(limit, 5)
                return []
        class Mcp:
            last_discovery = {'tools': ['git_context']}
            def read(_): return {'branch': 'test'}
        row = q.assemble(self.cases[:1], Index(), Mcp())[0]
        self.assertFalse(row['model_eligible'])
        self.assertIsNone(row['actual_input'])
        self.assertIsNone(row['request_reserve_usd'])

    def test_readonly_budget_does_not_mutate_or_create(self):
        before = q.SHARED_LEDGER.read_bytes()
        budget = q.read_budget()
        self.assertEqual(q.SHARED_LEDGER.read_bytes(), before)
        self.assertEqual(budget['entries'], self.plan['budget_before']['entries'])
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp)/'never-created.sqlite3'
            with self.assertRaises(FileNotFoundError): q.read_budget(missing)
            self.assertFalse(missing.exists())

    def test_total_budget_shortfall_keeps_all_ten(self):
        total = sum(r['request_reserve_usd'] for r in self.rows)
        self.assertEqual(total, self.plan['series_reserve_ceiling_usd'])
        projection = q.budget_projection(total, self.plan['budget_before'])
        self.assertFalse(projection['fits_current_budget'])
        self.assertAlmostEqual(projection['additional_limit_needed_usd'], total-self.plan['budget_before']['remaining_usd'])

    def gates(self):
        return (patch.object(q, 'assemble', return_value=copy.deepcopy(self.rows)),
                patch.object(q, 'independent_git', return_value=self.plan['git']))

    def test_execute_budget_refusal_before_provider_or_ledger(self):
        assemble, git = self.gates()
        with tempfile.TemporaryDirectory() as tmp, assemble, git, patch.object(q, 'read_budget', return_value=self.plan['budget_before']), patch.object(q, 'OpenRouterProvider') as provider, patch.object(q, 'BudgetLedger') as ledger, patch.object(q, 'check_endpoint') as preflight:
            output = Path(tmp)/'run'
            with self.assertRaisesRegex(ValueError, 'не помещается'):
                q.execute(PLAN_DIR, output, self.cases, key='test-only', budget_usd=.50)
            provider.assert_not_called(); ledger.assert_not_called(); preflight.assert_not_called()
            self.assertFalse(output.exists())

    def test_changed_context_refused_before_any_reservation(self):
        altered = copy.deepcopy(self.rows)
        altered[0]['context']['git_context']['branch'] = 'invented-main'
        with tempfile.TemporaryDirectory() as tmp, patch.object(q, 'assemble', return_value=altered), patch.object(q, 'OpenRouterProvider') as provider, patch.object(q, 'BudgetLedger') as ledger:
            with self.assertRaisesRegex(ValueError, 'top5/Git изменились'):
                q.execute(PLAN_DIR, Path(tmp)/'run', self.cases, key='test-only', budget_usd=.50)
            provider.assert_not_called(); ledger.assert_not_called()

    def test_changed_runner_refused_before_any_reservation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(q, 'runner_fingerprint', return_value='changed'), patch.object(q, 'OpenRouterProvider') as provider, patch.object(q, 'BudgetLedger') as ledger:
            with self.assertRaisesRegex(ValueError, 'runner изменился'):
                q.execute(PLAN_DIR, Path(tmp)/'run', self.cases, key='test-only', budget_usd=.50)
            provider.assert_not_called(); ledger.assert_not_called()

    def test_execute_fake_transport_ten_distinct_contexts_and_existing_guards(self):
        sent = []; reserved = []; finished = []
        ledger = SimpleNamespace(reserve=lambda trace, amount: reserved.append((trace, amount)), finish=lambda *args: finished.append(args))
        def create(**request):
            sent.append(request)
            context = json.loads(request['messages'][1]['content'])
            text = 'Фикстура транспорта, не оценка качества.'
            if len(sent) == 7:
                text += '\n```json\n{"type":"function","function":{"name":"get_recent_commits"}}\n```'
            content = json.dumps({'status': 'unknown' if len(sent) == 5 else 'ok', 'text': text, 'source_ids': [context['sources'][0]['id']]})
            return SimpleNamespace(id='fake-'+str(len(sent)), choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=content, refusal=None))], usage=None)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        def provider_factory(key, actual_ledger, **kwargs):
            self.assertIs(actual_ledger, ledger)
            return OpenRouterProvider(key, ledger, client=client, **kwargs)
        enough = {**self.plan['budget_before'], 'limit_usd': 1.10, 'remaining_usd': 1.10-self.plan['budget_before']['charged_usd']}
        assemble, git = self.gates()
        with tempfile.TemporaryDirectory() as tmp, assemble, git, patch.object(q, 'read_budget', return_value=enough), patch.object(q, 'BudgetLedger', return_value=ledger) as constructor, patch.object(q, 'OpenRouterProvider', side_effect=provider_factory), patch.object(q, 'check_endpoint', return_value={'fake': True}):
            summary = q.execute(PLAN_DIR, Path(tmp)/'run', self.cases, key='test-only', budget_usd=1.10)
            self.assertEqual(summary['status'], 'complete')
            constructor.assert_called_once_with(q.SHARED_LEDGER, 1.10)
            self.assertEqual(len(sent), 10); self.assertEqual(len(reserved), 10); self.assertEqual(len(finished), 10)
            self.assertEqual(len({r[0] for r in reserved}), 10)
            self.assertEqual(sent, [r['actual_input'] for r in self.rows])
            self.assertEqual([c['case_id'] for c in summary['calls']], [c['id'] for c in self.cases])

    def test_inner_json_accepts_real_json_and_rejects_pseudocode(self):
        self.assertEqual(q.inner_json_check('```json\n{"type":"function","function":{}}\n```')['status'], 'PASS')
        self.assertEqual(q.inner_json_check('```json\n{"type":"function","function":{...}}\n```')['status'], 'FAIL')
        self.assertEqual(q.inner_json_check('Описание без примера')['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main(verbosity=2)
