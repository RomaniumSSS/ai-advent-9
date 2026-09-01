"""Тест логики разбора ответа. Без обращения к API — быстро и бесплатно.

Смысл: проверяются не ответы модели, а наши выводы о них. Легко написать проверку,
которая хвалит не тот рычаг. Главный случай — ответ, обрезанный по max_tokens:
в нём нет стоп-слова, и наивная проверка запишет это в заслугу stop.

Запуск:
    uv run day02/test_verdict.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from formats import STOP_WORD, verdict  # noqa: E402

GOOD = '{"exercises":[{"name":"Наклоны головы","minutes":1,"reps":"10 раз","target":"шея"}]}'

CASES = [
    (
        "нормальный ответ: схема совпала, ничего не оборвалось",
        GOOD,
        "stop",
        {"json_ok": True, "schema_ok": True, "fits": True, "refusal": False},
        "чисто",
    ),
    (
        "обрезано по лимиту — заслуга не stop, а max_tokens",
        '{"exercises":[{"name":"Наклоны гол',
        "length",
        {"json_ok": False, "schema_ok": False, "fits": False},
        "max_tokens",
    ),
    (
        "обрыв по лимиту важнее маркера: порядок проверок нельзя менять местами",
        GOOD + f" {STOP_WORD} и дальше обор",
        "length",
        {"json_ok": False},
        "max_tokens",
    ),
    (
        "маркер остался в тексте — завершение не сработало",
        GOOD + f"\n{STOP_WORD}",
        "stop",
        {"json_ok": False, "schema_ok": False},
        "не сработало",
    ),
    (
        "markdown-заборчик ломает разбор, хотя глазами всё верно",
        f"```json\n{GOOD}\n```",
        "stop",
        {"json_ok": False, "schema_ok": False},
        "чисто",
    ),
    (
        "чужой ключ вместо exercises — схема не та",
        '{"warmup":[{"name":"a","minutes":1,"reps":"5","target":"шея"}]}',
        "stop",
        {"json_ok": True, "schema_ok": False},
        "чисто",
    ),
    (
        "не хватает поля target — схема не та",
        '{"exercises":[{"name":"a","minutes":1,"reps":"5"}]}',
        "stop",
        {"json_ok": True, "schema_ok": False},
        "чисто",
    ),
    (
        "отказ по теме — это правильное поведение, а не поломка",
        '{"error": "вопрос вне темы"}',
        "stop",
        {"json_ok": True, "refusal": True, "schema_ok": False},
        "чисто",
    ),
    (
        "шесть упражнений при лимите пять — схема верна, лимит нарушен",
        '{"exercises":['
        + ",".join(
            f'{{"name":"у{i}","minutes":1,"reps":"5","target":"шея"}}' for i in range(6)
        )
        + "]}",
        "stop",
        {"json_ok": True, "schema_ok": True, "fits": False},
        "чисто",
    ),
    (
        "слова считаются по содержимому, а не по разметке",
        GOOD,
        "stop",
        {"words": 6},
        "чисто",
    ),
]


def main() -> None:
    failed = 0

    for name, answer, stop_reason, expected, stop_contains in CASES:
        result = verdict(answer, stop_reason)
        problems = [
            f"{key}: ждали {value!r}, получили {result[key]!r}"
            for key, value in expected.items()
            if result[key] != value
        ]
        if stop_contains not in result["stop"]:
            problems.append(
                f"stop: ждали «{stop_contains}», получили «{result['stop']}»"
            )

        if problems:
            failed += 1
            print(f"FAIL  {name}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    {name}")

    print(f"\nпройдено {len(CASES) - failed} из {len(CASES)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
