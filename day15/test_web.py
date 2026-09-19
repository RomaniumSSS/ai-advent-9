"""Офлайн-проверки API панели без открытия сокета."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import base_agent
from offline import OfflineClient
from profile import DEMO_PROFILES
from web import Handler, Runtime, WEB


def dispatch(runtime, path, body=None):
    controller = SimpleNamespace(runtime=runtime)
    return Handler._dispatch(controller, path, body or {})


def test_full_demo(runtime):
    created = dispatch(runtime, "/api/demo-reset")
    assert created["state"]["task_state"]["stage"] == "planning"
    runtime.agent.store.save_workflow_proposal(runtime.agent.task_state(), "submit_plan", "Canary, метрики, rollback")
    dispatch(runtime, "/api/action", {"result": "Canary, метрики, rollback"})
    assert runtime.state()["task_state"]["stage"] == "execution"
    dispatch(runtime, "/api/pause")
    before = runtime.state()["task_state"]

    try:
        dispatch(runtime, "/api/continue")
    except ValueError as error:
        assert "модель не вызывалась" in str(error)
    else:
        raise AssertionError("панель не должна обходить pause guard")

    dispatch(runtime, "/api/clear")
    restarted = dispatch(runtime, "/api/restart")
    assert restarted["state"]["generation"] == 2
    after = restarted["state"]["task_state"]
    for key in ("objective", "stage", "status", "current_step", "expected_action", "artifacts"):
        assert after[key] == before[key]
    assert restarted["state"]["history"] == []

    dispatch(runtime, "/api/resume")
    continued = dispatch(runtime, "/api/continue")
    context = continued["context"]
    block = next(row["content"] for row in context if row["content"].startswith("СОСТОЯНИЕ"))
    assert '\"stage\": \"execution\"' in block
    assert context[-1] == {"role": "user", "content": "Продолжай"}
    assert continued["reply"]
    print("ok  web API: pause → clear → restart → resume → continue")


def test_validation_loop(runtime):
    dispatch(runtime, "/api/demo-reset")
    dispatch(runtime, "/api/workflow/run", {})
    dispatch(runtime, "/api/workflow/approve", {})
    revised = dispatch(runtime, "/api/action", {
        "action": "request_changes",
        "result": "Добавить rollback",
    })
    assert revised["state"]["task_state"]["stage"] == "execution"
    assert revised["state"]["task_state"]["artifacts"]["validation_feedback"] == "Добавить rollback"
    assert [event["event"] for event in revised["state"]["task_events"]][-1] == "request_changes"
    dispatch(runtime, "/api/workflow/run", {})
    dispatch(runtime, "/api/workflow/approve", {})
    terminal = dispatch(runtime, "/api/continue")
    assert terminal["state"]["task_state"]["stage"] == "done"
    assert not terminal["model_called"] and terminal["context"] is None
    assert "без вызова модели" in terminal["message"]
    print("ok  web API показывает validation-loop, журнал и terminal guard")


def test_day12_features_and_fsm_share_one_agent(runtime):
    opened = dispatch(runtime, "/api/demo-user", {"user": "brief"})
    assert opened["state"]["profile"] == DEMO_PROFILES["brief"].to_dict()
    dispatch(runtime, "/api/save", {"layer": "short", "key": "чат", "value": "коротко"})
    dispatch(runtime, "/api/save", {"layer": "working", "key": "релиз", "value": "canary"})
    dispatch(runtime, "/api/save", {"layer": "long", "key": "формат", "value": "списком"})
    dispatch(runtime, "/api/task/start", {"objective": "Выпустить приложение"})

    reply = dispatch(runtime, "/api/chat", {"text": "Что ты знаешь и какой следующий шаг?"})
    assert reply["ok"] and reply["saved"] and reply["context"]
    system = "\n".join(row["content"] for row in reply["context"] if row["role"] == "system")
    assert "ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ" in system and "Кратко и практично" in system
    assert "canary" in system and "Выпустить приложение" in system
    assert reply["state"]["task_state"]["stage"] == "planning"
    assert all(reply["state"]["notes"][layer] for layer in ("short", "working", "long"))

    switched = dispatch(runtime, "/api/scope", {
        "user": "brief",
        "task": "demo",
        "session": "fresh-session",
    })["state"]
    assert switched["history"] == [] and switched["notes"]["short"] == {}
    assert switched["notes"]["working"]["релиз"] == "canary"
    assert switched["notes"]["long"]["формат"] == "списком"
    assert switched["task_state"]["objective"] == "Выпустить приложение"

    cleared = dispatch(runtime, "/api/reset")["state"]
    assert cleared["task_state"]["stage"] == "planning"
    assert cleared["notes"]["working"] and cleared["notes"]["long"]
    print("ok  одна панель сохраняет профиль, память, чат и FSM дня 13")


def test_semi_autonomous_workflow(runtime):
    dispatch(runtime, "/api/task/start", {"objective": "Подготовить релиз"})
    planned = dispatch(runtime, "/api/workflow/run", {"max_model_turns": 4})
    assert planned["loop"]["reason"] == "approval_required"
    assert planned["state"]["workflow"]["actor"] == "user"
    assert planned["state"]["workflow"]["proposal"]["action"] == "submit_plan"

    dispatch(runtime, "/api/task/restart")
    calls = len(runtime.agent.client.requests)
    waiting = dispatch(runtime, "/api/workflow/run", {"max_model_turns": 4})
    assert waiting["loop"]["model_turns"] == 0
    assert len(runtime.agent.client.requests) == calls

    validated = dispatch(runtime, "/api/workflow/approve", {"max_model_turns": 4})
    assert validated["loop"]["model_turns"] == 2
    assert validated["state"]["task_state"]["stage"] == "validation"
    assert validated["state"]["workflow"]["proposal"]["action"] == "approve"
    done = dispatch(runtime, "/api/workflow/approve", {"max_model_turns": 4})
    assert done["state"]["task_state"]["stage"] == "done"
    assert done["state"]["workflow"]["actor"] == "none"
    print("ok  web API проводит semi-autonomous loop через две user boundaries")


def test_static_contract():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    script = (WEB / "app.js").read_text(encoding="utf-8")
    for marker in ("pipeline", "current_step", "expected", "pause", "resume", "restart", "events", "workflow-run", "workflow-approve", "workflow-revise"):
        assert marker in html + script
    for marker in ("profile-style", "short-notes", "working-notes", "long-notes", "open-scope", "chat-form"):
        assert marker in html + script
    for marker in ("invariants", "invariant-checks", "test-conflict"):
        assert marker in html + script
    assert "innerHTML = data" not in script
    assert ".innerHTML" not in script
    print("ok  UI содержит весь день 12 плюс этап, действие, pause/resume/restart и журнал")


def test_invariant_conflict(runtime):
    calls = len(runtime.agent.client.requests)
    result = dispatch(runtime, "/api/chat", {"text": "Перейти с SQLite на PostgreSQL"})
    assert result["decision"] == "refuse"
    assert not result["model_called"]
    assert len(runtime.agent.client.requests) == calls
    assert "INV-STACK-001" in result["message"]
    assert result["state"]["invariant_checks"][0]["decision"] == "deny"
    print("ok  web API показывает понятный отказ без model call")


def test_online_mode_uses_provider_client_without_exposing_context(directory):
    provider = OfflineClient()
    with patch.object(base_agent, "get_client", return_value=provider):
        runtime = Runtime(Path(directory) / "online.db", offline=False)
        result = dispatch(runtime, "/api/chat", {"text": "Проверка online-маршрута"})
    assert result["state"]["offline"] is False
    assert result["state"]["max_tokens"] == 8_000
    assert result["model_called"] and len(provider.requests) == 1
    assert provider.requests[0]["max_tokens"] == 8_000
    assert result["context"] is None
    print("ok  online-режим использует provider, лимит 8000 и не публикует payload")


def main():
    with tempfile.TemporaryDirectory() as directory:
        first = Runtime(Path(directory) / "web.db")
        test_full_demo(first)
        second = Runtime(Path(directory) / "loop.db")
        test_validation_loop(second)
        third = Runtime(Path(directory) / "cumulative.db")
        test_day12_features_and_fsm_share_one_agent(third)
        fourth = Runtime(Path(directory) / "workflow.db")
        test_semi_autonomous_workflow(fourth)
        fifth = Runtime(Path(directory) / "invariants.db")
        test_invariant_conflict(fifth)
        test_online_mode_uses_provider_client_without_exposing_context(directory)
    test_static_contract()


if __name__ == "__main__":
    main()
