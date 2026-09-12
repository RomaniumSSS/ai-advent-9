"""Сводка по прогонам: сколько стоила каждая стратегия и что она помнит.

Пишет `results/comparison.json` — его же читает панель. Ни одного обращения
к API: считаются уже полученные usage.

Неизвестное остаётся неизвестным. Если хотя бы у одного вызова не приехал
usage, сумма по этому показателю — `None`, а не «столько, сколько успели
насчитать»: неполный итог, выданный за полный, врёт тише всего.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from strategies import STRATEGY_LABELS  # noqa: E402

RESULTS = Path(__file__).parent / "results"


def quality_by_strategy() -> dict:
    path = RESULTS / "quality-lexical.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get("by_strategy", {})


def main() -> None:
    quality = quality_by_strategy()
    rows = []
    for path in sorted(RESULTS.glob("project-*.json")):
        if path.stem.endswith("branching"):
            continue
        data = json.loads(path.read_text())
        total = data["usage"]["total"]
        facts = data["usage"]["facts"]
        found = quality.get(data["strategy"])
        rows.append(
            {
                "strategy": data["strategy"],
                "strategy_label": data["strategy_label"],
                "turns": data["turns"],
                "calls": total["calls"],
                "facts_calls": facts["calls"],
                "prompt_tokens": total["prompt_tokens"],
                "completion_tokens": total["completion_tokens"],
                "tokens": total["tokens"],
                "facts_tokens": facts["tokens"],
                "cost_reported": total["cost_reported"],
                "sent_messages_last": data["rows"][-1]["sent_messages"],
                "archived_messages": data["history_messages"],
                "facts_kept": len(data["facts"]),
                "facts_found": found["passed"] if found else None,
                "facts_total": found["total"] if found else None,
            }
        )
    if not rows:
        print("нет результатов прогонов: сначала run_strategies.py")
        return

    baseline = next((row for row in rows if row["strategy"] == "full"), None)
    for row in rows:
        if baseline and baseline["tokens"] and row["tokens"] is not None:
            row["vs_full_percent"] = round(
                (row["tokens"] - baseline["tokens"]) / baseline["tokens"] * 100, 1
            )
        else:
            row["vs_full_percent"] = None

    (RESULTS / "comparison.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    )

    width = max(len(STRATEGY_LABELS[row["strategy"]]) for row in rows)
    header = f"{'стратегия':<{width}}  вызовов  вход    выход   всего   к full   память"
    print(header)
    print("-" * len(header))
    for row in rows:
        against = (
            "—" if row["vs_full_percent"] is None else f"{row['vs_full_percent']:+.1f}%"
        )
        memory = (
            "—"
            if row["facts_found"] is None
            else f"{row['facts_found']}/{row['facts_total']}"
        )
        print(
            f"{row['strategy_label']:<{width}}  {row['calls']:>7}  "
            f"{row['prompt_tokens']:>6}  {row['completion_tokens']:>6}  "
            f"{row['tokens']:>6}  {against:>7}  {memory:>6}"
        )

    branching = RESULTS / "project-branching.json"
    if branching.exists():
        data = json.loads(branching.read_text())
        names = ", ".join(
            f"{key} ({len(value['rows'])} хода)"
            for key, value in data["branches"].items()
        )
        print(
            f"\nветвление: точка {data['checkpoint']} сообщений, ветки {names}; "
            f"в исходной сессии осталось {data['root_messages_after']} сообщений"
        )


if __name__ == "__main__":
    main()
