"""Состояние Day 20 отдельно от SQLite предыдущих дней."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


SCHEMA = """
CREATE TABLE IF NOT EXISTS article_snapshots(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL, url TEXT NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, body_sha256 TEXT NOT NULL,
 links_json TEXT NOT NULL, read_at_utc TEXT NOT NULL, truncated INTEGER NOT NULL,
 next_index INTEGER NOT NULL DEFAULT 0, complete INTEGER NOT NULL DEFAULT 0,
 UNIQUE(run_id,url)
);
CREATE TABLE IF NOT EXISTS requests(
 id TEXT PRIMARY KEY, chat_id INTEGER, user_id INTEGER, origin_message_id INTEGER,
 parent_request_id TEXT, user_text TEXT NOT NULL, article_url TEXT,
 github_repo TEXT, link_basis TEXT NOT NULL DEFAULT 'unconfirmed',
 goal TEXT, candidates_json TEXT NOT NULL DEFAULT '[]',
 state TEXT NOT NULL, fullness TEXT, answer TEXT, trace_path TEXT,
 failure_code TEXT, created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incoming_updates(
 update_id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
 payload_json TEXT NOT NULL, request_id TEXT, processed INTEGER NOT NULL DEFAULT 0,
 received_utc TEXT NOT NULL, UNIQUE(chat_id,message_id)
);
CREATE TABLE IF NOT EXISTS ignored_updates(update_id INTEGER PRIMARY KEY, received_utc TEXT NOT NULL,
 reason TEXT NOT NULL DEFAULT 'unknown');
CREATE TABLE IF NOT EXISTS outbox(
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL, kind TEXT NOT NULL,
 chat_id INTEGER NOT NULL, text TEXT NOT NULL, status TEXT NOT NULL,
 message_id INTEGER, attempted_utc TEXT, created_utc TEXT NOT NULL,
 UNIQUE(request_id,kind,text)
);
CREATE INDEX IF NOT EXISTS outbox_message ON outbox(chat_id,message_id);
"""


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        with self.connect() as db:
            db.executescript(SCHEMA)
            columns = {row[1] for row in db.execute("PRAGMA table_info(requests)")}
            if "link_basis" not in columns:
                db.execute("ALTER TABLE requests ADD COLUMN link_basis TEXT NOT NULL DEFAULT 'unconfirmed'")
            ignored_columns = {row[1] for row in db.execute("PRAGMA table_info(ignored_updates)")}
            if "reason" not in ignored_columns:
                db.execute("ALTER TABLE ignored_updates ADD COLUMN reason TEXT NOT NULL DEFAULT 'unknown'")

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.rollback()
                raise
            else:
                db.commit()

    def save_article(self, run_id: str, url: str, title: str, body: str,
                     links: list[str], truncated: bool) -> dict:
        with self.tx() as db:
            prior = db.execute("SELECT * FROM article_snapshots WHERE run_id=? AND url=?",
                               (run_id, url)).fetchone()
            if prior:
                return dict(prior)
            record = {"id": str(uuid.uuid4()), "run_id": run_id, "url": url,
                      "title": title, "body": body, "body_sha256": digest(body),
                      "links_json": compact(links), "read_at_utc": now(),
                      "truncated": int(truncated)}
            db.execute("INSERT INTO article_snapshots(id,run_id,url,title,body,body_sha256,"
                       "links_json,read_at_utc,truncated) VALUES(:id,:run_id,:url,:title,:body,"
                       ":body_sha256,:links_json,:read_at_utc,:truncated)", record)
            return {**record, "next_index": 0, "complete": 0}

    def article(self, run_id: str, url: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM article_snapshots WHERE run_id=? AND url=?",
                             (run_id, url)).fetchone()
            return dict(row) if row else None

    def mark_chunk(self, run_id: str, url: str, index: int, total: int) -> bool:
        with self.tx() as db:
            row = db.execute("SELECT next_index,complete FROM article_snapshots "
                             "WHERE run_id=? AND url=?", (run_id, url)).fetchone()
            if row is None or index > row["next_index"]:
                raise ValueError("chunk_out_of_order")
            if index == row["next_index"]:
                db.execute("UPDATE article_snapshots SET next_index=?,complete=? "
                           "WHERE run_id=? AND url=?",
                           (index + 1, int(index + 1 == total), run_id, url))
            current = db.execute("SELECT complete,truncated FROM article_snapshots "
                                 "WHERE run_id=? AND url=?", (run_id, url)).fetchone()
            return bool(current["complete"] and not current["truncated"])

    def create_request(self, text: str, *, chat_id: int | None = None,
                       user_id: int | None = None, origin_message_id: int | None = None,
                       parent_request_id: str | None = None, article_url: str | None = None,
                       github_repo: str | None = None, link_basis: str = "unconfirmed",
                       goal: str | None = None, candidates: list[str] | None = None) -> str:
        ident = str(uuid.uuid4())
        stamp = now()
        with self.tx() as db:
            db.execute("INSERT INTO requests(id,chat_id,user_id,origin_message_id,"
                       "parent_request_id,user_text,article_url,github_repo,link_basis,goal,candidates_json,state,"
                       "created_utc,updated_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (ident,chat_id,user_id,origin_message_id,parent_request_id,text,
                        article_url,github_repo,link_basis,goal,compact(candidates or []),"received",stamp,stamp))
        return ident

    def request(self, ident: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (ident,)).fetchone()
            if row is None:
                raise KeyError(ident)
            return dict(row)

    def update_request(self, ident: str, prior: tuple[str, ...], state: str,
                       **changes: object) -> None:
        allowed = {"article_url","github_repo","goal","candidates_json","fullness",
                   "answer","trace_path","failure_code","link_basis"}
        if set(changes) - allowed:
            raise ValueError("request_field_not_allowed")
        with self.tx() as db:
            row = db.execute("SELECT state FROM requests WHERE id=?", (ident,)).fetchone()
            if row is None or row["state"] not in prior:
                raise ValueError("request_state_mismatch")
            fields = {"state": state, "updated_utc": now(), **changes}
            assignments = ",".join(f"{key}=?" for key in fields)
            db.execute(f"UPDATE requests SET {assignments} WHERE id=?",
                       (*fields.values(),ident))
