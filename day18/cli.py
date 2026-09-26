"""Операторский entrypoint Day 18; без HTTP listener и скрытого catch-up."""

from __future__ import annotations

import argparse
import json
import stat
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from day18.agent import Agent, OpenRouterProvider
from day18.delivery import Dispatcher, TelegramTransport
from day18.mcp_client import McpConfig
from day18.repository import Repository
from day18.scheduler import due_now, slot_for
from day18.store import Store
from day18.tool_calling import ToolRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--env-file", type=Path, default=None,
                        help="Файл .env с ключом модели и Telegram; права 600")
    parser.add_argument("--model", default="", help="Закреплённая модель OpenRouter/deepinfra")
    parser.add_argument("--verified-visible-budget", type=int, default=None,
                        help="Только после отдельной проверки tokenizer/hidden reasoning в live gate")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("status")
    sub.add_parser("scheduled")
    manual = sub.add_parser("manual")
    manual.add_argument("--date", required=True)
    manual.add_argument("--invocation-id", default=None)
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--date", required=True)
    backfill.add_argument("--actor", required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("run_id")
    resume.add_argument("--actor", required=True)
    sub.add_parser("dispatch")
    resolve = sub.add_parser("resolve")
    resolve.add_argument("run_id")
    resolve.add_argument("--actor", required=True)
    resolve.add_argument("--reason", required=True)
    resolve.add_argument("--evidence", required=True)
    resolve.add_argument("--decision", choices=("delivered", "negative", "quarantine"), required=True)
    resolve.add_argument("--message-id", type=int)
    retry = sub.add_parser("retry-definitive")
    retry.add_argument("run_id")
    retry.add_argument("--actor", required=True)
    retry.add_argument("--reason", required=True)
    retry.add_argument("--evidence", required=True)
    retire = sub.add_parser("retire")
    retire.add_argument("run_id")
    retire.add_argument("--actor", required=True)
    retire.add_argument("--reason", required=True)
    retire.add_argument("--evidence", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("target", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        if not args.env_file.is_file() or args.env_file.is_symlink():
            raise ValueError("Нужен обычный .env файл без symlink")
        if stat.S_IMODE(args.env_file.stat().st_mode) != 0o600:
            raise ValueError("Права .env должны быть 600")
        load_dotenv(args.env_file, override=False)
    store = Store(args.db)
    if args.command == "backup":
        store.backup(args.target)
        print(json.dumps({"backup": str(args.target)}, ensure_ascii=False))
        return 0
    store.migrate()
    repo = Repository(store)
    if args.command == "init-db":
        print(json.dumps({"schema": 1, "db": str(args.db)}, ensure_ascii=False))
        return 0
    if args.command == "status":
        with store.connect() as db:
            rows = db.execute("SELECT id,state,stage,reason_code,updated_utc FROM runs ORDER BY updated_utc DESC LIMIT 30").fetchall()
            dates = [date.fromisoformat(row[0]) for row in db.execute("SELECT DISTINCT local_date FROM slots ORDER BY local_date")]
            present = set(dates)
            gaps = []
            if dates:
                cursor = dates[0]
                while cursor < dates[-1]:
                    if cursor not in present:
                        gaps.append(cursor.isoformat())
                    cursor += timedelta(days=1)
            ready = db.execute("SELECT COUNT(*) FROM runs WHERE state='REPORT_READY' AND no_send=0").fetchone()[0]
            unknown = db.execute("SELECT COUNT(*) FROM runs WHERE state='DELIVERY_UNKNOWN'").fetchone()[0]
            partial = sum(json.loads(row[0])["kind"] != "complete_for_profile"
                          for row in db.execute("SELECT coverage_json FROM batches"))
            print(json.dumps({"runs": [dict(row) for row in rows], "missing_slot_dates": gaps,
                              "ready_reports": ready, "delivery_unknown": unknown,
                              "partial_batches": partial}, ensure_ascii=False))
        return 0
    dispatcher = Dispatcher(repo, TelegramTransport())
    if args.command == "resolve":
        dispatcher.resolve_unknown(args.run_id, actor=args.actor, reason=args.reason,
                                   evidence=args.evidence, decision=args.decision, message_id=args.message_id)
        print(json.dumps({"run_id": args.run_id, "decision": args.decision}))
        return 0
    if args.command == "retry-definitive":
        dispatcher.retry_definitive(args.run_id, actor=args.actor, reason=args.reason, evidence=args.evidence)
        print(json.dumps({"run_id": args.run_id, "state": "REPORT_READY"}))
        return 0
    if args.command == "retire":
        dispatcher.retire(args.run_id, actor=args.actor, reason=args.reason, evidence=args.evidence)
        print(json.dumps({"run_id": args.run_id, "retired": True}))
        return 0
    if args.command == "dispatch":
        print(json.dumps({"outcome": dispatcher.dispatch_once()}))
        return 0
    if args.command != "manual" and not (
        args.command == "resume" and repo.context(args.run_id).no_send
    ):
        # Восстановление committed REPORT_READY предшествует новому slot и не вызывает модель/MCP.
        dispatcher.dispatch_once()
    if args.command == "scheduled":
        slot = due_now(datetime.now(timezone.utc))
        if slot is None:
            print(json.dumps({"status": "not_due"}))
            return 0
        context = repo.get_or_create_run(slot)
    elif args.command == "backfill":
        slot = slot_for(date.fromisoformat(args.date))
        context = repo.get_or_create_run(slot)
        repo.record_operator_action(context.run_id, actor=args.actor, decision="backfill",
                                    reason="explicit_slot", evidence=slot.local_date)
    elif args.command == "manual":
        slot = slot_for(date.fromisoformat(args.date))
        context = repo.get_or_create_run(slot, manual_invocation_id=args.invocation_id or str(uuid.uuid4()))
    elif args.command == "resume":
        repo.begin_generation_resume(args.run_id, actor=args.actor)
        context = repo.context(args.run_id)
    else:
        raise AssertionError(args.command)
    state = repo.run(context.run_id)["state"]
    if state not in ("STARTED", "MCP_PENDING", "DATA_READY", "REPORT_PENDING"):
        print(json.dumps({"run_id": context.run_id, "state": state}))
        return 0
    if not args.model:
        raise ValueError("Для agent turn нужна закреплённая --model")
    provider = OpenRouterProvider(args.model, visible_budget_verified=args.verified_visible_budget)
    config = McpConfig(sys.executable, ("-m", "day18.rss_mcp_server", "--db", str(args.db)))
    agent = Agent(repo, provider, ToolRuntime(repo, config), None if context.no_send else dispatcher)
    print(json.dumps({"run_id": context.run_id, "state": agent.run(context)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
