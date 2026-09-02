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
    if not is_valid(OPTIMUM):
        problems.append(f"оптимум признан невалидным: {broken_rules(OPTIMUM)}")
    return problems


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
