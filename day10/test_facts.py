"""Офлайн-проверки извлечения фактов. Сети не требуют."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from facts import FACT_KEYS, MAX_FACT_VALUE_CHARS, normalize, parse_facts  # noqa: E402
from strategies import FactsState  # noqa: E402

failures = []


def check(condition, message):
    if condition:
        print(f"ok  {message}")
    else:
        failures.append(message)
        print(f"FAIL {message}")


def test_unknown_key_dropped():
    check(
        normalize({"погода": "дождь", "цель": "сайт"}) == {"цель": "сайт"},
        "ключ вне списка отбрасывается",
    )


def test_all_declared_keys_pass():
    updates = {key: "значение" for key in FACT_KEYS}
    check(normalize(updates) == updates, "все объявленные ключи проходят")


def test_empty_value_does_not_delete():
    state = FactsState(values={"цель": "сайт"})
    for erasure in ("", "   ", None):
        merged = state.merge(normalize({"цель": erasure}))
        check(
            merged.values == {"цель": "сайт"}, f"значение {erasure!r} не стирает факт"
        )


def test_value_trimmed_to_limit():
    long_value = "я" * (MAX_FACT_VALUE_CHARS + 100)
    check(
        len(normalize({"цель": long_value})["цель"]) == MAX_FACT_VALUE_CHARS,
        "слишком длинное значение обрезается",
    )


def test_numbers_become_strings():
    check(
        normalize({"бюджет": 1200}) == {"бюджет": "1200"}, "число приводится к строке"
    )


def test_nested_value_refused():
    check(
        normalize({"цель": {"вложено": 1}}) == {},
        "вложенная структура вместо значения отбрасывается",
    )


def test_broken_json_returns_empty():
    for text in ("не JSON вовсе", "", "   ", "[1, 2, 3]", "null"):
        check(parse_facts(text) == {}, f"из {text!r} фактов не извлекается")


def test_json_in_code_fence_is_read():
    check(
        parse_facts('```json\n{"цель": "сайт"}\n```') == {"цель": "сайт"},
        "JSON в ограждении разбирается",
    )
    check(
        parse_facts('```\n{"цель": "сайт"}\n```') == {"цель": "сайт"},
        "ограждение без языка разбирается",
    )


def test_json_with_prose_around_is_read():
    text = 'Вот факты:\n{"цель": "сайт", "срок": "25 октября"}\nГотово.'
    check(
        parse_facts(text) == {"цель": "сайт", "срок": "25 октября"},
        "JSON среди текста находится",
    )


def test_kind_marker_matches_prompt():
    """Бюджет узнаёт служебный вызов по началу промпта, и хранит эту строку у себя.

    Разъехавшись, договорённость не сломала бы ничего заметного: цена памяти
    просто растворилась бы в счёте за обычные ответы.
    """
    from experiment import FACTS_KIND_MARKER
    from facts import FACTS_SYSTEM_PROMPT

    check(
        FACTS_SYSTEM_PROMPT.startswith(FACTS_KIND_MARKER),
        "бюджет узнаёт служебный вызов по началу промпта",
    )


def test_cancelled_decision_has_its_own_key():
    check(
        "отменённое_решение" in FACT_KEYS,
        "для отменённого решения заведён отдельный ключ",
    )


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
