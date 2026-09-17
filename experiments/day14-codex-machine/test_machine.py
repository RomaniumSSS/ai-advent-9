#!/usr/bin/env python3
"""Офлайн-проверки внешней машины; сеть и Codex не вызываются."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("day14_machine", HERE / "machine.py")
assert SPEC and SPEC.loader
machine = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = machine
SPEC.loader.exec_module(machine)


class MachineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Machine Test",
                "-c",
                "user.email=machine@example.invalid",
                "commit",
                "--allow-empty",
                "-qm",
                "baseline",
            ],
            cwd=self.root,
            check=True,
        )
        self.config = self.root / "machine"
        self.config.mkdir()
        (self.root / "day14").mkdir()
        for name in ("profile", "task", "invariants", "acceptance", "phase-policies"):
            (self.config / f"{name}.json").write_text(
                (HERE / f"{name}.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
        task = json.loads((self.config / "task.json").read_text(encoding="utf-8"))
        task["scope"]["control_paths"] = ["machine/"]
        (self.config / "task.json").write_text(json.dumps(task), encoding="utf-8")
        policies = json.loads((self.config / "phase-policies.json").read_text(encoding="utf-8"))
        policies["VALIDATION"]["cwd"] = "machine/runs/validation-work"
        policies["VALIDATION"]["allowed_write_paths"] = ["machine/runs/"]
        (self.config / "phase-policies.json").write_text(json.dumps(policies), encoding="utf-8")
        self.state_path = self.config / "state.json"
        self.state_path.write_text((HERE / "state.json").read_text(encoding="utf-8"), encoding="utf-8")
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state.update(
            {
                "phase": "PLANNING",
                "status": "active",
                "retry_cycles": 0,
                "artifacts": {},
                "checks": {},
                "violations": [],
                "blockers": [],
                "history": [],
            }
        )
        state["baseline_ref"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        state["baseline_manifest"] = "machine/baseline.json"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        self.paths = machine.Paths.discover(self.root, self.config, self.state_path)
        (self.config / "baseline.json").write_text(
            json.dumps(machine.workspace_snapshot(self.root)), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_result(self, **overrides: object) -> Path:
        plan = self.config / "plan.md"
        plan.write_text("План", encoding="utf-8")
        result = {
            "phase": "PLANNING",
            "outcome": "pass",
            "summary": "План готов",
            "artifacts": {"plan": "machine/plan.md"},
            "checks": {"planning_complete": True},
            "violations": [],
            "blockers": [],
            "next_action": "Перейти к реализации",
        }
        result.update(overrides)
        path = self.config / "result.json"
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return path

    def test_prompt_contains_all_four_control_layers(self) -> None:
        prompt = machine.prompt_text(self.paths)
        for heading in ("ЗАДАЧА", "ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ", "ИНВАРИАНТЫ", "ТЕКУЩЕЕ СОСТОЯНИЕ"):
            self.assertIn(heading, prompt)
        self.assertIn("roman-day13-codex", prompt)
        self.assertIn("Будущие VALIDATION", prompt)

    def test_illegal_phase_jump_is_rejected_without_state_change(self) -> None:
        before = self.state_path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(machine.MachineError, "разрешён только переход"):
            machine.transition(self.paths, "DONE", self.write_result())
        self.assertEqual(before, self.state_path.read_text(encoding="utf-8"))

    def test_failed_result_requires_failure_evidence(self) -> None:
        state = machine.load_json(self.state_path)
        state["phase"] = "VALIDATION"
        machine.dump_json_atomic(self.state_path, state)
        result = self.write_result(
            phase="VALIDATION", outcome="fail", violations=[], blockers=[]
        )
        with self.assertRaisesRegex(machine.MachineError, "violation или blocker"):
            machine.transition(self.paths, "EXECUTION", result)

    def test_validation_must_pass_through_live_validation(self) -> None:
        state = machine.load_json(self.state_path)
        state.update({"phase": "VALIDATION", "status": "active"})
        machine.dump_json_atomic(self.state_path, state)
        with self.assertRaisesRegex(machine.MachineError, "разрешён только переход"):
            machine.transition(
                self.paths,
                "REVIEW",
                self.write_result(phase="VALIDATION"),
            )

    def test_reopen_done_clears_stale_acceptance(self) -> None:
        state = machine.load_json(self.state_path)
        state.update({
            "phase": "DONE",
            "status": "done",
            "artifacts": {"plan": "machine/plan.md", "review_report": "machine/old-review.md"},
            "checks": {"planning_complete": True, "independent_review": True},
        })
        machine.dump_json_atomic(self.state_path, state)
        updated = machine.reopen_machine(self.paths, "EXECUTION", "Добавлен live gate")
        self.assertEqual("EXECUTION", updated["phase"])
        self.assertEqual("active", updated["status"])
        self.assertEqual({"planning_complete": True}, updated["checks"])
        self.assertEqual({"plan": "machine/plan.md"}, updated["artifacts"])
        self.assertEqual("reopen", updated["history"][-1]["event"])

    def test_unblock_requires_blocked_and_starts_new_repair_cycle(self) -> None:
        with self.assertRaisesRegex(machine.MachineError, "заблокированной"):
            machine.unblock_machine(self.paths, "Новый контракт")

        state = machine.load_json(self.state_path)
        state.update({
            "phase": "BLOCKED",
            "status": "blocked",
            "retry_cycles": 3,
            "artifacts": {"plan": "machine/plan.md", "live_report": "machine/old-live.md"},
            "checks": {"planning_complete": True, "live_quality_threshold": False},
            "violations": ["quality"],
            "blockers": ["нужно решение"],
        })
        machine.dump_json_atomic(self.state_path, state)
        updated = machine.unblock_machine(self.paths, "Структурный state-envelope")
        self.assertEqual("EXECUTION", updated["phase"])
        self.assertEqual("active", updated["status"])
        self.assertEqual(0, updated["retry_cycles"])
        self.assertEqual({"planning_complete": True}, updated["checks"])
        self.assertEqual({"plan": "machine/plan.md"}, updated["artifacts"])
        self.assertEqual([], updated["violations"])
        self.assertEqual([], updated["blockers"])
        self.assertEqual("unblock", updated["history"][-1]["event"])

    def test_protected_day_change_is_detected(self) -> None:
        protected = machine.protected_changes(
            ["day12/agent.py", "day13/agent.py", "experiments/day13-codex-machine/state.json"],
            ["day01/", "day12/"],
        )
        self.assertEqual(["day12/agent.py"], protected)

    def test_change_outside_allowed_scope_is_detected(self) -> None:
        unexpected = machine.unexpected_changes(
            ["README.md", "day13/agent.py", ".agents/skills/day13-quality-machine/SKILL.md"],
            ["day13/", ".agents/skills/day13-quality-machine/"],
        )
        self.assertEqual(["README.md"], unexpected)

    def test_valid_planning_transition_persists_evidence(self) -> None:
        updated = machine.transition(self.paths, "EXECUTION", self.write_result())
        self.assertEqual("EXECUTION", updated["phase"])
        self.assertTrue(updated["checks"]["planning_complete"])
        self.assertEqual(1, len(updated["history"]))

    def test_current_phase_artifact_replaces_stale_attempt(self) -> None:
        old = self.config / "old.md"
        new = self.config / "new.md"
        old.write_text("old", encoding="utf-8")
        new.write_text("new", encoding="utf-8")
        state = machine.load_json(self.state_path)
        state.update({
            "phase": "VALIDATION",
            "artifacts": {"test_report": "machine/old.md"},
        })
        machine.dump_json_atomic(self.state_path, state)
        result = self.write_result(
            phase="VALIDATION",
            outcome="fail",
            artifacts={"test_report": "machine/new.md"},
            checks={"offline_tests": False},
            violations=["offline_tests"],
        )
        updated = machine.transition(self.paths, "EXECUTION", result)
        self.assertEqual("machine/new.md", updated["artifacts"]["test_report"])

    def test_done_gate_rechecks_evidence_from_previous_phases(self) -> None:
        for filename in ("plan.md", "implementation.md", "tests.md", "visual.md", "review.md"):
            (self.config / filename).write_text(filename, encoding="utf-8")
        state = machine.load_json(self.state_path)
        state.update(
            {
                "phase": "REVIEW",
                "artifacts": {
                    "plan": "machine/plan.md",
                    "implementation": "machine/implementation.md",
                    "test_report": "machine/tests.md",
                },
                "checks": {"planning_complete": True, "implementation_complete": True},
            }
        )
        machine.dump_json_atomic(self.state_path, state)
        result = self.write_result(
            phase="REVIEW",
            summary="Review завершён",
            artifacts={
                "visual_report": "machine/visual.md",
                "review_report": "machine/review.md",
            },
            checks={"visual_check": True, "independent_review": True},
            next_action="Завершить",
        )
        with self.assertRaisesRegex(machine.MachineError, "scope_guard"):
            machine.transition(self.paths, "DONE", result)

    def test_third_failed_validation_blocks_more_retries(self) -> None:
        state = machine.load_json(self.state_path)
        state.update({"phase": "VALIDATION", "retry_cycles": 0})
        machine.dump_json_atomic(self.state_path, state)
        failed = self.write_result(
            phase="VALIDATION",
            outcome="fail",
            summary="Тест не прошёл",
            checks={"offline_tests": False},
            violations=["offline_tests"],
            next_action="Исправить тест",
        )
        first = machine.transition(self.paths, "EXECUTION", failed)
        self.assertEqual("EXECUTION", first["phase"])
        self.assertEqual(1, first["retry_cycles"])

        first["phase"] = "VALIDATION"
        machine.dump_json_atomic(self.state_path, first)
        second = machine.transition(self.paths, "EXECUTION", failed)
        self.assertEqual("EXECUTION", second["phase"])
        self.assertEqual(2, second["retry_cycles"])
        second["phase"] = "VALIDATION"
        machine.dump_json_atomic(self.state_path, second)
        third = machine.transition(self.paths, "EXECUTION", failed)
        self.assertEqual("BLOCKED", third["phase"])
        self.assertEqual("blocked", third["status"])
        self.assertEqual(3, third["retry_cycles"])

    def test_external_evidence_is_recorded_through_controller(self) -> None:
        report = self.config / "visual.md"
        report.write_text("Проверено в браузере", encoding="utf-8")
        updated = machine.record_evidence(
            self.paths,
            "visual_check",
            "visual_report",
            "machine/visual.md",
            "Три размера проверены",
        )
        self.assertTrue(updated["checks"]["visual_check"])
        self.assertEqual("machine/visual.md", updated["artifacts"]["visual_report"])
        self.assertEqual("evidence", updated["history"][-1]["event"])

    def test_codex_command_is_preview_only(self) -> None:
        preview = machine.codex_preview(self.paths)
        self.assertFalse(preview["executed"])
        self.assertEqual("codex", preview["argv"][0])
        self.assertEqual("read-only", preview["sandbox"])
        self.assertEqual([], preview["allowed_write_paths"])

    def test_execution_is_scoped_to_day14(self) -> None:
        state = machine.load_json(self.state_path)
        state["phase"] = "EXECUTION"
        machine.dump_json_atomic(self.state_path, state)
        spec = machine.codex_spec(self.paths)
        self.assertEqual("workspace-write", spec["sandbox"])
        self.assertEqual(["day14/"], spec["allowed_write_paths"])
        self.assertEqual((self.root / "day14").resolve(), Path(spec["cwd"]))

    def test_pause_resume_preserves_exact_work_point(self) -> None:
        before = machine.load_json(self.state_path)
        paused = machine.pause_machine(self.paths, "Проверка handoff")
        self.assertEqual("paused", paused["status"])
        for key in ("phase", "current_step", "expected_action"):
            self.assertEqual(before[key], paused[key])
        with self.assertRaisesRegex(machine.MachineError, "на паузе"):
            machine.prompt_text(self.paths)
        resumed = machine.resume_machine(self.paths)
        self.assertEqual("active", resumed["status"])
        for key in ("phase", "current_step", "expected_action"):
            self.assertEqual(before[key], resumed[key])

    def test_sync_policy_updates_work_point_without_reopening_done(self) -> None:
        policies = machine.load_json(self.config / "phase-policies.json")
        policies["DONE"] = {
            "current_step": "Завершено",
            "expected_action": "Ожидать",
        }
        machine.dump_json_atomic(self.config / "phase-policies.json", policies)
        state = machine.load_json(self.state_path)
        state.update({"phase": "DONE", "status": "done"})
        machine.dump_json_atomic(self.state_path, state)

        updated = machine.sync_policy(self.paths)

        self.assertEqual("DONE", updated["phase"])
        self.assertEqual("done", updated["status"])
        self.assertEqual("Завершено", updated["current_step"])
        self.assertEqual("Ожидать", updated["expected_action"])
        self.assertEqual("sync_policy", updated["history"][-1]["event"])

    def test_validation_can_write_only_to_ignored_scratch(self) -> None:
        state = machine.load_json(self.state_path)
        state["phase"] = "VALIDATION"
        machine.dump_json_atomic(self.state_path, state)
        spec = machine.codex_spec(self.paths)
        self.assertEqual("workspace-write", spec["sandbox"])
        self.assertEqual(
            ["machine/runs/"],
            spec["allowed_write_paths"],
        )
        self.assertTrue(Path(spec["cwd"]).is_dir())

    def test_snapshot_detects_change_to_existing_untracked_file(self) -> None:
        target = self.config / "existing.txt"
        target.write_text("before", encoding="utf-8")
        before = machine.workspace_snapshot(self.root)
        target.write_text("after", encoding="utf-8")
        after = machine.workspace_snapshot(self.root)
        self.assertEqual(["machine/existing.txt"], machine.snapshot_changes(before, after))


if __name__ == "__main__":
    unittest.main(verbosity=2)
