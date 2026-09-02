# День 3: сравнение способов рассуждения — план реализации

> **Для агентов:** реализовывать по задачам через `superpowers:executing-plans`.
> Шаги отмечены чекбоксами `- [ ]`.

**Цель:** решить одну задачу через API четырьмя способами рассуждения и машинно измерить,
какой способ точнее.

**Архитектура:** три файла. `build.py` держит задачу, правила и эталон, вычисленный полным
перебором, и не обращается к API вообще. `reasoning.py` гоняет четыре режима параллельно,
складывает сырые ответы в JSON и печатает отчёт. `test_build.py` проверяет валидатор
и разбор ответа офлайн, потому что баг в проверке иначе запишется в ошибку модели.

**Стек:** Python 3.12, uv, `openai` (клиент к DeepSeek), `python-dotenv`,
`concurrent.futures` из стандартной библиотеки.

## Глобальные ограничения

- Модель: `deepseek-chat`, прямой API DeepSeek. Никаких фреймворков и обёрток.
- Температура: `1.0`. При нуле двадцать прогонов дадут двадцать одинаковых ответов.
- Новых зависимостей не добавлять: только `openai` и `python-dotenv`, уже в проекте.
- Тесты — скрипты со списком `CASES` и кодом возврата, как `day02/test_verdict.py`.
  Pytest в проекте нет и не заводить.
- Докстринги и вывод по-русски, имена в коде английские.
- Коэффициент тяги `2.5`, бюджет `210` — подобраны так, что связывают шесть правил из семи.
  Менять только по результату калибровки.
- Правильный ответ: `F-220 + M-2 + P-5 + E-30 + B-4S-2200`, 2.75 мин, цена 189, вес 550 г.
  21 валидная сборка из 1920.

---

## Структура файлов

| Файл | Ответственность |
| --- | --- |
| `day03/build.py` | каталог, семь правил, валидатор, перебор, текст задачи, разбор ответа. Без API |
| `day03/test_build.py` | офлайн-тесты валидатора, перебора и разбора. Без API |
| `day03/reasoning.py` | четыре режима, параллельные прогоны, results.json, отчёт. Здесь API |
| `day03/results.json` | сырые ответы модели, создаётся запуском |

---

### Задача 1: каталог, правила и эталон

**Файлы:**
- Создать: `day03/build.py`
- Тест: `day03/test_build.py`

**Интерфейсы:**
- Отдаёт наружу: `PARTS`, `CATALOGS`, `BUDGET`, `THRUST_RATIO`, `weight_of(build) -> int`,
  `price_of(build) -> int`, `minutes_of(build) -> float`, `broken_rules(build) -> list[str]`,
  `is_valid(build) -> bool`, `best_build() -> tuple[dict, int]`, `task_text() -> str`.
  `build` везде — это `dict` с ключами `frame`, `motor`, `props`, `esc`, `battery`.

- [ ] **Шаг 1: написать падающий тест на эталон**

```python
# day03/test_build.py
"""Офлайн-проверки конфигуратора. Без API, поэтому быстро и бесплатно.

Проверяется не модель, а наш собственный валидатор и разбор ответа. Баг здесь
молча запишется в ошибку модели — как во дне 2, где обрыв по max_tokens
наивная проверка засчитывала в заслугу stop.

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
    price_of,
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
    return problems
```

- [ ] **Шаг 2: запустить и убедиться, что падает**

Запуск: `uv run day03/test_build.py`
Ожидается: `ModuleNotFoundError: No module named 'build'`

- [ ] **Шаг 3: написать каталог и правила**

```python
# day03/build.py
"""День 3: задача-конфигуратор и эталонный решатель.

Обращений к API здесь нет. Только каталог, правила совместимости, проверка сборки
и полный перебор, дающий правильный ответ. Эталон считает машина, а не человек,
поэтому сравнение способов рассуждения получает честную единицу измерения.

Каталог вымышленный намеренно: на реальных названиях модель могла бы вспомнить
ответ из обучения вместо того, чтобы вывести его.

Запуск:
    uv run day03/build.py
"""

import re
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
    "M-1": {"prop": 4, "cells": 4, "thrust": 300, "current": 18, "weight": 28, "price": 14},
    "M-2": {"prop": 5, "cells": 4, "thrust": 400, "current": 24, "weight": 32, "price": 16},
    "M-3": {"prop": 5, "cells": 6, "thrust": 520, "current": 28, "weight": 34, "price": 19},
    "M-4": {"prop": 6, "cells": 6, "thrust": 640, "current": 34, "weight": 41, "price": 23},
    "M-5": {"prop": 7, "cells": 6, "thrust": 780, "current": 42, "weight": 48, "price": 28},
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
    return sum(
        CATALOGS[part][build[part]]["weight"] * QUANTITY[part] for part in PARTS
    )


def price_of(build: dict) -> int:
    return sum(
        CATALOGS[part][build[part]]["price"] * QUANTITY[part] for part in PARTS
    )


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
            f"пропеллер: комплект {props['size']}\", мотор рассчитан на {motor['prop']}\""
        )
    if props["size"] > frame["max_prop"]:
        problems.append(
            f"рама: пропеллер {props['size']}\", рама держит {frame['max_prop']}\""
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
```

- [ ] **Шаг 4: дописать в тест прогон и вывод**

```python
# day03/test_build.py, добавить в конец
def main() -> None:
    problems = check_optimum()
    if problems:
        print("FAIL  эталон")
        for problem in problems:
            print(f"        {problem}")
        sys.exit(1)
    print("ok    эталон совпал")


if __name__ == "__main__":
    main()
```

- [ ] **Шаг 5: запустить оба и убедиться, что сходится**

Запуск: `uv run day03/build.py && uv run day03/test_build.py`
Ожидается: перебор печатает `F-220 M-2 P-5 E-30 B-4S-2200`, 21 валидная сборка, 2.75 мин;
тест печатает `ok эталон совпал`.

- [ ] **Шаг 6: коммит**

```bash
git add day03/build.py day03/test_build.py
git commit -m "feat: day 03 — drone configurator with brute-force ground truth"
```

---

### Задача 2: правила по отдельности и текст задачи

**Файлы:**
- Изменить: `day03/build.py` (добавить `task_text`)
- Изменить: `day03/test_build.py` (добавить случаи на каждое правило)

**Интерфейсы:**
- Использует из задачи 1: `broken_rules`, `CATALOGS`, `PARTS`, `BUDGET`, `THRUST_RATIO`
- Отдаёт наружу: `task_text() -> str` — текст задачи с каталогом и правилами, который
  уходит в промпт всем четырём режимам

- [ ] **Шаг 1: написать падающие тесты на каждое правило**

```python
# day03/test_build.py, добавить перед main()
BROKEN = [
    (
        "пропеллер не того размера, что мотор",
        {"frame": "F-220", "motor": "M-2", "props": "P-4", "esc": "E-30",
         "battery": "B-4S-2200"},
        "пропеллер",
    ),
    (
        "пропеллер не влезает в раму",
        {"frame": "F-180", "motor": "M-2", "props": "P-5", "esc": "E-30",
         "battery": "B-4S-2200"},
        "рама",
    ),
    (
        "аккумулятор не на то число банок",
        {"frame": "F-220", "motor": "M-2", "props": "P-5", "esc": "E-30",
         "battery": "B-6S-2200"},
        "банки",
    ),
    (
        "регулятор не держит ток мотора",
        {"frame": "F-220", "motor": "M-2", "props": "P-5", "esc": "E-20",
         "battery": "B-4S-2200"},
        "регулятор",
    ),
    (
        "тяги не хватает на такой вес",
        {"frame": "F-220", "motor": "M-2", "props": "P-5", "esc": "E-30",
         "battery": "B-4S-3000"},
        "тяга",
    ),
    (
        "позиции нет в каталоге",
        {"frame": "F-999", "motor": "M-2", "props": "P-5", "esc": "E-30",
         "battery": "B-4S-2200"},
        "нет в каталоге",
    ),
]


def check_rules() -> list[str]:
    problems = []
    for name, build, expected in BROKEN:
        found = broken_rules(build)
        if not any(expected in problem for problem in found):
            problems.append(f"{name}: ждали «{expected}», получили {found}")
    if not is_valid(OPTIMUM):
        problems.append(f"оптимум признан невалидным: {broken_rules(OPTIMUM)}")
    return problems
```

Заменить в `main()` строку `problems = check_optimum()` на
`problems = check_optimum() + check_rules()`.

- [ ] **Шаг 2: запустить, убедиться, что тесты проходят**

Запуск: `uv run day03/test_build.py`
Ожидается: `ok`. Если какое-то правило не ловится — чинить `broken_rules`, а не тест.

- [ ] **Шаг 3: добавить текст задачи в build.py**

```python
# day03/build.py, добавить перед main()
RULES_TEXT = f"""Правила совместимости:
1. Размер комплекта пропеллеров совпадает с размером, на который рассчитан мотор.
2. Размер пропеллеров не больше максимума, который держит рама.
3. Число банок аккумулятора совпадает с числом банок, на которое рассчитан мотор.
4. Максимальный ток регулятора не меньше тока одного мотора.
5. Отдача аккумулятора (c * mah / 1000) не меньше суммарного тока четырёх моторов.
6. Суммарная тяга четырёх моторов не меньше {THRUST_RATIO} * взлётный вес.
   Взлётный вес = рама + 4 мотора + комплект пропеллеров + 4 регулятора + аккумулятор.
7. Суммарная цена не больше {BUDGET}. Моторы и регуляторы считаются по четыре штуки."""

GOAL_TEXT = f"""Цель: максимальное время полёта в минутах.
Время полёта = mah / 1000 / (4 * ток одного мотора * {THROTTLE}) * 60.
При равном времени полёта выбрать более дешёвую сборку."""

ANSWER_FORMAT = """Последней строкой ответа выведи ровно такую строку, без markdown:
ОТВЕТ: frame=..., motor=..., props=..., esc=..., battery=...
Подставь названия позиций из каталога."""


def task_text() -> str:
    lines = ["Собери квадрокоптер из каталога ниже.", "", "КАТАЛОГ:"]
    for part in PARTS:
        note = " (нужно 4 штуки, вес и цена указаны за одну)" if QUANTITY[part] == 4 else ""
        lines.append(f"\n{part}{note}:")
        for name, spec in CATALOGS[part].items():
            fields = ", ".join(f"{key} {value}" for key, value in spec.items())
            lines.append(f"  {name}: {fields}")
    lines += ["", RULES_TEXT, "", GOAL_TEXT]
    return "\n".join(lines)
```

- [ ] **Шаг 4: глазами проверить текст задачи**

Запуск: `uv run python -c "import sys; sys.path.insert(0,'day03'); from build import task_text; print(task_text())"`
Ожидается: каталог со всеми пятью разделами, у моторов и регуляторов пометка про четыре штуки,
семь правил, формула времени полёта.

- [ ] **Шаг 5: коммит**

```bash
git add day03/build.py day03/test_build.py
git commit -m "test: day 03 — per-rule checks and task text"
```

---

### Задача 3: разбор ответа модели

**Файлы:**
- Изменить: `day03/build.py` (добавить `parse_answer`)
- Изменить: `day03/test_build.py` (добавить случаи на разбор)

**Интерфейсы:**
- Отдаёт наружу: `parse_answer(text: str) -> dict | None`. Возвращает сборку
  или `None`, если строку `ОТВЕТ:` найти или разобрать не удалось.

- [ ] **Шаг 1: написать падающие тесты на разбор**

Сначала дописать `parse_answer` в блок импортов вверху `test_build.py`:

```python
from build import (  # noqa: E402
    best_build,
    broken_rules,
    is_valid,
    minutes_of,
    parse_answer,
    price_of,
    weight_of,
)
```

Затем добавить случаи:

```python
# day03/test_build.py
GOOD_LINE = "ОТВЕТ: frame=F-220, motor=M-2, props=P-5, esc=E-30, battery=B-4S-2200"

PARSING = [
    ("обычный ответ", f"Рассуждения...\n{GOOD_LINE}", OPTIMUM),
    ("текст после строки ответа", f"{GOOD_LINE}\nНадеюсь, помог!", OPTIMUM),
    (
        "другой порядок позиций",
        "ОТВЕТ: battery=B-4S-2200, esc=E-30, props=P-5, motor=M-2, frame=F-220",
        OPTIMUM,
    ),
    ("две строки ОТВЕТ, берём последнюю",
     "ОТВЕТ: frame=F-180, motor=M-1, props=P-4, esc=E-20, battery=B-4S-1300\n"
     f"Нет, пересчитал.\n{GOOD_LINE}", OPTIMUM),
    ("markdown вокруг", f"**{GOOD_LINE}**", OPTIMUM),
    ("строчными буквами", GOOD_LINE.replace("ОТВЕТ", "ответ"), OPTIMUM),
    ("не хватает позиции",
     "ОТВЕТ: frame=F-220, motor=M-2, props=P-5, esc=E-30", None),
    ("строки ОТВЕТ нет вовсе", "Думаю, надо взять F-220 и M-2.", None),
    ("пустой ответ", "", None),
]


def check_parsing() -> list[str]:
    problems = []
    for name, text, expected in PARSING:
        got = parse_answer(text)
        if got != expected:
            problems.append(f"{name}: ждали {expected}, получили {got}")
    return problems
```

Добавить `check_parsing()` в сумму в `main()`.

- [ ] **Шаг 2: запустить, убедиться, что падает**

Запуск: `uv run day03/test_build.py`
Ожидается: `ImportError: cannot import name 'parse_answer'`

- [ ] **Шаг 3: написать разбор**

```python
# day03/build.py, добавить после task_text()
ANSWER_LINE = re.compile(r"ответ\s*:(.+)", re.IGNORECASE)
PAIR = re.compile(r"(\w+)\s*=\s*([\w\-]+)")


def parse_answer(text: str) -> dict | None:
    """Достаёт сборку из последней строки «ОТВЕТ:». None, если разобрать не вышло.

    Берётся именно последняя: модель может передумать по ходу рассуждения
    и выдать несколько строк ответа.
    """
    matches = ANSWER_LINE.findall(text.replace("*", ""))
    if not matches:
        return None

    build = {key: value for key, value in PAIR.findall(matches[-1])}
    if set(build) != set(PARTS):
        return None
    return build
```

- [ ] **Шаг 4: запустить тесты**

Запуск: `uv run day03/test_build.py`
Ожидается: все случаи `ok`, включая три группы — эталон, правила, разбор.

- [ ] **Шаг 5: коммит**

```bash
git add day03/build.py day03/test_build.py
git commit -m "feat: day 03 — answer parsing with offline tests"
```

---

### Задача 4: четыре режима и один живой прогон

**Файлы:**
- Создать: `day03/reasoning.py`

**Интерфейсы:**
- Использует из задач 1–3: `task_text`, `ANSWER_FORMAT`, `parse_answer`, `broken_rules`,
  `is_valid`, `price_of`, `minutes_of`, `best_build`
- Отдаёт наружу: `MODES` (словарь имя → функция), `run_once(mode: str) -> dict`

- [ ] **Шаг 1: написать четыре режима и один прогон**

```python
# day03/reasoning.py
"""День 3: одна задача, четыре способа рассуждения.

Режимы:
    direct   прямой ответ без дополнительных инструкций
    steps    «решай пошагово»
    meta     модель сначала пишет промпт, затем решает по нему (два вызова)
    experts  группа экспертов в промпте: аналитик, инженер, критик

Инструкция про формат ответа дословно одинакова во всех режимах: иначе сравнивались
бы форматы, а не рассуждения.

Запуск:
    uv run day03/reasoning.py --mode direct --runs 1     # один живой прогон
    uv run day03/reasoning.py --runs 20                  # полный замер
    uv run day03/reasoning.py --report                   # отчёт из results.json
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

sys.path.insert(0, str(Path(__file__).parent))

from build import (  # noqa: E402
    ANSWER_FORMAT,
    best_build,
    broken_rules,
    minutes_of,
    parse_answer,
    price_of,
    task_text,
)

load_dotenv()

MODEL = "deepseek-chat"
TEMPERATURE = 1.0
RESULTS = Path(__file__).parent / "results.json"

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

STEPS_HINT = "Решай пошагово. Рассуждай вслух, по одному правилу за раз."

EXPERTS_HINT = """Реши задачу силами группы экспертов. Каждый высказывается по очереди:
АНАЛИТИК — разбирает ограничения и отсекает заведомо негодные варианты.
ИНЖЕНЕР — считает вес, тягу, ток и время полёта для оставшихся.
КРИТИК — ищет ошибки в расчётах инженера и нарушенные правила.
После них выведи общий вывод группы."""

META_REQUEST = """Ниже задача. Не решай её.
Составь промпт, который поможет языковой модели решить эту задачу максимально точно.
Выведи только текст промпта.

ЗАДАЧА:
{task}"""


def call(prompt: str) -> tuple[str, str]:
    """Возвращает (текст ответа, причина остановки). При сбое API отдаёт ("", "error")."""
    try:
        choice = client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
        ).choices[0]
    except OpenAIError as error:
        return "", f"error: {type(error).__name__}"
    return choice.message.content or "", choice.finish_reason or ""


def mode_direct(task: str) -> tuple[str, str, int]:
    answer, stop = call(f"{task}\n\n{ANSWER_FORMAT}")
    return answer, stop, 1


def mode_steps(task: str) -> tuple[str, str, int]:
    answer, stop = call(f"{task}\n\n{STEPS_HINT}\n\n{ANSWER_FORMAT}")
    return answer, stop, 1


def mode_experts(task: str) -> tuple[str, str, int]:
    answer, stop = call(f"{task}\n\n{EXPERTS_HINT}\n\n{ANSWER_FORMAT}")
    return answer, stop, 1


def mode_meta(task: str) -> tuple[str, str, int]:
    """Два вызова: сначала модель пишет промпт, затем решает по нему.

    Промпт генерируется заново на каждом прогоне. Если сгенерировать один раз
    и переиспользовать, у этого режима разброс окажется искусственно занижен,
    и сравнение с остальными тремя станет нечестным.

    Блок про формат ответа дописывается всегда: модель может его не включить,
    а без него ответ нечем разобрать.
    """
    generated, stop = call(META_REQUEST.format(task=task))
    if stop.startswith("error"):
        return "", stop, 1
    answer, stop = call(f"{generated}\n\n{task}\n\n{ANSWER_FORMAT}")
    return answer, stop, 2


MODES = {
    "direct": mode_direct,
    "steps": mode_steps,
    "meta": mode_meta,
    "experts": mode_experts,
}


def run_once(mode: str) -> dict:
    """Один прогон одного режима. Сырой ответ сохраняется целиком."""
    answer, stop, calls = MODES[mode](task_text())
    return {"mode": mode, "answer": answer, "stop": stop, "calls": calls}
```

- [ ] **Шаг 2: добавить временный запуск и проверить один прогон вживую**

```python
# day03/reasoning.py, временно в конец
if __name__ == "__main__":
    result = run_once("direct")
    print(result["answer"])
    print(f"\nstop: {result['stop']}")
    print(f"разобралось: {parse_answer(result['answer'])}")
```

Запуск: `uv run day03/reasoning.py`
Ожидается: модель что-то отвечает, последняя строка вида `ОТВЕТ: frame=...`,
`parse_answer` возвращает словарь из пяти ключей, а не `None`.

Если `None` — смотреть, что именно вернула модель, и чинить `ANSWER_FORMAT`
или `parse_answer`, а не подгонять тест.

- [ ] **Шаг 3: коммит**

```bash
git add day03/reasoning.py
git commit -m "feat: day 03 — four reasoning modes, single run"
```

---

### Задача 5: параллельный замер, results.json и отчёт

**Файлы:**
- Изменить: `day03/reasoning.py` (заменить временный запуск на полноценный)

**Интерфейсы:**
- Использует: `run_once`, `MODES`, `parse_answer`, `broken_rules`, `minutes_of`,
  `price_of`, `best_build`
- Отдаёт наружу: `measure(runs: int) -> list[dict]`, `score(record: dict) -> dict`,
  `report(records: list[dict]) -> None`

- [ ] **Шаг 1: написать подсчёт метрик и отчёт**

```python
# day03/reasoning.py, заменить временный блок __main__
def score(record: dict) -> dict:
    """Три метрики на один прогон плюс отдельная категория «не разобралось».

    Прогон с неразобранным ответом нельзя записывать в ошибку решения:
    это поломка формата, а не рассуждения.
    """
    optimum, _ = best_build()
    build = parse_answer(record["answer"])

    if build is None:
        return {"parsed": False, "valid": False, "in_budget": False,
                "optimal": False, "minutes": 0.0}

    problems = broken_rules(build)
    valid = not problems
    in_budget = not any(problem.startswith("бюджет") for problem in problems)
    return {
        "parsed": True,
        "valid": valid,
        "in_budget": in_budget,
        "optimal": build == optimum,
        "minutes": minutes_of(build) if valid else 0.0,
    }


def measure(runs: int) -> list[dict]:
    """Все режимы, все прогоны, параллельно. Порядок результатов не важен."""
    jobs = [mode for mode in MODES for _ in range(runs)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(run_once, jobs))


def report(records: list[dict]) -> None:
    optimum, valid_count = best_build()
    print(f"\nправильный ответ: {optimum}")
    print(f"{minutes_of(optimum):.2f} мин, цена {price_of(optimum)}, "
          f"валидных сборок в каталоге {valid_count}\n")

    header = f"{'режим':<9} {'разобралось':>12} {'валидна':>9} {'в бюджете':>11} {'оптимум':>9} {'вызовов':>8}"
    print(header)
    print("-" * len(header))

    for mode in MODES:
        rows = [record for record in records if record["mode"] == mode]
        if not rows:
            continue
        failed = sum(1 for row in rows if row["stop"].startswith("error"))
        scored = [score(row) for row in rows if not row["stop"].startswith("error")]
        total = len(scored)
        parsed = [s for s in scored if s["parsed"]]
        print(
            f"{mode:<9} {len(parsed):>7}/{total:<4} "
            f"{sum(s['valid'] for s in parsed):>6}/{len(parsed):<2} "
            f"{sum(s['in_budget'] for s in parsed):>8}/{len(parsed):<2} "
            f"{sum(s['optimal'] for s in parsed):>6}/{len(parsed):<2} "
            f"{sum(row['calls'] for row in rows):>8}"
            + (f"   не дошло: {failed}" if failed else "")
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--mode", choices=list(MODES))
    parser.add_argument("--report", action="store_true",
                        help="напечатать отчёт из results.json без обращений к API")
    args = parser.parse_args()

    if args.report:
        if not RESULTS.exists():
            sys.exit(f"нет файла {RESULTS} — сначала запусти замер")
        report(json.loads(RESULTS.read_text(encoding="utf-8")))
        return

    if args.mode:
        # Калибровочный прогон одного режима. Файл полного замера не трогаем,
        # иначе калибровка затрёт результаты, снятые для видео.
        records = [run_once(args.mode) for _ in range(args.runs)]
    else:
        records = measure(args.runs)
        RESULTS.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"сырые ответы сохранены в {RESULTS.name}")

    report(records)


if __name__ == "__main__":
    main()
```

- [ ] **Шаг 2: калибровка — только прямой режим, пять прогонов**

Запуск: `uv run day03/reasoning.py --mode direct --runs 5`

Ожидается: доля попаданий в оптимум **между 1 и 4 из 5**.

- 5 из 5 — задача слишком лёгкая, режимы не разойдутся. Поднять `THRUST_RATIO`
  до 3.0 в `build.py`, пересчитать `uv run day03/build.py`, обновить ожидаемые
  числа в `test_build.py`, повторить калибровку.
- 0 из 5 — слишком тяжёлая. Опустить `THRUST_RATIO` до 2.0, дальше так же.

- [ ] **Шаг 3: полный замер**

Запуск: `uv run day03/reasoning.py --runs 20`
Ожидается: примерно пять минут, 100 вызовов, файл `results.json`, таблица на четыре строки.

- [ ] **Шаг 4: проверить, что отчёт печатается без API**

Запуск: `uv run day03/reasoning.py --report`
Ожидается: та же таблица мгновенно. Это то, что показывается на видео.

- [ ] **Шаг 5: дописать раздел в README**

Добавить в `README.md` строку в таблицу дней и раздел «День 3: что получилось»
с таблицей из отчёта и выводом, какой режим точнее и на чём ломаются остальные.

- [ ] **Шаг 6: коммит**

```bash
git add day03/reasoning.py day03/results.json README.md
git commit -m "feat: day 03 — parallel measurement and comparison report"
```

---

## Проверка целиком

```bash
uv run day03/test_build.py                  # офлайн, должно быть всё ok
uv run day03/build.py                       # эталон: F-220 M-2 P-5 E-30 B-4S-2200
uv run day03/reasoning.py --mode direct --runs 1   # один живой прогон
uv run day03/reasoning.py --report          # таблица из сохранённых результатов
```

## Чего в плане сознательно нет

- судьи на второй модели: правильный ответ известен точно, судить нечего
- второй задачи другой сложности: задание требует одну задачу
- повторов при неразобравшемся ответе: доля таких прогонов сама по себе результат,
  её надо показать, а не спрятать
