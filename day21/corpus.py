"""Локальный импорт и согласование корпуса Day21. Не обращается к сети."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
from html import escape as html_escape
import json
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any


CHAT_KEY = "ai-advent-9"
CHAT_TITLE = "AI Advent Challenge #9"
START_DATE = "2026-08-31"
PAGE_CHARS = 1800  # Заранее объявленная оценка: содержательные символы на странице A4.
PARSER_REVISION = 2
ASSIGNMENT_IDS = {
    1: 877, 2: 1160, 3: 1474, 4: 1642, 5: 1798, 6: 2113,
    7: 2256, 8: 2393, 9: 2575, 10: 2638, 11: 2789, 12: 2891,
    13: 2977, 14: 3150, 15: 3282, 16: 3550, 17: 3652, 18: 3697,
    19: 3846, 20: 3917, 21: 4082, 22: 4154, 23: 4260, 24: 4362,
}
ASSIGNMENT_BY_ID = {v: k for k, v in ASSIGNMENT_IDS.items()}
DAY_PATTERN = re.compile(r"(?i)\bдень\s*№?\s*(\d{1,3})\b")
REPLY_PATTERN = re.compile(r"#go_to_message(\d+)$")
TECH_PATTERN = re.compile(r"(?i)\b(?:api|mcp|llm|rag|агент\w*|модел\w*|контекст\w*|эмбеддинг\w*|токен\w*|промпт\w*|инструмент\w*|памят\w*|запрос\w*)\b")


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    line: int
    children: list[Node | str] = field(default_factory=list)

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())


def walk(node: Node):
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from walk(child)


def direct_class(node: Node | None, name: str) -> Node | None:
    if node is None:
        return None
    return next((child for child in node.children if isinstance(child, Node) and name in child.classes), None)


def render(node: Node | str, omit_classes: set[str] | None = None) -> str:
    if isinstance(node, str):
        return node
    if omit_classes and node.classes & omit_classes:
        return ""
    if node.tag == "br":
        return "\n"
    body = "".join(render(c, omit_classes) for c in node.children)
    if node.tag in {"p", "div", "blockquote", "pre", "li"}:
        return "\n" + body + "\n"
    return body


def clean_text(node: Node | None, omit_classes: set[str] | None = None) -> str:
    if node is None:
        return ""
    raw = render(node, omit_classes).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in raw.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class TelegramParser(HTMLParser):
    """Сохраняет только узлы отдельных сообщений, не весь HTML в памяти."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}

    def __init__(self, filename: str, last_author: str | None = None):
        super().__init__(convert_charrefs=True)
        self.filename = filename
        self.stack: list[Node] = []
        self.records: list[dict[str, Any]] = []
        self.last_author = last_author

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        if not self.stack:
            if tag != "div" or "message" not in data.get("class", "").split():
                return
        node = Node(tag, data, self.getpos()[0])
        if self.stack:
            self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.stack:
            self.stack[-1].children.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            return
        # Экспорт Telegram бывает HTML с необязательными закрывающими тегами.
        index = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i].tag == tag), None)
        if index is None:
            return
        root = self.stack[0]
        del self.stack[index:]
        if not self.stack:
            record = self._record(root)
            if record:
                self.records.append(record)

    def _record(self, root: Node) -> dict[str, Any] | None:
        match = re.fullmatch(r"message(\d+)", root.attrs.get("id", ""))
        if not match:
            return None  # Служебные сообщения с другим ID не становятся содержимым.
        message_id = int(match.group(1))
        body = direct_class(root, "body")
        author_node = direct_class(body, "from_name")
        if author_node is not None:
            author = clean_text(author_node)
            self.last_author = author or None
            author_context = "explicit"
        elif "joined" in root.classes and self.last_author:
            author = self.last_author
            author_context = "joined_inherited"
        else:
            author = None
            self.last_author = None
            author_context = "unknown"
        if "service" in root.classes:
            self.last_author = None
        date_node = direct_class(body, "date")
        raw_date = date_node.attrs.get("title", "") if date_node else ""
        try:
            date = datetime.strptime(raw_date, "%d.%m.%Y %H:%M:%S UTC%z").isoformat() if raw_date else None
        except ValueError as exc:
            raise ValueError(f"{self.filename}:{root.line}: неверная дата сообщения {message_id}") from exc
        if not date and "service" not in root.classes:
            raise ValueError(f"{self.filename}:{root.line}: дата сообщения {message_id} отсутствует")
        reply_id = self._reply_id(direct_class(body, "reply_to"))
        outer_text = direct_class(body, "text")
        forwarded = []
        text_nodes = [outer_text] if outer_text else []
        if body:
            for nested in body.children:
                if not isinstance(nested, Node) or not {"forwarded", "body"} <= nested.classes:
                    continue
                forwarded_name = direct_class(nested, "from_name")
                forwarded_date = direct_class(forwarded_name, "date")
                forwarded_text = direct_class(nested, "text")
                forwarded.append({
                    "author": clean_text(forwarded_name, {"date"}) or None,
                    "date": forwarded_date.attrs.get("title") if forwarded_date else None,
                    "reply_to": self._reply_id(direct_class(nested, "reply_to")),
                    "text": clean_text(forwarded_text),
                    "links": self._links(forwarded_text),
                })
                if forwarded_text:
                    text_nodes.append(forwarded_text)
        text = "\n\n".join(value for node in text_nodes if (value := clean_text(node)))
        links = [link for node in text_nodes for link in self._links(node)]
        return {
            "chat_key": CHAT_KEY,
            "message_id": message_id,
            "date": date,
            "author": author,
            "author_context": author_context,
            "reply_to": reply_id,
            "text": text,
            "links": links,
            "forwarded": forwarded,
            "source_file": self.filename,
            "source_line": root.line,
            "service": "service" in root.classes,
        }

    @staticmethod
    def _reply_id(node: Node | None) -> int | None:
        if node:
            for child in walk(node):
                found = REPLY_PATTERN.fullmatch(child.attrs.get("href", ""))
                if found:
                    return int(found.group(1))
        return None

    @staticmethod
    def _links(node: Node | None) -> list[dict[str, str]]:
        if node is None:
            return []
        return [{"label": clean_text(child), "href": child.attrs["href"]}
                for child in walk(node) if child.tag == "a" and child.attrs.get("href")]


class ChatHeaderParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.current = ""
        self.headers: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.depth:
            self.depth += 1
        elif tag == "div" and {"text", "bold"} <= set(dict(attrs).get("class", "").split()):
            self.depth = 1
            self.current = ""

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.current += data

    def handle_endtag(self, tag: str) -> None:
        if self.depth:
            self.depth -= 1
            if not self.depth:
                self.headers.append(self.current.strip())


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def content_digest(record: dict[str, Any]) -> str:
    if record.get("source_key", "").startswith("note:"):
        return digest({key: record.get(key) for key in ("source", "section", "text")})
    fields = {key: record.get(key) for key in ("date", "author", "reply_to", "text", "links", "service")}
    if record.get("forwarded"):
        fields["forwarded"] = record["forwarded"]
    return digest(fields)


def assignment_day(record: dict[str, Any]) -> int | None:
    if record.get("author") != "Mobile Developer Manager" or not record.get("text"):
        return None
    found = DAY_PATTERN.search(record["text"][:80])
    return int(found.group(1)) if found else None


def parse_export(source_dir: Path, filenames: list[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_records = []
    files = []
    if filenames is None:
        filenames = ["messages" + (str(index) if index > 1 else "") + ".html" for index in range(1, 6)]
    if not filenames or len(set(filenames)) != len(filenames) or any(Path(name).name != name for name in filenames):
        raise ValueError("список файлов снимка пуст, повторяется или содержит путь")
    last_author = None
    previous_part = None
    for filename in filenames:
        path = source_dir / filename
        raw = path.read_bytes()
        header = ChatHeaderParser()
        header.feed(raw.decode("utf-8-sig"))
        if header.headers != [CHAT_TITLE]:
            raise ValueError(f"{path.name}: заголовок выбранного чата не совпал")
        part_match = re.fullmatch(r"messages(\d*)\.html", filename)
        part = int(part_match.group(1)) if part_match and part_match.group(1) else (1 if part_match else None)
        if previous_part is None or part is None or part != previous_part + 1:
            last_author = None
        parser = TelegramParser(path.name, last_author)
        parser.feed(raw.decode("utf-8-sig"))
        parser.close()
        if parser.stack:
            raise ValueError(f"{path.name}: незакрытое сообщение")
        last_author = parser.last_author
        previous_part = part
        all_records.extend(parser.records)
        files.append({"name": path.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "observations": len(parser.records)})
    by_id: dict[int, dict[str, Any]] = {}
    for record in all_records:
        ident = record["message_id"]
        if ident in by_id and content_digest(by_id[ident]) != content_digest(record):
            raise ValueError(f"ID {ident}: разные версии внутри одного снимка")
        by_id.setdefault(ident, record)
    return list(by_id.values()), files


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    conn = sqlite3.connect(path)
    os.chmod(path, 0o600)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            snapshot_id TEXT PRIMARY KEY, sequence INTEGER UNIQUE NOT NULL,
            captured_at TEXT NOT NULL, files_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
            imported_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS observations (
            snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
            message_id INTEGER NOT NULL, version_hash TEXT NOT NULL,
            record_json TEXT NOT NULL, PRIMARY KEY(snapshot_id, message_id)
        );
        CREATE TABLE IF NOT EXISTS decisions (
            source_key TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('include','exclude','review')),
            reason TEXT NOT NULL, day INTEGER, decided_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS accepted (
            source_key TEXT PRIMARY KEY, version_hash TEXT NOT NULL,
            record_json TEXT NOT NULL, accepted_at TEXT NOT NULL, approval_ref TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS proposals (
            source_key TEXT NOT NULL, version_hash TEXT NOT NULL,
            record_json TEXT NOT NULL, snapshot_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','accepted')),
            PRIMARY KEY(source_key, version_hash)
        );
        CREATE TABLE IF NOT EXISTS note_versions (
            source_key TEXT NOT NULL, version_hash TEXT NOT NULL,
            record_json TEXT NOT NULL, first_seen TEXT NOT NULL,
            PRIMARY KEY(source_key, version_hash)
        );
        CREATE TABLE IF NOT EXISTS accepted_history (
            event_id INTEGER PRIMARY KEY, source_key TEXT NOT NULL,
            version_hash TEXT NOT NULL, record_json TEXT NOT NULL,
            accepted_at TEXT NOT NULL, approval_ref TEXT NOT NULL,
            superseded_at TEXT NOT NULL, next_version_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS legacy_observations (
            snapshot_id TEXT NOT NULL, message_id INTEGER NOT NULL,
            parser_revision INTEGER NOT NULL, version_hash TEXT NOT NULL,
            record_json TEXT NOT NULL, archived_at TEXT NOT NULL,
            PRIMARY KEY(snapshot_id, message_id, parser_revision)
        );
        CREATE TABLE IF NOT EXISTS parser_migrations (
            snapshot_id TEXT PRIMARY KEY, parser_revision INTEGER NOT NULL,
            migrated_at TEXT NOT NULL
        );
    """)
    # Старые базы содержали только текущую заметку и предложения. Сохраняем всё,
    # что ещё доступно, до переключения активной версии.
    with conn:
        conn.execute("""INSERT OR IGNORE INTO note_versions
            SELECT source_key,version_hash,record_json,accepted_at FROM accepted
            WHERE source_key LIKE 'note:%'""")
        conn.execute("""INSERT OR IGNORE INTO note_versions
            SELECT source_key,version_hash,record_json,datetime('now') FROM proposals
            WHERE source_key LIKE 'note:%'""")
    return conn


def latest_record(conn: sqlite3.Connection, source_key: str) -> tuple[str, dict[str, Any]]:
    if source_key.startswith("telegram:"):
        message_id = int(source_key.split(":", 1)[1])
        row = conn.execute("""SELECT o.version_hash, o.record_json FROM observations o
            JOIN snapshots s ON s.snapshot_id=o.snapshot_id
            WHERE o.message_id=? ORDER BY s.sequence DESC LIMIT 1""", (message_id,)).fetchone()
    else:
        row = conn.execute("SELECT version_hash, record_json FROM note_versions WHERE source_key=? ORDER BY first_seen DESC, rowid DESC LIMIT 1", (source_key,)).fetchone()
    if row is None:
        raise ValueError(f"нет записи: {source_key}")
    return row["version_hash"], json.loads(row["record_json"])


def import_snapshot(conn: sqlite3.Connection, source_dir: Path, snapshot_id: str, sequence: int, captured_at: str,
                    filenames: list[str] | None = None, fail_after: int | None = None) -> dict[str, int]:
    if not snapshot_id.strip() or sequence < 1:
        raise ValueError("нужны непустой ID и положительный порядок снимка")
    records, files = parse_export(source_dir, filenames)
    snapshot_hash = digest(files)
    previous = conn.execute("SELECT snapshot_hash, sequence, captured_at FROM snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    if previous:
        if tuple(previous) != (snapshot_hash, sequence, captured_at):
            raise ValueError("ID снимка уже занят другим содержимым/порядком")
        if not conn.execute("SELECT 1 FROM parser_migrations WHERE snapshot_id=? AND parser_revision=?", (snapshot_id, PARSER_REVISION)).fetchone():
            raise ValueError("старый снимок требует migrate-parser перед повторным импортом")
        return {"observations": len(records), "new": 0, "proposals": 0, "repeat": 1}
    maximum = conn.execute("SELECT MAX(sequence) FROM snapshots").fetchone()[0]
    if maximum is not None and sequence <= maximum:
        raise ValueError("порядок снимка должен быть больше предыдущего")
    now = datetime.now(timezone.utc).isoformat()
    new_count = proposals = 0
    with conn:
        conn.execute("INSERT INTO snapshots VALUES (?,?,?,?,?,?)", (snapshot_id, sequence, captured_at, json.dumps(files), snapshot_hash, now))
        conn.execute("INSERT INTO parser_migrations VALUES (?,?,?)", (snapshot_id, PARSER_REVISION, now))
        for processed, record in enumerate(records, 1):
            key = f"telegram:{record['message_id']}"
            day = assignment_day(record)
            if record["message_id"] in ASSIGNMENT_BY_ID and day != ASSIGNMENT_BY_ID[record["message_id"]]:
                raise ValueError(f"условие ID {record['message_id']} не совпало с инвентарём")
            record["source_type"] = "assignment" if day else ("service" if record["service"] else "discussion")
            version = content_digest(record)
            packed = json.dumps(record, ensure_ascii=False)
            conn.execute("INSERT INTO observations VALUES (?,?,?,?)", (snapshot_id, record["message_id"], version, packed))
            decision = conn.execute("SELECT 1 FROM decisions WHERE source_key=?", (key,)).fetchone()
            if decision is None:
                new_count += 1
                if day:
                    status, reason = "include", "Условие курса: заголовок в начале и проверенный автор"
                elif record["service"]:
                    status, reason = "exclude", "Служебное событие"
                elif not record["date"] or record["date"][:10] < START_DATE:
                    status, reason = "exclude", "До начала курса 31.08.2026"
                elif not record["text"]:
                    status, reason = "exclude", "Нет текстового содержимого"
                else:
                    status, reason = "review", "Техническая релевантность требует просмотра"
                conn.execute("INSERT INTO decisions VALUES (?,?,?,?,?)", (key, status, reason, day, now))
                if status == "include":
                    conn.execute("INSERT INTO accepted VALUES (?,?,?,?,?)", (key, version, packed, now, "SPEC S1: условия курса"))
            accepted = conn.execute("SELECT version_hash FROM accepted WHERE source_key=?", (key,)).fetchone()
            if accepted and accepted["version_hash"] != version:
                prior = conn.execute("SELECT status FROM proposals WHERE source_key=? AND version_hash=?", (key, version)).fetchone()
                conn.execute("""INSERT INTO proposals VALUES (?,?,?,?,?)
                    ON CONFLICT(source_key,version_hash) DO UPDATE SET
                    record_json=excluded.record_json,snapshot_id=excluded.snapshot_id,status='pending'""",
                    (key, version, packed, snapshot_id, "pending"))
                proposals += prior is None or prior["status"] != "pending"
            if fail_after == processed:
                raise RuntimeError("искусственный сбой импорта")
    return {"observations": len(records), "new": new_count, "proposals": proposals, "repeat": 0}


def migrate_parser(conn: sqlite3.Connection, source_dir: Path, snapshot_id: str) -> dict[str, int]:
    snapshot = conn.execute("SELECT files_json FROM snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    if snapshot is None:
        raise ValueError("снимок для миграции не найден")
    marker = conn.execute("SELECT parser_revision FROM parser_migrations WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    if marker:
        if marker["parser_revision"] != PARSER_REVISION:
            raise ValueError("неизвестная редакция парсера")
        return {"archived": 0, "changed_hash": 0, "proposals": 0, "repeat": 1}
    original_files = json.loads(snapshot["files_json"])
    records, current_files = parse_export(source_dir, [item["name"] for item in original_files])
    if [(item["name"], item["sha256"], item["bytes"]) for item in current_files] != [
        (item["name"], item["sha256"], item["bytes"]) for item in original_files
    ]:
        raise ValueError("байты исходного снимка изменились; миграция остановлена")
    old_rows = {row["message_id"]: row for row in conn.execute(
        "SELECT message_id,version_hash,record_json FROM observations WHERE snapshot_id=?", (snapshot_id,))}
    if set(old_rows) != {record["message_id"] for record in records}:
        raise ValueError("набор ID исходного снимка не совпал с базой")
    now = datetime.now(timezone.utc).isoformat()
    changed_hash = proposals = 0
    with conn:
        for record in records:
            ident = record["message_id"]
            old = old_rows[ident]
            day = assignment_day(record)
            record["source_type"] = "assignment" if day else ("service" if record["service"] else "discussion")
            version = content_digest(record)
            packed = json.dumps(record, ensure_ascii=False)
            conn.execute("INSERT INTO legacy_observations VALUES (?,?,?,?,?,?)",
                         (snapshot_id, ident, 1, old["version_hash"], old["record_json"], now))
            conn.execute("UPDATE observations SET version_hash=?,record_json=? WHERE snapshot_id=? AND message_id=?",
                         (version, packed, snapshot_id, ident))
            changed_hash += old["version_hash"] != version
            key = f"telegram:{ident}"
            active = conn.execute("SELECT version_hash FROM accepted WHERE source_key=?", (key,)).fetchone()
            if active and active["version_hash"] != version:
                before = conn.execute("SELECT status FROM proposals WHERE source_key=? AND version_hash=?", (key, version)).fetchone()
                conn.execute("""INSERT INTO proposals VALUES (?,?,?,?,?)
                    ON CONFLICT(source_key,version_hash) DO UPDATE SET
                    record_json=excluded.record_json,snapshot_id=excluded.snapshot_id,status='pending'""",
                    (key, version, packed, snapshot_id, "pending"))
                proposals += before is None or before["status"] != "pending"
        conn.execute("INSERT INTO parser_migrations VALUES (?,?,?)", (snapshot_id, PARSER_REVISION, now))
    return {"archived": len(records), "changed_hash": changed_hash, "proposals": proposals, "repeat": 0}


def decide(conn: sqlite3.Connection, source_key: str, status: str, reason: str, approval_ref: str, day: int | None = None) -> None:
    if status not in {"include", "exclude", "review"} or not reason.strip() or not approval_ref.strip():
        raise ValueError("нужны статус, причина и ссылка на решение")
    active = conn.execute("SELECT 1 FROM accepted WHERE source_key=?", (source_key,)).fetchone()
    if active and status != "include":
        raise ValueError("принятый текст нельзя исключить повторным отбором")
    version, record = latest_record(conn, source_key)
    if status == "include" and not record.get("text"):
        raise ValueError("пустую запись нельзя включить в корпус")
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        if not active and status == "include":
            conn.execute("INSERT INTO accepted VALUES (?,?,?,?,?)", (source_key, version, json.dumps(record, ensure_ascii=False), now, approval_ref))
        conn.execute("INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?)", (source_key, status, reason, day, now))


def accept_proposal(conn: sqlite3.Connection, source_key: str, version_hash: str, approval_ref: str) -> None:
    if not approval_ref.strip():
        raise ValueError("нужна ссылка на явное решение о замене")
    row = conn.execute("SELECT record_json FROM proposals WHERE source_key=? AND version_hash=? AND status='pending'", (source_key, version_hash)).fetchone()
    active = conn.execute("SELECT version_hash,record_json,accepted_at,approval_ref FROM accepted WHERE source_key=?", (source_key,)).fetchone()
    if row is None or active is None:
        raise ValueError("нет ожидающей замены принятого текста")
    if source_key.startswith("note:") and not conn.execute(
        "SELECT 1 FROM note_versions WHERE source_key=? AND version_hash=?", (source_key, version_hash)).fetchone():
        raise ValueError("версия заметки отсутствует в истории")
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("INSERT INTO accepted_history (source_key,version_hash,record_json,accepted_at,approval_ref,superseded_at,next_version_hash) VALUES (?,?,?,?,?,?,?)",
                     (source_key, active["version_hash"], active["record_json"], active["accepted_at"], active["approval_ref"], now, version_hash))
        conn.execute("UPDATE accepted SET version_hash=?, record_json=?, accepted_at=?, approval_ref=? WHERE source_key=?", (version_hash, row["record_json"], now, approval_ref, source_key))
        conn.execute("UPDATE proposals SET status='accepted' WHERE source_key=? AND version_hash=?", (source_key, version_hash))


def import_note(conn: sqlite3.Connection, path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    heading = "## Понимание и полезные поправки для практики"
    if source.count(heading) != 1:
        raise ValueError("раздел учебной заметки не найден однозначно")
    section = source.split(heading, 1)[1].split("\n## ", 1)[0].strip()
    if not section:
        raise ValueError("выбранный раздел заметки пуст")
    key = "note:mcp-study:understanding"
    record = {"source": "MCP-STUDY.md", "section": heading[3:], "text": section, "source_key": key}
    version = content_digest(record)
    current = conn.execute("SELECT version_hash FROM accepted WHERE source_key=?", (key,)).fetchone()
    now = datetime.now(timezone.utc).isoformat()
    if current is None:
        with conn:
            conn.execute("INSERT OR IGNORE INTO note_versions VALUES (?,?,?,?)", (key, version, json.dumps(record, ensure_ascii=False), now))
            conn.execute("INSERT INTO accepted VALUES (?,?,?,?,?)", (key, version, json.dumps(record, ensure_ascii=False), now, "SPEC S1: выбранный раздел"))
            conn.execute("INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?)", (key, "include", "Раздел выбран в SPEC S1", None, now))
        return "added"
    if current["version_hash"] == version:
        return "repeat"
    with conn:
        conn.execute("INSERT OR IGNORE INTO note_versions VALUES (?,?,?,?)", (key, version, json.dumps(record, ensure_ascii=False), now))
        conn.execute("""INSERT INTO proposals VALUES (?,?,?,?,?)
            ON CONFLICT(source_key,version_hash) DO UPDATE SET
            record_json=excluded.record_json,snapshot_id=excluded.snapshot_id,status='pending'""",
            (key, version, json.dumps(record, ensure_ascii=False), "local-note", "pending"))
    return "proposal"


def write_private(path: Path, value: Any) -> None:
    write_private_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_private_text(path: Path, value: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(value)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)
    os.chmod(path, 0o600)


def build_manifest(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("""SELECT d.source_key,d.status,d.reason,d.day,
        a.version_hash AS active_hash,a.record_json AS active_json,
        (SELECT o.version_hash FROM observations o JOIN snapshots s ON s.snapshot_id=o.snapshot_id
         WHERE d.source_key='telegram:' || o.message_id ORDER BY s.sequence DESC LIMIT 1) AS latest_hash,
        (SELECT o.record_json FROM observations o JOIN snapshots s ON s.snapshot_id=o.snapshot_id
         WHERE d.source_key='telegram:' || o.message_id ORDER BY s.sequence DESC LIMIT 1) AS latest_json
        FROM decisions d LEFT JOIN accepted a ON a.source_key=d.source_key ORDER BY d.source_key""").fetchall()
    result = []
    selected = {row["source_key"]: json.loads(row["active_json"] if row["status"] == "include" and row["active_json"] else row["latest_json"])
                for row in rows if row["active_json"] or row["latest_json"]}
    all_records = {int(key.split(":", 1)[1]): record for key, record in selected.items() if key.startswith("telegram:")}
    assignment_ids = {ident for ident, record in all_records.items() if assignment_day(record)}
    pending: dict[str, list[dict[str, Any]]] = {}
    for proposal in conn.execute("SELECT source_key,version_hash,record_json,snapshot_id FROM proposals WHERE status='pending' ORDER BY source_key,version_hash"):
        record = json.loads(proposal["record_json"])
        pending.setdefault(proposal["source_key"], []).append({
            "version_hash": proposal["version_hash"], "snapshot_id": proposal["snapshot_id"],
            "reply_to": record.get("reply_to"), "text_hash": hashlib.sha256(record.get("text", "").encode()).hexdigest(),
            "source_file": record.get("source_file"), "source_line": record.get("source_line"),
        })
    for row in rows:
        source = selected.get(row["source_key"])
        parent = source.get("reply_to") if source else None
        if parent is None:
            parent_state = "none"
        elif parent not in all_records:
            parent_state = "missing"
        elif not all_records[parent].get("text"):
            parent_state = "nontext"
        else:
            parent_state = "available"
        signals = []
        if source and row["status"] == "review":
            if parent in assignment_ids:
                signals.append("direct_reply_to_assignment")
            if TECH_PATTERN.search(source.get("text", "")):
                signals.append("technical_vocabulary")
            if parent is None:
                signals.append("without_reply")
        result.append({"source_key": row["source_key"], "status": row["status"], "reason": row["reason"],
                       "day": row["day"], "accepted_hash": row["active_hash"],
                       "selected_version_hash": row["active_hash"] if row["status"] == "include" else row["latest_hash"],
                       "latest_observed_hash": row["latest_hash"],
                       "text_hash": hashlib.sha256(source.get("text", "").encode()).hexdigest() if source else None,
                       "source_type": source.get("source_type") if source else None,
                       "pending_proposals": pending.get(row["source_key"], []),
                       "reply_to": parent, "parent_state": parent_state,
                       "candidate_signals": signals,
                       "has_text": bool(source and source.get("text")),
                       "source_file": source.get("source_file") if source else None,
                       "source_line": source.get("source_line") if source else None})
    return result


def inert_markdown(text: str) -> str:
    # Длина ограждения строго больше любого ряда backticks в сообщении.
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", text)), default=0))
    return f"{fence}text\n{text}\n{fence}"


def review_preview(conn: sqlite3.Connection, manifest: list[dict[str, Any]]) -> str:
    latest = {int(row[0]): json.loads(row[1]) for row in conn.execute("""SELECT o.message_id,o.record_json
        FROM observations o JOIN snapshots s ON s.snapshot_id=o.snapshot_id
        WHERE s.sequence=(SELECT MAX(s2.sequence) FROM observations o2 JOIN snapshots s2 ON s2.snapshot_id=o2.snapshot_id WHERE o2.message_id=o.message_id)""")}
    categories = {
        "Ответы непосредственно под условием — связь не доказывает техническую релевантность":
            [m for m in manifest if "direct_reply_to_assignment" in m["candidate_signals"]],
        "Технические сигналы без reply — нужны ручные привязка и оценка":
            [m for m in manifest if "technical_vocabulary" in m["candidate_signals"] and "without_reply" in m["candidate_signals"]],
        "Ответы с техническими сигналами в других ветках":
            [m for m in manifest if "technical_vocabulary" in m["candidate_signals"] and m["reply_to"] is not None and "direct_reply_to_assignment" not in m["candidate_signals"]],
        "Примеры исключённого текста до начала курса":
            [m for m in manifest if m["status"] == "exclude" and m["has_text"]],
    }
    lines = ["# Приватный preview отбора Day21", "", "Это выборка для просмотра, не проверка всего корпуса. Кандидаты не включены автоматически; решение по смыслу и спорным веткам принимает пользователь.", ""]
    for title, entries in categories.items():
        lines.extend(["## " + title, "", f"Всего в группе: {len(entries)}. Ниже первые 12 по ID для локального просмотра.", ""])
        for item in sorted(entries, key=lambda value: int(value["source_key"].split(":", 1)[1]))[:12]:
            ident = int(item["source_key"].split(":", 1)[1])
            record = latest[ident]
            safe_file = html_escape(str(record["source_file"]), quote=True)
            lines.extend([f"### ID {ident}; reply {record['reply_to'] or 'нет'}; {safe_file}:{record['source_line']}",
                          "", inert_markdown(record["text"]), ""])
    return "\n".join(lines)


def build_documents(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    accepted_rows = conn.execute("SELECT a.source_key,a.version_hash,a.record_json,d.day FROM accepted a JOIN decisions d ON d.source_key=a.source_key WHERE d.status='include'").fetchall()
    telegram = {}
    notes = []
    for row in accepted_rows:
        record = json.loads(row["record_json"])
        if row["source_key"].startswith("telegram:"):
            telegram[record["message_id"]] = (record, row["day"], row["version_hash"])
        else:
            notes.append({"document_id": "personal-note:understanding", "source": "personal_note", "title": record["section"], "day": None,
                          "text": record["text"], "members": [{"source_key": row["source_key"], "version_hash": row["version_hash"]}]})
    documents = []
    assignments = {ident for ident, (record, day, _) in telegram.items() if day is not None and record.get("source_type") == "assignment"}
    for ident in sorted(assignments):
        rec, day, version = telegram[ident]
        documents.append({"document_id": f"assignment:{day}", "source": "assignment", "title": f"Day {day}", "day": day,
                          "text": rec["text"], "members": [{"source_key": f"telegram:{ident}", "version_hash": version,
                          "source_file": rec["source_file"], "source_line": rec["source_line"], "author": rec["author"], "date": rec["date"], "reply_to": rec["reply_to"], "links": rec["links"]}]})
    # Корень условия не склеивает между собой независимые вопросы в комментариях.
    groups: dict[int, list[int]] = {}
    def branch(ident: int) -> int:
        seen = set()
        cur = ident
        while cur not in seen:
            seen.add(cur)
            parent = telegram[cur][0].get("reply_to")
            if parent in assignments or parent not in telegram:
                return cur
            cur = parent
        return ident
    for ident in telegram:
        if ident not in assignments:
            groups.setdefault(branch(ident), []).append(ident)
    for root, members in sorted(groups.items()):
        members.sort(key=lambda i: (telegram[i][0]["date"], i))
        parent = telegram[root][0].get("reply_to")
        day = telegram[root][1] or (telegram[parent][1] if parent in assignments else None)
        blocks = []
        refs = []
        for ident in members:
            rec, _, version = telegram[ident]
            if rec["text"]:
                blocks.append(rec["text"])
            reply = rec["reply_to"]
            refs.append({"source_key": f"telegram:{ident}", "version_hash": version,
                         "source_file": rec["source_file"], "source_line": rec["source_line"],
                         "author": rec["author"], "date": rec["date"], "reply_to": reply,
                         "reply_context": "none" if reply is None else ("accepted_assignment" if reply in assignments else ("accepted_discussion" if reply in telegram else "not_selected_or_missing")),
                         "links": rec["links"]})
        if blocks:
            documents.append({"document_id": f"discussion:{root}", "source": "discussion", "title": f"Обсуждение {root}", "day": day,
                              "assignment_link": parent if parent in assignments else None, "text": "\n\n".join(blocks), "members": refs})
    documents.extend(notes)
    chars = sum(len(doc["text"]) for doc in documents)
    report = {"method": "Сумма символов очищенного текста документов / 1800; A4, 12 pt, межстрочный 1.5 — предварительная оценка, не реальная пагинация",
              "chars_per_page": PAGE_CHARS, "documents": len(documents),
              "messages": sum(len(doc["members"]) for doc in documents if doc["source"] != "personal_note"),
              "characters": chars, "estimated_pages": round(chars / PAGE_CHARS, 2),
              "minimum_30_pages_obvious": chars >= 30 * PAGE_CHARS * 1.2,
              "minimum_30_pages_estimated": chars >= 30 * PAGE_CHARS,
              "pending_reviews": conn.execute("SELECT COUNT(*) FROM decisions WHERE status='review'").fetchone()[0],
              "pending_replacements": conn.execute("SELECT COUNT(*) FROM proposals WHERE status='pending'").fetchone()[0]}
    return documents, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(__file__).parent / "private" / "corpus.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("--source-dir", type=Path, required=True)
    imp.add_argument("--snapshot-id", required=True)
    imp.add_argument("--sequence", type=int, required=True)
    imp.add_argument("--captured-at", required=True)
    imp.add_argument("--file", action="append", dest="files", help="Явный список файлов для частичного нового снимка")
    migration = sub.add_parser("migrate-parser")
    migration.add_argument("--source-dir", type=Path, required=True)
    migration.add_argument("--snapshot-id", required=True)
    note = sub.add_parser("import-note")
    note.add_argument("--path", type=Path, required=True)
    decision = sub.add_parser("decide")
    decision.add_argument("source_key")
    decision.add_argument("status", choices=["include", "exclude", "review"])
    decision.add_argument("--reason", required=True)
    decision.add_argument("--approval-ref", required=True)
    decision.add_argument("--day", type=int)
    proposal = sub.add_parser("accept-proposal")
    proposal.add_argument("source_key")
    proposal.add_argument("version_hash")
    proposal.add_argument("--approval-ref", required=True)
    sub.add_parser("build")
    args = parser.parse_args()
    os.umask(0o077)
    conn = connect(args.db)
    try:
        if args.command == "import":
            datetime.fromisoformat(args.captured_at)
            print(json.dumps(import_snapshot(conn, args.source_dir, args.snapshot_id, args.sequence, args.captured_at, args.files)))
        elif args.command == "migrate-parser":
            print(json.dumps(migrate_parser(conn, args.source_dir, args.snapshot_id)))
        elif args.command == "import-note":
            print(import_note(conn, args.path))
        elif args.command == "decide":
            decide(conn, args.source_key, args.status, args.reason, args.approval_ref, args.day)
            print("ok")
        elif args.command == "accept-proposal":
            accept_proposal(conn, args.source_key, args.version_hash, args.approval_ref)
            print("ok")
        elif args.command == "build":
            documents, report = build_documents(conn)
            manifest = build_manifest(conn)
            write_private(args.db.parent / "selection-manifest.json", manifest)
            write_private(args.db.parent / "corpus-documents.json", documents)
            write_private(args.db.parent / "corpus-volume.json", report)
            write_private_text(args.db.parent / "review-preview.md", review_preview(conn, manifest))
            print(json.dumps(report, ensure_ascii=False))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
