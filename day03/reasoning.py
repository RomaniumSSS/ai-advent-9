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
    PARTS,
    best_build,
    minutes_of,
    price_of,
    score,
    task_text,
)

load_dotenv()

MODEL = "deepseek-chat"
TEMPERATURE = 1.0
RESULTS = Path(__file__).parent / "results.json"

# Потолок длины ответа. Значение равно умолчанию DeepSeek — замерено запросом,
# который модель физически не может закончить: finish_reason=length на 8192.
# Задано явно, чтобы предел был виден в коде и замер воспроизводился,
# даже если провайдер поменяет умолчание. Именно в него упирался режим meta.
MAX_TOKENS = 8192

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
        "max_tokens": MAX_TOKENS,
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


def measure(runs: int) -> list[dict]:
    """Все режимы, все прогоны, параллельно."""
    jobs = [mode for mode in MODES for _ in range(runs)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(run_once, jobs))


def report(records: list[dict]) -> None:
    print(f"\nправильный ответ: {' + '.join(OPTIMUM[part] for part in PARTS)}")
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
        # Фильтруем по признаку, а не по вхождению объекта в список:
        # сравнение словарей через `in` квадратично и опирается на равенство значений.
        scored = [
            score(row["answer"]) for row in rows if not row["stop"].startswith("error")
        ]
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
