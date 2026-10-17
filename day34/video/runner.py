"""Воспроизведение двух целей: mock явно обозначен, live требует общий ledger."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import run
from mock_model import MockModel

GOALS = ["Найди все использования API send_invite и объясни поток вызовов", "Обнови README по текущему поведению кода и покажи изменения"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--budget-ledger")
    args = parser.parse_args()
    factory = MockModel
    if args.live:
        from budget import Budget
        from model import OpenRouterModel
        if not args.budget_ledger:
            parser.error("Нужен общий --budget-ledger")
        budget = Budget(args.budget_ledger)
        factory = lambda: OpenRouterModel(budget)
    print("LIVE" if args.live else "OFFLINE SCRIPTED MOCK — не AI")
    for goal in GOALS:
        result = run(goal, factory())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] != "completed":
            sys.exit(1)
