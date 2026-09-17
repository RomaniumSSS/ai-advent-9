"""Офлайн: проверяем фактические вызовы клиента и отдельное хранение."""
import json
import socket
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import base_agent
from profile import UserProfile, DEMO_PROFILES
from test_memory import agent, FakeClient, test_scope_and_restart, test_prompt_and_archive
from tokens import count_messages


def check_profiles(db):
    fake = FakeClient()
    first = agent(db, "a", user="a", client=fake)
    assert first.store.load_profile() == UserProfile()
    first.store.save_profile(DEMO_PROFILES["brief"])
    original = first.store.load_profile
    reads = []
    def read():
        reads.append(1)
        return original()
    first.store.load_profile = read
    for question in ["Как учиться?", "Ещё совет"]:
        reply = first.ask(question)
        assert reply.saved and reply.ok
        assert reply.budget.prompt == count_messages(fake.requests[-1]["messages"])
    assert len(reads) == 2
    first.store.save_profile(DEMO_PROFILES["detail"])
    first.ask("Теперь подробно")
    assert 'Подробно' in fake.requests[-1]["messages"][1]["content"]
    first.reset()
    assert first.store.load_profile() == DEMO_PROFILES["detail"]
    reopened = agent(db, "a", user="a", client=fake)
    reopened.ask("После перезапуска")
    other_task = agent(db, "new-task", user="a", task="other", client=fake)
    other_task.ask("Другая задача")
    second = agent(db, "b", user="b", client=fake)
    second.store.save_profile(DEMO_PROFILES["brief"])
    assert not second.history
    second.ask("Как учиться?")
    again = agent(db, "a", user="a", client=fake)
    assert all("Как учиться?" != m["content"] for m in again.history)
    again.ask("Возврат A")
    for index, request in enumerate(fake.requests):
        blocks = [m for m in request["messages"] if m["content"].startswith("ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ")]
        assert len(blocks) == 1
        expected = "Кратко" if index in (0, 1, 5) else "Подробно"
        assert expected in blocks[0]["content"]
    # Одинаковые история и вопрос; различается только отдельный блок профиля.
    a = agent(db, "ab-a", user="a", client=fake)
    b = agent(db, "ab-b", user="b", client=fake)
    a.ask("Один вопрос"); b.ask("Один вопрос")
    left, right = [r["messages"] for r in fake.requests[-2:]]
    assert left[:1] + left[2:] == right[:1] + right[2:]
    assert left[1] != right[1]
    Path("results/profile-ab.json").write_text(json.dumps({"a":left,"b":right}, ensure_ascii=False, indent=2))
    with sqlite3.connect(db) as connection:
        for table in ["messages", "short_notes", "working_notes", "long_notes"]:
            rows = str(connection.execute(f"SELECT * FROM {table}").fetchall())
            assert "ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ" not in rows
            assert "Кратко и практично" not in rows
        # Совместимое открытие прежней схемы без потери архива.
        connection.execute("PRAGMA user_version=1")
        connection.execute("DROP TABLE user_profiles")
    restored = agent(db, "a", user="a", client=fake)
    assert restored.history == again.history
    assert restored.store.load_profile() == UserProfile()
    print("ok  каждый вызов, единый снимок, бюджет, правка, reset, restart, A/B, A→B→A, миграция")


def check_with_config(db):
    fake = FakeClient()
    current = agent(db, "config", user="config-user", recent=3, client=fake)
    current.store.save_profile(DEMO_PROFILES["brief"])
    assert current.ask("Старый разговор").ok
    changed = current.with_config(max_tokens=77, system_prompt="Новая роль")
    assert type(changed) is type(current)
    assert changed.client is fake and changed.store is current.store
    assert changed.recent_turns == 3 and changed.name == current.name
    assert changed.history == [] and changed.store.load() == []
    assert changed.store.load_profile() == DEMO_PROFILES["brief"]
    assert current.config.max_tokens == 100
    for profile in (DEMO_PROFILES["brief"], DEMO_PROFILES["detail"]):
        changed.store.save_profile(profile)
        reply = changed.ask("После смены конфигурации")
        assert reply.ok and reply.saved
        request = fake.requests[-1]
        blocks = [m for m in request["messages"]
                  if m["content"].startswith("ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ")]
        assert blocks == [profile.message()]
        assert request["max_tokens"] == 77
        assert request["messages"][0]["content"] == "Новая роль"
        assert not any(m["content"] == "Старый разговор" for m in request["messages"])
        assert reply.budget.prompt == count_messages(request["messages"])
    assert len(fake.requests) == 3
    print("ok  with_config сохраняет класс, клиент, настройки и профиль каждого фактического запроса")


def check_errors(db):
    fake = FakeClient()
    current = agent(db, "errors", client=fake)
    current.store.save_profile(DEMO_PROFILES["brief"])
    for value in [{}, {"style":"x","format":"y","constraints":[]}, {"style":"x"*1001,"format":"y","constraints":"z"}, {**UserProfile().to_dict(), "extra":True}]:
        try:
            UserProfile.from_dict(value)
        except ValueError:
            pass
        else:
            raise AssertionError("невалидный профиль принят")
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TRIGGER fail_profile BEFORE UPDATE ON user_profiles BEGIN SELECT RAISE(ABORT, 'disk failure'); END")
    try:
        current.store.save_profile(DEMO_PROFILES["detail"])
    except sqlite3.Error:
        pass
    else:
        raise AssertionError("сбой записи скрыт")
    assert current.store.load_profile() == DEMO_PROFILES["brief"]
    with patch.object(current.store, "load_profile", side_effect=sqlite3.OperationalError("read failure")):
        try:
            current.ask("вопрос")
        except sqlite3.Error:
            pass
        else:
            raise AssertionError("сбой чтения скрыт")
    assert fake.requests == []
    print("ok  валидация, атомарность при ошибке SQLite, запрет вызова при ошибке чтения")


def main():
    with patch.object(base_agent, "get_client", side_effect=AssertionError("реальный клиент запрещён")), patch.object(socket.socket, "connect", side_effect=AssertionError("сеть запрещена")):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "test.db"
            test_scope_and_restart(db)
            test_prompt_and_archive(db)
            check_profiles(db)
            check_with_config(db)
            check_errors(db)


if __name__ == "__main__":
    main()
