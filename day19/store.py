"""Собственная SQLite Day 19: batch и model_seen сохраняются до вызова модели."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import PROFILE

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, state TEXT NOT NULL, profile TEXT NOT NULL,
 period_start_utc TEXT NOT NULL, period_end_utc TEXT NOT NULL,
 created_utc TEXT NOT NULL, failure_code TEXT, visible_budget_bytes INTEGER NOT NULL,
 batch_id TEXT, preview_id TEXT, report_path TEXT);
CREATE TABLE IF NOT EXISTS transitions(
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, prior TEXT, target TEXT NOT NULL,
 reason TEXT, at_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations(
 id TEXT PRIMARY KEY, article_id TEXT NOT NULL UNIQUE, url TEXT NOT NULL,
 title TEXT NOT NULL, rss_excerpt TEXT NOT NULL, published_at_utc TEXT,
 first_batch_id TEXT NOT NULL, handled INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS batches(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, coverage_json TEXT NOT NULL,
 counts_json TEXT NOT NULL, source_status TEXT NOT NULL, read_at_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS batch_members(
 batch_id TEXT NOT NULL, observation_id TEXT NOT NULL,
 PRIMARY KEY(batch_id,observation_id));
CREATE TABLE IF NOT EXISTS model_seen(
 batch_id TEXT NOT NULL, ordinal INTEGER NOT NULL, observation_id TEXT NOT NULL,
 PRIMARY KEY(batch_id,ordinal), UNIQUE(batch_id,observation_id));
CREATE TABLE IF NOT EXISTS previews(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, batch_id TEXT NOT NULL,
 payload TEXT NOT NULL, sha256 TEXT NOT NULL, draft_json TEXT NOT NULL,
 displayed_json TEXT NOT NULL, created_utc TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS immutable_seen_update BEFORE UPDATE ON model_seen
BEGIN SELECT RAISE(ABORT,'immutable model_seen'); END;
CREATE TRIGGER IF NOT EXISTS immutable_seen_delete BEFORE DELETE ON model_seen
BEGIN SELECT RAISE(ABORT,'immutable model_seen'); END;
CREATE TRIGGER IF NOT EXISTS immutable_member_update BEFORE UPDATE ON batch_members
BEGIN SELECT RAISE(ABORT,'immutable batch membership'); END;
CREATE TRIGGER IF NOT EXISTS immutable_member_delete BEFORE DELETE ON batch_members
BEGIN SELECT RAISE(ABORT,'immutable batch membership'); END;
CREATE TRIGGER IF NOT EXISTS immutable_observation_source BEFORE UPDATE OF article_id,url,title,rss_excerpt,published_at_utc,first_batch_id ON observations
BEGIN SELECT RAISE(ABORT,'immutable RSS observation'); END;
CREATE TRIGGER IF NOT EXISTS immutable_batch_update BEFORE UPDATE ON batches
WHEN OLD.source_status <> 'read'
BEGIN SELECT RAISE(ABORT,'immutable committed batch'); END;
CREATE TRIGGER IF NOT EXISTS immutable_batch_delete BEFORE DELETE ON batches
BEGIN SELECT RAISE(ABORT,'immutable committed batch'); END;
"""

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

class _ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type,exc_value,traceback)
        finally:
            self.close()

class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)
            if "visible_budget_bytes" not in {row[1] for row in db.execute("PRAGMA table_info(runs)")}:
                db.execute("ALTER TABLE runs ADD COLUMN visible_budget_bytes INTEGER NOT NULL DEFAULT 16384")

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10, factory=_ManagedConnection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def create_run(self, start: str, end: str, *, visible_budget_bytes: int = 16 * 1024) -> str:
        if visible_budget_bytes <= 0 or visible_budget_bytes > 16 * 1024:
            raise ValueError("invalid_visible_budget")
        try:
            begin = datetime.strptime(start,"%Y-%m-%dT%H:%M:%SZ")
            finish = datetime.strptime(end,"%Y-%m-%dT%H:%M:%SZ")
        except (TypeError,ValueError) as exc:
            raise ValueError("invalid_utc_window") from exc
        if (begin.strftime("%Y-%m-%dT%H:%M:%SZ") != start or
                finish.strftime("%Y-%m-%dT%H:%M:%SZ") != end or begin >= finish):
            raise ValueError("invalid_utc_window")
        run_id = str(uuid.uuid4())
        with self.tx() as db:
            db.execute("INSERT INTO runs(id,state,profile,period_start_utc,period_end_utc,created_utc,visible_budget_bytes) VALUES(?,?,?,?,?,?,?)",
                       (run_id, "created", PROFILE, start, end, now(), visible_budget_bytes))
            db.execute("INSERT INTO transitions(run_id,prior,target,at_utc) VALUES(?,?,?,?)",
                       (run_id, None, "created", now()))
        return run_id

    def run(self, run_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise ValueError("unknown_run")
            return dict(row)

    @staticmethod
    def transition(db: sqlite3.Connection, run_id: str, prior: str, target: str, reason: str | None = None) -> None:
        changed = db.execute("UPDATE runs SET state=?,failure_code=? WHERE id=? AND state=?",
                             (target, reason if target == "failed" else None, run_id, prior)).rowcount
        if changed != 1:
            raise ValueError("invalid_state")
        db.execute("INSERT INTO transitions(run_id,prior,target,reason,at_utc) VALUES(?,?,?,?,?)",
                   (run_id, prior, target, reason, now()))

    def fail(self, run_id: str, reason: str) -> None:
        with self.tx() as db:
            row = db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
            if row and row[0] not in ("saved", "no_data", "failed"):
                self.transition(db, run_id, row[0], "failed", reason)

    def snapshot(self, batch_id: str) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT o.*,s.ordinal FROM model_seen s JOIN observations o ON o.id=s.observation_id "
                "WHERE s.batch_id=? ORDER BY s.ordinal", (batch_id,))]
