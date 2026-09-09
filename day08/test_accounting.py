"""Регрессии учёта расхода. Только временные базы и подставной API."""

import io
import sqlite3
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from agent import Agent
from cli import show_growth, show_store
from store import SqliteStore
from test_agent import FakeClient
from tokens import count_text


def test_empty_is_paid_but_not_history(path):
    store = SqliteStore(path, 'empty')
    reply = Agent(client=FakeClient(''), store=store).ask('вопрос')
    revived = SqliteStore(path, 'empty')
    assert revived.load() == []
    assert revived.stats()['turns'] == 0
    assert revived.stats()['calls'] == 1
    assert revived.stats()['prompt_tokens'] == reply.prompt_tokens == 100
    assert revived.stats()['completion_tokens'] == 20
    assert revived.stats()['cost_reported'] == 0.0001
    assert revived.growth()[0]['empty'] == 1


def test_missing_usage_does_not_become_zero(path):
    store = SqliteStore(path, 'missing')
    agent = Agent(client=FakeClient(), store=store)
    agent.ask('с замером')
    agent.client.usage = None
    agent.ask('без замера')
    stats = store.stats()
    assert stats['calls'] == 2
    assert stats['prompt_tokens'] is None
    assert stats['completion_tokens'] is None
    assert stats['cost_reported'] is None
    output = io.StringIO()
    with redirect_stdout(output):
        show_growth(store)
        show_store(store)
    assert 'вход ?' in output.getvalue()
    assert '?' in output.getvalue().splitlines()[2]


def test_zero_is_valid_usage(path):
    usage = SimpleNamespace(prompt_tokens=0, completion_tokens=0, cost=0.0)
    store = SqliteStore(path, 'zero')
    reply = Agent(client=FakeClient(usage=usage), store=store).ask('вопрос')
    assert store.stats()['prompt_tokens'] == 0
    assert store.stats()['cost_reported'] == 0.0
    assert '0→0' in reply.debug_line()


def test_failed_history_write_keeps_usage(path):
    class BrokenHistory(SqliteStore):
        def append_turn(self, question, reply):
            raise RuntimeError('диск переписки недоступен')

    store = BrokenHistory(path, 'broken-history')
    reply = Agent(client=FakeClient(), store=store).ask('вопрос')
    assert reply.ok and not reply.saved
    assert store.load() == []
    assert SqliteStore(path, 'broken-history').stats()['prompt_tokens'] == 100


def test_failed_accounting_write_is_visible(path):
    class BrokenAccounting(SqliteStore):
        def append_call(self, reply):
            raise RuntimeError('диск расхода недоступен')

    store = BrokenAccounting(path, 'broken-usage')
    reply = Agent(client=FakeClient(), store=store).ask('вопрос')
    assert reply.ok and not reply.saved
    assert 'учёт расхода' in reply.store_error
    assert len(store.load()) == 2


def test_clear_only_own_accounting(path):
    left = SqliteStore(path, 'left')
    right = SqliteStore(path, 'right')
    Agent(client=FakeClient(''), store=left).ask('левый')
    Agent(client=FakeClient(), store=right).ask('правый')
    left.clear()
    assert left.stats()['calls'] == 0
    assert right.stats()['calls'] == 1


def test_migration_backfills_once(path):
    # Настоящая схема v1: без журнала calls. Не имитация новой базы с другим PRAGMA.
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT, role TEXT,
                content TEXT, created_at TEXT, model TEXT, elapsed REAL,
                prompt_tokens INTEGER, completion_tokens INTEGER, cost REAL
            );
            INSERT INTO messages VALUES (1, 'legacy', 'user', 'вопрос', '2026-09-09', NULL, NULL, NULL, NULL, NULL);
            INSERT INTO messages VALUES (2, 'legacy', 'assistant', 'ответ', '2026-09-09', 'gpt-oss-20b', 1, 123, 45, 0.001);
            PRAGMA user_version = 1;
        ''')
    for _ in range(3):
        store = SqliteStore(path, 'legacy')
        assert len(store.load()) == 2
        assert store.stats()['calls'] == 1
        assert store.stats()['prompt_tokens'] == 123
        assert store.stats()['cost_reported'] is None
    Agent(client=FakeClient(), store=store).ask('новый вопрос')
    assert store.stats()['calls'] == 2
    assert store.stats()['prompt_tokens'] == 223


def test_special_tokens_are_user_text(path):
    assert count_text('Поясни строку <|endoftext|>') > 0
    assert Agent(client=FakeClient()).ask('Поясни строку <|endoftext|>').ok


def main():
    tests = [value for name, value in globals().items() if name.startswith('test_')]
    for test in tests:
        with tempfile.TemporaryDirectory() as tmp:
            test(Path(tmp) / 'test.db')
        print(f'ok   {test.__name__}')
    print(f'{len(tests)} из {len(tests)} проверок прошли')


if __name__ == '__main__':
    main()
