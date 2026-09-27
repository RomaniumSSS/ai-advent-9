"""Локальный ручной запуск Day 19. Секреты не выводятся."""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import dotenv_values

from .agent import Agent, OpenRouterProvider
from .config import PROFILE, select_profile
from .mcp_client import McpConfig
from .store import Store
from .preflight import check

HERE = Path(__file__).resolve().parent

def utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,default=HERE/"state.sqlite3")
    parser.add_argument("--trace",type=Path,default=HERE/"results"/"live-trace.json")
    parser.add_argument("--rss-file",type=Path,help="Сохранённый реальный RSS; без него live RSS")
    parser.add_argument("--env-file",type=Path,default=HERE/".env")
    parser.add_argument("--profile",default="deepseek")
    parser.add_argument("--start",help="Начало периода в UTC, ISO 8601 Z")
    parser.add_argument("--end",help="Конец периода в UTC, ISO 8601 Z")
    parser.add_argument("--request",default="Собери сводку о применении ИИ-агентов из RSS Хабра и сохрани её")
    parser.add_argument("--show-steps",action="store_true",help="Показывать безопасные события агентного цикла в stdout")
    args = parser.parse_args()
    profile = select_profile(args.profile)
    if args.env_file.is_file():
        if args.env_file.stat().st_mode & 0o077:
            raise SystemExit("env_file_permissions_must_be_0600")
        key = dotenv_values(args.env_file).get("OPENROUTER_API_KEY")
        if key:
            os.environ["OPENROUTER_API_KEY"] = key
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("missing_OPENROUTER_API_KEY")
    current = datetime.now(timezone.utc)
    start = args.start or utc(current - timedelta(days=1))
    end = args.end or utc(current)
    if not start.endswith("Z") or not end.endswith("Z") or start >= end:
        raise SystemExit("invalid_utc_window")
    if args.rss_file and not args.rss_file.is_file():
        raise SystemExit("rss_file_missing")
    preflight = check(profile)
    store = Store(args.db)
    run_id = store.create_run(start,end)
    argv = ["-m","day19.server","--db",str(args.db.resolve())]
    if args.rss_file:
        argv += ["--rss-file",str(args.rss_file.resolve())]
    config = McpConfig(sys.executable,tuple(argv))
    provider = OpenRouterProvider(profile)
    def show_event(event: dict) -> None:
        print(json.dumps(event,ensure_ascii=False),flush=True)
    if args.show_steps:
        show_event({"event":"request","text":args.request,"source":"saved_rss" if args.rss_file else "live_rss"})
    trace = Agent(store,config,provider,profile,trace_path=args.trace,preflight=preflight,
                  on_event=show_event if args.show_steps else None).run(run_id,args.request)
    print(json.dumps({"run_id":run_id,"status":trace["status"],"reason":trace["reason"],
                      "tool_calls":len(trace["tool_calls"]),"model_calls":len(trace["model_calls"]),
                      "reported_cost_usd":trace["reported_cost_usd"],"preflight_upper_usd":preflight["conservative_upper_usd"],"trace":str(args.trace)},ensure_ascii=False))
    if trace["status"] != "saved":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
