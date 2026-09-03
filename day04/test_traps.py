"""Офлайн-проверки капканов дня 4. Без API.

Проверяется не модель, а наши же проверки: подсчёт эталона буквы и код,
который решает, выполнены ли четыре требования гаджет-питча.

Запуск:
    uv run day04/test_traps.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from traps import (  # noqa: E402
    HUMAN_EXAMPLE,
    check_gadget,
    letter_truth,
    normalize,
    score_letter,
)


def check_letter_truth() -> list[str]:
    problems = []
    if letter_truth() != 3:
        problems.append(f"эталон буквы: ждали 3, получили {letter_truth()}")
    return problems


LETTER_PARSING = [
    ("голое число", "3", {"parsed": True, "value": 3, "correct": True}),
    (
        "число с текстом",
        "В слове 3 буквы «с».",
        {"parsed": True, "value": 3, "correct": True},
    ),
    ("неверное число", "4", {"parsed": True, "value": 4, "correct": False}),
    (
        "рассуждение, ответ последним числом",
        "Считаю по буквам: р-а-с-с... получилось 3",
        {"parsed": True, "value": 3, "correct": True},
    ),
    (
        "прописью, не парсится",
        "три",
        {"parsed": False, "value": None, "correct": False},
    ),
    ("пусто", "", {"parsed": False, "value": None, "correct": False}),
]


def check_letter_parsing() -> list[str]:
    problems = []
    for name, text, expected in LETTER_PARSING:
        got = score_letter(text)
        if got != expected:
            problems.append(f"буквы, {name}: ждали {expected}, получили {got}")
    return problems


GADGET_CASES = [
    ("не 3 предложения", "Термочашка. Цена 500 руб.", "sentences", False),
    (
        "есть 3 предложения для контраста",
        "Термочашка. Цена 500 руб. Держит тепло, надёжно.",
        "sentences",
        True,
    ),
    (
        "нет цены",
        "Термокружка держит тепло долго. Она прочная и лёгкая. Всем советую.",
        "price",
        False,
    ),
    (
        "есть цена",
        "Термокружка стоит 500 руб. Она прочная. Всем советую.",
        "price",
        True,
    ),
    (
        "цена словом «доллары»",
        "Штука. Цена 499 долларов. Она экономит время.",
        "price",
        True,
    ),
    ("нет слов выгоды", "Штука. Цена 10 руб. Просто штука.", "benefit", False),
    (
        "есть слово выгоды (глагол)",
        "Гаджет экономит время. Цена 10 руб. Просто гаджет.",
        "benefit",
        True,
    ),
    ("есть слово выгоды (прилагательное)", HUMAN_EXAMPLE, "benefit", True),
    (
        "запрещённый корень есть",
        "Революционный гаджет. Цена 10 руб. Он экономит время.",
        "no_banned",
        False,
    ),
    (
        "запрещённого корня нет",
        "Обычный гаджет. Цена 10 руб. Он экономит время.",
        "no_banned",
        True,
    ),
]


def check_gadget_requirements() -> list[str]:
    problems = []
    for name, text, key, expected in GADGET_CASES:
        got = check_gadget(text)[key]
        if got != expected:
            problems.append(f"гаджет, {name}: ждали {key}={expected}, получили {got}")
    return problems


def check_human_example() -> list[str]:
    problems = []
    result = check_gadget(HUMAN_EXAMPLE)
    if result["score"] != 4:
        problems.append(f"человеческий эталон: ждали score=4, получили {result}")
    return problems


def check_normalize() -> list[str]:
    problems = []
    base = normalize("Уже Готово!")
    variant = normalize("  Уже   готово!  ")
    if base != variant:
        problems.append(f"normalize: не совпали {base!r} vs {variant!r}")
    other = normalize("Термочашка")
    if base == other:
        problems.append("normalize: разные тексты схлопнулись в одно")
    return problems


def main() -> None:
    problems = (
        check_letter_truth()
        + check_letter_parsing()
        + check_gadget_requirements()
        + check_human_example()
        + check_normalize()
    )
    if problems:
        print("FAIL")
        for problem in problems:
            print(f"        {problem}")
        sys.exit(1)

    print("ok    эталон буквы: «рассредоточенность» содержит 3 «с»")
    print(f"ok    разбор числового ответа: {len(LETTER_PARSING)} случаев")
    print(f"ok    четыре требования гаджета: {len(GADGET_CASES)} случаев")
    print("ok    человеческий эталон проходит все 4 требования")
    print("ok    normalize схлопывает регистр и пробелы, не путает разные тексты")


if __name__ == "__main__":
    main()
