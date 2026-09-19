#!/usr/bin/env python3
"""Короткая сохраняемая FSM работы над Днём 15."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATE = Path(__file__).with_name("state.json")
NEXT = {
    "PLAN": "IMPLEMENT",
    "IMPLEMENT": "VERIFY",
    "VERIFY": "DEMO",
    "DEMO": "REVIEW",
    "REVIEW": "LIVE_VALIDATION",
    "LIVE_VALIDATION": "CI",
    "CI": "DONE",
}
REPAIR_FROM = {"VERIFY", "DEMO", "REVIEW", "LIVE_VALIDATION", "CI"}


class MachineError(ValueError):
    """Ожидаемый отказ перехода."""


def read_state(path: Path = STATE) -> dict:
    state = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "version", "phase", "status", "current_step", "expected_action",
        "plan_approval", "artifacts", "blocker", "history",
    }
    if set(state) != required:
        raise MachineError("state.json: неверный набор полей")
    if state["phase"] not in {*NEXT, "DONE"}:
        raise MachineError("state.json: неизвестный этап")
    if state["status"] not in {"active", "paused", "done"}:
        raise MachineError("state.json: неизвестный статус")
    if (state["phase"] == "DONE") != (state["status"] == "done"):
        raise MachineError("state.json: этап и статус не согласованы")
    if type(state["version"]) is not int or state["version"] < 1:
        raise MachineError("state.json: неверная версия")
    if any(not isinstance(state[key], str) or not state[key].strip()
           for key in ("current_step", "expected_action")):
        raise MachineError("state.json: пустой текущий шаг или действие")
    if state["plan_approval"] is not None and (
        not isinstance(state["plan_approval"], str) or not state["plan_approval"].strip()
    ):
        raise MachineError("state.json: неверное утверждение плана")
    if not isinstance(state["artifacts"], dict) or not isinstance(state["history"], list):
        raise MachineError("state.json: неверные артефакты или история")
    return state


def write_state(state: dict, path: Path = STATE) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".state.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def evidence_path(value: str) -> str:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise MachineError(f"файл доказательства не найден в проекте: {value}")
    return str(path.relative_to(ROOT))


def verify_ci_evidence(artifact: str) -> None:
    if artifact != "day15/results/ci-report.json":
        raise MachineError("CI требует day15/results/ci-report.json")
    report = json.loads((ROOT / artifact).read_text(encoding="utf-8"))
    if report.get("conclusion") != "success":
        raise MachineError("CI не завершился успешно")
    url = report.get("run_url", "")
    if not isinstance(url, str) or not url.startswith(
        "https://github.com/RomaniumSSS/ai-advent-9/actions/runs/"
    ):
        raise MachineError("CI report не содержит ссылку на GitHub Actions run")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if report.get("head_sha") != head:
        raise MachineError("CI run относится к другому commit SHA")


def verify_live_evidence(artifact: str) -> None:
    if artifact != "day15/results/live-run-01/report.json":
        raise MachineError("LIVE_VALIDATION требует day15/results/live-run-01/report.json")
    report = json.loads((ROOT / artifact).read_text(encoding="utf-8"))
    if report.get("status") != "passed" or report.get("provider_calls", 0) < 10:
        raise MachineError("живой прогон не завершён или слишком короткий")
    if report.get("provider") != "DeepInfra" or report.get("mock_calls", -1) != 0:
        raise MachineError("требуется реальный DeepInfra без mock-вызовов")
    calls = report.get("calls", [])
    if len(calls) != report["provider_calls"] or any(
        call.get("status") != "completed" or call.get("provider") != "DeepInfra"
        or call.get("finish_reason") != "stop" or call.get("reported_cost_usd") is None
        for call in calls
    ):
        raise MachineError("в отчёте есть неполные или неподтверждённые вызовы")
    if len(report.get("tasks", [])) < 3 or any(
        task.get("final_stage") != "done" for task in report["tasks"]
    ) or not report.get("checks") or any(
        check.get("passed") is not True for check in report["checks"]
    ):
        raise MachineError("в отчёте нет трёх завершённых задач и всех успешных проверок")


def transition(state: dict, action: str, evidence: str | None = None) -> dict:
    if state["status"] != "active":
        raise MachineError("машина на паузе или завершена")
    phase = state["phase"]
    if action == "advance":
        if phase not in NEXT:
            raise MachineError("из DONE переходов нет")
        if phase == "PLAN" and not state["plan_approval"]:
            raise MachineError("план реализации ещё не утверждён Романом")
        artifact = evidence_path(evidence or "")
        if phase == "CI":
            verify_ci_evidence(artifact)
        if phase == "LIVE_VALIDATION":
            verify_live_evidence(artifact)
        target = NEXT[phase]
        state["artifacts"][phase.lower()] = artifact
        state["phase"] = target
        state["status"] = "done" if target == "DONE" else "active"
        state["blocker"] = None
        state["current_step"] = {
            "IMPLEMENT": "Реализовать day15/ по утверждённому плану",
            "VERIFY": "Проверить переходы, восстановление и регрессии",
            "DEMO": "Записать воспроизводимое видео",
            "REVIEW": "Проверить diff, обходы и доказательства",
            "LIVE_VALIDATION": "Прогнать длинный сценарий через реальный OpenRouter",
            "CI": "Проверить GitHub Actions run после пуша",
            "DONE": "Работа проверена, материалы готовы",
        }[target]
        state["expected_action"] = "нет" if target == "DONE" else f"Завершить {target} с файлом доказательства"
    elif action == "repair":
        if phase not in REPAIR_FROM:
            raise MachineError("возврат на исправление разрешён только из VERIFY, DEMO, REVIEW, LIVE_VALIDATION, CI")
        if not evidence or not evidence.strip():
            raise MachineError("нужна конкретная причина возврата")
        target = "IMPLEMENT"
        state["phase"] = target
        state["blocker"] = evidence.strip()
        state["current_step"] = "Исправить замечание и повторить затронутые проверки"
        state["expected_action"] = "Завершить IMPLEMENT с файлом доказательства"
        artifact = evidence.strip()
    else:
        raise MachineError(f"неизвестное действие: {action}")
    state["version"] += 1
    state["history"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "from": phase, "action": action, "to": target, "evidence": artifact,
    })
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "check", "approve-plan", "advance", "repair", "pause", "resume"))
    parser.add_argument("--evidence", help="Файл результата, ссылка на утверждение или причина возврата")
    args = parser.parse_args()
    try:
        state = read_state()
        if args.action == "check":
            evidence_path(state["artifacts"]["plan"])
            print("ok: состояние корректно, план существует")
            return
        if args.action == "status":
            print(json.dumps(state, ensure_ascii=False, indent=2))
            return
        if args.action == "approve-plan":
            if state["phase"] != "PLAN" or state["status"] != "active":
                raise MachineError("план можно утвердить только в активном PLAN")
            if not args.evidence or not args.evidence.strip():
                raise MachineError("нужна ссылка или дата явного утверждения плана Романом")
            state["plan_approval"] = args.evidence.strip()
            state["version"] += 1
            state["history"].append({
                "time": datetime.now(timezone.utc).isoformat(),
                "from": "PLAN", "action": "approve-plan", "to": "PLAN",
                "evidence": args.evidence.strip(),
            })
        elif args.action in {"pause", "resume"}:
            expected = "active" if args.action == "pause" else "paused"
            if state["phase"] == "DONE" or state["status"] != expected:
                raise MachineError(f"{args.action} сейчас недопустим")
            state["status"] = "paused" if args.action == "pause" else "active"
            state["version"] += 1
            state["history"].append({
                "time": datetime.now(timezone.utc).isoformat(),
                "from": state["phase"], "action": args.action,
                "to": state["phase"], "evidence": args.evidence or "",
            })
        else:
            state = transition(state, args.action, args.evidence)
        write_state(state)
        print(f"ok: {state['phase']} / {state['status']} / v{state['version']}")
    except (MachineError, OSError, ValueError) as error:
        parser.exit(2, f"отказ: {error}\n")


if __name__ == "__main__":
    main()
