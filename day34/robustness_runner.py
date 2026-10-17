"""Операторский bounded live-прогон; ledger существует, fixture задаёт только оператор."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from budget import Budget, amount
from core import run
from model import OpenRouterModel


class SessionCap:
    """Дополнительный потолок последовательного оператора поверх общего ledger $1."""
    def __init__(self, budget, cap):
        self.budget = budget
        self.cap = amount(cap)
        if not 0 < self.cap <= 1:
            raise ValueError("accounted-cap должен быть больше 0 и не больше 1")

    def reserve(self, run_id, ceiling):
        ceiling = amount(ceiling)
        # AICODE-NOTE: оператор запускает только один live процесс; общий reserve
        # дополнительно проверяет $1 атомарно. Этот cap не предназначен для concurrency.
        with self.budget.connect() as db:
            used = db.execute("SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM reservations").fetchone()[0]
        if not math.isfinite(used) or used + ceiling > self.cap:
            raise RuntimeError("operator_accounted_cap")
        return self.budget.reserve(run_id, ceiling)

    def settle(self, *args):
        return self.budget.settle(*args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--budget-ledger", required=True)
    parser.add_argument("--accounted-cap", type=float, required=True)
    parser.add_argument("--max-steps", type=int, default=6, choices=range(1, 7))
    args = parser.parse_args()
    if not args.fixture.is_dir():
        parser.error("fixture должна быть существующим каталогом")
    args.out.mkdir(parents=True, exist_ok=False)
    provenance = {
        "goal": args.goal, "fixture": str(args.fixture.resolve()),
        "max_steps": args.max_steps, "accounted_cap": args.accounted_cap,
        "code_sha256": {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in ["core.py", "model.py", "budget.py", "robustness_runner.py"]},
        "fixture_sha256": {p.relative_to(args.fixture).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.fixture.rglob("*")) if p.is_file() and not p.is_symlink()},
    }
    (args.out / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        model = OpenRouterModel(SessionCap(Budget(args.budget_ledger), args.accounted_cap))
        result = run(args.goal, model, parent=args.out / "runs", fixture=args.fixture.resolve(), max_steps=args.max_steps)
    except Exception as exc:
        result = {"status": "error", "reason": type(exc).__name__, "phase": "startup", "live_call_performed": False}
    (args.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "reason": result.get("reason"), "result": str(args.out / "result.json")}, ensure_ascii=False))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
