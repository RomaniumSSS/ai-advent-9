"""Офлайн-проверки хранения, учёта и механической защиты инвариантов."""

import json
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

from agent import Agent, AgentConfig
from invariants import DEMO_INVARIANTS
from store import SqliteStore


class FakeClient:
    def __init__(self, answer="Совместимое решение сохраняет текущий стек."):
        self.answer = answer
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=self.answer),
                finish_reason="stop",
            )],
            usage=None,
        )


def make_agent(db, client, session="chat"):
    agent = Agent(
        name="Агент дня 14",
        config=AgentConfig(max_tokens=100),
        store=SqliteStore(db, session=session, task_id="release", user_id="roman"),
        client=client,
    )
    for invariant in DEMO_INVARIANTS:
        agent.store.save_invariant(invariant, if_missing=True)
    return agent


def test_request_conflict_is_local_refusal(db):
    conflicts = (
        "Давай перейдём с SQLite на PostgreSQL",
        "Используй PostgreSQL вместо SQLite",
        "Рекомендую PostgreSQL как основную БД",
        "Лучший вариант — PostgreSQL",
        "Use PostgreSQL instead of SQLite",
        "Разверните микросервисную архитектуру",
        "Опубликуй без согласования",
        "Отправь релиз в прод без подтверждения",
        "Выкати в прод без согласования",
        "Публикация без подтверждения — делаем сейчас",
        "Выкати сейчас, подтверждение не нужно",
        "Deploy now, no approval needed",
    )
    for index, question in enumerate(conflicts):
        client = FakeClient()
        agent = make_agent(db.with_name(f"request-{index}.db"), client)
        reply = agent.ask(question)
        assert reply.finish_reason == "invariant_refusal", question
        assert not client.requests, question
        assert "Причина:" in reply.text
        assert agent.store.invariant_checks()[0]["decision"] == "deny"
    print(f"ok  {len(conflicts)} формулировок конфликта блокируются до model call и объясняются")


def test_safe_invariant_discussion_is_not_refusal(db):
    safe = (
        "Почему нельзя перейти с SQLite на PostgreSQL?",
        "Не предлагай перейти с SQLite на PostgreSQL",
        "Сравни правило про SQLite и PostgreSQL",
        "Why should we not use PostgreSQL?",
        "Почему нельзя отправить релиз в прод без подтверждения?",
        "Объясни запрет на публикацию без согласования",
    )
    for index, question in enumerate(safe):
        client = FakeClient()
        agent = make_agent(db.with_name(f"explain-{index}.db"), client)
        reply = agent.ask(question)
        assert reply.finish_reason == "invariant_explanation", question
        assert not client.requests, question
        assert "не требует нарушать" in reply.text
        assert agent.store.invariant_checks()[0]["decision"] == "explain"
    print(f"ok  {len(safe)} безопасных вопросов получают объяснение, а не ложный отказ")


def test_invariants_survive_chat_clear_and_restart(db):
    first = make_agent(db, FakeClient(), session="first")
    first.ask("Какие ограничения надо учитывать?")
    first.reset()
    second = make_agent(db, FakeClient(), session="second")
    assert len(second.store.load_invariants()) == len(DEMO_INVARIANTS)
    assert second.history == []
    reply = second.ask("Предложи совместимый план")
    assert reply.ok
    system = [row["content"] for row in second.client.requests[-1]["messages"] if row["role"] == "system"]
    assert any(text.startswith("АКТИВНЫЕ ИНВАРИАНТЫ") for text in system)
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM invariants").fetchone()[0] == len(DEMO_INVARIANTS)
        assert connection.execute("SELECT count(*) FROM messages WHERE session='first'").fetchone()[0] == 0
    print("ok  правила живут отдельно от диалога и явно входят в context")


def test_provider_violation_is_blocked_before_persistence(db):
    forbidden_outputs = (
        "Предлагаю перейти на PostgreSQL и заменить текущее хранилище.",
        "Используйте PostgreSQL вместо SQLite.",
        "Лучший вариант — PostgreSQL.",
        "Разверните микросервисную архитектуру.",
        "Отправьте релиз в прод без подтверждения.",
        "Выложите релиз без согласования.",
        "Публикация без подтверждения уже начата.",
        "Выкатываю сейчас, подтверждение не нужно.",
        "Deploy now, no approval needed.",
    )
    for index, raw in enumerate(forbidden_outputs):
        client = FakeClient(raw)
        agent = make_agent(db.with_name(f"output-{index}.db"), client)
        reply = agent.ask("Предложи совместимый вариант масштабирования")
        assert len(client.requests) == 1
        assert reply.finish_reason == "invariant_output_blocked", raw
        assert raw not in str(agent.history)
        assert raw not in str(agent.store.load())
        checks = agent.store.invariant_checks()
        assert checks[0]["phase"] == "response" and checks[0]["decision"] == "deny"
        assert checks[1]["phase"] == "request" and checks[1]["decision"] == "allow"
    print(f"ok  {len(forbidden_outputs)} вариантов нарушающего output блокируются до истории и SQLite")


def test_explicit_approval_allows_business_action(db):
    client = FakeClient("Публикация возможна только после явного подтверждения человека.")
    agent = make_agent(db, client)
    reply = agent.ask("Подготовь публикацию только после явного подтверждения человека")
    assert len(client.requests) == 1
    assert reply.finish_reason == "stop"
    assert reply.text in str(agent.store.load())
    checks = agent.store.invariant_checks()
    assert checks[0]["phase"] == "response" and checks[0]["decision"] == "allow"
    assert checks[1]["phase"] == "request" and checks[1]["decision"] == "allow"
    print("ok  external action разрешается только с явной позитивной approval-формулой")


def test_scope_isolation(db):
    one = make_agent(db, FakeClient())
    other = Agent(
        name="Агент дня 14",
        config=AgentConfig(max_tokens=100),
        store=SqliteStore(db, session="other", task_id="other", user_id="roman"),
        client=FakeClient(),
    )
    assert one.store.load_invariants()
    assert other.store.load_invariants() == ()
    print("ok  инварианты изолированы по user_id + task_id")


def test_legacy_policy_payload_is_readable(db):
    store = SqliteStore(db, session="legacy", task_id="legacy", user_id="roman")
    with sqlite3.connect(db) as connection:
        connection.execute(
            "INSERT INTO invariants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "roman", "legacy", "INV-OLD-001", "technical", "Старое правило",
                "Проверка совместимости", json.dumps([r"запрещено"]), 1,
                "2026-09-17T00:00:00+00:00",
            ),
        )
    loaded = store.load_invariants()
    assert len(loaded) == 1 and loaded[0].deny_patterns == ("запрещено",)
    assert loaded[0].forbidden_terms == () and loaded[0].response_patterns == ()
    print("ok  старый list payload инварианта читается после structured policy")


def test_workflow_does_not_save_blocked_output(db):
    raw = "Предлагаю перейти на PostgreSQL и заменить текущее хранилище."
    agent = make_agent(db, FakeClient(raw))
    agent.start_task("Подготовить архитектурный план")
    result = agent.run_to_boundary()
    assert result.reason == "invariant_violation"
    assert agent.task_state().stage.value == "planning"
    assert agent.workflow_state()["proposal"] is None
    print("ok  workflow не превращает заблокированный output в proposal или переход")


def main():
    with tempfile.TemporaryDirectory() as directory:
        test_request_conflict_is_local_refusal(Path(directory) / "request.db")
        test_safe_invariant_discussion_is_not_refusal(Path(directory) / "explain.db")
        test_invariants_survive_chat_clear_and_restart(Path(directory) / "restart.db")
        test_provider_violation_is_blocked_before_persistence(Path(directory) / "output.db")
        test_explicit_approval_allows_business_action(Path(directory) / "approval.db")
        test_scope_isolation(Path(directory) / "scope.db")
        test_legacy_policy_payload_is_readable(Path(directory) / "legacy.db")
        test_workflow_does_not_save_blocked_output(Path(directory) / "workflow.db")


if __name__ == "__main__":
    main()
