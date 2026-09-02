"""День 3: задача-конфигуратор и эталонный решатель.

Обращений к API здесь нет. Только каталог, правила совместимости, проверка сборки
и полный перебор, дающий правильный ответ. Эталон считает машина, а не человек,
поэтому сравнение способов рассуждения получает честную единицу измерения.

Каталог вымышленный намеренно: на реальных названиях модель могла бы вспомнить
ответ из обучения вместо того, чтобы вывести его.

Запуск:
    uv run day03/build.py
"""

from itertools import product

BUDGET = 210
THRUST_RATIO = 2.5
THROTTLE = 0.5  # доля газа, на которой считается среднее потребление

FRAMES = {
    "F-180": {"max_prop": 4, "weight": 75, "price": 35},
    "F-220": {"max_prop": 5, "weight": 95, "price": 40},
    "F-250": {"max_prop": 6, "weight": 120, "price": 55},
    "F-280": {"max_prop": 7, "weight": 150, "price": 70},
}

MOTORS = {  # вес и цена за ОДИН мотор, тяга и ток тоже на один
    "M-1": {
        "prop": 4,
        "cells": 4,
        "thrust": 300,
        "current": 18,
        "weight": 28,
        "price": 14,
    },
    "M-2": {
        "prop": 5,
        "cells": 4,
        "thrust": 400,
        "current": 24,
        "weight": 32,
        "price": 16,
    },
    "M-3": {
        "prop": 5,
        "cells": 6,
        "thrust": 520,
        "current": 28,
        "weight": 34,
        "price": 19,
    },
    "M-4": {
        "prop": 6,
        "cells": 6,
        "thrust": 640,
        "current": 34,
        "weight": 41,
        "price": 23,
    },
    "M-5": {
        "prop": 7,
        "cells": 6,
        "thrust": 780,
        "current": 42,
        "weight": 48,
        "price": 28,
    },
}

PROPS = {  # комплект из четырёх
    "P-4": {"size": 4, "weight": 12, "price": 5},
    "P-5": {"size": 5, "weight": 16, "price": 6},
    "P-6": {"size": 6, "weight": 22, "price": 8},
    "P-7": {"size": 7, "weight": 30, "price": 11},
}

ESCS = {  # вес и цена за ОДИН регулятор
    "E-20": {"max_current": 20, "weight": 7, "price": 9},
    "E-30": {"max_current": 30, "weight": 9, "price": 12},
    "E-40": {"max_current": 40, "weight": 12, "price": 16},
    "E-50": {"max_current": 50, "weight": 15, "price": 21},
}

BATTERIES = {
    "B-4S-1300": {"cells": 4, "mah": 1300, "c": 75, "weight": 160, "price": 22},
    "B-4S-2200": {"cells": 4, "mah": 2200, "c": 60, "weight": 275, "price": 31},
    "B-4S-3000": {"cells": 4, "mah": 3000, "c": 45, "weight": 375, "price": 40},
    "B-6S-1300": {"cells": 6, "mah": 1300, "c": 100, "weight": 235, "price": 34},
    "B-6S-2200": {"cells": 6, "mah": 2200, "c": 80, "weight": 390, "price": 47},
    "B-6S-3000": {"cells": 6, "mah": 3000, "c": 60, "weight": 530, "price": 60},
}

PARTS = ("frame", "motor", "props", "esc", "battery")

CATALOGS = {
    "frame": FRAMES,
    "motor": MOTORS,
    "props": PROPS,
    "esc": ESCS,
    "battery": BATTERIES,
}

QUANTITY = {"frame": 1, "motor": 4, "props": 1, "esc": 4, "battery": 1}


def weight_of(build: dict) -> int:
    """Взлётный вес в граммах. Моторы и регуляторы считаются по четыре."""
    return sum(CATALOGS[part][build[part]]["weight"] * QUANTITY[part] for part in PARTS)


def price_of(build: dict) -> int:
    return sum(CATALOGS[part][build[part]]["price"] * QUANTITY[part] for part in PARTS)


def minutes_of(build: dict) -> float:
    """Расчётное время полёта. Средний ток берётся на половине газа."""
    average_current = 4 * MOTORS[build["motor"]]["current"] * THROTTLE
    return BATTERIES[build["battery"]]["mah"] / 1000 / average_current * 60


def broken_rules(build: dict) -> list[str]:
    """Список нарушенных правил. Пустой список означает валидную сборку."""
    for part in PARTS:
        name = build.get(part)
        if name not in CATALOGS[part]:
            return [f"позиция {part}: {name!r} нет в каталоге"]

    frame = FRAMES[build["frame"]]
    motor = MOTORS[build["motor"]]
    props = PROPS[build["props"]]
    esc = ESCS[build["esc"]]
    battery = BATTERIES[build["battery"]]

    problems = []
    if props["size"] != motor["prop"]:
        problems.append(
            f'пропеллер: комплект {props["size"]}", мотор рассчитан на {motor["prop"]}"'
        )
    if props["size"] > frame["max_prop"]:
        problems.append(
            f'рама: пропеллер {props["size"]}", рама держит {frame["max_prop"]}"'
        )
    if battery["cells"] != motor["cells"]:
        problems.append(
            f"банки: аккумулятор {battery['cells']}S, мотор на {motor['cells']}S"
        )
    if esc["max_current"] < motor["current"]:
        problems.append(
            f"регулятор: держит {esc['max_current']} А, мотор тянет {motor['current']} А"
        )

    delivery = battery["c"] * battery["mah"] / 1000
    if delivery < 4 * motor["current"]:
        problems.append(
            f"отдача: аккумулятор даёт {delivery:.0f} А, нужно {4 * motor['current']} А"
        )

    thrust = 4 * motor["thrust"]
    needed = THRUST_RATIO * weight_of(build)
    if thrust < needed:
        problems.append(f"тяга: {thrust} г, нужно {needed:.0f} г")

    total = price_of(build)
    if total > BUDGET:
        problems.append(f"бюджет: сборка {total}, потолок {BUDGET}")

    return problems


def is_valid(build: dict) -> bool:
    return not broken_rules(build)


def rank(build: dict) -> tuple[float, int]:
    """Ключ сравнения: дольше летит лучше, при равном времени дешевле лучше."""
    return round(minutes_of(build), 4), -price_of(build)


def all_builds():
    for combo in product(*(CATALOGS[part] for part in PARTS)):
        yield dict(zip(PARTS, combo))


def best_build() -> tuple[dict, int]:
    """Правильный ответ полным перебором. Возвращает (сборка, сколько валидных всего)."""
    valid = [build for build in all_builds() if is_valid(build)]
    if not valid:
        raise ValueError("валидных сборок нет — каталог или бюджет заданы неудачно")
    return max(valid, key=rank), len(valid)


def main() -> None:
    total = 1
    for part in PARTS:
        total *= len(CATALOGS[part])
    build, valid_count = best_build()

    print(f"всего сочетаний: {total}")
    print(f"из них валидных: {valid_count}\n")
    print("правильный ответ:")
    for part in PARTS:
        print(f"  {part:8} {build[part]}")
    print(
        f"\n  {minutes_of(build):.2f} мин, цена {price_of(build)} из {BUDGET}, "
        f"вес {weight_of(build)} г"
    )


if __name__ == "__main__":
    main()
