#!/usr/bin/env python3
"""Локальный импорт и безопасная фиксация версий экспорта Telegram.

Тексты сохраняются только в day21/private. Скрипт печатает агрегаты и ошибки,
но не содержимое сообщений.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


CHAT_KEY = "ai-advent-9"
DEFAULT_EXPORT_DIR = Path(
    "/Users/ramanpazharytski/Downloads/Telegram Desktop/ChatExport_2026-10-01"
)
DEFAULT_SNAPSHOT_ID = "ChatExport_2026-10-01"
DEFAULT_SNAPSHOT_DATE = "2026-10-01"
DEFAULT_PERIOD_START = "2026-08-31"
DEFAULT_PARTS = ("messages.html", *(f"messages{i}.html" for i in range(2, 6)))
DEFAULT_PRIVATE_DIR = Path(__file__).resolve().parent / "private"
INVENTORY_PATH = DEFAULT_PRIVATE_DIR / "inventory.json"
NOTE_PATH = Path(__file__).resolve().parents[1] / "MCP-STUDY.md"
NOTE_HEADING = "Понимание и полезные поправки для практики"
EXPECTED_CHAT_TITLE = re.compile(r"AI\s+Advent\s+Challenge\s*#?\s*9\b", re.IGNORECASE)
SCHEMA_VERSION = 1

BLOCK_TAGS = {"blockquote", "div", "h1", "h2", "h3", "li", "p", "pre"}
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return sha256_bytes(stable_json(value))


def message_version_fields(version: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "author": version["author"],
        "author_inherited_from_message_id": version["author_inherited_from_message_id"],
        "author_provenance": version["author_provenance"],
        "date": version["date"],
        "reply_to": version["reply_to"],
        "reply_to_origin": version["reply_to_origin"],
        "text": version["text"],
    }
    if version.get("forwarded_reply_to") is not None:
        fields["forwarded_reply_to"] = version["forwarded_reply_to"]
        fields["forwarded_reply_to_origin"] = version["forwarded_reply_to_origin"]
    return fields


def normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    rows = [re.sub(r"[\t \u00a0]+", " ", row).strip() for row in value.split("\n")]
    value = "\n".join(rows)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    telegram = re.fullmatch(
        r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2}:\d{2})\s+UTC([+-]\d{2}:\d{2})",
        value,
    )
    if telegram:
        day, month, year, clock, offset = telegram.groups()
        return f"{year}-{month}-{day}T{clock}{offset}"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value


class TelegramPartParser(HTMLParser):
    """Извлекает только поля сообщения; тело не отправляется в stdout."""

    def __init__(self, filename: str):
        super().__init__(convert_charrefs=True)
        self.filename = filename
        self.stack: list[str] = []
        self.current: dict[str, Any] | None = None
        self.message_depth: int | None = None
        self.text_depth: int | None = None
        self.author_depth: int | None = None
        self.forwarded_depth: int | None = None
        self.reply_depth: int | None = None
        self.page_header_depth: int | None = None
        self.page_header_parts: list[str] = []
        self.anchor: dict[str, Any] | None = None
        self.records: list[dict[str, Any]] = []

    @property
    def chat_title(self) -> str:
        return normalize_text(" ".join(self.page_header_parts))

    def _start_message(self, attrs: dict[str, str | None]) -> None:
        ident = attrs.get("id") or ""
        match = re.fullmatch(r"message(\d+)", ident)
        if not match:
            raise ValueError(f"{self.filename}: message node has no numeric ID")
        self.current = {
            "message_id": match.group(1),
            "source_line": self.getpos()[0],
            "joined": "joined" in set((attrs.get("class") or "").split()),
            "author_parts": [],
            "author_captured": False,
            "date": None,
            "reply_to": None,
            "forwarded_reply_to": None,
            "reply_to_origin": None,
            "forwarded_reply_to_origin": None,
            "text_parts": [],
        }

    def handle_starttag(self, tag: str, raw_attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(raw_attrs)
        classes = set((attrs.get("class") or "").split())
        depth = len(self.stack) + 1

        if "page_header" in classes and self.current is None:
            self.page_header_depth = depth
        if self.current is None and {"message", "default"}.issubset(classes):
            self._start_message(attrs)
            self.message_depth = depth
        elif self.current is not None:
            if self.forwarded_depth is None and "date" in classes and "details" in classes:
                self.current["date"] = normalize_timestamp(attrs.get("title"))
            if "forwarded" in classes:
                self.forwarded_depth = depth
            if "from_name" in classes and self.forwarded_depth is None and not self.current["author_captured"]:
                self.author_depth = depth
                self.current["author_captured"] = True
            if "reply_to" in classes:
                self.reply_depth = depth
            if "text" in classes:
                self.text_depth = depth

            if self.text_depth is not None and tag in BLOCK_TAGS:
                if depth > self.text_depth:
                    self.current["text_parts"].append("\n")
            if self.text_depth is not None and tag == "br":
                self.current["text_parts"].append("\n")
            if self.reply_depth is not None and tag == "a":
                href = attrs.get("href") or ""
                parent = re.search(r"go_to_message(\d+)", href)
                if parent:
                    # AICODE-NOTE: reply исходного пересланного сообщения не создаёт связь с сообщением этой группы.
                    if self.forwarded_depth is None:
                        self.current["reply_to"] = parent.group(1)
                        self.current["reply_to_origin"] = "message_reply"
                    elif self.current["forwarded_reply_to"] is None:
                        self.current["forwarded_reply_to"] = parent.group(1)
                        self.current["forwarded_reply_to_origin"] = "forwarded_source_reply"
            if self.text_depth is not None and tag == "a":
                self.anchor = {"href": attrs.get("href") or "", "text": []}

        if tag not in VOID_TAGS:
            self.stack.append(tag)
        else:
            self._close_void_capture(tag, depth)

    def _close_void_capture(self, tag: str, depth: int) -> None:
        if tag == "br" and self.text_depth is not None and depth > self.text_depth:
            return

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.page_header_depth is not None and self.current is None:
            self.page_header_parts.append(data)
        if self.current is None:
            return
        if self.text_depth is not None:
            if self.anchor is not None:
                self.anchor["text"].append(data)
            else:
                self.current["text_parts"].append(data)
        if self.author_depth is not None:
            self.current["author_parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        depth = len(self.stack)
        if self.current is not None:
            if tag == "a" and self.anchor is not None:
                label = normalize_text("".join(self.anchor["text"]))
                href = str(self.anchor["href"]).strip()
                if label and href:
                    self.current["text_parts"].append(f"[{label}]({href})")
                elif label:
                    self.current["text_parts"].append(label)
                elif href:
                    self.current["text_parts"].append(href)
                self.anchor = None

            if self.text_depth == depth and tag in {"div", "span"}:
                self.text_depth = None
            elif self.text_depth is not None and tag in BLOCK_TAGS and depth > self.text_depth:
                self.current["text_parts"].append("\n")
            if self.author_depth == depth and tag in {"div", "span"}:
                self.author_depth = None
            if self.forwarded_depth == depth and tag in {"div", "span"}:
                self.forwarded_depth = None
            if self.reply_depth == depth and tag in {"div", "span"}:
                self.reply_depth = None
            if self.message_depth == depth and tag == "div":
                self._finish_message()

        if self.page_header_depth == depth:
            self.page_header_depth = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index] == tag:
                del self.stack[index:]
                break

    def _finish_message(self) -> None:
        assert self.current is not None
        row = {
            "message_id": self.current["message_id"],
            "joined": self.current["joined"],
            "author": normalize_text("".join(self.current["author_parts"])) or None,
            "date": self.current["date"],
            "reply_to": self.current["reply_to"],
            "forwarded_reply_to": self.current["forwarded_reply_to"],
            "reply_to_origin": self.current["reply_to_origin"],
            "forwarded_reply_to_origin": self.current["forwarded_reply_to_origin"],
            "text": normalize_text("".join(self.current["text_parts"])),
            "source_file": self.filename,
            "source_line": self.current["source_line"],
        }
        self.records.append(row)
        self.current = None
        self.message_depth = None
        self.text_depth = None
        self.author_depth = None
        self.forwarded_depth = None
        self.reply_depth = None
        self.anchor = None

    def finish(self) -> tuple[str, list[dict[str, Any]]]:
        self.close()
        if self.current is not None:
            raise ValueError(f"{self.filename}: unclosed message node")
        return self.chat_title, self.records


def parse_part(path: Path) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    payload = path.read_bytes()
    parser = TelegramPartParser(path.name)
    parser.feed(payload.decode("utf-8"))
    title, records = parser.finish()
    if not title or not EXPECTED_CHAT_TITLE.search(title):
        raise ValueError(f"{path.name}: exported chat title does not match the expected chat")
    ids = [row["message_id"] for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path.name}: duplicate message ID within source part")
    if any(row["date"] is None for row in records):
        raise ValueError(f"{path.name}: one or more messages have no timestamp")
    source = {
        "file": path.name,
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "message_count": len(records),
    }
    return title, records, source


def author_context_from_state(
    state: dict[str, Any] | None, message_id: str
) -> tuple[str, str | None] | None:
    if not state:
        return None
    target = int(message_id)
    candidates = [
        (int(key), record)
        for key, record in state.get("records", {}).items()
        if int(key) <= target
    ]
    for candidate_id, record in sorted(candidates, reverse=True, key=lambda pair: pair[0]):
        versions = record.get("versions", [])
        accepted_sha = record.get("accepted_version_sha256")
        version = next(
            (item for item in versions if item["version_sha256"] == accepted_sha),
            versions[-1] if versions else None,
        )
        if version and version.get("author"):
            inherited_from = version.get("author_inherited_from_message_id")
            return version["author"], inherited_from or str(candidate_id)
    return None


def prepare_snapshot(
    export_dir: Path,
    part_names: list[str],
    chat_key: str,
    snapshot_id: str,
    snapshot_date: str,
    existing_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    date.fromisoformat(snapshot_date)
    if not chat_key.strip() or not snapshot_id.strip():
        raise ValueError("chat key and snapshot ID must be non-empty")
    if len(part_names) != len(set(part_names)):
        raise ValueError("source part list contains duplicates")
    titles: set[str] = set()
    sources: list[dict[str, Any]] = []
    records_by_id: dict[str, dict[str, Any]] = {}
    previous_author: str | None = None
    previous_author_id: str | None = None
    for part_name in part_names:
        if Path(part_name).name != part_name:
            raise ValueError("source part names must be file names without directories")
        path = export_dir / part_name
        if not path.is_file():
            raise FileNotFoundError(f"missing export part: {part_name}")
        title, rows, source = parse_part(path)
        titles.add(title)
        sources.append(source)
        for row in rows:
            row = dict(row)
            joined = row.pop("joined")
            row["author_inherited_from_message_id"] = None
            row["author_provenance"] = "direct" if row["author"] is not None else "missing"
            # AICODE-NOTE: Telegram не повторяет from_name у .joined; автора наследуем только при этом явном маркере.
            if row["author"] is None and joined:
                if previous_author is not None:
                    row["author"] = previous_author
                    row["author_inherited_from_message_id"] = previous_author_id
                    row["author_provenance"] = "joined_previous_message"
                else:
                    context = author_context_from_state(existing_state, row["message_id"])
                    if context is not None:
                        row["author"], row["author_inherited_from_message_id"] = context
                        row["author_provenance"] = "prior_import_context"
            if row["author"] is not None:
                previous_author = row["author"]
                previous_author_id = row["message_id"]
            elif not joined:
                previous_author = None
                previous_author_id = None
            row["chat_key"] = chat_key
            row["snapshot_id"] = snapshot_id
            row["snapshot_date"] = snapshot_date
            version_fields = message_version_fields(row)
            row["content_sha256"] = sha256_bytes(row["text"].encode("utf-8"))
            row["version_sha256"] = sha256_json(version_fields)
            row["origin"] = {
                "snapshot_id": snapshot_id,
                "snapshot_date": snapshot_date,
                "source_file": row.pop("source_file"),
                "source_line": row.pop("source_line"),
                "source_sha256": source["sha256"],
            }
            prior = records_by_id.get(row["message_id"])
            if prior and prior["version_sha256"] != row["version_sha256"]:
                raise ValueError("the same message ID has conflicting versions in this import")
            if prior:
                if row["origin"] not in prior["origins"]:
                    prior["origins"].append(row["origin"])
            else:
                row["origins"] = [row.pop("origin")]
                records_by_id[row["message_id"]] = row
    if len(titles) != 1:
        raise ValueError("chat title differs between source parts")
    for row in records_by_id.values():
        row.pop("origin", None)
    source_fingerprint = sha256_json(
        {
            "chat_key": chat_key,
            "snapshot_id": snapshot_id,
            "snapshot_date": snapshot_date,
            "chat_title": next(iter(titles)),
            "parts": sources,
        }
    )
    snapshot_ref = f"{snapshot_id}:{source_fingerprint[:12]}"
    for row in records_by_id.values():
        for origin in row["origins"]:
            origin["snapshot_ref"] = snapshot_ref
    snapshot = {
        "snapshot_ref": snapshot_ref,
        "snapshot_id": snapshot_id,
        "snapshot_date": snapshot_date,
        "chat_key": chat_key,
        "chat_title": next(iter(titles)),
        "source_fingerprint": source_fingerprint,
        "parts": sources,
        "message_count": len(records_by_id),
    }
    return snapshot, list(records_by_id.values())


def empty_state(chat_key: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "chat_key": chat_key,
        "snapshots": {},
        "records": {},
    }


def migrate_legacy_forwarded_replies(
    state: dict[str, Any], manifest: dict[str, Any] | None
) -> tuple[dict[str, Any], dict[str, Any] | None, int]:
    """Separate old forwarded-source links from actual replies in preliminary state."""
    migrated = copy.deepcopy(state)
    migrated_manifest = copy.deepcopy(manifest)
    remapped: dict[tuple[str, str], tuple[str, str, str]] = {}
    for message_id, record in migrated["records"].items():
        for version in record["versions"]:
            if version.get("reply_to_origin") != "forwarded_source":
                continue
            old_sha = version["version_sha256"]
            if record.get("accepted_version_sha256") == old_sha:
                raise ValueError(
                    "accepted version contains a forwarded-source reply; manual review is required"
                )
            if migrated_manifest and migrated_manifest.get("decisions_are_final") is True:
                raise ValueError(
                    "final selection contains legacy forwarded-source reply semantics; manual review is required"
                )
            forwarded_reply = version.get("forwarded_reply_to") or version.get("reply_to")
            if forwarded_reply is None:
                raise ValueError("legacy forwarded-source reply has no target ID")
            version["reply_to"] = None
            version["reply_to_origin"] = None
            version["forwarded_reply_to"] = str(forwarded_reply)
            version["forwarded_reply_to_origin"] = "forwarded_source_reply"
            new_sha = sha256_json(message_version_fields(version))
            version["version_sha256"] = new_sha
            remapped[(message_id, old_sha)] = (
                new_sha,
                str(forwarded_reply),
                "forwarded_source_reply",
            )

    if migrated_manifest is not None:
        for row in migrated_manifest.get("telegram_decisions", []):
            mapped = remapped.get((str(row["message_id"]), row["version_sha256"]))
            if mapped is not None:
                row["version_sha256"], row["forwarded_reply_to"], row[
                    "forwarded_reply_to_origin"
                ] = mapped
                row["reply_to"] = None
    return migrated, migrated_manifest, len(remapped)


def merge_snapshot(
    state: dict[str, Any], snapshot: dict[str, Any], incoming: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, int]]:
    """Объединяет наблюдения, не удаляя старые и не меняя принятые версии."""
    merged = copy.deepcopy(state)
    if merged["chat_key"] != snapshot["chat_key"]:
        raise ValueError("chat key differs from imported state")
    snapshot_ref = snapshot["snapshot_ref"]
    old_snapshot = merged["snapshots"].get(snapshot_ref)
    if old_snapshot and old_snapshot != snapshot:
        raise ValueError("snapshot reference collision")
    merged["snapshots"][snapshot_ref] = snapshot
    stats = {"new_records": 0, "new_versions": 0, "same_versions": 0, "proposals": 0}
    for row in incoming:
        message_id = row["message_id"]
        record = merged["records"].get(message_id)
        if record is None:
            record = {
                "chat_key": row["chat_key"],
                "message_id": message_id,
                "accepted_version_sha256": None,
                "versions": [],
            }
            merged["records"][message_id] = record
            stats["new_records"] += 1
        existing = next(
            (version for version in record["versions"] if version["version_sha256"] == row["version_sha256"]),
            None,
        )
        origins = row["origins"]
        if existing is not None:
            for origin in origins:
                if origin not in existing["origins"]:
                    existing["origins"].append(origin)
            stats["same_versions"] += 1
            continue
        version = {
            "version_sha256": row["version_sha256"],
            "content_sha256": row["content_sha256"],
            "author": row["author"],
            "author_inherited_from_message_id": row["author_inherited_from_message_id"],
            "author_provenance": row["author_provenance"],
            "date": row["date"],
            "reply_to": row["reply_to"],
            "reply_to_origin": row["reply_to_origin"],
            "forwarded_reply_to": row["forwarded_reply_to"],
            "forwarded_reply_to_origin": row["forwarded_reply_to_origin"],
            "text": row["text"],
            "origins": origins,
            "version_status": "observed",
        }
        if record["accepted_version_sha256"] is not None:
            version["version_status"] = "proposed_replacement"
            stats["proposals"] += 1
        record["versions"].append(version)
        stats["new_versions"] += 1
    return merged, stats


def accept_replacement(
    state: dict[str, Any],
    message_id: str,
    version_sha256: str,
    explicitly_approved: bool,
) -> dict[str, Any]:
    """Принимает версию только после отдельного явного решения пользователя."""
    if not explicitly_approved:
        raise ValueError("replacement requires explicit approval")
    result = copy.deepcopy(state)
    record = result["records"][message_id]
    if not any(v["version_sha256"] == version_sha256 for v in record["versions"]):
        raise ValueError("replacement version is missing")
    record["accepted_version_sha256"] = version_sha256
    for version in record["versions"]:
        if version["version_sha256"] == version_sha256:
            version["version_status"] = "accepted"
        elif version["version_status"] == "accepted":
            version["version_status"] = "superseded"
    return result


def find_day_number(text: str) -> int | None:
    """Находит номер явного Day N/«День N» без верхней границы курса."""
    match = re.search(r"(?:^|\b)(?:day|день)\s*#?\s*(\d{1,3})\b", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_selected_note(path: Path = NOTE_PATH) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    heading_line = f"## {NOTE_HEADING}"
    starts = [i for i, line in enumerate(lines) if line.strip() == heading_line]
    if len(starts) != 1:
        raise ValueError("selected MCP study section is missing or ambiguous")
    start = starts[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    text = "\n".join(lines[start:end]).strip()
    return {
        "document_id": "mcp-study:understanding-practice",
        "source": "personal_note",
        "title": NOTE_HEADING,
        "section": NOTE_HEADING,
        "text": text,
        "text_sha256": sha256_bytes(text.encode("utf-8")),
        "origin": {"file": path.name, "line_start": start + 1, "line_end": end},
        "decision": "include",
        "reason": "раздел заметки выбран в утверждённой спецификации",
    }


def empty_personal_note_state(document_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": document_id,
        "accepted_version_sha256": None,
        "versions": [],
    }


def merge_personal_note(
    state: dict[str, Any], note: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, int]]:
    """Сохраняет правки выбранной заметки как версии с предложением замены."""
    merged = copy.deepcopy(state)
    if merged["document_id"] != note["document_id"]:
        raise ValueError("selected note identity differs from imported state")
    version_fields = {
        "document_id": note["document_id"],
        "source": note["source"],
        "title": note["title"],
        "section": note["section"],
        "text": note["text"],
    }
    version_sha = sha256_json(version_fields)
    existing = next(
        (row for row in merged["versions"] if row["version_sha256"] == version_sha),
        None,
    )
    if existing is not None:
        if note["origin"] not in existing["origins"]:
            existing["origins"].append(note["origin"])
        return merged, {"new_versions": 0, "same_versions": 1, "proposals": 0}
    version = {
        **version_fields,
        "version_sha256": version_sha,
        "text_sha256": note["text_sha256"],
        "origins": [note["origin"]],
        "version_status": "accepted" if not merged["versions"] else "proposed_replacement",
    }
    if merged["accepted_version_sha256"] is None and merged["versions"]:
        version["version_status"] = "review"
    merged["versions"].append(version)
    if merged["accepted_version_sha256"] is None and len(merged["versions"]) == 1:
        merged["accepted_version_sha256"] = version_sha
    return merged, {
        "new_versions": 1,
        "same_versions": 0,
        "proposals": int(version["version_status"] == "proposed_replacement"),
    }


def accept_personal_note_version(
    state: dict[str, Any], version_sha256: str, explicitly_approved: bool
) -> dict[str, Any]:
    if not explicitly_approved:
        raise ValueError("note replacement requires explicit approval")
    result = copy.deepcopy(state)
    if not any(row["version_sha256"] == version_sha256 for row in result["versions"]):
        raise ValueError("note version is missing")
    result["accepted_version_sha256"] = version_sha256
    for version in result["versions"]:
        if version["version_sha256"] == version_sha256:
            version["version_status"] = "accepted"
        elif version["version_status"] == "accepted":
            version["version_status"] = "superseded"
    return result


def active_personal_note(state: dict[str, Any]) -> dict[str, Any]:
    accepted = state["accepted_version_sha256"]
    version = next(
        (row for row in state["versions"] if row["version_sha256"] == accepted),
        None,
    )
    if version is None:
        raise ValueError("selected note has no accepted version")
    return {
        **{key: version[key] for key in ("document_id", "source", "title", "section", "text", "text_sha256")},
        "version_sha256": version["version_sha256"],
        "origin": version["origins"][0],
        "decision": "include",
        "reason": "раздел заметки выбран в утверждённой спецификации",
    }


def personal_note_decisions(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for version in state["versions"]:
        accepted = version["version_sha256"] == state["accepted_version_sha256"]
        rows.append(
            {
                **{key: version[key] for key in ("document_id", "source", "title", "section", "text", "text_sha256")},
                "version_sha256": version["version_sha256"],
                "origin": version["origins"][0],
                "decision": "include" if accepted else "review",
                "reason": (
                    "раздел заметки выбран в утверждённой спецификации"
                    if accepted
                    else "обнаружено изменение выбранного раздела; замена требует решения"
                ),
            }
        )
    return rows


def build_selection_manifest(
    state: dict[str, Any],
    inventory: dict[str, Any],
    period_start: str,
    personal_note_state: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    start = date.fromisoformat(period_start)
    known_assignments = {str(row["id"]): row for row in inventory["assignments"]}
    missing_assignments = sorted(set(known_assignments) - set(state["records"]))
    if missing_assignments:
        raise ValueError("one or more inventoried assignment IDs are missing from imported state")
    assignment_authors = {row["author"] for row in inventory["assignments"]}
    old_rows = {
        (row["message_id"], row["version_sha256"]): row
        for row in (previous or {}).get("telegram_decisions", [])
    }
    rows: list[dict[str, Any]] = []
    for message_id in sorted(state["records"], key=lambda value: int(value)):
        record = state["records"][message_id]
        for version in record["versions"]:
            key = (message_id, version["version_sha256"])
            if key in old_rows:
                rows.append(copy.deepcopy(old_rows[key]))
                continue
            origin = version["origins"][0]
            snapshot_date = origin["snapshot_date"]
            message_date = date.fromisoformat(version["date"][:10]) if version["date"] else None
            text = version["text"]
            known = known_assignments.get(message_id)
            day = int(known["day"]) if known else find_day_number(text)
            if message_date is None:
                decision, reason = "review", "дата не распознана надёжно"
                source_type = "discussion"
            elif message_date < start or message_date > date.fromisoformat(snapshot_date):
                decision, reason = "exclude", "сообщение вне временной области исходного снимка"
                source_type = "discussion"
            elif not text.strip():
                decision, reason = "exclude", "в экспорте нет текста; вложения не анализируются"
                source_type = "discussion"
            elif known is not None:
                decision, reason = "include", "условие курса подтверждено инвентаризацией"
                source_type = "assignment"
            elif (
                day is not None
                and version["author"] in assignment_authors
                and re.match(r"^\s*(?:day|день)\s*#?\s*\d+\b", text, re.IGNORECASE)
            ):
                decision, reason = "review", "возможное условие нового дня, требуется подтверждение"
                source_type = "assignment_candidate"
            else:
                decision, reason = "review", "смысловая релевантность требует просмотра"
                source_type = "discussion"
            rows.append(
                {
                    "chat_key": record["chat_key"],
                    "message_id": message_id,
                    "version_sha256": version["version_sha256"],
                    "decision": decision,
                    "source_type": source_type,
                    "day": day,
                    "reason": reason,
                    "reply_to": version["reply_to"],
                    "forwarded_reply_to": version.get("forwarded_reply_to"),
                    "forwarded_reply_to_origin": version.get("forwarded_reply_to_origin"),
                    "origin": origin,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "chat_key": state["chat_key"],
        "period_start": period_start,
        "decisions_are_final": False,
        "telegram_decisions": rows,
        "personal_notes": personal_note_decisions(personal_note_state),
        "note": "Статусы review требуют смыслового просмотра; эвристика не считается окончательным отбором.",
    }


def render_selection_preview(
    state: dict[str, Any], manifest: dict[str, Any]
) -> str:
    versions = {
        (message_id, version["version_sha256"]): version
        for message_id, record in state["records"].items()
        for version in record["versions"]
    }
    rows = [
        row for row in manifest["telegram_decisions"]
        if row["decision"] in {"include", "review"}
    ]
    rows.sort(
        key=lambda row: (
            versions[(row["message_id"], row["version_sha256"])]["date"] or "",
            int(row["message_id"]),
        )
    )
    output = [
        "# Приватный предварительный просмотр корпуса",
        "",
        "Локальный материал для смыслового отбора. Содержимое ещё не является утверждённым корпусом.",
        "Для каждого сообщения сохранены ID, дата, автор, reply и происхождение.",
        "",
    ]
    for row in rows:
        version = versions[(row["message_id"], row["version_sha256"])]
        origin = version["origins"][0]
        body = version["text"] or "В экспорте нет текста."
        output.extend(
            [
                f"## Telegram ID {row['message_id']} — {row['decision']}",
                "",
                f"- Дата: {version['date'] or 'не распознана'}",
                "- Автор:",
                fenced_markdown(version['author'] or 'не указан'),
                f"- Reply: {version['reply_to'] or 'нет'}",
                f"- Reply внутри пересланного сообщения: {version.get('forwarded_reply_to') or 'нет'}",
                f"- Файл и строка: {origin['source_file']}:{origin['source_line']}",
                f"- Предварительная причина: {row['reason']}",
                "",
                "Текст сообщения:",
                fenced_markdown(body),
                "",
            ]
        )
    return "\n".join(output)


def fenced_markdown(value: str) -> str:
    """Keeps source content inert when a Markdown viewer renders a private preview."""
    # AICODE-NOTE: личный текст может содержать Markdown-картинки и ссылки; preview не должен загружать их при рендере.
    longest = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{value}\n{fence}"


def render_selection_audit_preview(
    state: dict[str, Any], manifest: dict[str, Any]
) -> tuple[str, dict[str, int]]:
    """Готовит небольшую приватную выборку для проверки границ отбора."""
    versions = {
        (message_id, version["version_sha256"]): version
        for message_id, record in state["records"].items()
        for version in record["versions"]
    }
    ordered = sorted(
        manifest["telegram_decisions"],
        key=lambda row: (
            versions[(row["message_id"], row["version_sha256"])]["date"] or "",
            int(row["message_id"]),
        ),
    )
    excluded_text = [
        row for row in ordered
        if row["decision"] == "exclude"
        and versions[(row["message_id"], row["version_sha256"])]["text"].strip()
    ][:5]
    empty_examples = [
        row for row in ordered
        if row["decision"] == "exclude"
        and not versions[(row["message_id"], row["version_sha256"])]["text"].strip()
    ][:5]
    no_reply = [
        row for row in ordered
        if row["decision"] == "review" and row["reply_to"] is None
    ][:12]
    output = [
        "# Приватная выборка для аудита отбора",
        "",
        "Локальный материал для проверки примеров исключений и сообщений без reply.",
        "Это не утверждённый смысловой отбор; полный список решений лежит в соседнем манифесте.",
    ]
    counts = {
        "excluded_text_examples": len(excluded_text),
        "empty_examples": len(empty_examples),
        "no_reply_examples": len(no_reply),
    }
    groups = (
        ("Примеры исключений с текстом", excluded_text, True),
        ("Примеры сообщений без текста", empty_examples, False),
        ("Сообщения на просмотр без reply", no_reply, True),
    )
    for heading, rows, include_text in groups:
        output.extend(["", f"## {heading}", ""])
        if not rows:
            output.extend(["Выборка пуста.", ""])
            continue
        for row in rows:
            version = versions[(row["message_id"], row["version_sha256"])]
            origin = version["origins"][0]
            body = (version["text"] or "В экспорте нет текста.") if include_text else "В экспорте нет текста."
            output.extend(
                [
                    f"### Telegram ID {row['message_id']} — {row['decision']}",
                    "",
                    f"- Дата: {version['date'] or 'не распознана'}",
                    "- Автор:",
                    fenced_markdown(version['author'] or 'не указан'),
                    f"- Reply: {version['reply_to'] or 'нет'}",
                    f"- Reply внутри пересланного сообщения: {version.get('forwarded_reply_to') or 'нет'}",
                    f"- Файл и строка: {origin['source_file']}:{origin['source_line']}",
                    f"- Предварительная причина: {row['reason']}",
                    "",
                    "Текст сообщения:",
                    fenced_markdown(body),
                    "",
                ]
            )
    return "\n".join(output), counts


def secure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def atomic_write_json(path: Path, value: Any) -> None:
    secure_directory(path.parent)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temporary_name = tempfile.mkstemp(prefix=".day21-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(path: Path, value: str) -> None:
    secure_directory(path.parent)
    fd, temporary_name = tempfile.mkstemp(prefix=".day21-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(fallback)
    return json.loads(path.read_text(encoding="utf-8"))


def import_snapshot(
    export_dir: Path,
    part_names: list[str],
    snapshot_id: str,
    snapshot_date: str,
    period_start: str,
    private_dir: Path,
    chat_key: str = CHAT_KEY,
) -> dict[str, Any]:
    os.umask(0o077)
    secure_directory(private_dir)
    state_path = private_dir / "import-state.json"
    state = load_json(state_path, empty_state(chat_key))
    note_current = extract_selected_note()
    note_state_path = private_dir / "personal-note-versions.json"
    note_state = load_json(
        note_state_path, empty_personal_note_state(note_current["document_id"])
    )
    note_state, note_stats = merge_personal_note(note_state, note_current)
    if snapshot_id == DEFAULT_SNAPSHOT_ID and set(part_names) != set(DEFAULT_PARTS):
        raise ValueError("the initial export requires all five specified parts")
    snapshot, incoming = prepare_snapshot(
        export_dir, part_names, chat_key, snapshot_id, snapshot_date, state
    )
    manifest_path = private_dir / "selection-manifest.json"
    if not INVENTORY_PATH.is_file():
        raise FileNotFoundError("the pre-import assignment inventory is required")
    inventory = load_json(INVENTORY_PATH, {"assignments": []})
    old_manifest = load_json(manifest_path, None)
    state, old_manifest, legacy_reply_migrations = migrate_legacy_forwarded_replies(
        state, old_manifest
    )
    merged, stats = merge_snapshot(state, snapshot, incoming)
    manifest = build_selection_manifest(
        merged, inventory, period_start, note_state, old_manifest
    )
    preview = render_selection_preview(merged, manifest)
    audit_preview, audit_counts = render_selection_audit_preview(merged, manifest)
    note = active_personal_note(note_state)

    atomic_write_json(state_path, merged)
    atomic_write_json(manifest_path, manifest)
    atomic_write_json(note_state_path, note_state)
    atomic_write_json(private_dir / "personal-note.json", note)
    atomic_write_text(private_dir / "selection-preview.md", preview)
    atomic_write_text(private_dir / "selection-audit-preview.md", audit_preview)
    return {
        "snapshot": snapshot,
        "stats": stats,
        "legacy_forwarded_reply_migrations": legacy_reply_migrations,
        "note_stats": note_stats,
        "manifest_counts": {
            decision: sum(1 for row in manifest["telegram_decisions"] if row["decision"] == decision)
            for decision in ("include", "exclude", "review")
        },
        "preview_messages": len(
            [row for row in manifest["telegram_decisions"] if row["decision"] in {"include", "review"}]
        ),
        "preview_bytes": len(preview.encode("utf-8")),
        "audit_preview_counts": audit_counts,
        "audit_preview_bytes": len(audit_preview.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--snapshot-id", default=DEFAULT_SNAPSHOT_ID)
    parser.add_argument("--snapshot-date", default=DEFAULT_SNAPSHOT_DATE)
    parser.add_argument("--period-start", default=DEFAULT_PERIOD_START)
    parser.add_argument("--chat-key", default=CHAT_KEY)
    parser.add_argument(
        "--part", action="append", dest="parts",
        help="Имя части экспорта; можно повторить. По умолчанию читаются все пять частей.",
    )
    args = parser.parse_args()
    try:
        result = import_snapshot(
            args.export_dir,
            args.parts or list(DEFAULT_PARTS),
            args.snapshot_id,
            args.snapshot_date,
            args.period_start,
            DEFAULT_PRIVATE_DIR,
            args.chat_key,
        )
    except (OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL: {type(error).__name__}: {error}")
        return 1
    snapshot = result["snapshot"]
    print(
        "OK: imported "
        f"{snapshot['message_count']} unique messages from {len(snapshot['parts'])} parts; "
        f"new records={result['stats']['new_records']}, "
        f"new versions={result['stats']['new_versions']}, "
        f"same versions={result['stats']['same_versions']}, "
        f"replacement proposals={result['stats']['proposals']}"
    )
    print(
        "Selection manifest: "
        f"include={result['manifest_counts']['include']}, "
        f"exclude={result['manifest_counts']['exclude']}, "
        f"review={result['manifest_counts']['review']}; "
        f"local preview={result['preview_messages']} messages / {result['preview_bytes']} bytes"
    )
    print(
        "Audit preview: "
        f"excluded text={result['audit_preview_counts']['excluded_text_examples']}, "
        f"empty={result['audit_preview_counts']['empty_examples']}, "
        f"review without reply={result['audit_preview_counts']['no_reply_examples']} "
        f"({result['audit_preview_bytes']} bytes)"
    )
    print(
        "Personal note: "
        f"new versions={result['note_stats']['new_versions']}, "
        f"same versions={result['note_stats']['same_versions']}, "
        f"replacement proposals={result['note_stats']['proposals']}"
    )
    print("Private files written with mode 0600 under day21/private/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
