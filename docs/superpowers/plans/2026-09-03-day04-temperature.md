# День 4: температура — план реализации

> **Для агентов-исполнителей:** ОБЯЗАТЕЛЬНЫЙ ПОДСКИЛЛ: используй superpowers:subagent-driven-development (рекомендуется) или superpowers:executing-plans, чтобы выполнить план по задачам. Шаги отмечены чекбоксами (`- [ ]`).

**Цель:** измерить точность, разнообразие и креативность DeepSeek на трёх температурах (0 / 0.7 / 1.2) на двух запросах — капкан на подсчёт букв и открытая генерация с зашитыми требованиями — и показать результат в локальной панели в теме Гвинта.

**Архитектура:** три модуля без API (`traps.py`), с API (`temperature.py`), панель (`web.py` + `index.html`). Тот же принцип, что в дне 3: эталон и проверки считаются кодом и тестируются офлайн, вызовы к модели изолированы в отдельном файле.

**Технологии:** Python 3.12, `openai` SDK на `base_url=https://api.deepseek.com`, `http.server` из стандартной библиотеки для панели, без внешних веб-фреймворков.

## Глобальные ограничения

- Спека: `docs/superpowers/specs/2026-09-03-day04-temperature-design.md` — обязательна к прочтению перед вопросами.
- Модель `deepseek-chat`, ключ в `.env` как `DEEPSEEK_API_KEY` (уже настроено в проекте).
- 10 прогонов на температуру на запрос → 60 вызовов на измерение, до 31 вызов на судью.
- Тесты — в стиле дня 3: обычные функции, возвращающие список строк-проблем, `main()` печатает `ok`/`FAIL` и делает `sys.exit(1)` при провале. **Не pytest** — в проекте его нет и не должно появиться.
- Импорт и его использование добавлять в одном и том же редактировании файла: в проекте есть автоформаттер (`ruff-lint.sh` хук), который между двумя правками успевает удалить только что добавленный и ещё не используемый импорт как «неиспользуемый». Раньше это уже ломало код в дне 3.
- Панель слушает только `127.0.0.1` — в процессе живёт ключ DeepSeek, наружу не выставлять.

---

## Файловая структура

```
day04/traps.py       эталоны и проверки, без API вообще
day04/test_traps.py  офлайн-тесты traps.py
day04/temperature.py вызовы к DeepSeek: измерение + судья + отчёт + CLI
day04/results.json   сырые ответы + оценки судьи (появится после первого запуска)
day04/web.py         локальный сервер панели
day04/web/index.html панель в теме Гвинта
```

---

### Task 1: `traps.py` — эталоны и проверки без API

**Файлы:**
- Создать: `day04/traps.py`
- Создать: `day04/test_traps.py`

**Интерфейсы:**
- Производит: `LETTER_WORD: str`, `LETTER: str`, `LETTER_QUESTION: str`, `GADGET_PROMPT: str`, `HUMAN_EXAMPLE: str`, `letter_truth() -> int`, `parse_letter_answer(text: str) -> int | None`, `score_letter(answer: str) -> dict` (ключи `parsed`, `value`, `correct`), `check_gadget(text: str) -> dict` (ключи `sentences`, `price`, `benefit`, `no_banned`, `score`), `normalize(text: str) -> str`.

- [ ] **Шаг 1: Написать `day04/test_traps.py` целиком**

```python
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
    ("число с текстом", "В слове 3 буквы «с».", {"parsed": True, "value": 3, "correct": True}),
    ("неверное число", "4", {"parsed": True, "value": 4, "correct": False}),
    (
        "рассуждение, ответ последним числом",
        "Считаю по буквам: р-а-с-с... получилось 3",
        {"parsed": True, "value": 3, "correct": True},
    ),
    ("прописью, не парсится", "три", {"parsed": False, "value": None, "correct": False}),
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
    ("есть цена", "Термокружка стоит 500 руб. Она прочная. Всем советую.", "price", True),
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
```

- [ ] **Шаг 2: Запустить тесты, убедиться что падают из-за отсутствия `traps.py`**

Run: `uv run day04/test_traps.py`
Expected: `ModuleNotFoundError: No module named 'traps'`

- [ ] **Шаг 3: Написать `day04/traps.py` целиком**

```python
"""День 4: капканы для модели — эталоны и проверки. Без API вообще.

Капкан на буквы: классические ловушки (9.11 vs 9.9, strawberry) больше не
работают на deepseek-chat — проверено вживую при подготовке спеки. Подсчёт
букв в реальных словах с двойными буквами всё ещё воспроизводимо ловит
модель: она завышает счёт на единицу.

Открытый запрос: точность у творческой задачи не может быть «совпадением
с текстом», поэтому она заменена на выполнение четырёх явных требований,
зашитых в промпт. Их проверяет код, не человек и не вторая модель.
"""

import re

LETTER_WORD = "рассредоточенность"
LETTER = "с"
LETTER_QUESTION = f'Сколько букв «{LETTER}» в слове «{LETTER_WORD}»? Ответь только числом.'

GADGET_PROMPT = (
    "Придумай название для нового гаджета, который ещё не существует. "
    "Ответь ровно 3 предложениями. Обязательно укажи цену (целым числом, любая "
    "валюта) и одно конкретное преимущество. Не используй слово «революционный» "
    "и его однокоренные формы."
)

# Написан руками, соблюдает все 4 требования. Служит и визуальным якорем
# на панели, и проверкой честности судьи: если судья не оценит человеческий
# текст высоко, это повод не доверять судье.
HUMAN_EXAMPLE = "Деловой чемодан. Цена 19₽. Он силен своей кожей, крокодильей, не поверишь."

# Два семейства: глаголы действия и прилагательные качества. Первая версия
# (только глаголы) не прошла HUMAN_EXAMPLE — «силён своей кожей» не совпадало
# ни с одним словом. Список расширен после этой проверки.
BENEFIT_WORDS = [
    "позвол", "помога", "экономит", "увеличива", "снижа", "преимуществ", "благодаря",
    "прочн", "надёжн", "надежн", "качеств", "долговечн", "силён", "силен", "сильн",
    "мощн", "быстр", "лёгк", "легк", "удобн", "эконом",
]
BANNED_ROOT = "революцион"
PRICE_PATTERN = re.compile(r"\d[\d\s]*(?:₽|руб|\$|USD|EUR|€)", re.IGNORECASE)
SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s+|$)")


def letter_truth() -> int:
    return LETTER_WORD.count(LETTER)


def parse_letter_answer(text: str) -> int | None:
    """Последнее число в тексте — модель может порассуждать перед ответом."""
    matches = re.findall(r"\d+", text)
    return int(matches[-1]) if matches else None


def score_letter(answer: str) -> dict:
    value = parse_letter_answer(answer)
    return {
        "parsed": value is not None,
        "value": value,
        "correct": value == letter_truth() if value is not None else False,
    }


def count_sentences(text: str) -> int:
    return len([s for s in SENTENCE_SPLIT.split(text) if s.strip()])


def check_gadget(text: str) -> dict:
    """Четыре требования из GADGET_PROMPT, каждое проверяется независимо."""
    sentences_ok = count_sentences(text) == 3
    price_ok = bool(PRICE_PATTERN.search(text))
    benefit_ok = any(word in text.lower() for word in BENEFIT_WORDS)
    banned_ok = BANNED_ROOT not in text.lower()
    return {
        "sentences": sentences_ok,
        "price": price_ok,
        "benefit": benefit_ok,
        "no_banned": banned_ok,
        "score": sum([sentences_ok, price_ok, benefit_ok, banned_ok]),
    }


def normalize(text: str) -> str:
    """Для подсчёта уникальных ответов: регистр и пробелы не считаются различием."""
    return re.sub(r"\s+", " ", text.strip().lower())
```

- [ ] **Шаг 4: Запустить тесты снова**

Run: `uv run day04/test_traps.py`
Expected: пять строк `ok`, без `FAIL`

- [ ] **Шаг 5: Коммит**

```bash
git add day04/traps.py day04/test_traps.py
git commit -m "feat: day 4 — traps and checks (no API)"
```

---

### Task 2: `temperature.py` — измерение и судья

**Файлы:**
- Создать: `day04/temperature.py`

**Интерфейсы:**
- Потребляет: всё из Task 1 — `LETTER_QUESTION`, `GADGET_PROMPT`, `HUMAN_EXAMPLE`, `check_gadget`, `letter_truth`, `normalize`, `score_letter` из `traps.py`.
- Производит: `RESULTS: Path`, `TASKS: dict[str, str]`, `TEMPERATURES: tuple`, `ask(prompt: str, temperature: float) -> tuple[str, str]`, `judge(answer: str) -> int | None`, `run_once(task: str, temperature: float) -> dict`, `measure(runs: int) -> list[dict]`, `annotate(data: dict) -> list[dict]`, `summarize(data: dict) -> dict` (ключи `letter`, `gadget`, каждый — список словарей по температурам), `report(data: dict) -> None`.

Task 3 (`web.py`) импортирует `RESULTS`, `TASKS`, `TEMPERATURES`, `annotate`, `judge`, `run_once`, `summarize` из этого файла — сигнатуры должны совпасть один в один.

- [ ] **Шаг 1: Написать `day04/temperature.py` целиком**

```python
"""День 4: одна и та же пара запросов на трёх температурах.

temperature = 0 / 0.7 / 1.2, каждая прогоняется 10 раз на двух запросах:
    letter   капкан на подсчёт букв, эталон точный, точность считается кодом
    gadget   открытый запрос с зашитыми требованиями; точность и разнообразие
             считаются кодом, креативность — отдельным вызовом-судьёй

Запуск:
    uv run day04/temperature.py
    uv run day04/temperature.py --runs 5
    uv run day04/temperature.py --report
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

sys.path.insert(0, str(Path(__file__).parent))

from traps import (  # noqa: E402
    GADGET_PROMPT,
    HUMAN_EXAMPLE,
    LETTER_QUESTION,
    check_gadget,
    normalize,
    score_letter,
)

load_dotenv()

MODEL = "deepseek-chat"
TEMPERATURES = (0, 0.7, 1.2)
MAX_TOKENS = 2000
RESULTS = Path(__file__).parent / "results.json"

TASKS = {"letter": LETTER_QUESTION, "gadget": GADGET_PROMPT}

JUDGE_PROMPT = """Оцени оригинальность этого питча гаджета по шкале от 1 до 10, где 1 — банально,
10 — очень оригинально. Ответь только числом.

{answer}"""

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)


def ask(prompt: str, temperature: float) -> tuple[str, str]:
    """Возвращает (текст ответа, причина остановки). При сбое API — ("", "error: ...")."""
    try:
        choice = client.chat.completions.create(
            model=MODEL,
            temperature=temperature,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ).choices[0]
    except OpenAIError as error:
        return "", f"error: {type(error).__name__}"
    return choice.message.content or "", choice.finish_reason or ""


def judge(answer: str) -> int | None:
    """Оценка оригинальности 1-10 отдельным вызовом. None, если не распарсилось.

    Оценивает каждый ответ по отдельности, не видя остальные — иначе оценка
    сместилась бы относительно порядка показа, а не самого текста.
    """
    text, stop = ask(JUDGE_PROMPT.format(answer=answer), temperature=0)
    if stop.startswith("error"):
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    value = int(match.group())
    return value if 1 <= value <= 10 else None


def run_once(task: str, temperature: float) -> dict:
    answer, stop = ask(TASKS[task], temperature)
    return {"task": task, "temperature": temperature, "answer": answer, "stop": stop}


def measure(runs: int) -> list[dict]:
    """Оба запроса, все три температуры, параллельно. Судья — отдельным проходом,
    только после того как есть что судить."""
    jobs = [
        (task, temperature)
        for task in TASKS
        for temperature in TEMPERATURES
        for _ in range(runs)
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(lambda job: run_once(*job), jobs))

    gadget_records = [
        r for r in records if r["task"] == "gadget" and not r["stop"].startswith("error")
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        judged = list(pool.map(lambda r: judge(r["answer"]), gadget_records))
    for record, score in zip(gadget_records, judged):
        record["judge"] = score

    return records


def annotate(data: dict) -> list[dict]:
    """Каждая сырая запись плюс её проверка. Используется и отчётом, и панелью."""
    out = []
    for r in data["records"]:
        if r["stop"].startswith("error"):
            out.append({**r, "score": None})
            continue
        if r["task"] == "letter":
            score = score_letter(r["answer"])
        else:
            score = check_gadget(r["answer"])
            score["judge"] = r.get("judge")
        out.append({**r, "score": score})
    return out


def summarize(data: dict) -> dict:
    """Агрегаты по температуре для обоих запросов."""
    annotated = annotate(data)

    letter_rows = []
    for temperature in TEMPERATURES:
        rows = [r for r in annotated if r["task"] == "letter" and r["temperature"] == temperature]
        errors = [r for r in rows if r["score"] is None]
        scored = [r["score"] for r in rows if r["score"] is not None]
        parsed = [s for s in scored if s["parsed"]]
        letter_rows.append(
            {
                "temperature": temperature,
                "total": len(scored),
                "parsed": len(parsed),
                "correct": sum(s["correct"] for s in parsed),
                "errors": len(errors),
            }
        )

    gadget_rows = []
    for temperature in TEMPERATURES:
        rows = [r for r in annotated if r["task"] == "gadget" and r["temperature"] == temperature]
        errors = [r for r in rows if r["score"] is None]
        oks = [r for r in rows if r["score"] is not None]
        checks = [r["score"] for r in oks]
        accuracy = sum(c["score"] for c in checks) / (4 * len(checks)) * 100 if checks else 0
        unique = len({normalize(r["answer"]) for r in oks}) / len(oks) * 100 if oks else 0
        judged = [c["judge"] for c in checks if c.get("judge") is not None]
        creativity = sum(judged) / len(judged) if judged else 0
        gadget_rows.append(
            {
                "temperature": temperature,
                "total": len(oks),
                "accuracy": round(accuracy, 1),
                "unique": round(unique, 1),
                "creativity": round(creativity, 1),
                "errors": len(errors),
            }
        )

    return {"letter": letter_rows, "gadget": gadget_rows}


def report(data: dict) -> None:
    summary = summarize(data)
    human_judge = data["human_judge"]

    print("=== капкан: буквы «с» в «рассредоточенность» (эталон 3) ===")
    print(f"{'температура':<12} {'разобралось':>12} {'верно':>8}")
    for row in summary["letter"]:
        line = f"{row['temperature']:<12} {row['parsed']:>7}/{row['total']:<4} {row['correct']:>8}"
        if row["errors"]:
            line += f"   не дошло: {row['errors']}"
        print(line)

    print("\n=== открытый: гаджет с 4 требованиями ===")
    print(f"{'температура':<12} {'точность':>9} {'уникальных':>11} {'креативность':>13}")
    for row in summary["gadget"]:
        line = (
            f"{row['temperature']:<12} {row['accuracy']:>8.0f}% "
            f"{row['unique']:>10.0f}% {row['creativity']:>13.1f}"
        )
        if row["errors"]:
            line += f"   не дошло: {row['errors']}"
        print(line)

    print(f"\nчеловеческий эталон: {HUMAN_EXAMPLE!r}")
    print(f"  проверка кодом: {check_gadget(HUMAN_EXAMPLE)}")
    print(f"  оценка судьи: {human_judge}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument(
        "--report",
        action="store_true",
        help="напечатать отчёт из results.json без обращений к API",
    )
    args = parser.parse_args()

    if args.report:
        if not RESULTS.exists():
            sys.exit(f"нет файла {RESULTS} — сначала запусти замер")
        report(json.loads(RESULTS.read_text(encoding="utf-8")))
        return

    records = measure(args.runs)
    human_judge = judge(HUMAN_EXAMPLE)
    data = {"records": records, "human_judge": human_judge}
    RESULTS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"сырые ответы сохранены в {RESULTS.name}")
    report(data)


if __name__ == "__main__":
    main()
```

- [ ] **Шаг 2: Проверить синтаксис без обращения к API**

Run: `python3 -c "import ast; ast.parse(open('day04/temperature.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Шаг 3: Дымовой прогон на реальном API, по одному вызову на комбинацию**

Run: `uv run day04/temperature.py --runs 1`
Expected: обе таблицы печатаются, `не дошло` нигде не появляется (если появилось — проверить `.env` и ключ), в конце строка `человеческий эталон: ... оценка судьи: <число от 1 до 10>`. Это 6 вызовов измерения + 2 вызова судьи (1 gadget-ответ + сам эталон) — дёшево, делать перед полным замером.

- [ ] **Шаг 4: Коммит**

```bash
git add day04/temperature.py
git commit -m "feat: day 4 — temperature sweep and judge"
```

---

### Task 3: панель в теме Гвинта

**Файлы:**
- Создать: `day04/web.py`
- Создать: `day04/web/index.html`

**Интерфейсы:**
- Потребляет: `LETTER`, `LETTER_QUESTION`, `LETTER_WORD`, `GADGET_PROMPT`, `HUMAN_EXAMPLE`, `check_gadget`, `letter_truth`, `score_letter` из `traps.py`; `RESULTS`, `TASKS`, `TEMPERATURES`, `annotate`, `judge`, `run_once`, `summarize` из `temperature.py` (Task 2).
- Производит: HTTP-эндпоинты `GET /api/state`, `POST /api/ask`.

- [ ] **Шаг 1: Написать `day04/web.py` целиком**

```python
"""Локальная панель дня 4: температура на двух запросах, тема Гвинта.

Только для localhost — в процессе живёт ключ от DeepSeek, наружу не выставлять.

Запуск:
    uv run day04/web.py          # http://127.0.0.1:8034
    uv run day04/web.py --port 9000
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from traps import (  # noqa: E402
    GADGET_PROMPT,
    HUMAN_EXAMPLE,
    LETTER,
    LETTER_QUESTION,
    LETTER_WORD,
    check_gadget,
    letter_truth,
    score_letter,
)
from temperature import (  # noqa: E402
    RESULTS,
    TASKS,
    TEMPERATURES,
    annotate,
    judge,
    run_once,
    summarize,
)

PAGE = Path(__file__).parent / "web" / "index.html"


def state() -> dict:
    """Всё, что нужно странице при загрузке. Без обращений к API."""
    table = {"letter": [], "gadget": []}
    records = []
    human_judge = None
    if RESULTS.exists():
        data = json.loads(RESULTS.read_text(encoding="utf-8"))
        table = summarize(data)
        records = annotate(data)
        human_judge = data.get("human_judge")

    return {
        "letter_word": LETTER_WORD,
        "letter": LETTER,
        "letter_question": LETTER_QUESTION,
        "letter_truth": letter_truth(),
        "gadget_prompt": GADGET_PROMPT,
        "human_example": HUMAN_EXAMPLE,
        "human_check": check_gadget(HUMAN_EXAMPLE),
        "human_judge": human_judge,
        "temperatures": list(TEMPERATURES),
        "table": table,
        "records": records,
    }


def ask(task: str, temperature: float) -> dict:
    """Один живой прогон. Обращается к API."""
    record = run_once(task, temperature)
    if record["stop"].startswith("error"):
        score = {"error": record["stop"]}
    elif task == "letter":
        score = score_letter(record["answer"])
    else:
        score = check_gadget(record["answer"])
        score["judge"] = judge(record["answer"])
    return {**record, "score": score}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # тише в консоли
        pass

    def send_json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            body = PAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/state":
            self.send_json(state())
        else:
            self.send_json({"error": "нет такого адреса"}, 404)

    def do_POST(self) -> None:
        if self.path == "/api/ask":
            payload = self.read_json()
            task = payload.get("task")
            temperature = payload.get("temperature")
            if task not in TASKS or temperature not in TEMPERATURES:
                self.send_json(
                    {"error": f"нет task={task!r} temperature={temperature!r}"}, 400
                )
                return
            self.send_json(ask(task, temperature))
        else:
            self.send_json({"error": "нет такого адреса"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8034)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"открой http://127.0.0.1:{args.port}   (Ctrl+C чтобы остановить)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
```

- [ ] **Шаг 2: Создать директорию и написать `day04/web/index.html` целиком**

Run сначала: `mkdir -p day04/web`

```html
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>День 4 — капканы для нейронки</title>
<style>
  :root {
    --bg: #140d08;
    --wood: #241a10;
    --card: #2b1f14;
    --text: #e8dcc0;
    --dim: #a8926c;
    --bronze: #976006;
    --bronze-light: #c98a1c;
    --gold: #cfb53b;
    --gold-light: #f4e07a;
    --crack: #5c1f1f;
    --ok: #7fae5a;
    --bad: #a5433a;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 1.5rem;
    background: radial-gradient(ellipse at top, #2a1d10 0%, var(--bg) 70%);
    color: var(--text);
    font: 15px/1.55 Georgia, "Times New Roman", serif;
  }
  main { max-width: 68rem; margin: 0 auto; }
  h1 {
    font-size: 1.6rem; margin: 0 0 .2rem;
    letter-spacing: .04em; text-transform: uppercase;
    color: var(--gold-light);
    text-shadow: 0 1px 0 #000;
  }
  h2 {
    font-size: 1.05rem; margin: 0 0 .8rem; font-weight: 600;
    letter-spacing: .03em; text-transform: uppercase;
    color: var(--gold);
    border-bottom: 1px solid var(--bronze);
    padding-bottom: .3rem;
  }
  p.lead { color: var(--dim); margin: 0 0 1.5rem; }

  section.board {
    background: var(--wood);
    border: 1px solid var(--bronze);
    border-radius: 6px;
    padding: 1.2rem;
    margin-bottom: 1.4rem;
    box-shadow: inset 0 0 40px rgba(0, 0, 0, .5);
  }

  .leader {
    display: flex; align-items: center; gap: 1rem;
    background: linear-gradient(180deg, #3a2a12, var(--wood));
    border: 2px solid var(--gold);
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1.4rem;
    box-shadow: 0 0 18px rgba(207, 181, 59, .25);
  }
  .leader .badge {
    font-size: .7rem; text-transform: uppercase; letter-spacing: .08em;
    color: var(--gold-light); border: 1px solid var(--gold);
    border-radius: 4px; padding: .2rem .5rem; white-space: nowrap;
  }
  .leader .text { flex: 1; font-style: italic; }
  .leader .power {
    font-size: 1.4rem; font-weight: 700; color: var(--gold-light);
    min-width: 3rem; text-align: center;
  }

  .row { margin-bottom: 1rem; }
  .row-head {
    display: flex; justify-content: space-between; align-items: baseline;
    margin-bottom: .5rem;
  }
  .row-head .temp {
    font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
    color: var(--dim);
  }
  .row-head .sum { font-size: 1.3rem; font-weight: 700; color: var(--gold-light); }
  .cards { display: flex; flex-wrap: wrap; gap: .5rem; }

  .card {
    width: 6.5rem; min-height: 5.5rem;
    background: linear-gradient(180deg, #3a2a17, var(--card));
    border: 2px solid var(--bronze);
    border-radius: 6px;
    padding: .4rem;
    font-size: .78rem;
    display: flex; flex-direction: column; justify-content: space-between;
  }
  .card.gold { border-color: var(--gold); box-shadow: 0 0 8px rgba(207, 181, 59, .4); }
  .card.crack { border-color: var(--crack); border-style: dashed; opacity: .7; }
  .card .value { font-size: 1.3rem; font-weight: 700; text-align: center; }
  .card.gold .value { color: var(--gold-light); }
  .card.crack .value { color: var(--bad); font-size: .9rem; }
  .card:not(.gold):not(.crack) .value { color: var(--bronze-light); }
  .card .foot { font-size: .68rem; color: var(--dim); text-align: center; }

  .empty { color: var(--dim); font-style: italic; }

  select, button {
    padding: .5rem .7rem; border-radius: 6px;
    background: var(--card); color: var(--text);
    border: 1px solid var(--bronze); font: inherit;
  }
  button { color: var(--gold-light); cursor: pointer; }
  button:hover:not(:disabled) { border-color: var(--gold); }
  button:disabled { opacity: .45; cursor: wait; }

  .verdict { font-size: 1.1rem; font-weight: 700; margin: .6rem 0; }
  .verdict.ok { color: var(--ok); }
  .verdict.bad { color: var(--bad); }
  pre {
    white-space: pre-wrap; word-break: break-word;
    background: var(--card); border: 1px solid var(--bronze); border-radius: 6px;
    padding: .7rem; font-size: .85rem; color: var(--dim);
  }
  details summary { cursor: pointer; color: var(--gold); font-size: .85rem; }
</style>
</head>
<body>
<main>
  <h1>Капканы для нейронки</h1>
  <p class="lead">
    Задача дня 4. Один и тот же запрос на трёх температурах — три ряда боя,
    как в Гвинте. Каждый ответ модели — карта в своём ряду.
  </p>

  <div id="leader"></div>

  <section class="board">
    <h2>Капкан: буквы «с» в «рассредоточенность» (эталон 3)</h2>
    <div id="letter-rows"></div>
  </section>

  <section class="board">
    <h2>Открытый: гаджет с 4 требованиями</h2>
    <div id="gadget-rows"></div>
  </section>

  <section class="board">
    <h2>Спросить модель вживую</h2>
    <p class="lead" style="margin-bottom:.8rem">Один прогон. Вердикт считает тот же код, что и на панели.</p>
    <select id="ask-task"></select>
    <select id="ask-temp"></select>
    <button id="ask-button">Спросить</button>
    <p class="verdict" id="ask-verdict"></p>
    <div id="ask-out"></div>
  </section>
</main>

<script>
const $ = (id) => document.getElementById(id);
let STATE = null;

async function boot() {
  STATE = await (await fetch('/api/state')).json();
  renderLeader();
  renderRows('letter-rows', 'letter', letterCard);
  renderRows('gadget-rows', 'gadget', gadgetCard);
  renderAskControls();
}

function renderLeader() {
  $('leader').innerHTML = `
    <div class="leader">
      <span class="badge">лидер · человек</span>
      <span class="text">${STATE.human_example}</span>
      <span class="power">${STATE.human_judge ?? '—'}</span>
    </div>`;
}

function cardsFor(task, temperature) {
  return STATE.records.filter((r) => r.task === task && r.temperature === temperature);
}

function letterCard(record) {
  const s = record.score;
  if (!s) return '<div class="card crack"><div class="value">✗</div><div class="foot">сбой</div></div>';
  const cls = s.correct ? 'gold' : (s.parsed ? '' : 'crack');
  const value = s.parsed ? s.value : '?';
  const foot = s.parsed ? (s.correct ? 'верно' : 'мимо') : 'не разобралось';
  return `<div class="card ${cls}"><div class="value">${value}</div><div class="foot">${foot}</div></div>`;
}

function gadgetCard(record) {
  const s = record.score;
  if (!s) return '<div class="card crack"><div class="value">✗</div><div class="foot">сбой</div></div>';
  const cls = s.score === 4 ? 'gold' : (s.score === 0 ? 'crack' : '');
  const power = s.judge ?? '—';
  const foot = `${s.score}/4 · ${s.judge != null ? 'судья' : 'без судьи'}`;
  return `<div class="card ${cls}"><div class="value">${power}</div><div class="foot">${foot}</div></div>`;
}

function renderRows(containerId, task, cardFn) {
  const el = $(containerId);
  el.innerHTML = '';
  for (const summary of STATE.table[task]) {
    const records = cardsFor(task, summary.temperature);
    const sum = task === 'letter' ? `${summary.correct}/${summary.total}` : `${summary.accuracy}%`;
    const cardsHtml = records.length
      ? records.map(cardFn).join('')
      : '<span class="empty">нет прогонов — запусти uv run day04/temperature.py</span>';
    el.insertAdjacentHTML('beforeend', `
      <div class="row">
        <div class="row-head">
          <span class="temp">temperature ${summary.temperature}</span>
          <span class="sum">${sum}</span>
        </div>
        <div class="cards">${cardsHtml}</div>
      </div>`);
  }
}

function renderAskControls() {
  $('ask-task').innerHTML = '<option value="letter">буквы</option><option value="gadget">гаджет</option>';
  $('ask-temp').innerHTML = STATE.temperatures.map((t) => `<option value="${t}">temperature ${t}</option>`).join('');
  $('ask-button').onclick = ask;
}

async function ask() {
  const button = $('ask-button');
  button.disabled = true;
  button.textContent = 'спрашиваю…';
  $('ask-verdict').textContent = '';
  $('ask-out').innerHTML = '';

  try {
    const task = $('ask-task').value;
    const temperature = parseFloat($('ask-temp').value);
    const result = await (await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, temperature }),
    })).json();

    const s = result.score;
    const verdict = $('ask-verdict');
    if (!s || s.error) {
      verdict.textContent = 'Запрос не прошёл: ' + (s ? s.error : result.error);
      verdict.className = 'verdict bad';
    } else if (task === 'letter') {
      verdict.textContent = s.parsed
        ? (s.correct ? `Верно: ${s.value}` : `Мимо: ${s.value}, правильно ${STATE.letter_truth}`)
        : 'Ответ не разобрался';
      verdict.className = 'verdict ' + (s.correct ? 'ok' : 'bad');
    } else {
      verdict.textContent = `${s.score}/4 требований, судья: ${s.judge ?? '—'}`;
      verdict.className = 'verdict ' + (s.score === 4 ? 'ok' : 'bad');
    }

    const details = document.createElement('details');
    details.innerHTML = `<summary>ответ модели, stop=${result.stop}</summary>`;
    const pre = document.createElement('pre');
    pre.textContent = result.answer || '(пусто)';
    details.append(pre);
    $('ask-out').append(details);
  } catch (error) {
    $('ask-verdict').textContent = 'Запрос не дошёл: ' + error;
    $('ask-verdict').className = 'verdict bad';
  } finally {
    button.disabled = false;
    button.textContent = 'Спросить';
  }
}

boot();
</script>
</body>
</html>
```

- [ ] **Шаг 3: Запустить панель и проверить вручную**

Run: `uv run day04/web.py`
Открыть `http://127.0.0.1:8034` в браузере (через web-preview skill или вручную). Ожидается: карта-лидер сверху с текстом эталона, два блока по три ряда температур. Если `day04/results.json` ещё нет (Task 2, шаг 3 создал его с `--runs 1`), ряды покажут карточки по одному прогону на температуру — это нормально, полный замер будет в Task 4.

Проверить кнопку «Спросить»: выбрать «буквы», temperature 0, нажать — должен появиться вердикт и раскрывающийся блок с сырым ответом.

Остановить сервер: `Ctrl+C`.

- [ ] **Шаг 4: Коммит**

```bash
git add day04/web.py day04/web/index.html
git commit -m "feat: day 4 — Gwent-themed panel"
```

---

### Task 4: полный замер и README

**Файлы:**
- Изменить: `README.md` (в корне `ai-advent-9`)

**Интерфейсы:**
- Потребляет: `day04/temperature.py --runs 10` (Task 2), `day04/temperature.py --report` (Task 2).

- [ ] **Шаг 1: Запустить полный замер**

Run: `uv run day04/temperature.py --runs 10`

Это 60 вызовов измерения + до 31 вызова судьи, параллельно, пул на 8 потоков — пара минут. Результат перезапишет `day04/results.json` (файл из дымового прогона Task 2 будет заменён полным). В конце команда сама печатает отчёт — обе таблицы и строку про человеческий эталон.

- [ ] **Шаг 2: Свериться вручную с судьёй на 2-3 ответах**

Открыть `day04/results.json`, найти 2-3 записи с `"task": "gadget"`. До того как смотреть на поле `"judge"` в этой же записи, самому поставить каждому ответу оценку 1-10 по критерию «насколько оригинально» — так же, как это сформулировано в `JUDGE_PROMPT`. Затем сравнить со значением `"judge"`. Если оценки сильно разошлись (разница 4+ балла) — зафиксировать это в README как отдельный вывод, не сглаживать.

- [ ] **Шаг 3: Проверить панель на полных данных**

Run: `uv run day04/web.py`, открыть `http://127.0.0.1:8034`. Убедиться, что в каждом ряду по 10 карточек (для гаджета — с оценками судьи, для букв — с гол/бронза/трещина по правильности). Остановить сервер.

- [ ] **Шаг 4: Обновить таблицу дней в README**

Найти таблицу «## Дни» в README.md, добавить строку после дня 3:

```
| 04 | температура на двух запросах: точность, разнообразие, креативность | [`day04/temperature.py`](day04/temperature.py) |
```

- [ ] **Шаг 5: Добавить раздел «День 4: что получилось»**

Взять реальные числа из вывода `uv run day04/temperature.py --report` (Шаг 1) и ручной сверки (Шаг 2). Написать раздел в README.md после раздела «День 3: что получилось», по образцу его структуры: короткое вступление про задачу, таблица с колонками температура/точность/разнообразие/креативность для обоих запросов, затем прозой — что из этого следует. Прозе обязательно ответить на три вопроса, используя фактически полученные цифры:

1. Растёт ли доля ошибок капкана на буквы с температурой, или температура на неё не влияет?
2. Как соотносятся точность (доля из 4 требований) и разнообразие (доля уникальных ответов) на разных температурах у открытого запроса — растут вместе, идут вразрез, или один почти не меняется?
3. Совпала ли ручная оценка с судьёй на сверенных 2-3 ответах (Шаг 2) и какую оценку судья поставил человеческому эталону — это прямая проверка, можно ли доверять LLM-as-judge в этой конкретной настройке.
4. Отдельным пунктом — почему выбран именно капкан на подсчёт букв, а не классика вроде `9.11 vs 9.9` или `strawberry`: обе классические ловушки были проверены при подготовке спеки и не сработали на `deepseek-chat` (модель отвечает верно), а подсчёт букв в словах с двойными буквами — воспроизводимо сработал. Значит капкан отражает реальный, ещё не пропатченный баг, а не измеряет устаревший мем.

- [ ] **Шаг 6: Коммит**

```bash
git add README.md day04/results.json
git commit -m "docs: day 4 — full measurement, readme, conclusions"
```
