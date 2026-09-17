"""Сравнение с исходным снимком и baseline машины; без изменения Git."""
import hashlib
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_REF = "4968ef48c9059d8d4739341ad46838db05753939"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "day12/results/baseline.json")
    parser.add_argument("--report", type=Path, default=ROOT / "day12/results/scope-report.json")
    args = parser.parse_args()
    baseline = json.loads(args.snapshot.read_text())
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    ).decode().split("\0")
    current = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
               for name in names if name and (ROOT/name).is_file()}
    changed = sorted(name for name in baseline.keys() | current.keys()
                     if baseline.get(name) != current.get(name))
    outside = [name for name in changed if not name.startswith("day12/")]
    protected = subprocess.check_output(
        ["git", "diff", "--name-only", BASELINE_REF, "--"]
        + [f"day{day:02d}/" for day in range(1, 12)], cwd=ROOT
    ).decode().splitlines()
    result = {"baseline_ref": BASELINE_REF,
              "snapshot": str(args.snapshot),
              "outside_day12_since_snapshot": outside,
              "protected_diff_from_baseline": protected,
              "changed_since_snapshot": changed,
              "pass": not outside and not protected}
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    assert result["pass"], result
    print("ok  вне day12 нет новых изменений; day01–day11 совпадают с baseline; исходные пользовательские изменения сохранены")


if __name__ == "__main__":
    main()
