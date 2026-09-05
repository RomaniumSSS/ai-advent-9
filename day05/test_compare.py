"""Офлайн-проверки движка дня 5. Без API.

Проверяются чистые части compare.py: имя файла сессии и подсчёт агрегатов.
Сами вызовы к моделям здесь не проверяются — для этого есть живой прогон.

Запуск:
    uv run day05/test_compare.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from compare import session_name, summarize  # noqa: E402


def record(
    elapsed, prompt_tokens, completion_tokens, money, error=None, judge=None, chars=42
):
    return {
        "model": "glm-5.3",
        "answer": "текст",
        "answer_chars": chars,
        "finish_reason": "stop",
        "elapsed": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": None,
        "cost": money,
        "temperature": None,
        "error": error,
        "judge": judge,
    }


def check_session_name() -> list[str]:
    problems = []
    cases = [
        ("Объясни рекурсию простыми словами", "obyasni-rekursiyu"),
        ("Hello world", "hello-world"),
    ]
    for question, expected_part in cases:
        name = session_name(question)
        if expected_part not in name:
            problems.append(
                f"имя сессии для {question!r} не содержит {expected_part!r}: {name}"
            )
        if not name.endswith(".json"):
            problems.append(f"имя сессии не заканчивается на .json: {name}")

    for bad in ("???", "   ", "!!!---"):
        name = session_name(bad)
        if not name.endswith("-question.json"):
            problems.append(
                f"вопрос без букв обязан дать хвост -question.json, получили {name}"
            )

    for dangerous in ("../../etc/passwd", "a/b/c", "..\\win"):
        name = session_name(dangerous)
        if "/" in name or "\\" in name or ".." in name.replace(".json", ""):
            problems.append(f"имя сессии выходит за папку results: {name}")

    if len(session_name("я" * 300)) > 80:
        problems.append(
            "имя сессии не обрезается: длинный вопрос дал слишком длинное имя"
        )
    return problems


def check_summarize() -> list[str]:
    problems = []

    got = summarize([record(1.0, 100, 200, 0.001), record(3.0, 100, 200, 0.001)])
    if got["ok"] != 2:
        problems.append(f"два успешных вызова: ждали ok=2, получили {got['ok']}")
    if got["time_avg"] != 2.0 or got["time_min"] != 1.0 or got["time_max"] != 3.0:
        problems.append(f"время: ждали среднее 2.0 при 1.0 и 3.0, получили {got}")
    if abs(got["cost_total"] - 0.002) > 1e-12:
        problems.append(f"стоимость обязана складываться: {got['cost_total']}")

    mixed = summarize(
        [record(1.0, 100, 200, 0.001), record(9.0, None, None, None, error="сбой")]
    )
    if mixed["ok"] != 1 or mixed["runs"] != 2:
        problems.append(f"сбойный вызов обязан считаться в runs, но не в ok: {mixed}")
    if mixed["time_avg"] != 1.0:
        problems.append(f"агрегаты обязаны считаться только по успешным: {mixed}")

    empty = summarize([record(1.0, None, None, None, error="сбой")])
    if empty["ok"] != 0:
        problems.append(f"все вызовы упали: ждали ok=0, получили {empty}")

    no_usage = summarize([record(1.0, None, None, None)])
    if no_usage["cost_total"] is not None or no_usage["prompt_avg"] is not None:
        problems.append(
            f"без usage стоимость и токены обязаны быть None, а не нулём: {no_usage}"
        )

    judged = summarize(
        [record(1.0, 100, 200, 0.001, judge=8), record(1.0, 100, 200, 0.001, judge=6)]
    )
    if judged["judge_avg"] != 7.0:
        problems.append(
            f"средняя оценка судьи: ждали 7.0, получили {judged['judge_avg']}"
        )

    chars = summarize(
        [record(1.0, 100, 200, 0.001, chars=10), record(1.0, 100, 200, 0.001, chars=20)]
    )
    if chars["chars_avg"] != 15.0:
        problems.append(
            f"средняя длина ответа: ждали 15.0, получили {chars['chars_avg']}"
        )
    return problems


def main() -> None:
    problems = check_session_name() + check_summarize()
    if problems:
        print("FAIL")
        for problem in problems:
            print(f"        {problem}")
        sys.exit(1)

    print(
        "ok    имя сессии: транслитерация, хвост -question, без выхода за папку, обрезка"
    )
    print(
        "ok    агрегаты: сбойные вызовы не портят средние, без usage — None, а не ноль"
    )


if __name__ == "__main__":
    main()
