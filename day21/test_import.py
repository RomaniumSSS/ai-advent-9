#!/usr/bin/env python3
"""Офлайн-проверки импорта Day21 на синтетических HTML-фрагментах."""

from __future__ import annotations

import json
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from import_corpus import (  # noqa: E402
    TelegramPartParser,
    accept_personal_note_version,
    accept_replacement,
    active_personal_note,
    atomic_write_json,
    build_selection_manifest,
    empty_state,
    empty_personal_note_state,
    find_day_number,
    merge_snapshot,
    merge_personal_note,
    message_version_fields,
    prepare_snapshot,
    render_selection_preview,
    sha256_bytes,
    sha256_json,
)


def synthetic_row(message_id: str, text: str, date: str = "2026-10-01T12:00:00+01:00"):
    version_fields = {
        "author": "Учебный пример",
        "author_inherited_from_message_id": None,
        "author_provenance": "direct",
        "date": date,
        "reply_to": None,
        "reply_to_origin": None,
        "text": text,
    }
    version_sha = sha256_json(version_fields)
    return {
        "chat_key": "ai-advent-9",
        "snapshot_id": "fixture",
        "snapshot_date": "2026-10-01",
        "message_id": message_id,
        **version_fields,
        "forwarded_reply_to": None,
        "forwarded_reply_to_origin": None,
        "content_sha256": sha256_bytes(text.encode("utf-8")),
        "version_sha256": version_sha,
        "origins": [
            {
                "snapshot_id": "fixture",
                "snapshot_date": "2026-10-01",
                "snapshot_ref": "fixture:abc123",
                "source_file": "messages.html",
                "source_line": 1,
                "source_sha256": "f" * 64,
            }
        ],
    }


def synthetic_snapshot(snapshot_ref: str = "fixture:abc123"):
    return {
        "snapshot_ref": snapshot_ref,
        "snapshot_id": "fixture",
        "snapshot_date": "2026-10-01",
        "chat_key": "ai-advent-9",
        "chat_title": "Synthetic fixture",
        "source_fingerprint": "a" * 64,
        "parts": [],
        "message_count": 1,
    }


def synthetic_note(text: str):
    import hashlib

    return {
        "document_id": "mcp-study:understanding-practice",
        "source": "personal_note",
        "title": "Synthetic note",
        "section": "Synthetic section",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "origin": {"file": "MCP-STUDY.fixture", "line_start": 1, "line_end": 2},
    }


def check_html_fields_and_paragraphs() -> None:
    html = """<!doctype html><html><body><div class="page_header">Fixture</div>
    <div class="message default clearfix" id="message125">
      <div class="pull_right date details" title="01.10.2026 12:00:00 UTC+01:00"></div>
      <div class="from_name">Учебный пример</div>
      <div class="forwarded body"><div class="from_name">Автор оригинала</div>
        <span class="date details" title="02.10.2026 12:00:00 UTC+01:00"></span>
        <div class="reply_to details"><a href="#go_to_message999">forwarded reply</a></div></div>
      <div class="reply_to details"><a href="#go_to_message124">parent</a></div>
      <div class="text">Первый абзац<br/>второй <a href="https://example.invalid/a">пример</a>.</div>
    </div></body></html>"""
    parser = TelegramPartParser("messages.html")
    parser.feed(html)
    title, rows = parser.finish()
    assert title == "Fixture"
    assert len(rows) == 1
    assert rows[0]["message_id"] == "125"
    assert rows[0]["author"] == "Учебный пример"
    assert rows[0]["date"] == "2026-10-01T12:00:00+01:00"
    assert rows[0]["reply_to"] == "124"
    assert rows[0]["reply_to_origin"] == "message_reply"
    assert rows[0]["forwarded_reply_to"] == "999"
    assert rows[0]["forwarded_reply_to_origin"] == "forwarded_source_reply"
    assert rows[0]["text"] == "Первый абзац\nвторой [пример](https://example.invalid/a)."

    forwarded_only = """<div class="page_header">Fixture</div>
    <div class="message default clearfix" id="message126">
      <div class="forwarded body"><div class="reply_to details"><a href="#go_to_message998">source</a></div></div>
      <div class="text">Forwarded only</div></div>"""
    parser = TelegramPartParser("messages2.html")
    parser.feed(forwarded_only)
    _, rows = parser.finish()
    assert rows[0]["reply_to"] is None
    assert rows[0]["reply_to_origin"] is None
    assert rows[0]["forwarded_reply_to"] == "998"
    assert rows[0]["forwarded_reply_to_origin"] == "forwarded_source_reply"


def check_repeat_and_partial_import() -> None:
    state = empty_state("ai-advent-9")
    snapshot = synthetic_snapshot()
    first = synthetic_row("125", "Исходная версия")
    state, stats = merge_snapshot(state, snapshot, [first])
    assert stats["new_records"] == 1
    repeated, stats = merge_snapshot(state, snapshot, [first])
    assert stats["new_records"] == 0 and stats["same_versions"] == 1
    assert repeated == state

    partial_snapshot = synthetic_snapshot("fixture-partial:def456")
    second = synthetic_row("126", "Новая запись")
    second["snapshot_id"] = "fixture-partial"
    second["origins"][0]["snapshot_id"] = "fixture-partial"
    second["origins"][0]["snapshot_ref"] = "fixture-partial:def456"
    partial, _ = merge_snapshot(state, partial_snapshot, [second])
    assert set(partial["records"]) == {"125", "126"}
    assert partial["records"]["125"] == state["records"]["125"]


def check_legacy_forwarded_reply_migration() -> None:
    from import_corpus import migrate_legacy_forwarded_replies

    row = synthetic_row("127", "Legacy forwarded reply")
    row["reply_to"] = "998"
    row["reply_to_origin"] = "forwarded_source"
    row["version_sha256"] = sha256_json(message_version_fields(row))
    state, _ = merge_snapshot(empty_state("ai-advent-9"), synthetic_snapshot(), [row])
    old_sha = row["version_sha256"]
    manifest = {
        "decisions_are_final": False,
        "telegram_decisions": [{
            "message_id": "127",
            "version_sha256": old_sha,
            "decision": "include",
            "reason": "synthetic accepted decision",
            "reply_to": "998",
        }],
    }

    migrated, migrated_manifest, count = migrate_legacy_forwarded_replies(state, manifest)
    version = migrated["records"]["127"]["versions"][0]
    decision = migrated_manifest["telegram_decisions"][0]
    assert count == 1
    assert version["reply_to"] is None and version["reply_to_origin"] is None
    assert version["forwarded_reply_to"] == "998"
    assert version["forwarded_reply_to_origin"] == "forwarded_source_reply"
    assert decision["decision"] == "include"
    assert decision["reply_to"] is None
    assert decision["forwarded_reply_to"] == "998"
    assert decision["version_sha256"] == version["version_sha256"] != old_sha

    accepted = json.loads(json.dumps(state))
    accepted["records"]["127"]["accepted_version_sha256"] = old_sha
    try:
        migrate_legacy_forwarded_replies(accepted, manifest)
    except ValueError:
        pass
    else:
        raise AssertionError("accepted legacy version was migrated automatically")


def check_private_preview_fences_source_markdown() -> None:
    body = "![remote](https://example.invalid/pixel)\n```\nsource text"
    row = synthetic_row("128", body)
    row["author"] = "![author](https://example.invalid/author)"
    row["version_sha256"] = sha256_json(message_version_fields(row))
    state, _ = merge_snapshot(empty_state("ai-advent-9"), synthetic_snapshot(), [row])
    manifest = {
        "telegram_decisions": [{
            "message_id": "128",
            "version_sha256": row["version_sha256"],
            "decision": "review",
            "reason": "synthetic preview check",
            "reply_to": None,
            "forwarded_reply_to": None,
            "origin": row["origins"][0],
        }],
    }
    preview = render_selection_preview(state, manifest)
    assert "````\n" + body + "\n````" in preview
    assert "- Автор:\n```\n" + row["author"] + "\n```" in preview


def check_replacement_requires_decision() -> None:
    state = empty_state("ai-advent-9")
    old = synthetic_row("125", "Исходный текст")
    state, _ = merge_snapshot(state, synthetic_snapshot(), [old])
    state = accept_replacement(state, "125", old["version_sha256"], True)

    changed = synthetic_row("125", "Исправленный текст")
    changed["origins"][0]["snapshot_ref"] = "fixture-next:ffeedd"
    next_snapshot = synthetic_snapshot("fixture-next:ffeedd")
    next_snapshot["snapshot_id"] = "fixture-next"
    next_snapshot["source_fingerprint"] = "b" * 64
    result, stats = merge_snapshot(state, next_snapshot, [changed])
    record = result["records"]["125"]
    assert stats["proposals"] == 1
    assert record["accepted_version_sha256"] == old["version_sha256"]
    proposed = next(v for v in record["versions"] if v["version_sha256"] == changed["version_sha256"])
    assert proposed["version_status"] == "proposed_replacement"
    try:
        accept_replacement(result, "125", changed["version_sha256"], False)
    except ValueError:
        pass
    else:
        raise AssertionError("replacement was accepted without explicit approval")
    accepted = accept_replacement(result, "125", changed["version_sha256"], True)
    assert accepted["records"]["125"]["accepted_version_sha256"] == changed["version_sha256"]
    assert len(accepted["records"]["125"]["versions"]) == 2


def check_dynamic_day_number_and_private_write() -> None:
    assert find_day_number("День 25. Синтетическое условие") == 25
    assert find_day_number("Обсуждение задания Day 125") == 125
    assert find_day_number("Обычное сообщение без дня") is None
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary) / "private"
        target = directory / "state.json"
        atomic_write_json(target, {"fixture": True})
        assert json.loads(target.read_text(encoding="utf-8")) == {"fixture": True}
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def check_day25_candidate_and_interrupted_recovery() -> None:
    candidate = synthetic_row("125", "Day 25. Synthetic assignment")
    candidate["author"] = "Course Admin"
    fields = {
        "author": candidate["author"],
        "author_inherited_from_message_id": candidate["author_inherited_from_message_id"],
        "author_provenance": candidate["author_provenance"],
        "date": candidate["date"],
        "reply_to": candidate["reply_to"], "text": candidate["text"],
        "reply_to_origin": candidate["reply_to_origin"],
    }
    candidate["version_sha256"] = sha256_json(fields)
    state = empty_state("ai-advent-9")
    state, _ = merge_snapshot(
        state,
        synthetic_snapshot(),
        [candidate, synthetic_row("999", "Known assignment")],
    )
    manifest = build_selection_manifest(
        state,
        {"assignments": [{"id": "999", "author": "Course Admin", "day": 1}]},
        "2026-08-31",
        merge_personal_note(
            empty_personal_note_state("mcp-study:understanding-practice"),
            synthetic_note("Stable note text"),
        )[0],
    )
    row = next(item for item in manifest["telegram_decisions"] if item["message_id"] == "125")
    assert row["day"] == 25 and row["source_type"] == "assignment_candidate"
    assert row["decision"] == "review"

    old = synthetic_row("126", "Accepted synthetic text")
    accepted_state, _ = merge_snapshot(empty_state("ai-advent-9"), synthetic_snapshot(), [old])
    accepted_state = accept_replacement(accepted_state, "126", old["version_sha256"], True)
    new = synthetic_row("126", "Changed synthetic text")
    new["origins"][0]["snapshot_ref"] = "fixture-next:789abc"
    next_snapshot = synthetic_snapshot("fixture-next:789abc")
    next_snapshot["snapshot_id"] = "fixture-next"
    next_snapshot["source_fingerprint"] = "c" * 64
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "private" / "state.json"
        changed_state, _ = merge_snapshot(accepted_state, next_snapshot, [new])
        atomic_write_json(path, changed_state)
        recovered = json.loads(path.read_text(encoding="utf-8"))
        retried, retry_stats = merge_snapshot(recovered, next_snapshot, [new])
        assert retry_stats["new_versions"] == 0 and retry_stats["same_versions"] == 1
        record = retried["records"]["126"]
        assert record["accepted_version_sha256"] == old["version_sha256"]
        assert len(record["versions"]) == 2
        old_manifest = {
            "telegram_decisions": [
                {
                    "message_id": "126",
                    "version_sha256": old["version_sha256"],
                    "decision": "include",
                    "source_type": "discussion",
                    "day": None,
                    "reason": "synthetic accepted decision",
                    "reply_to": None,
                    "origin": old["origins"][0],
                }
            ]
        }
        repaired_manifest = build_selection_manifest(
            retried,
            {"assignments": []},
            "2026-08-31",
            merge_personal_note(
                empty_personal_note_state("mcp-study:understanding-practice"),
                synthetic_note("Stable note text"),
            )[0],
            old_manifest,
        )
        decisions = {item["version_sha256"]: item["decision"] for item in repaired_manifest["telegram_decisions"]}
        assert decisions[old["version_sha256"]] == "include"
        assert decisions[new["version_sha256"]] == "review"


def check_personal_note_replacement() -> None:
    state = empty_personal_note_state("mcp-study:understanding-practice")
    state, stats = merge_personal_note(state, synthetic_note("Original note text"))
    original_sha = state["accepted_version_sha256"]
    assert stats["new_versions"] == 1
    repeated, stats = merge_personal_note(state, synthetic_note("Original note text"))
    assert stats["same_versions"] == 1 and repeated == state

    changed_note = synthetic_note("Revised note text")
    changed_note["origin"] = {"file": "MCP-STUDY.fixture", "line_start": 2, "line_end": 3}
    proposed, stats = merge_personal_note(state, changed_note)
    pending_sha = proposed["versions"][-1]["version_sha256"]
    assert stats["proposals"] == 1
    assert proposed["accepted_version_sha256"] == original_sha
    assert active_personal_note(proposed)["text"] == "Original note text"
    try:
        accept_personal_note_version(proposed, pending_sha, False)
    except ValueError:
        pass
    else:
        raise AssertionError("note replacement was accepted without explicit approval")
    accepted = accept_personal_note_version(proposed, pending_sha, True)
    assert active_personal_note(accepted)["text"] == "Revised note text"
    assert len(accepted["versions"]) == 2


def check_joined_author_recovery_for_partial_part() -> None:
    header = '<div class="page_header">AI Advent Challenge #9</div>'
    first = """<div class="message default clearfix" id="message126">
      <div class="pull_right date details" title="01.10.2026 12:00:00 UTC+01:00"></div>
      <div class="from_name">Course Admin</div><div class="text">First</div></div>"""
    joined = """<div class="message default clearfix joined" id="message127">
      <div class="pull_right date details" title="01.10.2026 12:01:00 UTC+01:00"></div>
      <div class="text">Second</div></div>"""
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        full_path = directory / "messages.html"
        full_path.write_text(header + first + joined, encoding="utf-8")
        _, full_rows = prepare_snapshot(
            directory, ["messages.html"], "ai-advent-9", "fixture", "2026-10-01"
        )
        previous = next(row for row in full_rows if row["message_id"] == "127")
        assert previous["author"] == "Course Admin"
        assert previous["author_provenance"] == "joined_previous_message"
        assert previous["author_inherited_from_message_id"] == "126"

        partial_path = directory / "messages2.html"
        partial_path.write_text(header + joined.replace("127", "128"), encoding="utf-8")
        state, _ = merge_snapshot(empty_state("ai-advent-9"), synthetic_snapshot(), full_rows)
        _, partial_rows = prepare_snapshot(
            directory,
            ["messages2.html"],
            "ai-advent-9",
            "fixture-partial",
            "2026-10-01",
            state,
        )
        partial = partial_rows[0]
        assert partial["message_id"] == "128"
        assert partial["author"] == "Course Admin"
        assert partial["author_provenance"] == "prior_import_context"
        assert partial["author_inherited_from_message_id"] == "126"


def main() -> int:
    checks = [
        check_html_fields_and_paragraphs,
        check_repeat_and_partial_import,
        check_legacy_forwarded_reply_migration,
        check_private_preview_fences_source_markdown,
        check_replacement_requires_decision,
        check_dynamic_day_number_and_private_write,
        check_day25_candidate_and_interrupted_recovery,
        check_personal_note_replacement,
        check_joined_author_recovery_for_partial_part,
    ]
    problems = []
    for check in checks:
        try:
            check()
        except Exception as error:  # noqa: BLE001 - собрать все локальные ошибки скрипта
            problems.append(f"{check.__name__}: {type(error).__name__}: {error}")
    if problems:
        print("FAIL: " + " | ".join(problems))
        return 1
    print(f"OK: {len(checks)} offline import checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
