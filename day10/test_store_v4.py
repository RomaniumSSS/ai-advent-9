"""Офлайн-проверки хранилища дня 10: facts и ветки. Сети не требуют."""

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from store import SqliteStore  # noqa: E402

failures = []


def check(condition, message):
    if condition:
        print(f"ok  {message}")
    else:
        failures.append(message)
        print(f"FAIL {message}")


@dataclass
class FakeReply:
    """Достаточно полей, чтобы `append_turn` записал ход."""

    text: str = "ответ"
    model: str = "deepseek-v4-flash"
    elapsed: float = 0.1
    prompt_tokens: int = 10
    completion_tokens: int = 5
    cost: float = 0.000001
    cost_reported: float = 0.000001
    empty: bool = False


def store(directory, session="main"):
    return SqliteStore(Path(directory) / "history.db", session)


def with_turns(directory, session, count):
    target = store(directory, session)
    target.remember_config("deepseek-v4-flash", "роль")
    for index in range(count):
        target.append_turn(f"вопрос {index}", FakeReply())
    return target


def test_facts_roundtrip():
    with tempfile.TemporaryDirectory() as directory:
        target = store(directory)
        target.save_facts({"цель": "сайт записи", "бюджет": "1200 евро"})
        check(
            target.load_facts() == {"бюджет": "1200 евро", "цель": "сайт записи"},
            "facts переживают запись и чтение",
        )
        target.save_facts({"цель": "сайт бронирования"})
        check(
            target.load_facts()["цель"] == "сайт бронирования",
            "повторная запись обновляет значение",
        )
        check(
            "бюджет" in target.load_facts(), "запись одного ключа не стирает остальные"
        )


def test_facts_are_per_session():
    with tempfile.TemporaryDirectory() as directory:
        store(directory, "main").save_facts({"цель": "сайт"})
        check(
            store(directory, "other").load_facts() == {},
            "facts не видны из другой сессии",
        )


def test_fork_copies_prefix_only():
    with tempfile.TemporaryDirectory() as directory:
        source = with_turns(directory, "main", 3)
        source.save_facts({"цель": "сайт"})
        source.fork("main/a", checkpoint=4)
        branch = store(directory, "main/a")
        check(len(branch.load()) == 4, "в ветку уехали только сообщения до границы")
        check(len(source.load()) == 6, "исходная сессия не изменилась")
        check(branch.load_facts() == {"цель": "сайт"}, "facts скопированы в ветку")


def test_branches_are_independent():
    with tempfile.TemporaryDirectory() as directory:
        source = with_turns(directory, "main", 1)
        source.fork("main/a", checkpoint=2)
        source.fork("main/b", checkpoint=2)
        with_turns(directory, "main/a", 1)
        check(len(source.load()) == 2, "ход в ветке не попал в исходную сессию")
        check(len(store(directory, "main/b").load()) == 2, "ветки не видят друг друга")
        names = [row["session"] for row in source.branches()]
        check(names == ["main/a", "main/b"], "обе ветки записаны в журнал")


def test_checkpoint_beyond_history_refused():
    with tempfile.TemporaryDirectory() as directory:
        source = with_turns(directory, "main", 1)
        try:
            source.fork("main/a", checkpoint=99)
        except ValueError:
            check(True, "граница вне истории отвергается")
        else:
            check(False, "граница вне истории отвергается")
        check(store(directory, "main/a").load() == [], "после отказа ветка не создана")


def test_existing_session_not_overwritten():
    with tempfile.TemporaryDirectory() as directory:
        source = with_turns(directory, "main", 1)
        with_turns(directory, "main/a", 1)
        try:
            source.fork("main/a", checkpoint=2)
        except ValueError:
            check(True, "занятое имя ветки отвергается")
        else:
            check(False, "занятое имя ветки отвергается")


def test_clear_removes_facts_and_branch_record():
    with tempfile.TemporaryDirectory() as directory:
        source = with_turns(directory, "main", 1)
        source.save_facts({"цель": "сайт"})
        source.fork("main/a", checkpoint=2)
        branch = store(directory, "main/a")
        branch.clear()
        check(branch.load_facts() == {}, "очистка ветки уносит её facts")
        check(source.branches() == [], "очистка ветки уносит запись о ней")
        check(len(source.load()) == 2, "очистка ветки не тронула исходную сессию")


def test_usage_split_by_kind():
    with tempfile.TemporaryDirectory() as directory:
        target = store(directory)
        target.append_call(FakeReply(), kind="chat")
        target.append_call(FakeReply(), kind="facts")
        usage = target.usage_by_kind()
        check(usage["chat"]["calls"] == 1, "вызовы чата считаются отдельно")
        check(usage["facts"]["calls"] == 1, "вызовы facts считаются отдельно")
        check(usage["total"]["calls"] == 2, "итог включает оба вида")


def main():
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    if failures:
        print(f"\nПРОВАЛЕНО {len(failures)}:")
        for item in failures:
            print(f"  - {item}")
        raise SystemExit(1)
    print("\nвсе проверки прошли")


if __name__ == "__main__":
    main()
