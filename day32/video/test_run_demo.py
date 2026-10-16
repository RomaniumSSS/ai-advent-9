"""Офлайн guards записи: адрес публикации, budget/error исходы; без GitHub/API."""
import tempfile
import json
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from run_demo import cleanup_resources, history_row, watcher, write, outcome, push_target, scenario_status, source_for, CASES
from review import Store


class RecorderGuards(unittest.TestCase):
    def test_publish_address_is_pinned(self):
        self.assertEqual(push_target('owner/lesson', 'day32-demo'),
                         ('https://github.com/owner/lesson.git', 'HEAD:refs/heads/day32-demo'))
        for repository in ('https://other/repo', '../owner/repo', 'owner/repo/extra', 'owner/repo;evil'):
            with self.assertRaises(ValueError):
                push_target(repository, 'day32-demo')
        for branch in ('', 'main', 'master'):
            with self.assertRaises(ValueError):
                push_target('owner/lesson', branch)

    def test_real_store_blocked_row_without_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d)
            try:
                ident, created = store.claim('unaffordable', 1, .5)
                self.assertFalse(created)
                row = store.reports()[0]
                self.assertIsNone(row['report'])
                result = outcome('upper', 'a'*40, row, 'rag')
                self.assertEqual(result['trace_id'], ident)
                self.assertEqual(result['status'], 'budget_blocked')
                self.assertEqual(result['mode'], 'rag')
                self.assertEqual(result['findings'], [])
                self.assertEqual(scenario_status([result]), 'stopped_budget')
            finally:
                store.db.close()

    def test_poll_retry_is_separate_from_single_provider_call(self):
        from cli import fixture
        from review import Fixture, GitSnapshot
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'output'
            output.mkdir()
            state = Path(d) / 'state'
            repo, meta = fixture(Path(d) / 'fixture')
            snapshot = GitSnapshot.build(repo, 'offline/fixture', 1, meta['base'], meta['head'])
            write(output / 'control.json', {'head':meta['head'], 'modes':['rag']})
            provider = Fixture()
            calls = []
            class CountedProvider:
                name = 'offline fixture'
                def __call__(self, messages):
                    calls.append(1)
                    return provider(messages)
            sleeps = []
            def bounded_sleep(_):
                sleeps.append(1)
                if len(sleeps) == 3:
                    (output / 'stop').touch()
            args = SimpleNamespace(output=str(output), state=str(state), budget=.5,
                                   pr_repo='offline/fixture', pr_number=1)
            with patch('run_demo.poll', side_effect=[ValueError('transient read'), [snapshot], [snapshot]]), \
                 patch('run_demo.OpenRouter', return_value=CountedProvider()), \
                 patch('run_demo.time.sleep', side_effect=bounded_sleep):
                watcher(args)
            self.assertEqual(len(calls), 1)
            events = [json.loads(line) for line in (output/'events.jsonl').read_text().splitlines()]
            self.assertEqual(sum(e['event']=='read_retry' for e in events), 1)
            self.assertEqual(next(e for e in events if e['event']=='read_retry')['phase'], 'poll_fetch_snapshot')
            self.assertFalse(next(e for e in events if e['event']=='dedupe')['new'])
            store = Store(state)
            try:
                self.assertEqual(len(store.reports()), 1)
                self.assertEqual(store.reports()[0]['status'], 'complete')
            finally:
                store.db.close()

    def test_history_requires_existing_error_or_limited(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'отсутствует'):
                history_row(d, 'a'*32)
            with self.assertRaisesRegex(ValueError, '32 hex'):
                history_row(d, '../escape')
            store = Store(d)
            try:
                ident, _ = store.claim('historical', 0, 0)
                store.finish(ident, {'status':'error', 'error':'original provider failure'})
                self.assertEqual(history_row(d, ident)['report']['error'], 'original provider failure')
                store.finish(ident, {'status':'complete'})
                with self.assertRaisesRegex(ValueError, 'error/limited'):
                    history_row(d, ident)
            finally:
                store.db.close()

    def test_errors_cannot_be_completed(self):
        self.assertEqual(scenario_status([{'status':'complete'}, {'status':'error'}]),
                         'scenario_finished_with_errors')
        self.assertEqual(scenario_status([{'status':'error'}, {'status':'budget_blocked'}]),
                         'stopped_budget')
        self.assertEqual(scenario_status([{'status':'complete'}, {'status':'limited'}]),
                         'scenario_completed')

    def test_mutations_are_independent_and_compile(self):
        baseline = (Path(__file__).resolve().parents[1] / 'target/git_tool.py').read_text()
        for case in CASES:
            value = source_for(baseline, case, 'offline')
            compile(value, 'target.py', 'exec')
            self.assertEqual(value.count('Учебный прогон'), 1)
            self.assertEqual('limit < 10:' in value, case in ('upper', 'injection'))
            self.assertEqual('not isinstance(limit, int)' in value, case == 'bool')
            self.assertEqual("'log', '-5'" in value, case == 'ignored')


class CleanupGuards(unittest.IsolatedAsyncioTestCase):
    async def test_context_and_video_failures_still_close_other_resources(self):
        context = Mock(close=AsyncMock(side_effect=RuntimeError('context failed')))
        video = Mock(path=AsyncMock(side_effect=RuntimeError('video failed')))
        browser = Mock(close=AsyncMock())
        playwright = Mock(stop=AsyncMock())
        child = Mock()
        raw, errors = await cleanup_resources(context, video, browser, playwright, [child])
        self.assertIsNone(raw)
        self.assertEqual([e['resource'] for e in errors], ['context', 'video'])
        browser.close.assert_awaited_once()
        playwright.stop.assert_awaited_once()
        child.terminate.assert_called_once()
        child.wait.assert_called_once_with(timeout=10)

    async def test_child_timeout_escalates_to_kill(self):
        import subprocess
        child = Mock()
        child.wait.side_effect = [subprocess.TimeoutExpired('owned child', 10), 0]
        raw, errors = await cleanup_resources(None, None, None, None, [child])
        self.assertEqual(errors, [])
        child.kill.assert_called_once()
        self.assertEqual(child.wait.call_count, 2)


if __name__ == '__main__':
    unittest.main()
