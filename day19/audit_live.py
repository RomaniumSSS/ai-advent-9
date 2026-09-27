"""Механическая сверка одного реального trace; смысловая сверка в results/live-audit.md."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from dotenv import dotenv_values
from .rss import parse

HERE=Path(__file__).resolve().parent

def audit(trace_path: Path, fixture: Path, metadata: Path) -> dict:
    trace=json.loads(trace_path.read_text(encoding="utf-8"))
    calls=trace["tool_calls"]
    assert trace["status"] == "saved"
    assert len(calls)==3
    assert [c["name"] for c in calls]==["collect_habr_agent_cases","prepare_report_preview","save_report"]
    assert [c["result"]["status"] for c in calls]==["data_ready","preview_ready","saved"]
    assert len({c["call_id"] for c in calls})==3
    a,b,c=calls
    assert b["arguments"]["batch_id"]==a["result"]["batch_id"]
    assert c["arguments"]["preview_id"]==b["result"]["preview_id"]
    assert c["arguments"]["sha256"]==b["result"]["sha256"]
    seen=a["result"]["model_seen"]
    entries=b["arguments"]["draft"]["entries"]
    assert {e["observation_id"] for e in entries}=={r["observation_id"] for r in seen}
    assert all(not e["metric_claims"] for e in entries if e["category"]!="confirmed_described_case")
    source_meta=json.loads(metadata.read_text(encoding="utf-8"))
    assert hashlib.sha256(fixture.read_bytes()).hexdigest()==source_meta["selected_file_sha256"]
    source,coverage,_=parse(fixture.read_bytes(),a["arguments"]["period_start_utc"],a["arguments"]["period_end_utc"])
    original=fixture.parent/source_meta["original_file"]
    assert hashlib.sha256(original.read_bytes()).hexdigest()==source_meta["original_sha256"]
    original_rows,_,_=parse(original.read_bytes(),a["arguments"]["period_start_utc"],a["arguments"]["period_end_utc"])
    original_by_id={row["article_id"]:row for row in original_rows}
    assert all(original_by_id.get(row["article_id"])==row for row in source)
    assert coverage["kind"]=="partial"
    assert {r["url"] for r in seen}=={r["url"] for r in source}
    assert {r["rss_excerpt"] for r in seen}=={r["rss_excerpt"] for r in source}
    relative=Path(c["result"]["path"])
    assert not relative.is_absolute()
    path=HERE/relative
    assert path.resolve().is_relative_to((HERE/"output").resolve()) and not path.is_symlink()
    payload=path.read_text(encoding="utf-8")
    assert hashlib.sha256(path.read_bytes()).hexdigest()==c["result"]["sha256"]
    links=set(re.findall(r"https://habr\.com/ru/articles/[0-9]+/",payload))
    assert links==set(b["result"]["source_urls"])
    assert links.issubset({r["url"] for r in seen})
    assert "Охват неполный" in payload
    assert "Результат, по словам автора:" not in payload
    raw=trace_path.read_text(encoding="utf-8")+payload
    assert "reasoning_content" not in raw and "OPENROUTER_API_KEY" not in raw
    env=HERE/".env"
    if env.is_file():
        key=dotenv_values(env).get("OPENROUTER_API_KEY")
        assert not key or key not in raw
    costs=[m["usage"]["cost"] for m in trace["model_calls"] if m.get("usage") and isinstance(m["usage"].get("cost"),(int,float))]
    assert abs(sum(costs)-trace["reported_cost_usd"])<1e-9
    return {"status":"automated_pass","run_id":trace["run_id"],"tool_calls":len(calls),
            "model_calls":len(trace["model_calls"]),"source_links":sorted(links),
            "file":str(path),"sha256":c["result"]["sha256"],
            "reported_cost_usd":trace["reported_cost_usd"]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--trace",type=Path,default=HERE/"results"/"live-trace.json")
    parser.add_argument("--fixture",type=Path,default=HERE/"fixtures"/"habr-real-selected-20260927.xml")
    parser.add_argument("--metadata",type=Path,default=HERE/"fixtures"/"habr-real-selected-20260927.json")
    args=parser.parse_args()
    print(json.dumps(audit(args.trace,args.fixture,args.metadata),ensure_ascii=False))

if __name__=="__main__":main()
