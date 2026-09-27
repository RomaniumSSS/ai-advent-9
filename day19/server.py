"""Один локальный stdio MCP-сервер трёх инструментов Day 19."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .config import MAX_MODEL_SEEN, PROFILE
from .report import RELEVANT, ValidationIssue, render, validate
from .models import Draft
from .rss import fetch, parse
from .store import Store, compact, digest, now

HERE = Path(__file__).resolve().parent

def error(code: str) -> dict:
    return {"status": "error", "code": code}

class Operations:
    def __init__(self, store: Store, output: Path, fetcher: Callable[[], bytes]):
        self.store = store
        self.output = Path(output)
        self.fetcher = fetcher

    def collect(self, run_id: str, source_profile_id: str, period_start_utc: str,
                period_end_utc: str) -> dict:
        try:
            run = self.store.run(run_id)
            if (source_profile_id != PROFILE or period_start_utc != run["period_start_utc"]
                    or period_end_utc != run["period_end_utc"]):
                return error("context_mismatch")
            if run["state"] in ("data_ready", "preview_ready", "saved", "no_data"):
                return self._collect_result(run_id)
            if run["state"] != "created":
                return error("invalid_state")
            try:
                items, coverage, counts = parse(self.fetcher(), period_start_utc, period_end_utc)
            except Exception as exc:
                self.store.fail(run_id, "source_error")
                return error("source_error")
            batch_id = str(uuid.uuid4())
            read_at = now()
            with self.store.tx() as db:
                if db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()[0] != "created":
                    raise ValueError("invalid_state")
                current: list[dict] = []
                current_ids: set[str] = set()
                for item in items:
                    if item["article_id"] in current_ids:
                        continue
                    current_ids.add(item["article_id"])
                    row = db.execute("SELECT * FROM observations WHERE article_id=?",
                                     (item["article_id"],)).fetchone()
                    if row is None:
                        observation_id = str(uuid.uuid4())
                        db.execute("INSERT INTO observations(id,article_id,url,title,rss_excerpt,published_at_utc,first_batch_id) "
                                   "VALUES(?,?,?,?,?,?,?)",
                                   (observation_id, item["article_id"], item["url"], item["title"],
                                    item["rss_excerpt"], item["published_at_utc"], batch_id))
                        current.append({**item, "id": observation_id, "first_batch_id": batch_id, "handled": 0})
                    else:
                        observation_id = row["id"]
                db.execute("INSERT INTO batches(id,run_id,coverage_json,counts_json,source_status,read_at_utc) "
                           "VALUES(?,?,?,?,?,?)",
                           (batch_id, run_id, compact(coverage), compact(counts), "read", read_at))
                for item in items:
                    row = db.execute("SELECT id FROM observations WHERE article_id=?",
                                     (item["article_id"],)).fetchone()
                    db.execute("INSERT OR IGNORE INTO batch_members(batch_id,observation_id) VALUES(?,?)",
                               (batch_id, row["id"]))
                backlog = [dict(r) for r in db.execute(
                    "SELECT * FROM observations WHERE handled=0 AND first_batch_id<>? "
                    "ORDER BY published_at_utc DESC,article_id", (batch_id,))]
                # AICODE-NOTE: старые ID принадлежат текущему снимку через model_seen,
                # хотя first_batch_id остаётся исходным batch для provenance.
                new_count = min(15, len(current))
                backlog_count = min(5, len(backlog))
                remaining = MAX_MODEL_SEEN - new_count - backlog_count
                backlog_count += min(remaining, len(backlog) - backlog_count)
                remaining = MAX_MODEL_SEEN - new_count - backlog_count
                new_count += min(remaining, len(current) - new_count)
                selected = current[:new_count] + backlog[:backlog_count]
                total = len(current) + len(backlog)
                while selected and len(compact(selected).encode()) > run["visible_budget_bytes"]:
                    selected.pop()
                if total and not selected:
                    target, reason = "failed", "budget_exhausted"
                elif not selected and coverage["kind"] != "complete_for_profile":
                    target, reason = "failed", "source_incomplete"
                elif not selected:
                    target, reason = "no_data", None
                else:
                    target, reason = "data_ready", None
                for ordinal, row in enumerate(selected):
                    db.execute("INSERT INTO model_seen(batch_id,ordinal,observation_id) VALUES(?,?,?)",
                               (batch_id, ordinal, row["id"]))
                db.execute("UPDATE runs SET batch_id=? WHERE id=?", (batch_id, run_id))
                self.store.transition(db, run_id, "created", target, reason)
                counts.update({"new_observations": len(current), "backlog_candidates": len(backlog),
                               "eligible_candidates": total, "omitted_candidates": total - len(selected)})
                db.execute("UPDATE batches SET counts_json=?,source_status=? WHERE id=?",
                           (compact(counts), target, batch_id))
            return self._collect_result(run_id)
        except (ValueError, sqlite3.Error):
            return error("invalid_request_or_storage")

    def _collect_result(self, run_id: str) -> dict:
        run = self.store.run(run_id)
        with self.store.connect() as db:
            batch = db.execute("SELECT * FROM batches WHERE id=?", (run["batch_id"],)).fetchone()
            if not batch:
                return error("unknown_batch")
        rows = self.store.snapshot(batch["id"])
        return {"status": batch["source_status"], "run_id": run_id, "batch_id": batch["id"],
                "source_profile_id": PROFILE, "read_at_utc": batch["read_at_utc"],
                "coverage": json.loads(batch["coverage_json"]), "counts": json.loads(batch["counts_json"]),
                "reason_code": run["failure_code"] or "none",
                "model_seen": [{"observation_id": r["id"], "first_batch_id": r["first_batch_id"],
                                "article_id": r["article_id"], "url": r["url"], "title": r["title"],
                                "rss_excerpt": r["rss_excerpt"], "published_at_utc": r["published_at_utc"]}
                               for r in rows]}

    def prepare(self, run_id: str, batch_id: str, draft: dict) -> dict:
        try:
            run = self.store.run(run_id)
            if run["batch_id"] != batch_id:
                return error("batch_mismatch")
            if run["state"] in ("preview_ready", "saved"):
                with self.store.connect() as db:
                    preview = db.execute("SELECT * FROM previews WHERE run_id=?", (run_id,)).fetchone()
                if preview and json.loads(preview["draft_json"]) == draft:
                    return self._preview_result(preview)
                return error("preview_already_exists")
            if run["state"] != "data_ready":
                return error("invalid_state")
            with self.store.connect() as db:
                batch = db.execute("SELECT * FROM batches WHERE id=? AND run_id=?", (batch_id,run_id)).fetchone()
            if batch is None:
                return error("batch_mismatch")
            rows = self.store.snapshot(batch_id)
            coverage = json.loads(batch["coverage_json"])
            counts = json.loads(batch["counts_json"])
            validate(draft, run_id, rows, coverage, counts["eligible_candidates"])
            for row in rows:
                row["current_batch_id"] = batch_id
            payload, displayed, urls = render(draft, rows, coverage, counts["eligible_candidates"],
                                              run["period_end_utc"][:10])
            preview_id = str(uuid.uuid4())
            with self.store.tx() as db:
                db.execute("INSERT INTO previews(id,run_id,batch_id,payload,sha256,draft_json,displayed_json,created_utc) "
                           "VALUES(?,?,?,?,?,?,?,?)",
                           (preview_id,run_id,batch_id,payload,digest(payload),compact(draft),compact(displayed),now()))
                db.execute("UPDATE runs SET preview_id=? WHERE id=?", (preview_id,run_id))
                self.store.transition(db,run_id,"data_ready","preview_ready")
            with self.store.connect() as db:
                preview = db.execute("SELECT * FROM previews WHERE id=?", (preview_id,)).fetchone()
            return self._preview_result(preview)
        except ValidationIssue as exc:
            return {**error(str(exc)),"observation_id":exc.observation_id}
        except ValueError as exc:
            return error(str(exc))
        except Exception:
            return error("processing_error")

    @staticmethod
    def _preview_result(preview: sqlite3.Row) -> dict:
        return {"status": "preview_ready", "preview_id": preview["id"],
                "sha256": preview["sha256"], "source_urls": [line for line in preview["payload"].splitlines()
                    if line.startswith("https://habr.com/ru/articles/")],
                "summary": "Проверенный draft обработан; текст отчёта готов к сохранению."}

    def save(self, run_id: str, preview_id: str, sha256: str) -> dict:
        try:
            run = self.store.run(run_id)
            if run["preview_id"] != preview_id:
                return error("preview_mismatch")
            if run["state"] not in ("preview_ready", "saved"):
                return error("invalid_state")
            with self.store.connect() as db:
                preview = db.execute("SELECT * FROM previews WHERE id=? AND run_id=?", (preview_id,run_id)).fetchone()
            if not preview or sha256 != preview["sha256"]:
                return error("hash_mismatch")
            path = self._safe_path(run_id)
            payload = preview["payload"].encode("utf-8")
            if path.exists():
                if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
                    return error("existing_file_mismatch")
            else:
                fd, tmp = tempfile.mkstemp(prefix=".day19-", suffix=".tmp", dir=self.output)
                try:
                    with os.fdopen(fd,"wb") as stream:
                        stream.write(payload)
                        stream.flush()
                        os.fsync(stream.fileno())
                    if path.exists() or path.is_symlink():
                        return error("write_race")
                    os.replace(tmp,path)
                    dir_fd = os.open(self.output,os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
                return error("file_hash_mismatch")
            if run["state"] == "preview_ready":
                with self.store.tx() as db:
                    displayed = set(json.loads(preview["displayed_json"]))
                    draft = json.loads(preview["draft_json"])
                    for entry in draft["entries"]:
                        if entry["category"] not in RELEVANT or entry["observation_id"] in displayed:
                            db.execute("UPDATE observations SET handled=1 WHERE id=?", (entry["observation_id"],))
                    db.execute("UPDATE runs SET report_path=? WHERE id=?", (str(path),run_id))
                    self.store.transition(db,run_id,"preview_ready","saved")
            return {"status": "saved", "path": str(path.relative_to(HERE)) if path.is_relative_to(HERE) else str(path),
                    "sha256": sha256}
        except ValueError as exc:
            return error(str(exc))
        except OSError:
            return error("write_refused")
        except Exception:
            return error("storage_error")

    def _safe_path(self, run_id: str) -> Path:
        uuid.UUID(run_id)
        if self.output.is_symlink():
            raise OSError("output_symlink")
        self.output.mkdir(parents=True,exist_ok=True)
        if self.output.is_symlink():
            raise OSError("output_symlink")
        path = self.output / f"report-{run_id}.txt"
        if path.is_symlink() or path.parent.resolve() != self.output.resolve():
            raise OSError("unsafe_path")
        return path

def build_server(db_path: Path, output: Path, fetcher: Callable[[], bytes]) -> MCPServer:
    operations = Operations(Store(db_path), output, fetcher)
    server = MCPServer("day19-habr-agent", title="Day 19 Habr agent",
                       instructions="Три инструмента: поиск RSS, проверка и preview, сохранение сервером.")
    @server.tool(description="Найти материалы фиксированного RSS Хабра и вернуть неизменяемый model_seen.",
                 annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True), structured_output=True)
    def collect_habr_agent_cases(run_id: str, source_profile_id: str, period_start_utc: str,
                                 period_end_utc: str) -> dict[str, Any]:
        return operations.collect(run_id,source_profile_id,period_start_utc,period_end_utc)
    @server.tool(description="Проверить draft для batch_id и создать сохранённый preview с sha256.",
                 annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True), structured_output=True)
    def prepare_report_preview(run_id: str, batch_id: str, draft: Draft) -> dict[str, Any]:
        return operations.prepare(run_id,batch_id,draft.model_dump())
    @server.tool(description="Сохранить preview по ID и sha256 в серверную папку Day 19.",
                 annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True), structured_output=True)
    def save_report(run_id: str, preview_id: str, sha256: str) -> dict[str, Any]:
        return operations.save(run_id,preview_id,sha256)
    return server

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=HERE / "output")
    parser.add_argument("--rss-file",type=Path)
    args = parser.parse_args()
    build_server(args.db,args.output,lambda: fetch(fixture=args.rss_file)).run("stdio")

if __name__ == "__main__":
    main()
