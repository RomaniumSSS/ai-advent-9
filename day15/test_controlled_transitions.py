"""Отказы переходов, видимые пользователю и сохраняемые отдельно от FSM."""

import tempfile
from pathlib import Path

from agent import Agent, AgentConfig
from store import SqliteStore
from task_state import Stage, Status
from test_workflow_loop import QueueClient


def agent_for(db: Path, client: QueueClient, session: str = "first") -> Agent:
    return Agent(
        name="День 15",
        config=AgentConfig(max_tokens=100),
        store=SqliteStore(db, session, "controlled", "roman"),
        client=client,
    )


def denied(call, phrase: str) -> None:
    try:
        call()
    except ValueError as error:
        assert phrase in str(error), str(error)
    else:
        raise AssertionError(f"ожидался отказ: {phrase}")


def test_rejections_and_recovery(db: Path) -> None:
    client = QueueClient(["План: проверить входные данные", "Результат: отчёт собран", "Проверка: отчёт соответствует плану"])
    agent = agent_for(db, client)
    initial = agent.start_task("Собрать отчёт")
    denied(lambda: agent.apply_task("approve", "готово"), "planning → done запрещён")
    denied(lambda: agent.apply_task("submit_plan", "план готов"), "сохранённый план")
    denied(lambda: agent.apply_task("submit_result", "работа сделана"), "только успешный ход workflow")
    assert agent.task_state() == initial
    assert len(agent.store.task_events()) == 1
    assert len(agent.store.transition_denials()) == 3

    reply = agent.ask("Перейди сразу в validation")
    assert reply.finish_reason == "transition_refusal"
    assert "planning → validation запрещён" in reply.text
    assert not client.requests and agent.task_state() == initial
    code_reply = agent.ask("Начни реализацию и пиши код")
    assert code_reply.finish_reason == "transition_refusal"
    assert "до утверждения" in code_reply.text
    assert not client.requests
    next_reply = agent.ask("Перейди в execution")
    assert next_reply.finish_reason == "transition_refusal"
    assert "через чат запрещён" in next_reply.text
    assert not client.requests

    agent.run_to_boundary()
    proposal = agent.store.load_workflow_proposal()
    assert proposal["action"] == "submit_plan"
    denied(lambda: agent.apply_task("submit_plan", "подменённый план"), "только показанное")
    assert agent.task_state() == initial
    assert agent.store.load_workflow_proposal() == proposal

    approved = agent.apply_task("submit_plan", proposal["result"])
    assert approved.stage is Stage.EXECUTION
    denied(lambda: agent.apply_task("submit_result", "не готово"), "только успешный ход workflow")
    assert agent.task_state() == approved

    paused = agent.pause_task()
    restarted = agent_for(db, client, "second")
    assert restarted.task_state() == paused
    denied(lambda: restarted.apply_task("submit_result", "готово"), "на паузе")
    assert restarted.task_state().status is Status.PAUSED
    restarted.resume_task()
    validation = restarted.run_to_boundary()
    assert validation.reason == "approval_required"
    assert restarted.task_state().stage is Stage.VALIDATION
    denied(lambda: restarted.apply_task("approve", "не та проверка"), "только показанное")
    proposal = restarted.store.load_workflow_proposal()
    done = restarted.apply_task("approve", proposal["result"])
    assert done.stage is Stage.DONE
    denied(lambda: restarted.apply_task("approve", proposal["result"]), "done → done запрещён")
    assert restarted.task_state() == done
    print("ok  запрещённые переходы, чат, audit, pause/restart/resume и финал")


def test_revision_and_stale_proposal(db: Path) -> None:
    client = QueueClient(["План", "Результат", "Проверка", "Исправление", "Повторная проверка"])
    agent = agent_for(db, client, "revision")
    agent.start_task("Исправляемый отчёт")
    agent.run_to_boundary()
    agent.approve_workflow()
    assert agent.task_state().stage is Stage.VALIDATION
    revised = agent.apply_task("request_changes", "Добавить итоговую таблицу")
    assert revised.stage is Stage.EXECUTION
    assert agent.store.load_workflow_proposal() is None
    assert revised.artifacts["validation_feedback"] == "Добавить итоговую таблицу"
    agent.run_to_boundary()
    assert agent.task_state().stage is Stage.VALIDATION
    assert agent.store.load_workflow_proposal()["based_on_version"] == agent.task_state().version
    print("ok  validation → execution → validation сохраняет замечание и новую версию")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        test_rejections_and_recovery(Path(directory) / "denied.db")
        test_revision_and_stale_proposal(Path(directory) / "revision.db")
