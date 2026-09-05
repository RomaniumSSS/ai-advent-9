"""Офлайн-проверки каталога дня 5. Без API.

Проверяется не модель, а наши же данные и арифметика: полнота записей каталога,
пересчёт токенов в доллары и оценка верхней границы расхода до запуска.

Запуск:
    uv run day05/test_models.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from models import (  # noqa: E402
    DEFAULT_TRIO,
    MAX_TOKENS,
    MODELS,
    cheapest_key,
    cost,
    estimate_calls,
    estimate_prompt_tokens,
    estimate_worst_cost,
    sampling_args,
)

REQUIRED_FIELDS = (
    "id",
    "params",
    "params_num",
    "price_in",
    "price_out",
    "default_temp",
    "hf",
)


def check_catalog() -> list[str]:
    problems = []
    for key, entry in MODELS.items():
        for field in REQUIRED_FIELDS:
            if field not in entry:
                problems.append(f"каталог, {key}: нет поля {field}")
        if not entry.get("id", "").endswith(":deepinfra"):
            problems.append(
                f"каталог, {key}: провайдер не закреплён — {entry.get('id')!r}"
            )
        if not isinstance(entry.get("params_num"), int) or entry["params_num"] <= 0:
            problems.append(f"каталог, {key}: params_num не положительное целое")
        for field in ("price_in", "price_out"):
            if not isinstance(entry.get(field), (int, float)) or entry[field] <= 0:
                problems.append(f"каталог, {key}: {field} не положительное число")
        temp = entry.get("default_temp")
        if temp is not None and not isinstance(temp, (int, float)):
            problems.append(f"каталог, {key}: default_temp не число и не None")
    for key in DEFAULT_TRIO:
        if key not in MODELS:
            problems.append(
                f"тройка по умолчанию ссылается на неизвестную модель {key!r}"
            )
    if len(set(DEFAULT_TRIO)) != 3:
        problems.append(
            f"тройка по умолчанию не из трёх разных моделей: {DEFAULT_TRIO}"
        )
    return problems


COST_CASES = [
    ("gpt-oss-120b", 1000, 500, 0.000125),
    ("deepseek-v4-flash", 1000, 500, 0.00017),
    ("glm-5.3", 1000, 500, 0.0032),
    ("gpt-oss-120b", 0, 0, 0.0),
]


def check_cost() -> list[str]:
    problems = []
    for key, prompt_tokens, completion_tokens, expected in COST_CASES:
        got = cost(prompt_tokens, completion_tokens, key)
        if got is None or abs(got - expected) > 1e-12:
            problems.append(
                f"cost({key}, {prompt_tokens}, {completion_tokens}): "
                f"ждали {expected}, получили {got}"
            )
    if cost(None, 500, "glm-5.3") is not None:
        problems.append("cost без входных токенов обязан вернуть None, а не число")
    if cost(1000, None, "glm-5.3") is not None:
        problems.append("cost без выходных токенов обязан вернуть None, а не число")
    return problems


def check_calls() -> list[str]:
    problems = []
    trio = list(DEFAULT_TRIO)
    if estimate_calls(trio, 3, False) != 9:
        problems.append(
            f"3 модели × 3 прогона без судьи: ждали 9, получили {estimate_calls(trio, 3, False)}"
        )
    if estimate_calls(trio, 3, True) != 18:
        problems.append(
            f"3 модели × 3 прогона с судьёй: ждали 18, получили {estimate_calls(trio, 3, True)}"
        )
    if estimate_calls(trio, 1, False) != 3:
        problems.append(
            f"3 модели × 1 прогон: ждали 3, получили {estimate_calls(trio, 1, False)}"
        )
    return problems


def check_worst_cost() -> list[str]:
    problems = []
    question = "Объясни рекурсию простыми словами."
    trio = list(DEFAULT_TRIO)

    manual = sum(
        cost(estimate_prompt_tokens(question), MAX_TOKENS, key) * 3 for key in trio
    )
    got = estimate_worst_cost(trio, 3, False, question)
    if abs(got - manual) > 1e-12:
        problems.append(f"верхняя граница без судьи: ждали {manual}, получили {got}")

    with_judge = estimate_worst_cost(trio, 3, True, question)
    if with_judge <= got:
        problems.append("верхняя граница с судьёй обязана быть больше, чем без него")

    typical = sum(cost(estimate_prompt_tokens(question), 500, key) * 3 for key in trio)
    if got <= typical:
        problems.append(
            "верхняя граница обязана быть выше типичного расхода, иначе она не граница"
        )
    return problems


def check_cheapest() -> list[str]:
    problems = []
    key = cheapest_key()
    if key not in MODELS:
        problems.append(f"cheapest_key вернул неизвестную модель {key!r}")
        return problems
    chosen = MODELS[key]["price_out"]
    for other, entry in MODELS.items():
        if entry["price_out"] < chosen:
            problems.append(f"cheapest_key вернул {key}, но {other} дешевле на выходе")
    return problems


def check_sampling_args() -> list[str]:
    problems = []
    if sampling_args(None) != {}:
        problems.append(
            f"тумблер выключен: ключа temperature быть не должно, получили {sampling_args(None)}"
        )
    if sampling_args(0) != {"temperature": 0}:
        problems.append(
            "температура 0 обязана уехать в запрос: это настройка, а не умолчание"
        )
    if sampling_args(0.7) != {"temperature": 0.7}:
        problems.append(f"температура 0.7 не доехала: {sampling_args(0.7)}")
    return problems


def main() -> None:
    problems = (
        check_catalog()
        + check_cost()
        + check_calls()
        + check_worst_cost()
        + check_cheapest()
        + check_sampling_args()
    )
    if problems:
        print("FAIL")
        for problem in problems:
            print(f"        {problem}")
        sys.exit(1)

    print(
        f"ok    каталог: {len(MODELS)} моделей, у всех закреплён провайдер и заполнены поля"
    )
    print(
        f"ok    пересчёт токенов в доллары: {len(COST_CASES)} случаев "
        "+ два на отсутствующий usage"
    )
    print("ok    подсчёт вызовов: 9 без судьи, 18 с судьёй")
    print("ok    верхняя граница расхода выше типичного и растёт от судьи")
    print("ok    самая дешёвая модель определяется по цене выхода")
    print("ok    выключенный тумблер не кладёт temperature в запрос, ноль — кладёт")


if __name__ == "__main__":
    main()
