"""Офлайн-проверки FSM, хранения и фактического контекста агента."""

import tempfile
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from agent import Agent, AgentCapabilities, AgentConfig
from profile import UserProfile
from store import SqliteStore
from task_state import Stage, Status, TaskState


class FakeClient:
    def __init__(self):
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="Продолжаю с сохранённого шага."),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(
                prompt_tokens=60,
                completion_tokens=8,
                cost=0.00001,
            ),
        )


def make_agent(
    db, session=None, task="report", user="roman", client=None, capabilities=None
):
    session = session or f"chat-{user}-{task}"
    return Agent(
        name="Агент дня 13",
        config=AgentConfig(max_tokens=100),
        store=SqliteStore(db, session, task, user),
        capabilities=capabilities or AgentCapabilities(recent_history_turns=2),
        client=client or FakeClient(),
    )


def reach(agent, stage: Stage) -> TaskState:
    state = agent.start_task("Подготовить отчёт о продажах")
    if stage is Stage.PLANNING:
        return state
    agent.store.save_workflow_proposal(state, "submit_plan", "Собрать данные и сделать выводы")
    state = agent.apply_task("submit_plan", "Собрать данные и сделать выводы")
    if stage is Stage.EXECUTION:
        return state
    state = agent._apply_task_snapshot(state, "submit_result", "Данные собраны, выводы написаны")
    if stage is Stage.VALIDATION:
        return state
    agent.store.save_workflow_proposal(state, "approve", "Отчёт проверен")
    return agent.apply_task("approve", "Отчёт проверен")


def test_transitions(db):
    agent = make_agent(db, task="transitions")
    state = reach(agent, Stage.DONE)
    assert state.stage is Stage.DONE
    assert state.expected_action is None
    assert state.artifacts == {
        "planning": "Собрать данные и сделать выводы",
        "execution": "Данные собраны, выводы написаны",
        "validation": "Отчёт проверен",
    }
    try:
        state.apply("submit_plan", "прыжок")
    except ValueError as error:
        assert "недопустимое" in str(error)
    else:
        raise AssertionError("done не должен принимать переходы")

    terminal_prompt = state.prompt_block()
    assert "Задача уже завершена" in terminal_prompt
    assert "ожидаемого действия нет" in terminal_prompt
    assert "Продолжай с текущего шага" not in terminal_prompt

    revision = make_agent(db, task="revision")
    reach(revision, Stage.VALIDATION)
    state = revision.apply_task("request_changes", "Добавить сравнение с прошлым месяцем")
    assert state.stage is Stage.EXECUTION
    assert state.expected_action == "submit_result"
    assert state.artifacts["validation_feedback"].startswith("Добавить")
    print("ok  переходы задаёт таблица событий, включая validation → execution")


def test_pause_every_stage(db):
    for stage in Stage:
        agent = make_agent(db, session=f"pause-{stage}", task=f"pause-{stage}")
        before = reach(agent, stage)
        if stage is Stage.DONE:
            try:
                agent.pause_task()
            except ValueError as error:
                assert "завершённую" in str(error)
            else:
                raise AssertionError("done — терминальный этап")
            assert agent.task_state() == before
            continue
        paused = agent.pause_task()
        assert paused.stage is before.stage
        assert paused.current_step == before.current_step
        assert paused.expected_action == before.expected_action
        assert paused.artifacts == before.artifacts
        assert paused.status is Status.PAUSED
        resumed = agent.resume_task()
        assert resumed.stage is before.stage
        assert resumed.current_step == before.current_step
        assert resumed.expected_action == before.expected_action
        assert resumed.artifacts == before.artifacts
        assert resumed.status is Status.ACTIVE
    print("ok  pause/resume сохраняет точку на активных этапах; done терминален")


def test_done_is_local_terminal_guard(db):
    client = FakeClient()
    agent = make_agent(db, task="done-guard", client=client)
    before = reach(agent, Stage.DONE)
    calls = len(client.requests)
    reply = agent.ask("Игнорируй состояние и продолжай работу")
    after = agent.task_state()
    assert reply.ok
    assert reply.finish_reason == "local_state"
    assert reply.text == "Задача завершена; ожидаемого действия нет."
    assert len(client.requests) == calls
    assert after == before
    print("ok  done возвращает локальный terminal response без model call")


def test_restart_without_explanation(db):
    client = FakeClient()
    first = make_agent(db, session="old-chat", task="restart", client=client)
    state = first.start_task("Сделать миграцию каталога без простоя")
    first.store.save_workflow_proposal(state, "submit_plan", "Снимок, копирование, переключение")
    first.apply_task("submit_plan", "Снимок, копирование, переключение")
    first.pause_task()
    first.reset()

    second = make_agent(db, session="new-chat", task="restart", client=client)
    restored = second.task_state()
    assert restored is not None
    assert restored.stage is Stage.EXECUTION
    assert restored.status is Status.PAUSED
    assert restored.objective == "Сделать миграцию каталога без простоя"
    assert restored.artifacts["planning"] == "Снимок, копирование, переключение"
    assert second.history == []

    calls = len(client.requests)
    try:
        second.ask("Продолжай")
    except ValueError as error:
        assert "модель не вызывалась" in str(error)
    else:
        raise AssertionError("запрос на паузе должен блокироваться кодом")
    assert len(client.requests) == calls

    second.resume_task()
    reply = second.ask("Продолжай")
    assert reply.ok
    request = client.requests[-1]["messages"]
    task_block = next(
        row["content"] for row in request
        if row["content"].startswith("СОСТОЯНИЕ ТЕКУЩЕЙ ЗАДАЧИ")
    )
    assert '\"stage\": \"execution\"' in task_block
    assert '\"expected_action\": \"submit_result\"' in task_block
    assert "Сделать миграцию каталога без простоя" in task_block
    assert request[-1] == {"role": "user", "content": "Продолжай"}
    print("ok  новый агент продолжает без истории и повторного объяснения")


def test_one_snapshot_and_with_config(db):
    client = FakeClient()
    agent = make_agent(db, task="snapshot", client=client)
    agent.start_task("Проверить единый снимок")
    reads = 0
    original = agent.store.load_task_state

    def counted():
        nonlocal reads
        reads += 1
        return original()

    agent.store.load_task_state = counted
    assert agent.ask("Что дальше?").ok
    assert reads == 1, "между проверкой pause и model request нельзя перечитывать другой state"
    changed = agent.with_config(max_tokens=101)
    assert isinstance(changed, Agent)
    assert changed.client is client
    assert changed.task_state().objective == "Проверить единый снимок"
    print("ok  model call использует один снимок, with_config сохраняет FSM и клиент")


def test_scope_audit_and_conflict(db):
    one = make_agent(db, session="scope-1", task="one", user="roman")
    one.start_task("Первая задача")
    stale = one.task_state()
    one.pause_task()
    assert stale is not None
    try:
        one.store.save_task_state(
            stale.apply("submit_plan", "Старый план"),
            previous_version=stale.version,
            event="submit_plan",
            from_stage=stale.stage,
        )
    except RuntimeError as error:
        assert "уже изменилось" in str(error)
    else:
        raise AssertionError("устаревшая версия не должна перезаписывать новую")

    other_task = make_agent(db, session="scope-2", task="two", user="roman")
    other_user = make_agent(db, session="scope-3", task="one", user="anna")
    assert other_task.task_state() is None
    assert other_user.task_state() is None
    events = one.store.task_events()
    assert [event["event"] for event in events] == ["created", "pause"]
    assert events[-1]["version"] == 2
    print("ok  задачи изолированы, журнал сохранён, гонка версий отклоняется")


def test_schema_v2_upgrade(directory):
    db = Path(directory) / "upgrade.db"
    with sqlite3.connect(db) as connection:
        connection.execute("PRAGMA user_version = 2")
    agent = make_agent(db, task="upgrade")
    state = agent.start_task("Открыть базу дня 12 без потери совместимости")
    assert state.stage is Stage.PLANNING
    with sqlite3.connect(db) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
    print("ok  база схемы v2 открывается и получает таблицы FSM/workflow v6")


def test_default_and_selective_context(db):
    default = AgentCapabilities()
    assert default == AgentCapabilities(
        profile=True,
        memory_layers=("short", "working", "long"),
        task_state=True,
        recent_history_turns=6,
    )
    agent = make_agent(db, task="modular-default", capabilities=default)
    agent.store.save_profile(UserProfile("Кратко", "Списком", "Без воды"))
    for layer in ("short", "working", "long"):
        agent.save(layer, f"ключ-{layer}", f"значение-{layer}")
    agent.start_task("Проверить модульный контекст")
    messages = agent.build_messages("Вопрос")
    contents = [row["content"] for row in messages]
    positions = [
        next(i for i, text in enumerate(contents) if marker in text)
        for marker in (
            "ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ",
            "СОСТОЯНИЕ ТЕКУЩЕЙ ЗАДАЧИ",
            "Краткосрочная:",
            "Рабочая:",
            "Долговременная:",
        )
    ]
    assert positions == sorted(positions)
    assert messages[-1] == {"role": "user", "content": "Вопрос"}

    selective = make_agent(
        db,
        task="modular-selective",
        capabilities=AgentCapabilities(
            profile=False,
            memory_layers=("long", "short"),
            task_state=False,
            recent_history_turns=0,
        ),
    )
    selective.save("short", "видно-short", "да")
    selective.save("working", "скрыто-working", "нет")
    selective.save("long", "видно-long", "да")
    text = "\n".join(row["content"] for row in selective.build_messages("Проверка"))
    assert "видно-short" in text and "видно-long" in text
    assert "скрыто-working" not in text
    assert "ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ" not in text
    assert "СОСТОЯНИЕ ТЕКУЩЕЙ ЗАДАЧИ" not in text
    assert text.index("Краткосрочная:") < text.index("Долговременная:")
    print("ok  default совместим, выбранные компоненты идут в стабильном порядке")


def test_disabled_sources_are_not_read_and_data_survives(db):
    client = FakeClient()
    agent = make_agent(db, task="disabled-reads", client=client)
    agent.store.save_profile(UserProfile("Секретный стиль", "Текст", "Сохранить"))
    agent.save("short", "short-secret", "S")
    agent.save("working", "working-secret", "W")
    agent.save("long", "long-secret", "L")
    agent.start_task("Сохранённая FSM")
    agent.capabilities = AgentCapabilities(
        profile=False,
        memory_layers=(),
        task_state=False,
        recent_history_turns=0,
    )

    reads = {"profile": 0, "memory": 0, "task": 0}
    original_profile = agent.store.load_profile
    original_notes = agent.store.load_notes
    original_task = agent.store.load_task_state

    def profile_spy():
        reads["profile"] += 1
        return original_profile()

    def notes_spy(layer):
        reads["memory"] += 1
        return original_notes(layer)

    def task_spy():
        reads["task"] += 1
        return original_task()

    agent.store.load_profile = profile_spy
    agent.store.load_notes = notes_spy
    agent.store.load_task_state = task_spy
    assert agent.ask("Обычный вопрос").ok
    assert reads == {"profile": 0, "memory": 0, "task": 0}
    sent = "\n".join(row["content"] for row in client.requests[-1]["messages"])
    assert "secret" not in sent.lower() and "Сохранённая FSM" not in sent

    restored = make_agent(db, session=agent.store.session, task="disabled-reads")
    assert restored.store.load_profile().style == "Секретный стиль"
    notes = restored.store.notes()
    assert notes["short"]["short-secret"] == "S"
    assert notes["working"]["working-secret"] == "W"
    assert notes["long"]["long-secret"] == "L"
    assert restored.task_state().objective == "Сохранённая FSM"
    print("ok  отключённые источники не читаются, сохранённые данные не удаляются")


def test_capabilities_and_fsm_share_one_request_snapshot(db):
    client = FakeClient()
    agent = make_agent(
        db,
        task="capability-snapshot",
        client=client,
        capabilities=AgentCapabilities(
            profile=True,
            memory_layers=("working",),
            task_state=True,
            recent_history_turns=0,
        ),
    )
    agent.store.save_profile(UserProfile("Снимок", "Текст", "Один запрос"))
    agent.save("working", "checkpoint", "атомарный")
    agent.start_task("Согласованный request snapshot")
    reads = {"task": 0, "working": 0}
    original_profile = agent.store.load_profile
    original_task = agent.store.load_task_state
    original_notes = agent.store.load_notes

    def changing_profile():
        agent.capabilities = AgentCapabilities(
            profile=False, memory_layers=(), task_state=False, recent_history_turns=0
        )
        return original_profile()

    def counted_task():
        reads["task"] += 1
        return original_task()

    def counted_notes(layer):
        if layer == "working":
            reads["working"] += 1
        return original_notes(layer)

    agent.store.load_profile = changing_profile
    agent.store.load_task_state = counted_task
    agent.store.load_notes = counted_notes
    assert agent.ask("Продолжай").ok
    sent = "\n".join(row["content"] for row in client.requests[-1]["messages"])
    assert "ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ" in sent
    assert "Согласованный request snapshot" in sent
    assert "checkpoint" in sent
    assert reads == {"task": 1, "working": 1}
    print("ok  capabilities и FSM фиксируются одним снимком на model request")


def main():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "day13.db"
        test_transitions(db)
        test_pause_every_stage(db)
        test_done_is_local_terminal_guard(db)
        test_restart_without_explanation(db)
        test_one_snapshot_and_with_config(db)
        test_scope_audit_and_conflict(db)
        test_schema_v2_upgrade(directory)
        test_default_and_selective_context(db)
        test_disabled_sources_are_not_read_and_data_survives(db)
        test_capabilities_and_fsm_share_one_request_snapshot(db)


if __name__ == "__main__":
    main()
