"""SQLite, миграция и guarded FSM одного выпуска."""

from __future__ import annotations

import sqlite3
import os
import hashlib
import fcntl
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1
EDGES = {
    "STARTED": {"MCP_PENDING", "FAILED_BEFORE_DATA"},
    "MCP_PENDING": {"DATA_READY", "FAILED_BEFORE_DATA"},
    "DATA_READY": {"REPORT_PENDING", "FAILED_AFTER_DATA"},
    "REPORT_PENDING": {"REPORT_READY", "FAILED_AFTER_DATA"},
    "REPORT_READY": {"SENDING", "FAILED_BEFORE_SEND"},
    "SENDING": {"DELIVERED", "DELIVERY_FAILED", "DELIVERY_UNKNOWN", "FAILED_BEFORE_SEND"},
    "FAILED_BEFORE_DATA": {"MCP_PENDING"},
    "FAILED_AFTER_DATA": {"REPORT_PENDING"},
    "FAILED_BEFORE_SEND": {"REPORT_READY"},
    "DELIVERY_FAILED": {"REPORT_READY"},
    "DELIVERY_UNKNOWN": {"DELIVERED", "DELIVERY_FAILED"},
    "DELIVERED": set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


DDL = """
CREATE TABLE IF NOT EXISTS schema_meta(version INTEGER PRIMARY KEY CHECK(version=1));
CREATE TABLE IF NOT EXISTS slots(
 id INTEGER PRIMARY KEY, profile TEXT NOT NULL, local_date TEXT NOT NULL, zone TEXT NOT NULL,
 instant_utc TEXT NOT NULL, period_start_utc TEXT NOT NULL, period_end_utc TEXT NOT NULL,
 UNIQUE(profile,local_date,zone));
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, slot_id INTEGER REFERENCES slots(id), origin TEXT NOT NULL,
 manual_invocation_id TEXT UNIQUE, no_send INTEGER NOT NULL CHECK(no_send IN (0,1)),
 context_json TEXT NOT NULL,
 state TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0, stage TEXT, reason_code TEXT,
 generation_attempt INTEGER NOT NULL DEFAULT 1 CHECK(generation_attempt BETWEEN 1 AND 2),
 model_calls INTEGER NOT NULL DEFAULT 0 CHECK(model_calls BETWEEN 0 AND 4),
 mcp_executions INTEGER NOT NULL DEFAULT 0 CHECK(mcp_executions BETWEEN 0 AND 2),
 active_ms INTEGER NOT NULL DEFAULT 0, attempt_active_ms INTEGER NOT NULL DEFAULT 0,
 lease_owner TEXT, lease_until_utc TEXT, created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL,
 CHECK((origin='scheduled' AND slot_id IS NOT NULL AND manual_invocation_id IS NULL AND no_send=0)
    OR (origin='manual' AND slot_id IS NULL AND manual_invocation_id IS NOT NULL AND no_send=1)));
CREATE UNIQUE INDEX IF NOT EXISTS one_scheduled_run ON runs(slot_id) WHERE origin='scheduled';
CREATE TABLE IF NOT EXISTS transitions(
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), old_state TEXT NOT NULL,
 new_state TEXT NOT NULL, at_utc TEXT NOT NULL, stage TEXT, reason_code TEXT,
 evidence_ref TEXT, version INTEGER NOT NULL, UNIQUE(run_id,version));
CREATE TABLE IF NOT EXISTS phase_reservations(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), phase TEXT NOT NULL,
 attempt INTEGER NOT NULL, reserved_ms INTEGER NOT NULL, started_utc TEXT NOT NULL,
 settled_ms INTEGER, ended_utc TEXT, CHECK(reserved_ms>0));
CREATE TABLE IF NOT EXISTS model_attempts(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), generation_attempt INTEGER NOT NULL,
 call_sequence INTEGER NOT NULL, outcome TEXT NOT NULL, reason_code TEXT, usage_json TEXT,
 started_utc TEXT NOT NULL, ended_utc TEXT, UNIQUE(run_id,call_sequence));
CREATE TABLE IF NOT EXISTS tool_attempts(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), call_sequence INTEGER NOT NULL,
 request_ordinal INTEGER NOT NULL, raw_call_id TEXT, audit_call_id TEXT NOT NULL,
 tool_name TEXT NOT NULL, arguments_digest TEXT, result_json TEXT NOT NULL,
 outcome TEXT NOT NULL, reason_code TEXT NOT NULL, at_utc TEXT NOT NULL,
 UNIQUE(run_id,call_sequence,request_ordinal));
CREATE TABLE IF NOT EXISTS articles(
 id INTEGER PRIMARY KEY, profile TEXT NOT NULL, canonical_id TEXT NOT NULL, canonical_url TEXT NOT NULL,
 first_seen_utc TEXT NOT NULL, latest_seen_utc TEXT NOT NULL, latest_rss_hash TEXT NOT NULL,
 UNIQUE(profile,canonical_id));
CREATE TABLE IF NOT EXISTS batches(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), idempotency_key TEXT NOT NULL,
 tool_call_id TEXT NOT NULL, period_start_utc TEXT NOT NULL, period_end_utc TEXT NOT NULL,
 read_at_utc TEXT NOT NULL, coverage_json TEXT NOT NULL, counts_json TEXT NOT NULL,
 result_json TEXT NOT NULL, committed_utc TEXT NOT NULL, UNIQUE(run_id,idempotency_key));
CREATE TABLE IF NOT EXISTS observations(
 id TEXT PRIMARY KEY, article_id INTEGER NOT NULL UNIQUE REFERENCES articles(id),
 first_batch_id TEXT NOT NULL REFERENCES batches(id), title TEXT NOT NULL, rss_excerpt TEXT NOT NULL,
 original_pubdate TEXT, published_at_utc TEXT, seen_at_utc TEXT NOT NULL,
 evidence_hash TEXT NOT NULL, eligibility TEXT NOT NULL CHECK(eligibility IN ('eligible','out_of_profile')));
CREATE TABLE IF NOT EXISTS batch_members(
 batch_id TEXT NOT NULL REFERENCES batches(id), observation_id TEXT NOT NULL REFERENCES observations(id),
 ordinal INTEGER NOT NULL, PRIMARY KEY(batch_id,observation_id), UNIQUE(batch_id,ordinal));
CREATE TABLE IF NOT EXISTS source_rejections(
 id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id),
 feed_ordinal INTEGER NOT NULL, reason_code TEXT NOT NULL, evidence_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS classifications(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), observation_id TEXT NOT NULL REFERENCES observations(id),
 category TEXT NOT NULL, confidence TEXT NOT NULL, evidence_refs_json TEXT NOT NULL,
 metric_json TEXT, evidence_hash TEXT NOT NULL, disposition TEXT NOT NULL,
 UNIQUE(run_id,observation_id));
CREATE TABLE IF NOT EXISTS reports(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES runs(id), payload TEXT NOT NULL,
 payload_hash TEXT NOT NULL, period_start_utc TEXT NOT NULL, period_end_utc TEXT NOT NULL,
 coverage_json TEXT NOT NULL, pool_total INTEGER NOT NULL, model_seen INTEGER NOT NULL,
 analysis_omitted INTEGER NOT NULL, payload_displayed INTEGER NOT NULL CHECK(payload_displayed BETWEEN 0 AND 2),
 payload_omitted INTEGER NOT NULL, dispatch_active_ms INTEGER NOT NULL DEFAULT 0,
 retired INTEGER NOT NULL DEFAULT 0 CHECK(retired IN (0,1)),
 created_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_members(
 report_id TEXT NOT NULL REFERENCES reports(id), observation_id TEXT NOT NULL REFERENCES observations(id),
 category TEXT NOT NULL, displayed_in_payload INTEGER NOT NULL CHECK(displayed_in_payload IN (0,1)),
 PRIMARY KEY(report_id,observation_id));
CREATE TABLE IF NOT EXISTS claims(
 id INTEGER PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observations(id),
 report_id TEXT NOT NULL REFERENCES reports(id), state TEXT NOT NULL
 CHECK(state IN ('owned','delivered','quarantined','released')),
 changed_utc TEXT NOT NULL, evidence TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_claim ON claims(observation_id)
 WHERE state IN ('owned','delivered','quarantined');
CREATE TABLE IF NOT EXISTS claim_events(
 id INTEGER PRIMARY KEY, claim_id INTEGER NOT NULL REFERENCES claims(id),
 old_state TEXT, new_state TEXT NOT NULL, at_utc TEXT NOT NULL, evidence TEXT);
CREATE TABLE IF NOT EXISTS send_gate(
 id INTEGER PRIMARY KEY CHECK(id=1), report_id TEXT REFERENCES reports(id),
 owner TEXT, lease_until_utc TEXT);
CREATE TABLE IF NOT EXISTS publication_config(
 profile TEXT PRIMARY KEY, recipient_fingerprint TEXT NOT NULL, recorded_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS delivery_attempts(
 id TEXT PRIMARY KEY, report_id TEXT NOT NULL REFERENCES reports(id), attempt_no INTEGER NOT NULL
 CHECK(attempt_no BETWEEN 1 AND 2), recipient_fingerprint TEXT NOT NULL,
 payload_hash TEXT NOT NULL, started_utc TEXT NOT NULL, request_started_utc TEXT,
 ended_utc TEXT, reserved_ms INTEGER NOT NULL DEFAULT 15000, settled_ms INTEGER,
 api_status TEXT, message_id INTEGER, proof_class TEXT,
 reason_code TEXT, UNIQUE(report_id,attempt_no));
CREATE TABLE IF NOT EXISTS delivery_checkpoints(
 profile TEXT NOT NULL, recipient_fingerprint TEXT NOT NULL, slot_date TEXT,
 report_id TEXT REFERENCES reports(id), changed_utc TEXT NOT NULL,
 PRIMARY KEY(profile,recipient_fingerprint));
CREATE TABLE IF NOT EXISTS operator_resolutions(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), attempt_id TEXT REFERENCES delivery_attempts(id),
 actor TEXT NOT NULL, at_utc TEXT NOT NULL, reason TEXT NOT NULL, evidence TEXT NOT NULL,
 decision TEXT NOT NULL);
"""

TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS transitions_no_update BEFORE UPDATE ON transitions
BEGIN SELECT RAISE(ABORT,'append-only transitions'); END;
CREATE TRIGGER IF NOT EXISTS transitions_no_delete BEFORE DELETE ON transitions
BEGIN SELECT RAISE(ABORT,'append-only transitions'); END;
CREATE TRIGGER IF NOT EXISTS batch_immutable AFTER UPDATE ON batches WHEN OLD.result_json != '{}'
BEGIN SELECT RAISE(ABORT,'committed batch immutable'); END;
CREATE TRIGGER IF NOT EXISTS batch_no_delete BEFORE DELETE ON batches
BEGIN SELECT RAISE(ABORT,'committed batch immutable'); END;
CREATE TRIGGER IF NOT EXISTS observation_immutable BEFORE UPDATE ON observations
BEGIN SELECT RAISE(ABORT,'observation immutable'); END;
CREATE TRIGGER IF NOT EXISTS observation_no_delete BEFORE DELETE ON observations
BEGIN SELECT RAISE(ABORT,'observation immutable'); END;
CREATE TRIGGER IF NOT EXISTS report_members_immutable BEFORE UPDATE ON report_members
BEGIN SELECT RAISE(ABORT,'report membership immutable'); END;
CREATE TRIGGER IF NOT EXISTS report_members_no_delete BEFORE DELETE ON report_members
BEGIN SELECT RAISE(ABORT,'report membership immutable'); END;
CREATE TRIGGER IF NOT EXISTS report_payload_immutable BEFORE UPDATE OF payload,payload_hash,
 period_start_utc,period_end_utc,coverage_json,pool_total,model_seen,analysis_omitted,
 payload_displayed,payload_omitted,created_utc ON reports
BEGIN SELECT RAISE(ABORT,'report payload immutable'); END;
CREATE TRIGGER IF NOT EXISTS claim_insert_event AFTER INSERT ON claims
BEGIN INSERT INTO claim_events(claim_id,old_state,new_state,at_utc,evidence)
VALUES (NEW.id,NULL,NEW.state,NEW.changed_utc,NEW.evidence); END;
CREATE TRIGGER IF NOT EXISTS claim_update_event AFTER UPDATE OF state ON claims
WHEN OLD.state != NEW.state
BEGIN INSERT INTO claim_events(claim_id,old_state,new_state,at_utc,evidence)
VALUES (NEW.id,OLD.state,NEW.state,NEW.changed_utc,NEW.evidence); END;
CREATE TRIGGER IF NOT EXISTS claim_events_no_update BEFORE UPDATE ON claim_events
BEGIN SELECT RAISE(ABORT,'append-only claim history'); END;
CREATE TRIGGER IF NOT EXISTS claim_events_no_delete BEFORE DELETE ON claim_events
BEGIN SELECT RAISE(ABORT,'append-only claim history'); END;
CREATE TRIGGER IF NOT EXISTS operator_no_update BEFORE UPDATE ON operator_resolutions
BEGIN SELECT RAISE(ABORT,'append-only operator audit'); END;
CREATE TRIGGER IF NOT EXISTS operator_no_delete BEFORE DELETE ON operator_resolutions
BEGIN SELECT RAISE(ABORT,'append-only operator audit'); END;
"""


class _ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise PermissionError("SQLite path не должен быть symlink")
        if not self.path.exists():
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(descriptor)
        if self.path.stat().st_mode & 0o077:
            raise PermissionError("SQLite file должен быть доступен только владельцу")
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None, factory=_ManagedConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def migrate(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = self.path.with_name(self.path.name + ".init.lock")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            with self.connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                existing = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'").fetchone()
                if existing:
                    version = connection.execute("SELECT version FROM schema_meta").fetchone()
                    if not version or version[0] != SCHEMA_VERSION:
                        raise RuntimeError("Неизвестная версия SQLite schema; нужен backup и явная миграция")
                    connection.execute("INSERT OR IGNORE INTO send_gate(id) VALUES (1)")
                    connection.executescript(TRIGGERS)
                    return
                connection.executescript("BEGIN IMMEDIATE;\n" + DDL + TRIGGERS +
                                        "\nINSERT OR IGNORE INTO schema_meta(version) VALUES (1);"
                                        "\nINSERT OR IGNORE INTO send_gate(id) VALUES (1);\nCOMMIT;")
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def backup(self, target: Path) -> None:
        if target.exists():
            raise FileExistsError(target)
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        with self.connect() as source, sqlite3.connect(target) as dest:
            source.backup(dest)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


def transition(connection: sqlite3.Connection, run_id: str, target: str, *,
               stage: str | None = None, reason: str | None = None,
               evidence_ref: str | None = None) -> int:
    row = connection.execute("SELECT state,version FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None or target not in EDGES.get(row["state"], set()):
        raise ValueError("Недопустимый переход FSM")
    if target == "DATA_READY" and not connection.execute("SELECT 1 FROM batches WHERE run_id=?", (run_id,)).fetchone():
        raise ValueError("DATA_READY требует committed batch")
    report = connection.execute("SELECT id,payload,payload_hash,payload_displayed FROM reports WHERE run_id=?", (run_id,)).fetchone()
    if target == "REPORT_READY":
        if report is None or hashlib.sha256(report["payload"].encode()).hexdigest() != report["payload_hash"]:
            raise ValueError("REPORT_READY требует validated report")
        displayed = connection.execute("SELECT COUNT(*) FROM report_members WHERE report_id=? AND displayed_in_payload=1",
                                       (report["id"],)).fetchone()[0]
        if displayed != report["payload_displayed"]:
            raise ValueError("REPORT_READY требует согласованного membership")
        no_send = connection.execute("SELECT no_send FROM runs WHERE id=?", (run_id,)).fetchone()[0]
        if not no_send:
            without_claim = connection.execute(
                "SELECT 1 FROM report_members m WHERE m.report_id=? AND NOT EXISTS "
                "(SELECT 1 FROM claims c WHERE c.report_id=m.report_id AND c.observation_id=m.observation_id "
                "AND c.state IN ('owned','quarantined')) LIMIT 1", (report["id"],)
            ).fetchone()
            if without_claim:
                raise ValueError("REPORT_READY требует ownership claims")
    if target == "SENDING":
        attempt = (connection.execute(
            "SELECT id FROM delivery_attempts WHERE report_id=? AND payload_hash=? ORDER BY attempt_no DESC LIMIT 1",
            (report["id"], report["payload_hash"])
        ).fetchone() if report else None)
        gate = connection.execute("SELECT report_id,owner FROM send_gate WHERE id=1").fetchone()
        if attempt is None or gate["report_id"] != report["id"] or gate["owner"] != attempt["id"]:
            raise ValueError("SENDING требует persisted attempt и hash")
    latest = (connection.execute("SELECT * FROM delivery_attempts WHERE report_id=? ORDER BY attempt_no DESC LIMIT 1",
                                 (report["id"],)).fetchone() if report else None)
    if row["state"] == "SENDING" and target == "FAILED_BEFORE_SEND" and (latest is None or latest["request_started_utc"]):
        raise ValueError("FAILED_BEFORE_SEND требует proof до request boundary")
    if target == "DELIVERY_UNKNOWN" and (latest is None or not latest["request_started_utc"]):
        raise ValueError("DELIVERY_UNKNOWN требует request-start marker")
    if row["state"] == "SENDING" and target == "DELIVERY_FAILED" and (latest is None or latest["proof_class"] != "definitive_rejection"):
        raise ValueError("DELIVERY_FAILED требует definitive rejection")
    if row["state"] == "DELIVERY_UNKNOWN" and target == "DELIVERY_FAILED" and not connection.execute(
        "SELECT 1 FROM operator_resolutions WHERE run_id=? AND decision='negative'", (run_id,)
    ).fetchone():
        raise ValueError("DELIVERY_FAILED требует linked operator proof")
    if target == "DELIVERED":
        if report is None or latest is None or latest["message_id"] is None:
            raise ValueError("DELIVERED требует message_id")
    version = row["version"] + 1
    now = utc_now()
    changed = connection.execute(
        "UPDATE runs SET state=?,version=?,stage=?,reason_code=?,updated_utc=? WHERE id=? AND version=?",
        (target, version, stage, reason, now, run_id, row["version"]),
    ).rowcount
    if changed != 1:
        raise RuntimeError("Concurrent FSM transition")
    connection.execute(
        "INSERT INTO transitions(run_id,old_state,new_state,at_utc,stage,reason_code,evidence_ref,version) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, row["state"], target, now, stage, reason, evidence_ref, version),
    )
    return version
