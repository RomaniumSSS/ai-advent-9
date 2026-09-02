"""День 3: одна задача, четыре способа рассуждения.

Режимы:
    direct   прямой ответ без дополнительных инструкций
    steps    «решай пошагово»
    meta     модель сначала пишет промпт, затем решает по нему (два вызова)
    experts  группа экспертов в промпте: аналитик, инженер, критик

Инструкция про формат ответа дословно одинакова во всех режимах: иначе сравнивались
бы форматы, а не рассуждения.

Запуск:
    uv run day03/reasoning.py
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

# Опорная точка, а не режим промптинга: тот же промпт, но рассуждения
# придушены параметром API. Показывает, сколько стоит само рассуждение.
NO_THINKING = {"thinking": {"type": "disabled"}}

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


def call(prompt: str, extra: dict | None = None) -> tuple[str, str]:
    """Возвращает (текст ответа, причина остановки). При сбое API отдаёт ("", "error: ...").

    extra уходит в extra_body — туда кладутся параметры, которых нет в схеме
    OpenAI, но которые понимает DeepSeek.
    """
    params = {
        "model": MODEL,
        "temperature": TEMPERATURE,
        "messages": [{"role": "user", "content": prompt}],
    }
    if extra:
        params["extra_body"] = extra

    try:
        choice = client.chat.completions.create(**params).choices[0]
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


def mode_direct_nothink(task: str) -> tuple[str, str, int]:
    """Тот же промпт, что у direct, но с придушенными рассуждениями."""
    answer, stop = call(f"{task}\n\n{ANSWER_FORMAT}", NO_THINKING)
    return answer, stop, 1


MODES = {
    "direct": mode_direct,
    "direct-nothink": mode_direct_nothink,
    "steps": mode_steps,
    "meta": mode_meta,
    "experts": mode_experts,
}


def run_once(mode: str) -> dict:
    """Один прогон одного режима. Сырой ответ сохраняется целиком."""
    answer, stop, calls = MODES[mode](task_text())
    return {"mode": mode, "answer": answer, "stop": stop, "calls": calls}


OPTIMUM, VALID_TOTAL = best_build()


def score(record: dict) -> dict:
    """Метрики одного прогона.

    Три категории провала разведены намеренно, потому что означают разное:
      parsed=False   — модель не выдала разбираемую строку. Поломка формата,
                       а не рассуждения, в ошибку решения не записывается.
      invented=True  — модель придумала деталь, которой нет в каталоге.
                       Она не считала и ошиблась, она вообще не смотрела в каталог.
      valid=False    — все детали настоящие, но нарушено правило совместимости.
    """
    build = parse_answer(record["answer"])
    empty = {
        "parsed": False,
        "invented": False,
        "valid": False,
        "in_budget": False,
        "optimal": False,
        "minutes": 0.0,
    }
    if build is None:
        return empty

    problems = broken_rules(build)
    if any("нет в каталоге" in problem for problem in problems):
        return empty | {"parsed": True, "invented": True}

    valid = not problems
    return {
        "parsed": True,
        "invented": False,
        "valid": valid,
        # Считать бюджет осмысленно только когда все позиции настоящие,
        # иначе price_of вообще не на чем вызвать.
        "in_budget": not any(problem.startswith("бюджет") for problem in problems),
        "optimal": build == OPTIMUM,
        "minutes": minutes_of(build) if valid else 0.0,
    }


def measure(runs: int) -> list[dict]:
    """Все режимы, все прогоны, параллельно."""
    jobs = [mode for mode in MODES for _ in range(runs)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(run_once, jobs))


def report(records: list[dict]) -> None:
    print(f"\nправильный ответ: {' + '.join(OPTIMUM[part] for part in OPTIMUM)}")
    print(
        f"{minutes_of(OPTIMUM):.2f} мин, цена {price_of(OPTIMUM)}, "
        f"валидных сборок в каталоге {VALID_TOTAL} из 1920\n"
    )

    head = (
        f"{'режим':<15} {'разобралось':>12} {'выдумал':>8} {'валидна':>8} "
        f"{'в бюджете':>10} {'оптимум':>8} {'ср. мин':>8} {'вызовов':>8}"
    )
    print(head)
    print("-" * len(head))

    for mode in MODES:
        rows = [record for record in records if record["mode"] == mode]
        if not rows:
            continue
        failed = [row for row in rows if row["stop"].startswith("error")]
        scored = [score(row) for row in rows if row not in failed]
        parsed = [s for s in scored if s["parsed"]]
        flying = [s["minutes"] for s in parsed if s["valid"]]

        print(
            f"{mode:<15} {len(parsed):>7}/{len(scored):<4} "
            f"{sum(s['invented'] for s in parsed):>8} "
            f"{sum(s['valid'] for s in parsed):>8} "
            f"{sum(s['in_budget'] for s in parsed):>10} "
            f"{sum(s['optimal'] for s in parsed):>8} "
            f"{(sum(flying) / len(flying) if flying else 0):>8.2f} "
            f"{sum(row['calls'] for row in rows):>8}"
            + (f"   не дошло: {len(failed)}" if failed else "")
        )

    print(
        "\nстолбцы «выдумал», «валидна», «в бюджете», «оптимум» считаются "
        "от числа разобравшихся ответов."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--mode", choices=list(MODES))
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
