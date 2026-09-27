"""Проверка сохранённых trace и файлов без повторного обращения к модели."""
from __future__ import annotations

import hashlib
import argparse
import json
from collections import Counter
from pathlib import Path
from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def audit_trace(path: Path) -> dict:
    raw = path.read_bytes()
    trace = json.loads(raw)
    calls = trace["tool_calls"]
    assert b"OPENROUTER_API_KEY" not in raw, path
    env = ROOT / ".env"
    if env.is_file():
        key = dotenv_values(env).get("OPENROUTER_API_KEY")
        assert not key or key.encode() not in raw, path
    assert len(calls) <= 5 and len(trace["model_calls"]) <= 6, path
    assert all(c["result"].get("status") != "saved" or c["name"] == "save_report"
               for c in calls), path
    output = ROOT / "output" / f"report-{trace['run_id']}.txt"
    if trace["status"] != "saved":
        assert not output.exists(), path
        return trace
    search = next(c for c in calls if c["name"] == "collect_habr_agent_cases"
                  and c["result"].get("status") == "data_ready")
    preview = next(c for c in calls if c["name"] == "prepare_report_preview"
                   and c["result"].get("status") == "preview_ready")
    save = next(c for c in calls if c["name"] == "save_report"
                and c["result"].get("status") == "saved")
    seen = search["result"]["model_seen"]
    draft = preview["arguments"]["draft"]
    assert preview["arguments"]["batch_id"] == search["result"]["batch_id"], path
    assert {e["observation_id"] for e in draft["entries"]} == {r["observation_id"] for r in seen}, path
    assert save["arguments"]["preview_id"] == preview["result"]["preview_id"], path
    assert save["arguments"]["sha256"] == preview["result"]["sha256"], path
    assert save["result"]["path"] == str(output.relative_to(ROOT)), path
    data = output.read_bytes()
    assert hashlib.sha256(data).hexdigest() == save["result"]["sha256"], path
    links = {line for line in data.decode("utf-8").splitlines() if line.startswith("https://")}
    assert links == set(preview["result"]["source_urls"]), path
    assert links <= {r["url"] for r in seen}, path
    return trace


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, help="Проверить один trace вместо сохранённой серии")
    args = parser.parse_args()
    if args.trace:
        traces = [audit_trace(args.trace)]
    else:
        rows = [json.loads(line) for line in (HERE / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
        traces = [audit_trace(ROOT / row["trace"]) for row in rows]
        traces.extend(audit_trace(path) for path in sorted((HERE / "traces").glob("live_feed-*.json")))
    print(json.dumps({"traces_checked": len(traces),
                      "status": dict(Counter(t["status"] for t in traces)),
                      "tool_errors": dict(Counter(c["result"].get("code") for t in traces
                                                 for c in t["tool_calls"]
                                                 if c["result"].get("status") == "error")),
                      "reported_cost_usd": round(sum(t["reported_cost_usd"] for t in traces), 6)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
