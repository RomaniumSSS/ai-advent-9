"""Офлайн-регрессии семантических проверок recorder."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import run, SYSTEM
from mock_model import MockModel
from run_demo import verify, delivery_warnings


class RecorderChecks(unittest.TestCase):
    def test_io_policy_and_delivery_regression(self):
        for policy in ["не доказывает", "docstring", "теле реализации", "сверяй", "I/O"]:
            self.assertIn(policy, SYSTEM)
        for claim in ["dry_run=False, т.е. реальная отправка с ролью member", "API отправляет письмо", "Приглашение отправляется"]:
            self.assertTrue(delivery_warnings(claim))
        for fact in ["Реальной отправки нет", "Реальная отправка не реализована", "Функция не отправляет письмо", "Письмо не отправляется", "Возвращается sent=True, I/O отсутствует"]:
            self.assertEqual(delivery_warnings(fact), [])

    def test_warning_is_not_human_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            search = run("Найди API", MockModel(), Path(temp))
            for extra in ["dry_run=False, т.е. реальная отправка с ролью member", "Устаревший README утверждает: «отправляет приглашение». В реализации реальной отправки нет."]:
                sample = copy.deepcopy(search)
                sample["answer"] += "\n" + extra
                checks = verify(sample, 0)
                self.assertTrue(checks["semantic_warnings"])
                self.assertEqual(checks["human_semantic_acceptance"], "required")

    def test_both_goals_and_missing_callsite(self):
        with tempfile.TemporaryDirectory() as temp:
            search = run("Найди API", MockModel(), Path(temp))
            self.assertTrue(verify(search, 0)["definition_and_two_callsites"])
            broken = copy.deepcopy(search)
            event = next(e for e in broken["events"] if e["tool"] == "search_text")
            event["result"]["data"] = [h for h in event["result"]["data"] if h["path"] != "src/cli.py"]
            with self.assertRaises(AssertionError):
                verify(broken, 0)
            update = run("Обнови README", MockModel(), Path(temp))
            self.assertTrue(verify(update, 1)["readme_facts_and_real_diff"])
            (Path(update["sandbox"]) / "README.md").write_text("send_invite(email) --team default")
            with self.assertRaises(AssertionError):
                verify(update, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
