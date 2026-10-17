"""Офлайн robustness: настоящие файлы, сценарные ответы; семантика live отдельно."""
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from core import HERE, MAX_FILE, Sandbox, run
from mock_model import MockModel
from model import OpenRouterModel, ModelResponseError
from budget import Budget
from robustness_runner import SessionCap

FIXTURES = HERE / "robustness/fixtures"


class Scripted(MockModel):
    def __init__(self, replies):
        super().__init__()
        self.replies = iter(replies)

    def complete(self, *args, **kwargs):
        return {"message": next(self.replies)}


def call(name, args, ident="one"):
    return {"id": ident, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.parent = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def box(self, fixture="distributed"):
        return Sandbox(self.parent, "box", fixture=FIXTURES / fixture)

    def test_distributed_search_is_literal_not_semantic_oracle(self):
        box = self.box()
        hits = box.execute("search_text", {"query": "prepare_invite"})
        self.assertTrue(hits["ok"])
        self.assertIn("notes/example.txt", {h["path"] for h in hits["data"]})
        # Alias-вызовы требуют чтения импортов, буквальный поиск их не классифицирует.
        self.assertIn('return make(email, role="admin")', box.read("commands/signup.py"))
        self.assertEqual(box.execute("search_text", {"query": "not_present_742"})["data"], [])
        self.assertEqual(box.diff(), "")

    def test_binary_nonutf_large_search_retains_hits_and_marks_incomplete(self):
        fixture = self.parent / "fixture"
        shutil.copytree(FIXTURES / "distributed", fixture)
        (fixture / "empty.txt").write_bytes(b"")
        (fixture / "binary.bin").write_bytes(b"\0prepare_invite")
        (fixture / "bad.txt").write_bytes(b"\xff")
        (fixture / "large.txt").write_text("x" * (MAX_FILE + 1))
        box = Sandbox(self.parent, "box", fixture=fixture)
        self.assertEqual(box.diff(), "")
        result = box.execute("search_text", {"query": "prepare_invite"})
        self.assertFalse(result["ok"])
        self.assertEqual({p["path"] for p in result["data"]["skipped"]}, {"binary.bin", "bad.txt", "large.txt"})
        self.assertTrue(result["data"]["matches"])
        for name in ["binary.bin", "bad.txt", "large.txt"]:
            self.assertFalse(box.execute("read_file", {"path": name})["ok"])
        self.assertEqual(box.execute("read_file", {"path": "empty.txt"})["data"], "")
        self.assertTrue(box.execute("write_file", {"path": "README.md", "content": "new\n"})["ok"])
        self.assertIn("+new", box.diff())

    def test_source_symlink_never_copied_as_external_bytes(self):
        source = self.parent / "fixture"
        shutil.copytree(FIXTURES / "distributed", source)
        outside = self.parent / "private.txt"
        outside.write_text("PRIVATE SENTINEL")
        (source / "external.txt").symlink_to(outside)
        box = Sandbox(self.parent, "box", fixture=source)
        self.assertTrue((box.root / "external.txt").is_symlink())
        self.assertNotIn("external.txt", box.baseline)
        self.assertFalse(box.execute("read_file", {"path": "external.txt"})["ok"])
        self.assertNotIn("PRIVATE SENTINEL", json.dumps(box.execute("search_text", {"query": "PRIVATE"})))
        self.assertEqual(outside.read_text(), "PRIVATE SENTINEL")

    def test_repeat_noop_and_fresh_reset_exact_bytes(self):
        content = (FIXTURES / "distributed/README.md").read_text()
        writes = {"tool_calls": [call("write_file", {"path": "README.md", "content": content})]}
        first = run("noop", Scripted([writes, {"content": "готово"}]), self.parent, fixture=FIXTURES / "distributed")
        self.assertEqual(first["diff"], "")
        Path(first["sandbox"], "README.md").write_text("changed")
        second = run("reset", Scripted([{"content": "ответ"}]), self.parent, fixture=FIXTURES / "distributed")
        self.assertNotEqual(first["sandbox"], second["sandbox"])
        self.assertEqual(Path(second["sandbox"], "README.md").read_text(), content)
        self.assertEqual(second["diff"], "")

    def test_truncation_malformed_and_step_stop(self):
        box = self.box()
        for i in range(80):
            (box.root / f"notes/{i}.txt").write_text("hit " * 100)
        result = box.execute("search_text", {"query": "hit"})
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["data"]), 24000)
        scripted = Scripted([{"tool_calls": [None, call("read_file", {"path": "../outside"}, "bad"), call("read_file", {"path": "/etc/passwd"}, "absolute")]}, {"content": "успех"}])
        result = run("negative", scripted, self.parent)
        self.assertEqual(len(result["events"]), 3)
        self.assertEqual(result["status"], "error")
        result = run("limit", Scripted([{"tool_calls": [call("list_files", {})]}]), self.parent, max_steps=1)
        self.assertEqual(result["reason"], "step_limit")

    def test_new_empty_file_visible_and_repeat_write_is_noop(self):
        box = self.box()
        args = {"path": "reports/empty.txt", "content": ""}
        self.assertTrue(box.execute("write_file", args)["ok"])
        first = box.execute("show_diff", {})
        self.assertTrue(first["ok"])
        self.assertIn("diff --git a/reports/empty.txt b/reports/empty.txt", first["data"])
        self.assertIn(f"new file mode {(box.root / 'reports/empty.txt').stat().st_mode:o}", first["data"])
        self.assertEqual((box.root / "reports/empty.txt").read_bytes(), b"")
        self.assertTrue(box.execute("write_file", args)["ok"])
        self.assertEqual(box.execute("show_diff", {}), first)
        box.baseline["reports/empty.txt"] = b""
        self.assertEqual(box.diff(), "")

    def test_preserved_symlink_does_not_hide_readme_diff(self):
        fixture = self.parent / "fixture"
        shutil.copytree(FIXTURES / "distributed", fixture)
        outside = self.parent / "private.txt"
        outside.write_text("PRIVATE SENTINEL")
        (fixture / "external.txt").symlink_to(outside)
        model = Scripted([{"tool_calls": [call("write_file", {"path": "README.md", "content": "updated\n"})]}, {"content": "готово"}])
        with patch.object(Path, "read_bytes", autospec=True, side_effect=Path.read_bytes) as reads:
            result = run("update", model, self.parent, fixture=fixture)
        self.assertEqual(result["status"], "completed")
        self.assertIn("+updated", result["diff"])
        self.assertTrue(all(c.args[0] != outside and c.args[0].name != "external.txt" for c in reads.call_args_list))
        self.assertEqual(outside.read_text(), "PRIVATE SENTINEL")
        self.assertTrue(Path(result["sandbox"], "external.txt").is_symlink())

    def test_final_diff_failure_is_error_and_changed_symlink_rejected(self):
        with patch.object(Sandbox, "diff", side_effect=ValueError("denied")):
            result = run("test", Scripted([{"content": "готово"}]), self.parent)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["reason"], "diff_error")
        self.assertIn("не подтверждён", result["answer"])
        box = self.box()
        (box.root / "extra").symlink_to(self.parent / "missing-target")
        self.assertFalse(box.execute("show_diff", {})["ok"])

    def test_operator_cap_counts_unknown_holds_without_real_ledger(self):
        ledger = self.parent / "temporary-test-only.sqlite3"
        Budget.initialize(str(ledger))
        budget = Budget(str(ledger))
        hold = budget.reserve("unknown-test", 0.2)
        budget.settle(hold, None)
        capped = SessionCap(budget, 0.3)
        with self.assertRaisesRegex(RuntimeError, "operator_accounted_cap"):
            capped.reserve("rejected", 0.11)
        reservation = capped.reserve("accepted", 0.09)
        capped.settle(reservation, 0.01)
        with budget.connect() as db:
            self.assertAlmostEqual(db.execute("SELECT SUM(COALESCE(actual,reserved)) FROM reservations").fetchone()[0], 0.21)
            self.assertEqual(db.execute("SELECT reserved,actual FROM reservations WHERE id=?", (hold,)).fetchone(), (0.2, None))

    def test_malformed_envelopes_preserve_usage_identity_and_holds(self):
        class Budget:
            def reserve(self, *args):
                return "id"
            def settle(self, *args):
                self.settled = args
        budget = Budget()
        good = {"model": OpenRouterModel.name, "provider": "Alibaba", "choices": [{"finish_reason": "stop", "message": {"content": "ok"}}]}
        for cost in [float("nan"), float("inf"), -1, True, "0.1", None]:
            model = OpenRouterModel(budget, "fake", transport=lambda *args: json.dumps({**good, "usage": {"cost": cost}}).encode())
            model.complete([], [], run_id="test", timeout=1)
            self.assertEqual(budget.settled, ("id", None))
        for patch in [{"choices": []}, {"choices": [{}]}, {"choices": [{"message": []}]}]:
            data = {**good, **patch, "usage": {"cost": 0.002}}
            model = OpenRouterModel(budget, "fake", transport=lambda *args: json.dumps(data).encode())
            with self.assertRaises(ModelResponseError) as caught:
                model.complete([], [], run_id="test", timeout=1)
            self.assertEqual(caught.exception.usage, {"cost": 0.002})
            self.assertEqual(caught.exception.metadata["actual_model"], model.name)
            self.assertEqual(budget.settled, ("id", 0.002))
        for field in ["model", "provider"]:
            data = {**good, "usage": {"cost": 0.003}}
            del data[field]
            model = OpenRouterModel(budget, "fake", transport=lambda *args: json.dumps(data).encode())
            with self.assertRaises(ModelResponseError) as caught:
                model.complete([], [], run_id="test", timeout=1)
            self.assertEqual(caught.exception.reason, "response_identity_missing")
            self.assertEqual(budget.settled, ("id", 0.003))


if __name__ == "__main__":
    unittest.main(verbosity=2)
