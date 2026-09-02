"""Офлайн-проверки конфигуратора. Без API, поэтому быстро и бесплатно.

Проверяется не модель, а наш собственный валидатор. Баг здесь молча запишется
в ошибку модели — как во дне 2, где обрыв по max_tokens наивная проверка
засчитывала в заслугу stop.

Запуск:
    uv run day03/test_build.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build import (  # noqa: E402
    best_build,
    broken_rules,
    is_valid,
    minutes_of,
    parse_answer,
    price_of,
    score,
    weight_of,
)

OPTIMUM = {
    "frame": "F-220",
    "motor": "M-2",
    "props": "P-5",
    "esc": "E-30",
    "battery": "B-4S-2200",
}


def check_optimum() -> list[str]:
    build, valid_count = best_build()
    problems = []
    if build != OPTIMUM:
        problems.append(f"эталон: ждали {OPTIMUM}, получили {build}")
    if valid_count != 21:
        problems.append(f"валидных сборок: ждали 21, получили {valid_count}")
    if round(minutes_of(build), 2) != 2.75:
        problems.append(f"время: ждали 2.75, получили {minutes_of(build):.2f}")
    if price_of(build) != 189:
        problems.append(f"цена: ждали 189, получили {price_of(build)}")
    if weight_of(build) != 550:
        problems.append(f"вес: ждали 550, получили {weight_of(build)}")
    if not is_valid(OPTIMUM):
        problems.append(f"оптимум признан невалидным: {broken_rules(OPTIMUM)}")
    return problems


BROKEN = [
    (
        "правило 1: пропеллер не того размера, что мотор",
        {
            "frame": "F-220",
            "motor": "M-2",
            "props": "P-4",
            "esc": "E-30",
            "battery": "B-4S-2200",
        },
        "пропеллер",
    ),
    (
        "правило 2: пропеллер не влезает в раму",
        {
            "frame": "F-180",
            "motor": "M-2",
            "props": "P-5",
            "esc": "E-30",
            "battery": "B-4S-2200",
        },
        "рама",
    ),
    (
        "правило 3: аккумулятор не на то число банок",
        {
            "frame": "F-220",
            "motor": "M-2",
            "props": "P-5",
            "esc": "E-30",
            "battery": "B-6S-1300",
        },
        "банки",
    ),
    (
        "правило 4: регулятор не держит ток мотора",
        {
            "frame": "F-220",
            "motor": "M-2",
            "props": "P-5",
            "esc": "E-20",
            "battery": "B-4S-2200",
        },
        "регулятор",
    ),
    (
        "правило 5: аккумулятор не отдаёт нужный ток",
        {
            "frame": "F-280",
            "motor": "M-5",
            "props": "P-7",
            "esc": "E-50",
            "battery": "B-6S-1300",
        },
        "отдача",
    ),
    (
        "правило 6: тяги не хватает на такой вес",
        {
            "frame": "F-220",
            "motor": "M-2",
            "props": "P-5",
            "esc": "E-30",
            "battery": "B-4S-3000",
        },
        "тяга",
    ),
    (
        "правило 7: сборка дороже бюджета",
        {
            "frame": "F-250",
            "motor": "M-2",
            "props": "P-5",
            "esc": "E-50",
            "battery": "B-4S-2200",
        },
        "бюджет",
    ),
    (
        "позиции нет в каталоге",
        {
            "frame": "F-999",
            "motor": "M-2",
            "props": "P-5",
            "esc": "E-30",
            "battery": "B-4S-2200",
        },
        "нет в каталоге",
    ),
]

# Случаи, где должно ломаться РОВНО одно правило. Если валидатор ловит лишнее,
# значит сборка подобрана неудачно и тест проверяет не то, что заявлено.
SINGLE_FAULT = {
    "правило 1: пропеллер не того размера, что мотор",
    "правило 2: пропеллер не влезает в раму",
    "правило 3: аккумулятор не на то число банок",
    "правило 4: регулятор не держит ток мотора",
    "правило 6: тяги не хватает на такой вес",
    "правило 7: сборка дороже бюджета",
}


def check_rules() -> list[str]:
    problems = []
    for name, build, expected in BROKEN:
        found = broken_rules(build)
        if not any(expected in problem for problem in found):
            problems.append(f"{name}: ждали «{expected}», получили {found}")
        elif name in SINGLE_FAULT and len(found) != 1:
            problems.append(f"{name}: ждали одно нарушение, получили {found}")
    return problems


GOOD_LINE = "ОТВЕТ: frame=F-220, motor=M-2, props=P-5, esc=E-30, battery=B-4S-2200"

PARSING = [
    ("обычный ответ", f"Долгие рассуждения...\n{GOOD_LINE}", OPTIMUM),
    ("текст после строки ответа", f"{GOOD_LINE}\nНадеюсь, помог!", OPTIMUM),
    (
        "другой порядок позиций",
        "ОТВЕТ: battery=B-4S-2200, esc=E-30, props=P-5, motor=M-2, frame=F-220",
        OPTIMUM,
    ),
    (
        "две строки ОТВЕТ, берём последнюю",
        "ОТВЕТ: frame=F-180, motor=M-1, props=P-4, esc=E-20, battery=B-4S-1300\n"
        f"Стоп, пересчитал.\n{GOOD_LINE}",
        OPTIMUM,
    ),
    ("markdown вокруг", f"**{GOOD_LINE}**", OPTIMUM),
    ("строчными буквами", GOOD_LINE.replace("ОТВЕТ", "ответ"), OPTIMUM),
    (
        "без запятых",
        "ОТВЕТ: frame=F-220 motor=M-2 props=P-5 esc=E-30 battery=B-4S-2200",
        OPTIMUM,
    ),
    ("в блоке кода", f"```\n{GOOD_LINE}\n```", OPTIMUM),
    ("пробелы вокруг знака равенства", GOOD_LINE.replace("=", " = "), OPTIMUM),
    ("не хватает позиции", "ОТВЕТ: frame=F-220, motor=M-2, props=P-5, esc=E-30", None),
    ("лишняя позиция", f"{GOOD_LINE}, camera=C-1", None),
    ("слово есть, пар нет", "ОТВЕТ: думаю, надо взять F-220 и M-2", None),
    ("строки ОТВЕТ нет вовсе", "Пожалуй, F-220 и M-2 подойдут.", None),
    ("пустой ответ", "", None),
]


def check_parsing() -> list[str]:
    problems = []
    for name, text, expected in PARSING:
        got = parse_answer(text)
        if got != expected:
            problems.append(f"разбор, {name}: ждали {expected}, получили {got}")
    return problems


def line(**parts: str) -> str:
    return "ОТВЕТ: " + ", ".join(f"{key}={value}" for key, value in parts.items())


SCORING = [
    (
        "оптимум",
        line(frame="F-220", motor="M-2", props="P-5", esc="E-30", battery="B-4S-2200"),
        {
            "parsed": True,
            "invented": False,
            "valid": True,
            "in_budget": True,
            "optimal": True,
            "minutes": 2.75,
        },
    ),
    (
        "валидна, но не оптимум",
        line(frame="F-180", motor="M-1", props="P-4", esc="E-20", battery="B-4S-1300"),
        {
            "parsed": True,
            "invented": False,
            "valid": True,
            "in_budget": True,
            "optimal": False,
        },
    ),
    (
        "нарушено правило, но не бюджет",
        line(frame="F-180", motor="M-2", props="P-5", esc="E-30", battery="B-4S-2200"),
        {
            "parsed": True,
            "invented": False,
            "valid": False,
            "in_budget": True,
            "optimal": False,
            "minutes": 0.0,
        },
    ),
    (
        "вылезла за бюджет",
        line(frame="F-250", motor="M-2", props="P-5", esc="E-50", battery="B-4S-2200"),
        {
            "parsed": True,
            "invented": False,
            "valid": False,
            "in_budget": False,
            "optimal": False,
        },
    ),
    (
        # Главный случай: цену выдуманной сборки посчитать не на чем,
        # поэтому in_budget обязан быть False, а не True по умолчанию.
        "выдуманная деталь не должна засчитываться как «в бюджете»",
        line(frame="F-220", motor="M-9", props="P-5", esc="E-30", battery="B-4S-2200"),
        {
            "parsed": True,
            "invented": True,
            "valid": False,
            "in_budget": False,
            "optimal": False,
            "minutes": 0.0,
        },
    ),
    (
        "ответ не разобрался",
        "Думаю, подойдёт что-нибудь лёгкое.",
        {
            "parsed": False,
            "invented": False,
            "valid": False,
            "in_budget": False,
            "optimal": False,
            "minutes": 0.0,
        },
    ),
]


def check_scoring() -> list[str]:
    problems = []
    for name, answer, expected in SCORING:
        got = score(answer)
        for key, value in expected.items():
            actual = round(got[key], 2) if key == "minutes" else got[key]
            if actual != value:
                problems.append(
                    f"метрики, {name}: {key} ждали {value}, получили {actual}"
                )
    return problems


def main() -> None:
    problems = check_optimum() + check_rules() + check_parsing() + check_scoring()
    if problems:
        print("FAIL")
        for problem in problems:
            print(f"        {problem}")
        sys.exit(1)

    print("ok    эталон: сборка, время, цена, вес и число валидных совпали")
    print(f"ok    правила: {len(BROKEN)} нарушений ловятся, каждое своим сообщением")
    print(
        f"ok    разбор:  {len(PARSING)} случаев, из них "
        f"{sum(1 for _, _, expected in PARSING if expected is None)} должны дать None"
    )
    print(
        f"ok    метрики: {len(SCORING)} случаев, включая выдуманную деталь "
        f"и разведение «невалидна» с «не в бюджете»"
    )


if __name__ == "__main__":
    main()
