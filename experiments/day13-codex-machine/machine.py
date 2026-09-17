#!/usr/bin/env python3
"""Внешний контроллер этапов Codex для задания дня 13."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PHASES = ("PLANNING", "EXECUTION", "VALIDATION", "LIVE_VALIDATION", "REVIEW", "DONE", "BLOCKED")
GATE_ORDER = {"EXECUTION": 1, "VALIDATION": 2, "LIVE_VALIDATION": 3, "REVIEW": 4, "DONE": 5}
FORWARD = {
    "PLANNING": "EXECUTION",
    "EXECUTION": "VALIDATION",
    "VALIDATION": "LIVE_VALIDATION",
    "LIVE_VALIDATION": "REVIEW",
    "REVIEW": "DONE",
}
FAILURE_RETURN_PHASES = {"VALIDATION", "LIVE_VALIDATION", "REVIEW"}
REQUIRED_RESULT_KEYS = {
    "phase",
    "outcome",
    "summary",
    "artifacts",
    "checks",
    "violations",
    "blockers",
    "next_action",
}


class MachineError(RuntimeError):
    """Ожидаемая ошибка контракта машины."""


@dataclass(frozen=True)
class Paths:
    root: Path
    config: Path
    state: Path

    @classmethod
    def discover(
        cls,
        root: Path | None = None,
        config: Path | None = None,
        state: Path | None = None,
    ) -> "Paths":
        script_config = Path(__file__).resolve().parent
        repo_root = (root or script_config.parents[1]).resolve()
        config_dir = (config or script_config).resolve()
        state_path = (state or config_dir / "state.json").resolve()
        return cls(repo_root, config_dir, state_path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MachineError(f"Не найден файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MachineError(f"Некорректный JSON в {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MachineError(f"Верхний уровень {path} должен быть объектом JSON")
    return value


def dump_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def configs(paths: Paths) -> dict[str, dict[str, Any]]:
    return {
        name: load_json(paths.config / f"{name}.json")
        for name in ("profile", "task", "invariants", "acceptance", "phase-policies")
    }


def validate_state(state: dict[str, Any]) -> None:
    required = {
        "version",
        "phase",
        "status",
        "retry_cycles",
        "baseline_ref",
        "baseline_manifest",
        "current_step",
        "expected_action",
        "pause_reason",
        "artifacts",
        "checks",
        "violations",
        "blockers",
        "history",
    }
    missing = sorted(required - state.keys())
    if missing:
        raise MachineError(f"В state.json отсутствуют поля: {', '.join(missing)}")
    if state["phase"] not in PHASES:
        raise MachineError(f"Неизвестный этап: {state['phase']}")
    if state["status"] not in {"active", "paused", "done", "blocked"}:
        raise MachineError(f"Неизвестный status: {state['status']}")
    terminal_status = "done" if state["phase"] == "DONE" else "blocked" if state["phase"] == "BLOCKED" else None
    if terminal_status is not None and state["status"] != terminal_status:
        raise MachineError(
            f"Несогласованные phase/status: {state['phase']}/{state['status']}, ожидался {terminal_status}"
        )
    if terminal_status is None and state["status"] not in {"active", "paused"}:
        raise MachineError("рабочий этап должен быть active или paused")
    if not isinstance(state["current_step"], str) or not state["current_step"].strip():
        raise MachineError("current_step должен быть непустой строкой")
    if not isinstance(state["expected_action"], str) or not state["expected_action"].strip():
        raise MachineError("expected_action должен быть непустой строкой")
    if state["pause_reason"] is not None and not isinstance(state["pause_reason"], str):
        raise MachineError("pause_reason должен быть строкой или null")
    if not isinstance(state["retry_cycles"], int) or state["retry_cycles"] < 0:
        raise MachineError("retry_cycles должен быть неотрицательным целым")
    for key in ("artifacts", "checks"):
        if not isinstance(state[key], dict):
            raise MachineError(f"{key} должен быть объектом")
    for key in ("violations", "blockers", "history"):
        if not isinstance(state[key], list):
            raise MachineError(f"{key} должен быть массивом")


def validate_result(result: dict[str, Any], current_phase: str) -> None:
    missing = sorted(REQUIRED_RESULT_KEYS - result.keys())
    extra = sorted(result.keys() - REQUIRED_RESULT_KEYS)
    if missing or extra:
        details = []
        if missing:
            details.append(f"нет полей: {', '.join(missing)}")
        if extra:
            details.append(f"лишние поля: {', '.join(extra)}")
        raise MachineError("Некорректный phase result: " + "; ".join(details))
    if result["phase"] != current_phase:
        raise MachineError(
            f"Результат относится к {result['phase']}, текущий этап — {current_phase}"
        )
    if result["outcome"] not in {"pass", "fail"}:
        raise MachineError("outcome должен быть pass или fail")
    if not isinstance(result["summary"], str) or not result["summary"].strip():
        raise MachineError("summary должен быть непустой строкой")
    if not isinstance(result["next_action"], str) or not result["next_action"].strip():
        raise MachineError("next_action должен быть непустой строкой")
    if not isinstance(result["artifacts"], dict) or not all(
        isinstance(key, str) and (value is None or isinstance(value, str) and value)
        for key, value in result["artifacts"].items()
    ):
        raise MachineError("artifacts должен отображать строковые id в пути или null")
    if not isinstance(result["checks"], dict) or not all(
        isinstance(key, str) and (value is None or isinstance(value, bool))
        for key, value in result["checks"].items()
    ):
        raise MachineError("checks должен отображать строковые id в boolean или null")
    for key in ("violations", "blockers"):
        if not isinstance(result[key], list) or not all(
            isinstance(item, str) for item in result[key]
        ):
            raise MachineError(f"{key} должен быть массивом строк")
    if result["outcome"] == "pass" and (result["violations"] or result["blockers"]):
        raise MachineError("pass несовместим с violations или blockers")
    if result["outcome"] == "fail" and not (result["violations"] or result["blockers"]):
        raise MachineError("fail должен содержать хотя бы одно violation или blocker")


def resolve_artifact(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise MachineError(f"Артефакт выходит за корень репозитория: {relative}") from exc
    return path


def validate_artifacts(root: Path, artifacts: dict[str, str]) -> None:
    missing = [name for name, value in artifacts.items() if not resolve_artifact(root, value).exists()]
    if missing:
        raise MachineError(f"Не найдены артефакты: {', '.join(sorted(missing))}")


def run_git(root: Path, argv: list[str]) -> str:
    process = subprocess.run(
        ["git", *argv],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        raise MachineError(
            f"git {' '.join(argv)} завершился с кодом {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout


def changed_paths(root: Path, baseline_ref: str) -> list[str]:
    tracked = run_git(
        root, ["diff", "--no-renames", "--name-only", baseline_ref, "--"]
    ).splitlines()
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"]).splitlines()
    return sorted(set(filter(None, [*tracked, *untracked])))


def protected_changes(paths: list[str], protected_prefixes: list[str]) -> list[str]:
    return sorted(
        path
        for path in paths
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in protected_prefixes)
    )


def unexpected_changes(paths: list[str], allowed_prefixes: list[str]) -> list[str]:
    return sorted(
        path
        for path in paths
        if not any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in allowed_prefixes)
    )


def mechanical_check(paths: Paths) -> dict[str, Any]:
    cfg = configs(paths)
    state = load_json(paths.state)
    validate_state(state)
    manifest_path = resolve_artifact(paths.root, state["baseline_manifest"])
    baseline = load_json(manifest_path)
    changes = snapshot_changes(baseline, workspace_snapshot(paths.root))
    scope = cfg["task"]["scope"]
    protected = protected_changes(changes, scope["protected_paths"])
    unexpected = unexpected_changes(
        changes,
        [*scope["write_paths"], *scope["control_paths"], *scope.get("status_paths", [])],
    )
    return {
        "ok": not protected and not unexpected,
        "phase": state["phase"],
        "status": state["status"],
        "changed_paths": changes,
        "protected_changes": protected,
        "unexpected_changes": unexpected,
    }


def required_checks(acceptance: dict[str, Any], target: str) -> list[str]:
    target_order = GATE_ORDER[target]
    return [
        item["id"]
        for item in acceptance["checks"]
        if GATE_ORDER[item["gate"]] <= target_order
    ]


def required_artifacts(acceptance: dict[str, Any], target: str) -> list[str]:
    return [
        item["artifact"]
        for item in acceptance["checks"]
        if GATE_ORDER[item["gate"]] <= GATE_ORDER[target] and "artifact" in item
    ]


def prompt_text(paths: Paths) -> str:
    cfg = configs(paths)
    state = load_json(paths.state)
    validate_state(state)
    if state["status"] == "paused":
        raise MachineError(
            f"Машина на паузе: {state['pause_reason'] or 'причина не указана'}; сначала resume"
        )
    policy = cfg["phase-policies"].get(state["phase"])
    if policy is None:
        raise MachineError(f"Для этапа {state['phase']} нет исполняемой phase-policy")
    next_gate = FORWARD.get(state["phase"])
    gate_contract = {
        "current_phase": state["phase"],
        "proposed_transition": next_gate,
        "required_checks_now": required_checks(cfg["acceptance"], next_gate) if next_gate else [],
        "required_artifacts_now": required_artifacts(cfg["acceptance"], next_gate) if next_gate else [],
        "outcome_rule": (
            "Ставь pass, если выполнен именно текущий gate. Будущие VALIDATION, REVIEW, visual check "
            "или видео не являются причиной fail на более раннем этапе. Не записывай будущую работу "
            "в blockers или violations текущего pass; укажи её только в next_action."
        ),
    }
    sections = [
        ("РОЛЬ МАШИНЫ", "Ты — исполнитель текущего этапа. Предлагай результат; переход выполняет внешний валидатор."),
        ("РОЛЬ ЭТАПА", json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True)),
        ("ТЕКУЩИЙ GATE", json.dumps(gate_contract, ensure_ascii=False, indent=2, sort_keys=True)),
        ("ЗАДАЧА", json.dumps(cfg["task"], ensure_ascii=False, indent=2, sort_keys=True)),
        ("ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ", json.dumps(cfg["profile"], ensure_ascii=False, indent=2, sort_keys=True)),
        ("ИНВАРИАНТЫ", json.dumps(cfg["invariants"], ensure_ascii=False, indent=2, sort_keys=True)),
        ("КРИТЕРИИ ПРИЁМКИ", json.dumps(cfg["acceptance"], ensure_ascii=False, indent=2, sort_keys=True)),
        ("ТЕКУЩЕЕ СОСТОЯНИЕ", json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)),
        (
            "КОНТРАКТ ОТВЕТА",
            "Верни только JSON по schemas/phase-result.schema.json. Не объявляй переход выполненным и не меняй state.json вручную.",
        ),
    ]
    return "\n\n".join(f"## {title}\n{body}" for title, body in sections) + "\n"


def transition(paths: Paths, target: str, result_path: Path) -> dict[str, Any]:
    cfg = configs(paths)
    state = load_json(paths.state)
    validate_state(state)
    if state["status"] != "active":
        raise MachineError(f"Машина уже остановлена: {state['status']}")

    resolved_result = result_path.resolve()
    try:
        resolved_result.relative_to(paths.root)
    except ValueError as exc:
        raise MachineError(f"Phase result находится вне репозитория: {resolved_result}") from exc
    result = load_json(resolved_result)
    current = state["phase"]
    validate_result(result, current)
    check_report = mechanical_check(paths)
    supplied_checks = {key: value for key, value in result["checks"].items() if value is not None}
    supplied_artifacts = {key: value for key, value in result["artifacts"].items() if value is not None}
    merged_checks = {**state["checks"], **supplied_checks}
    # AICODE-NOTE: уже записанное внешним валидатором evidence авторитетнее
    # повторённого моделью пути; новый этап всё равно добавляет отсутствующий ключ.
    # AICODE-NOTE: result текущей фазы должен заменять устаревший одноимённый
    # artifact прошлой попытки; иначе failed live-02 оставлял ссылку на live-01.
    merged_artifacts = {**state["artifacts"], **supplied_artifacts}
    validate_artifacts(paths.root, merged_artifacts)

    if result["outcome"] == "fail":
        if current not in FAILURE_RETURN_PHASES:
            raise MachineError(f"Провал этапа {current} требует решения человека, автоматического возврата нет")
        if target != "EXECUTION":
            raise MachineError(f"Провал этапа {current} можно вернуть только в EXECUTION")
        retries = state["retry_cycles"] + 1
        max_retries = cfg["invariants"]["max_retry_cycles"]
        next_phase = "BLOCKED" if retries >= max_retries else "EXECUTION"
        next_status = "blocked" if next_phase == "BLOCKED" else "active"
    else:
        expected = FORWARD.get(current)
        if target != expected:
            raise MachineError(f"Из {current} разрешён только переход в {expected}, запрошен {target}")
        if not check_report["ok"]:
            details = []
            if check_report["protected_changes"]:
                details.append("защищённые пути: " + ", ".join(check_report["protected_changes"]))
            if check_report["unexpected_changes"]:
                details.append("пути вне scope: " + ", ".join(check_report["unexpected_changes"]))
            raise MachineError("Нарушена область изменений — " + "; ".join(details))
        missing_checks = [
            check for check in required_checks(cfg["acceptance"], target) if merged_checks.get(check) is not True
        ]
        if missing_checks:
            raise MachineError(f"Для {target} не пройдены проверки: {', '.join(missing_checks)}")
        missing_artifacts = [
            artifact
            for artifact in required_artifacts(cfg["acceptance"], target)
            if artifact not in merged_artifacts
        ]
        if missing_artifacts:
            raise MachineError(f"Для {target} нет артефактов: {', '.join(missing_artifacts)}")
        next_phase = target
        next_status = "done" if target == "DONE" else "active"
        retries = state["retry_cycles"]

    event = {
        "from": current,
        "to": next_phase,
        "outcome": result["outcome"],
        "summary": result["summary"],
        "next_action": result["next_action"],
    }
    next_policy = cfg["phase-policies"].get(next_phase, {})
    updated = {
        **state,
        "version": state["version"] + 1,
        "phase": next_phase,
        "status": next_status,
        "current_step": next_policy.get("current_step", "Ожидание решения человека"),
        "expected_action": next_policy.get("expected_action", "Разблокировать машину после решения"),
        "pause_reason": None,
        "retry_cycles": retries,
        "artifacts": merged_artifacts,
        "checks": merged_checks,
        "violations": result["violations"],
        "blockers": result["blockers"],
        "history": [*state["history"], event],
    }
    dump_json_atomic(paths.state, updated)
    return updated


def record_evidence(
    paths: Paths,
    check_id: str,
    artifact_id: str,
    artifact_path: str,
    summary: str,
) -> dict[str, Any]:
    cfg = configs(paths)
    state = load_json(paths.state)
    validate_state(state)
    if state["status"] != "active":
        raise MachineError(f"Машина уже остановлена: {state['status']}")
    acceptance_item = next(
        (item for item in cfg["acceptance"]["checks"] if item["id"] == check_id),
        None,
    )
    if acceptance_item is None:
        raise MachineError(f"Неизвестная проверка: {check_id}")
    if acceptance_item.get("artifact") != artifact_id:
        raise MachineError(
            f"Для {check_id} ожидается артефакт {acceptance_item.get('artifact')}, а не {artifact_id}"
        )
    resolved = resolve_artifact(paths.root, artifact_path)
    if not resolved.is_file():
        raise MachineError(f"Файл доказательства не найден: {artifact_path}")
    report = mechanical_check(paths)
    if not report["ok"]:
        raise MachineError("Нельзя записать evidence при нарушенном scope")
    updated = {
        **state,
        "version": state["version"] + 1,
        "checks": {**state["checks"], check_id: True},
        "artifacts": {**state["artifacts"], artifact_id: artifact_path},
        "history": [
            *state["history"],
            {
                "event": "evidence",
                "phase": state["phase"],
                "check": check_id,
                "artifact": artifact_path,
                "summary": summary,
            },
        ],
    }
    dump_json_atomic(paths.state, updated)
    return updated


def pause_machine(paths: Paths, reason: str) -> dict[str, Any]:
    state = load_json(paths.state)
    validate_state(state)
    if state["status"] != "active":
        raise MachineError(f"Пауза возможна только из active, сейчас {state['status']}")
    reason = reason.strip()
    if not reason:
        raise MachineError("Причина паузы не может быть пустой")
    updated = {
        **state,
        "version": state["version"] + 1,
        "status": "paused",
        "pause_reason": reason,
        "history": [
            *state["history"],
            {
                "event": "pause",
                "phase": state["phase"],
                "current_step": state["current_step"],
                "expected_action": state["expected_action"],
                "reason": reason,
            },
        ],
    }
    dump_json_atomic(paths.state, updated)
    return updated


def resume_machine(paths: Paths) -> dict[str, Any]:
    state = load_json(paths.state)
    validate_state(state)
    if state["status"] != "paused":
        raise MachineError(f"Resume возможен только из paused, сейчас {state['status']}")
    updated = {
        **state,
        "version": state["version"] + 1,
        "status": "active",
        "pause_reason": None,
        "history": [
            *state["history"],
            {
                "event": "resume",
                "phase": state["phase"],
                "current_step": state["current_step"],
                "expected_action": state["expected_action"],
            },
        ],
    }
    dump_json_atomic(paths.state, updated)
    return updated


def sync_policy(paths: Paths) -> dict[str, Any]:
    """Обновить описательную точку работы из политики, не меняя этап/status."""
    state = load_json(paths.state)
    validate_state(state)
    policy = configs(paths)["phase-policies"].get(state["phase"])
    if policy is None:
        raise MachineError(f"Для этапа {state['phase']} нет политики")
    updated = {
        **state,
        "version": state["version"] + 1,
        "current_step": policy["current_step"],
        "expected_action": policy["expected_action"],
        "history": [
            *state["history"],
            {
                "event": "sync_policy",
                "phase": state["phase"],
                "current_step": policy["current_step"],
                "expected_action": policy["expected_action"],
            },
        ],
    }
    dump_json_atomic(paths.state, updated)
    return updated


def reopen_machine(paths: Paths, target: str, reason: str) -> dict[str, Any]:
    """Явно открыть завершённую задачу после нового требования пользователя."""
    state = load_json(paths.state)
    validate_state(state)
    if state["phase"] != "DONE" or state["status"] != "done":
        raise MachineError("reopen разрешён только для завершённой машины")
    if target not in {"EXECUTION", "VALIDATION", "LIVE_VALIDATION"}:
        raise MachineError("reopen допускает только EXECUTION, VALIDATION или LIVE_VALIDATION")
    reason = reason.strip()
    if not reason:
        raise MachineError("Причина reopen не может быть пустой")
    policy = configs(paths)["phase-policies"][target]
    preserved_checks = {
        key: value for key, value in state["checks"].items()
        if key == "planning_complete"
    }
    updated = {
        **state,
        "version": state["version"] + 1,
        "phase": target,
        "status": "active",
        "current_step": policy["current_step"],
        "expected_action": policy["expected_action"],
        "pause_reason": None,
        "artifacts": {
            key: value for key, value in state["artifacts"].items()
            if key == "plan"
        },
        "checks": preserved_checks,
        "violations": [],
        "blockers": [],
        "history": [
            *state["history"],
            {"event": "reopen", "from": "DONE", "to": target, "reason": reason},
        ],
    }
    dump_json_atomic(paths.state, updated)
    return updated


def unblock_machine(paths: Paths, reason: str) -> dict[str, Any]:
    """Открыть новый repair-cycle после явного решения человека."""
    state = load_json(paths.state)
    validate_state(state)
    if state["phase"] != "BLOCKED" or state["status"] != "blocked":
        raise MachineError("unblock разрешён только для заблокированной машины")
    reason = reason.strip()
    if not reason:
        raise MachineError("Причина unblock не может быть пустой")
    policy = configs(paths)["phase-policies"]["EXECUTION"]
    preserved_checks = {
        key: value for key, value in state["checks"].items()
        if key == "planning_complete"
    }
    updated = {
        **state,
        "version": state["version"] + 1,
        "phase": "EXECUTION",
        "status": "active",
        "current_step": policy["current_step"],
        "expected_action": policy["expected_action"],
        "pause_reason": None,
        "retry_cycles": 0,
        "artifacts": {
            key: value for key, value in state["artifacts"].items()
            if key == "plan"
        },
        "checks": preserved_checks,
        "violations": [],
        "blockers": [],
        "history": [
            *state["history"],
            {
                "event": "unblock",
                "from": "BLOCKED",
                "to": "EXECUTION",
                "previous_retry_cycles": state["retry_cycles"],
                "reason": reason,
            },
        ],
    }
    dump_json_atomic(paths.state, updated)
    return updated


def phase_run_paths(paths: Paths, state: dict[str, Any]) -> tuple[Path, Path]:
    sequence = len(state["history"])
    stem = f"{sequence:02d}-{state['phase'].lower()}"
    suffix = 0
    while True:
        attempt = stem if suffix == 0 else f"{stem}-retry{suffix}"
        result = paths.config / "runs" / f"{attempt}-result.json"
        meta = paths.config / "runs" / f"{attempt}-meta.json"
        if not result.exists() and not meta.exists():
            return result, meta
        suffix += 1


def codex_spec(paths: Paths) -> dict[str, Any]:
    cfg = configs(paths)
    state = load_json(paths.state)
    validate_state(state)
    policy = cfg["phase-policies"].get(state["phase"])
    if policy is None:
        raise MachineError(f"Этап {state['phase']} нельзя запустить")
    output_file, meta_file = phase_run_paths(paths, state)
    run_cwd = (paths.root / policy["cwd"]).resolve()
    try:
        run_cwd.relative_to(paths.root)
    except ValueError as exc:
        raise MachineError(f"cwd этапа выходит за репозиторий: {run_cwd}") from exc
    if not run_cwd.exists():
        runs_root = (paths.config / "runs").resolve()
        try:
            run_cwd.relative_to(runs_root)
        except ValueError as exc:
            raise MachineError(f"Рабочий каталог этапа не существует: {run_cwd}") from exc
        run_cwd.mkdir(parents=True)
    if not run_cwd.is_dir():
        raise MachineError(f"Рабочий каталог этапа не является каталогом: {run_cwd}")
    argv = [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--sandbox",
        policy["sandbox"],
        "-C",
        str(run_cwd),
        "--output-schema",
        str(paths.config / "schemas" / "phase-result.schema.json"),
        "-o",
        str(output_file),
        "-",
    ]
    return {
        "phase": state["phase"],
        "role": policy["role"],
        "sandbox": policy["sandbox"],
        "allowed_write_paths": policy["allowed_write_paths"],
        "cwd": str(run_cwd),
        "argv": argv,
        "output_file": str(output_file),
        "meta_file": str(meta_file),
        "shell_preview": " ".join(shlex.quote(item) for item in argv),
        "stdin": prompt_text(paths),
    }


def codex_preview(paths: Paths) -> dict[str, Any]:
    return {
        "executed": False,
        "reason": "Preview команды; для реального запуска используется отдельная команда run.",
        **codex_spec(paths),
    }


def file_digest(path: Path) -> str:
    if path.is_symlink():
        return "symlink:" + os.readlink(path)
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_snapshot(root: Path) -> dict[str, str]:
    files = run_git(root, ["ls-files", "--cached", "--others", "--exclude-standard"]).splitlines()
    return {relative: file_digest(root / relative) for relative in files}


def snapshot_changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(
        path
        for path in before.keys() | after.keys()
        if before.get(path) != after.get(path)
    )


def outside_prefixes(changes: list[str], allowed_prefixes: list[str]) -> list[str]:
    if not allowed_prefixes:
        return changes
    return [
        path
        for path in changes
        if not any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in allowed_prefixes)
    ]


def attach_phase_artifact(paths: Paths, result_path: Path, phase: str) -> dict[str, Any]:
    result = load_json(result_path)
    validate_result(result, phase)
    relative = result_path.resolve().relative_to(paths.root).as_posix()
    automatic = {
        "PLANNING": "plan",
        "VALIDATION": "test_report",
        "REVIEW": "review_report",
    }.get(phase)
    if automatic:
        result["artifacts"][automatic] = relative
        dump_json_atomic(result_path, result)
    return result


def run_codex(paths: Paths) -> dict[str, Any]:
    spec = codex_spec(paths)
    output_file = Path(spec["output_file"])
    meta_file = Path(spec["meta_file"])
    output_file.parent.mkdir(parents=True, exist_ok=True)
    before = workspace_snapshot(paths.root)
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    process = subprocess.run(
        spec["argv"],
        cwd=spec["cwd"],
        input=spec["stdin"],
        text=True,
        capture_output=True,
        timeout=1800,
        env=environment,
    )
    after = workspace_snapshot(paths.root)
    changed = snapshot_changes(before, after)
    forbidden = outside_prefixes(changed, spec["allowed_write_paths"])
    meta = {
        "phase": spec["phase"],
        "role": spec["role"],
        "sandbox": spec["sandbox"],
        "returncode": process.returncode,
        "changed_paths": changed,
        "forbidden_changes": forbidden,
        "stdout": process.stdout[-12000:],
        "stderr": process.stderr[-12000:],
    }
    dump_json_atomic(meta_file, meta)
    if process.returncode != 0:
        raise MachineError(f"codex exec завершился с кодом {process.returncode}; детали: {meta_file}")
    if forbidden:
        raise MachineError(
            "Codex изменил запрещённые для этапа пути: " + ", ".join(forbidden)
        )
    if not output_file.exists():
        raise MachineError(f"Codex не создал структурированный результат: {output_file}")
    result = attach_phase_artifact(paths, output_file, spec["phase"])
    return {
        "executed": True,
        "phase": spec["phase"],
        "role": spec["role"],
        "result_file": str(output_file),
        "meta_file": str(meta_file),
        "outcome": result["outcome"],
        "summary": result["summary"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Корень тестового репозитория")
    parser.add_argument("--config", type=Path, help="Каталог конфигурации машины")
    parser.add_argument("--state", type=Path, help="Альтернативный state.json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("check")
    commands.add_parser("prompt")
    commands.add_parser("codex-command")
    commands.add_parser("run")
    pause_parser = commands.add_parser("pause")
    pause_parser.add_argument("--reason", required=True)
    commands.add_parser("resume")
    commands.add_parser("sync-policy")
    reopen_parser = commands.add_parser("reopen")
    reopen_parser.add_argument("target", choices=("EXECUTION", "VALIDATION", "LIVE_VALIDATION"))
    reopen_parser.add_argument("--reason", required=True)
    unblock_parser = commands.add_parser("unblock")
    unblock_parser.add_argument("--reason", required=True)
    transition_parser = commands.add_parser("transition")
    transition_parser.add_argument("target", choices=PHASES)
    transition_parser.add_argument("--result", required=True, type=Path)
    evidence_parser = commands.add_parser("record-evidence")
    evidence_parser.add_argument("check_id")
    evidence_parser.add_argument("artifact_id")
    evidence_parser.add_argument("artifact_path")
    evidence_parser.add_argument("--summary", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    paths = Paths.discover(arguments.root, arguments.config, arguments.state)
    try:
        if arguments.command == "status":
            state = load_json(paths.state)
            validate_state(state)
            output: Any = state
        elif arguments.command == "check":
            output = mechanical_check(paths)
        elif arguments.command == "prompt":
            print(prompt_text(paths), end="")
            return 0
        elif arguments.command == "codex-command":
            output = codex_preview(paths)
        elif arguments.command == "run":
            output = run_codex(paths)
        elif arguments.command == "pause":
            output = pause_machine(paths, arguments.reason)
        elif arguments.command == "resume":
            output = resume_machine(paths)
        elif arguments.command == "sync-policy":
            output = sync_policy(paths)
        elif arguments.command == "reopen":
            output = reopen_machine(paths, arguments.target, arguments.reason)
        elif arguments.command == "unblock":
            output = unblock_machine(paths, arguments.reason)
        elif arguments.command == "transition":
            output = transition(paths, arguments.target, arguments.result)
        elif arguments.command == "record-evidence":
            output = record_evidence(
                paths,
                arguments.check_id,
                arguments.artifact_id,
                arguments.artifact_path,
                arguments.summary,
            )
        else:  # pragma: no cover
            raise MachineError(f"Неизвестная команда: {arguments.command}")
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except MachineError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
