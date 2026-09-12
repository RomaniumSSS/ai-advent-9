"""Лексическая сверка заранее заданных фактов в контрольных ответах.

Совпадение слова не доказывает правильность утверждения: «срок не обсуждался»
и «срок 25 октября» для регулярки различаются, а «онлайн-оплата не нужна» и
«добавим онлайн-оплату» — нет. Поэтому ответы сохраняются целиком, а результат
называется проверкой, а не оценкой качества. Семантическое чтение — руками.

Сверяются только контрольные ходы: 9-й и 14-й прямо просят назвать факты,
16-й — перечислить ограничения и отменённый срок. В остальных ответах памяти
взяться неоткуда, и требовать её там значило бы штрафовать за чужой вопрос.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from strategies import STRATEGY_LABELS  # noqa: E402

RESULTS = Path(__file__).parent / "results"


def checks(text: str, turn: int) -> dict:
    normalized = text.casefold().replace("*", "")

    def has(pattern):
        return bool(re.search(pattern, normalized))

    result = {
        "название Маяк": has("маяк"),
        "бюджет 1200 евро": has(r"1[\s,]?200") and has(r"евро|€|\beur\b"),
        "актуальный срок 25 октября": has(r"25\s*(?:октябр|[./]10)"),
        "языки русский и польский": has("русск") and has("польск"),
        "онлайн-оплата упомянута (отрицание проверяется глазами)": has(
            r"онлайн.{0,2}оплат"
        ),
    }
    if turn == 16:
        # Финальный вопрос просит ограничения и отменённый срок, а не название.
        result.pop("название Маяк")
        result["отменённый срок 18 октября назван"] = has(r"18\s*(?:октябр|[./]10)")
    return result


def main() -> None:
    rows = []
    for path in sorted(RESULTS.glob("project-*.json")):
        if path.stem.endswith("branching"):
            continue
        data = json.loads(path.read_text())
        for row in data["rows"]:
            if not row["control"]:
                continue
            found = checks(row["answer"], row["turn"])
            rows.append(
                {
                    "strategy": data["strategy"],
                    "strategy_label": data["strategy_label"],
                    "turn": row["turn"],
                    "checks": found,
                    "passed": sum(found.values()),
                    "total": len(found),
                    "answer": row["answer"],
                }
            )
    if not rows:
        print("нет результатов прогонов: сначала run_strategies.py")
        return

    by_strategy = {}
    for row in rows:
        entry = by_strategy.setdefault(row["strategy"], {"passed": 0, "total": 0})
        entry["passed"] += row["passed"]
        entry["total"] += row["total"]

    output = {
        "method": "лексическая сверка, не семантический судья и не человеческая приёмка",
        "control_turns": sorted({row["turn"] for row in rows}),
        "by_strategy": by_strategy,
        "answers": rows,
    }
    (RESULTS / "quality-lexical.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    for strategy, entry in by_strategy.items():
        print(f"{STRATEGY_LABELS[strategy]:<16} {entry['passed']} / {entry['total']}")
    for row in rows:
        if row["passed"] < row["total"]:
            missing = [name for name, ok in row["checks"].items() if not ok]
            print(
                f"  {row['strategy']} ход {row['turn']}: не найдено — {'; '.join(missing)}"
            )


if __name__ == "__main__":
    main()
