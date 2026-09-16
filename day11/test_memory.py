"""Офлайн-проверка срока жизни трёх слоёв и фактического запроса агенту."""

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig  # noqa: E402
from store import SqliteStore  # noqa: E402


class FakeClient:
    def __init__(self):
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="ответ модели"),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=50, completion_tokens=5, cost=0.00001),
        )


def agent(db, session, task="landing", user="roman", recent=2, client=None):
    return Agent(
        config=AgentConfig(max_tokens=100),
        store=SqliteStore(db, session, task, user),
        recent_turns=recent,
        client=client,
    )


def test_scope_and_restart(db):
    first = agent(db, "chat-1")
    first.save("short", "ссылка", "макет 1")
    first.save("working", "срок", "18 сентября")
    first.save("long", "язык", "русский")
    assert first.store.notes() == {
        "short": {"ссылка": "макет 1"},
        "working": {"срок": "18 сентября"},
        "long": {"язык": "русский"},
    }

    reopened = agent(db, "chat-1")
    assert reopened.store.notes() == first.store.notes(), "записи пережили перезапуск"
    second_chat = agent(db, "chat-2")
    assert second_chat.store.notes() == {
        "short": {},
        "working": {"срок": "18 сентября"},
        "long": {"язык": "русский"},
    }, "рабочая память переживает смену сессии, короткая — нет"
    other_task = agent(db, "chat-3", task="shop")
    assert other_task.store.notes() == {
        "short": {}, "working": {}, "long": {"язык": "русский"}
    }, "долговременная память переживает смену задачи"
    other_user = agent(db, "chat-4", task="landing", user="anna")
    assert all(not notes for notes in other_user.store.notes().values()), (
        "чужому пользователю не видна память Романа"
    )

    first.reset()
    assert first.store.notes()["short"] == {}, "reset убирает короткие заметки"
    assert first.store.notes()["working"] == {"срок": "18 сентября"}
    assert first.store.notes()["long"] == {"язык": "русский"}
    assert first.forget("working", "срок")
    assert second_chat.store.notes()["working"] == {}, "удаление видно всей задаче"
    try:
        agent(db, "chat-1", task="shop")
    except ValueError:
        pass
    else:
        raise AssertionError("нельзя переназначить сессию другой задаче")
    print("ok  слои изолированы по сессии, задаче и пользователю")


def test_prompt_and_archive(db):
    client = FakeClient()
    current = agent(db, "prompt-chat", recent=2, client=client)
    current.save("working", "срок", "18 сентября")
    note_reads = 0
    original_notes = current.store.notes

    def counted_notes():
        nonlocal note_reads
        note_reads += 1
        return original_notes()

    current.store.notes = counted_notes
    for index in range(4):
        reply = current.ask(f"Вопрос {index}")
        assert reply.ok and reply.saved
    assert note_reads == 4, "каждый вызов читает единый снимок памяти один раз"
    assert len(current.history) == 8, "полный архив остаётся на диске"
    context = current.build_messages("Назови срок")
    assert context[0]["role"] == "system"
    assert any("18 сентября" in row["content"] for row in context), (
        "рабочий слой действительно входит в запрос"
    )
    assert not any("Вопрос 0" in row["content"] for row in context), (
        "старые реплики не входят в короткий контекст"
    )
    assert any("Вопрос 3" in row["content"] for row in context)
    assert current.budget("Назови срок").prompt > current.budget("Назови").prompt
    assert len(agent(db, "prompt-chat").history) == 8, "архив переживает запуск"
    print("ok  память попадает в запрос, окно ограничено без удаления архива")


def main():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "memory.db"
        test_scope_and_restart(db)
        test_prompt_and_archive(db)


if __name__ == "__main__":
    main()
