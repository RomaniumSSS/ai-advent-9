"""Полуавтономный loop: model turns до явной границы пользователя."""

import tempfile
from pathlib import Path
from types import SimpleNamespace

from agent import Agent, AgentCapabilities, AgentConfig
from store import SqliteStore
from task_state import Stage, Status


class QueueClient:
    def __init__(self, replies, callback=None, finish_reasons=None):
        self.replies = list(replies)
        self.callback = callback
        self.finish_reasons = list(finish_reasons or [])
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.callback:
            self.callback(len(self.requests))
        text = self.replies.pop(0)
        finish_reason = self.finish_reasons.pop(0) if self.finish_reasons else "stop"
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=text), finish_reason=finish_reason
            )],
            usage=SimpleNamespace(prompt_tokens=20, completion_tokens=5, cost=0.0),
        )


def make_agent(db, client, session="loop", task="loop"):
    return Agent(
        name="workflow",
        config=AgentConfig(max_tokens=100),
        store=SqliteStore(db, session, task, "roman"),
        client=client,
        capabilities=AgentCapabilities(recent_history_turns=2),
    )


def test_normal_and_restart(db):
    client = QueueClient(["План A", "Результат A", "Проверка A"])
    first = make_agent(db, client, "first", "normal")
    first.start_task("Подготовить релиз")
    boundary = first.run_to_boundary()
    assert boundary.status == "waiting_user" and boundary.model_turns == 1
    assert first.workflow_state()["proposal"]["action"] == "submit_plan"

    restarted = make_agent(db, client, "second", "normal")
    before_calls = len(client.requests)
    assert restarted.workflow_state()["actor"] == "user"
    assert restarted.run_to_boundary().reason == "approval_required"
    assert len(client.requests) == before_calls

    validation = restarted.approve_workflow()
    assert validation.status == "waiting_user" and validation.model_turns == 2
    assert "Подготовить релиз" in client.requests[0]["messages"][-1]["content"]
    assert "План A" in client.requests[-2]["messages"][-1]["content"]
    assert "Результат A" in client.requests[-1]["messages"][-1]["content"]
    assert "нет инструментов" in client.requests[-2]["messages"][-1]["content"]
    assert "без наблюдения инструмента" in client.requests[-1]["messages"][-1]["content"]
    assert restarted.task_state().stage is Stage.VALIDATION
    assert restarted.workflow_state()["proposal"]["action"] == "approve"
    done = restarted.approve_workflow()
    assert done.status == "done" and restarted.task_state().stage is Stage.DONE
    print("ok  plan approval → autonomous execution+validation → final approval")


def test_revision_and_budget(db):
    client = QueueClient([
        "План 1", "План 2", "Результат 1", "Проверка 1",
        "Результат 2", "Проверка 2",
    ])
    agent = make_agent(db, client, "revision", "revision")
    agent.start_task("Исправляемая задача")
    agent.run_to_boundary()
    revised_plan = agent.revise_workflow("Добавить rollback")
    assert revised_plan.reason == "approval_required"
    assert "Добавить rollback" in client.requests[-1]["messages"][-1]["content"]

    limited = agent.approve_workflow(max_model_turns=1)
    assert limited.reason == "turn_limit"
    assert agent.task_state().stage is Stage.VALIDATION
    assert agent.workflow_state()["proposal"] is None
    agent.run_to_boundary()
    assert agent.workflow_state()["actor"] == "user"
    rerun = agent.revise_workflow("Нужны метрики", max_model_turns=4)
    assert rerun.reason == "approval_required" and rerun.model_turns == 2
    assert agent.task_state().stage is Stage.VALIDATION
    print("ok  revise feedback сохраняется, turn limit останавливает и resume продолжает")


def test_pause_drops_inflight_transition(db):
    holder = {}

    def pause_first(call):
        if call == 1:
            holder["agent"].pause_task()

    client = QueueClient(["Ответ после паузы"], pause_first)
    agent = make_agent(db, client, "pause", "pause")
    holder["agent"] = agent
    agent.start_task("Пауза во время модели")
    result = agent.run_to_boundary()
    assert result.reason == "paused"
    assert agent.task_state().status is Status.PAUSED
    assert agent.task_state().stage is Stage.PLANNING
    assert agent.workflow_state()["proposal"] is None
    assert agent.store.load() == []
    print("ok  in-flight ответ не меняет FSM и не создаёт proposal после pause")


def test_pause_preserves_pending_boundary(db):
    client = QueueClient(["План до паузы", "Результат", "Проверка"])
    agent = make_agent(db, client, "boundary-pause", "boundary-pause")
    agent.start_task("Сохранить границу")
    agent.run_to_boundary()
    calls = len(client.requests)
    proposal = agent.workflow_state()["proposal"]

    agent.pause_task()
    assert agent.workflow_state()["proposal"]["result"] == proposal["result"]
    agent.resume_task()
    assert agent.workflow_state()["proposal"]["based_on_version"] == agent.task_state().version
    assert agent.run_to_boundary().reason == "approval_required"
    assert len(client.requests) == calls
    assert agent.approve_workflow().reason == "approval_required"
    print("ok  pending proposal переживает pause/resume без повторного model call")


def test_empty_response_and_stale_proposal(db):
    empty = make_agent(db, QueueClient([""]), "empty", "empty")
    empty.start_task("Пустой ответ")
    failed = empty.run_to_boundary()
    assert failed.status == "stopped" and failed.reason == "model_error"
    assert empty.task_state().stage is Stage.PLANNING
    assert empty.workflow_state()["proposal"] is None

    stale = make_agent(db, QueueClient(["План"]), "stale", "stale")
    stale.start_task("Устаревшее предложение")
    stale.run_to_boundary()
    with stale.store._connect() as connection, connection:
        connection.execute(
            "UPDATE task_states SET version = version + 1 WHERE user_id = ? AND task_id = ?",
            (stale.store.user_id, stale.store.task_id),
        )
    try:
        stale.approve_workflow()
    except RuntimeError as error:
        assert "устарело" in str(error)
    else:
        raise AssertionError("stale proposal не должно применяться")
    print("ok  empty response останавливает loop, stale proposal отклоняется")


def test_pause_in_commit_window_is_structured_stop(db):
    planning = make_agent(
        db, QueueClient(["План в окне commit"]), "commit-plan", "commit-plan"
    )
    planning.start_task("Planning commit race")
    save_proposal = planning.store.save_workflow_proposal

    def pause_before_proposal(state, action, result):
        planning.pause_task()
        return save_proposal(state, action, result)

    planning.store.save_workflow_proposal = pause_before_proposal
    stopped = planning.run_to_boundary()
    assert stopped.reason == "paused"
    assert planning.task_state().stage is Stage.PLANNING
    assert planning.workflow_state()["proposal"] is None

    execution = make_agent(
        db,
        QueueClient(["План", "Результат в окне commit"]),
        "commit-execution",
        "commit-execution",
    )
    execution.start_task("Execution commit race")
    execution.run_to_boundary()
    execution.store.apply_workflow_proposal()
    apply_snapshot = execution._apply_task_snapshot

    def pause_before_transition(state, action, result):
        execution.pause_task()
        return apply_snapshot(state, action, result)

    execution._apply_task_snapshot = pause_before_transition
    stopped = execution.run_to_boundary()
    assert stopped.reason == "paused"
    assert execution.task_state().stage is Stage.EXECUTION
    assert execution.store.load() == []
    print("ok  pause в обоих commit windows возвращает structured stop")


def test_truncated_execution_cannot_advance(db):
    client = QueueClient(["План", "Обрезанный результат"],
                         finish_reasons=["stop", "length"])
    agent = make_agent(db, client, "truncated", "truncated")
    agent.start_task("Создать полный результат")
    assert agent.run_to_boundary().reason == "approval_required"
    stopped = agent.approve_workflow()
    assert stopped.reason == "truncated_response"
    assert agent.task_state().stage is Stage.EXECUTION
    assert agent.workflow_state()["proposal"] is None
    assert len(client.requests) == 2
    print("ok  обрезанный execution не может перейти в validation")


def main():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "workflow.db"
        test_normal_and_restart(db)
        test_revision_and_budget(db)
        test_pause_drops_inflight_transition(db)
        test_pause_preserves_pending_boundary(db)
        test_empty_response_and_stale_proposal(db)
        test_pause_in_commit_window_is_structured_stop(db)
        test_truncated_execution_cannot_advance(db)


if __name__ == "__main__":
    main()
