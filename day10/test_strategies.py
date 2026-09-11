"""Офлайн-проверки сборки контекста. Сети не требуют."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from strategies import (  # noqa: E402
    FACTS_PREFIX,
    FactsState,
    StrategyConfig,
    context_history,
)

failures = []


def check(condition, message):
    if condition:
        print(f"ok  {message}")
    else:
        failures.append(message)
        print(f"FAIL {message}")


def messages(count):
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
        for i in range(count)
    ]


def test_sliding_keeps_tail():
    result = context_history(
        StrategyConfig("sliding", recent_messages=4), messages(10), FactsState()
    )
    check(
        [m["content"] for m in result] == ["m6", "m7", "m8", "m9"],
        "sliding отдаёт последние N сообщений",
    )


def test_sliding_shorter_history_is_whole():
    result = context_history(
        StrategyConfig("sliding", recent_messages=6), messages(2), FactsState()
    )
    check(len(result) == 2, "sliding на короткой истории отдаёт её целиком")


def test_full_returns_everything():
    result = context_history(StrategyConfig("full"), messages(10), FactsState())
    check(len(result) == 10, "full отдаёт всю историю")


def test_facts_block_first_and_not_system():
    facts = FactsState(values={"цель": "сайт записи"})
    result = context_history(
        StrategyConfig("facts", recent_messages=2), messages(10), facts
    )
    first = result[0]
    check(first["role"] == "assistant", "блок facts не получает системную роль")
    check(first["content"].startswith(FACTS_PREFIX), "блок facts помечен как память")
    check("цель: сайт записи" in first["content"], "факт виден в блоке")
    check(len(result) == 3, "facts шлёт блок плюс последние N сообщений")


def test_facts_without_values_sends_no_block():
    result = context_history(
        StrategyConfig("facts", recent_messages=2), messages(4), FactsState()
    )
    check(len(result) == 2, "пустая память не занимает место в запросе")


def test_merge_overwrites_and_bumps_revision():
    state = FactsState(values={"срок": "18 октября"})
    changed = state.merge({"срок": "25 октября"})
    check(changed.values["срок"] == "25 октября", "перезапись меняет значение")
    check(changed.revision == state.revision + 1, "перезапись увеличивает revision")
    check(state.values["срок"] == "18 октября", "прежнее состояние не менялось")


def test_merge_without_changes_returns_same_state():
    state = FactsState(values={"цель": "сайт"})
    check(
        state.merge({"цель": "сайт"}) is state, "мерж без изменений не плодит состояния"
    )


def test_unknown_strategy_refused():
    try:
        StrategyConfig("magic")
    except ValueError:
        check(True, "неизвестная стратегия отвергается")
        return
    check(False, "неизвестная стратегия отвергается")


def test_recent_messages_validated():
    for bad in (0, -1, True, 1.5):
        try:
            StrategyConfig("sliding", recent_messages=bad)
        except (ValueError, TypeError):
            continue
        check(False, f"recent_messages={bad!r} должен отвергаться")
        return
    check(True, "recent_messages проверяется на тип и диапазон")


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
