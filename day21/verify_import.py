#!/usr/bin/env python3
"""Проверяет локальный Day21-импорт без вывода личных данных."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from import_corpus import (  # noqa: E402
    CHAT_KEY,
    DEFAULT_EXPORT_DIR,
    DEFAULT_PARTS,
    DEFAULT_PRIVATE_DIR,
    DEFAULT_SNAPSHOT_DATE,
    DEFAULT_SNAPSHOT_ID,
    DEFAULT_PERIOD_START,
    INVENTORY_PATH,
    NOTE_PATH,
    active_personal_note,
    atomic_write_json,
    extract_selected_note,
    merge_personal_note,
    merge_snapshot,
    migrate_legacy_forwarded_replies,
    empty_personal_note_state,
    prepare_snapshot,
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    private = DEFAULT_PRIVATE_DIR
    state = read_json(private / "import-state.json")
    manifest = read_json(private / "selection-manifest.json")
    note_state = read_json(private / "personal-note-versions.json")
    active_note = read_json(private / "personal-note.json")
    inventory = read_json(INVENTORY_PATH)
    observations = read_json(private / "observations.json")

    state, manifest, legacy_reply_migrations = migrate_legacy_forwarded_replies(
        state, manifest
    )
    snapshot, incoming = prepare_snapshot(
        DEFAULT_EXPORT_DIR,
        list(DEFAULT_PARTS),
        CHAT_KEY,
        DEFAULT_SNAPSHOT_ID,
        DEFAULT_SNAPSHOT_DATE,
        state,
    )
    repeated, repeat_stats = merge_snapshot(state, snapshot, incoming)
    repeat_stable = repeated == state and repeat_stats["new_versions"] == 0
    stored_snapshot = state["snapshots"].get(snapshot["snapshot_ref"])
    imported_ids = set(state["records"])
    source_ids = {row["message_id"] for row in incoming}

    previous: dict[str, dict] = {}
    for message_id, versions in observations.items():
        rows = [
            row for row in versions
            if row["export"].startswith("ChatExport_2026-10-01/")
        ]
        if len(rows) == 1:
            previous[message_id] = rows[0]

    current = {row["message_id"]: row for row in incoming}
    reply_provenance_valid = all(
        (row["reply_to"] is None and row["reply_to_origin"] is None)
        or (row["reply_to"] is not None and row["reply_to_origin"] == "message_reply")
        for row in incoming
    ) and all(
        (row["forwarded_reply_to"] is None and row["forwarded_reply_to_origin"] is None)
        or (
            row["forwarded_reply_to"] is not None
            and row["forwarded_reply_to_origin"] == "forwarded_source_reply"
        )
        for row in incoming
    )
    author_mismatches = []
    date_mismatches = []
    reply_mismatches = []
    forwarded_reply_reclassified = []
    line_mismatches = []
    content_mismatches = []
    content_hash_matches = 0
    for message_id, old in previous.items():
        version = current.get(message_id)
        if version is None:
            continue
        if version["author"] != old["author"]:
            author_mismatches.append(message_id)
        if version["date"] != old["date"]:
            date_mismatches.append(message_id)
        old_reply = str(old["reply_to"]) if old["reply_to"] is not None else None
        new_reply = str(version["reply_to"]) if version["reply_to"] is not None else None
        if new_reply != old_reply:
            forwarded_reply = (
                str(version["forwarded_reply_to"])
                if version["forwarded_reply_to"] is not None
                else None
            )
            if old_reply is not None and forwarded_reply == old_reply and new_reply is None:
                forwarded_reply_reclassified.append(message_id)
            else:
                reply_mismatches.append(message_id)
        if version["origins"][0]["source_line"] != old["line"]:
            line_mismatches.append(message_id)
        without_link_targets = re.sub(
            r"\[([^\]]*)\]\([^)]*\)", r"\1", version["text"]
        )
        old_hash = old.get("sha256")
        if hashlib.sha256(without_link_targets.encode("utf-8")).hexdigest() == old_hash:
            content_hash_matches += 1
        else:
            content_mismatches.append(message_id)

    course_start = date.fromisoformat(DEFAULT_PERIOD_START)
    snapshot_end = date.fromisoformat(DEFAULT_SNAPSHOT_DATE)
    period = Counter()
    for version in current.values():
        message_date = date.fromisoformat(version["date"][:10])
        if course_start <= message_date <= snapshot_end:
            period["messages"] += 1
            period["with_text"] += bool(version["text"].strip())

    selection_counts = Counter(row["decision"] for row in manifest["telegram_decisions"])
    assignments = {str(row["id"]) for row in inventory["assignments"]}
    included_assignments = {
        row["message_id"]
        for row in manifest["telegram_decisions"]
        if row["source_type"] == "assignment" and row["decision"] == "include"
    }
    note_repeat, note_repeat_stats = merge_personal_note(note_state, extract_selected_note(NOTE_PATH))
    note_active = active_personal_note(note_state)

    private_files = [path for path in private.rglob("*") if path.is_file()]
    modes_ok = stat.S_IMODE(private.stat().st_mode) == 0o700 and all(
        stat.S_IMODE(path.stat().st_mode) == 0o600 for path in private_files
    )
    part_hashes_match = all(
        hashlib.sha256((DEFAULT_EXPORT_DIR / row["file"]).read_bytes()).hexdigest()
        == row["sha256"]
        for row in snapshot["parts"]
    )
    inventory_export_rows = [
        row for row in inventory["exports"]
        if row["file"].startswith("ChatExport_2026-10-01/")
    ]
    inventory_hashes = {Path(row["file"]).name: row["sha256"] for row in inventory_export_rows}
    previous_hash_match_count = sum(
        inventory_hashes.get(row["file"]) == row["sha256"] for row in snapshot["parts"]
    )
    manifest_keys = [
        (row["message_id"], row["version_sha256"])
        for row in manifest["telegram_decisions"]
    ]
    checks = {
        "chat_key_matches": state["chat_key"] == CHAT_KEY,
        "initial_snapshot_present": stored_snapshot == snapshot,
        "all_five_parts_imported": {row["file"] for row in snapshot["parts"]} == set(DEFAULT_PARTS),
        "all_part_hashes_match_state": part_hashes_match,
        "all_part_hashes_match_inventory": previous_hash_match_count == len(DEFAULT_PARTS),
        "all_source_ids_match_import": source_ids == imported_ids,
        "historical_id_coverage_complete": imported_ids == set(previous),
        "reimport_is_idempotent": repeat_stable,
        "all_inventoried_assignments_included": assignments == included_assignments,
        "selection_is_still_preliminary": manifest["decisions_are_final"] is False,
        "period_counts_match_inventory": (
            period["messages"] == inventory["course_period_unique_ids"]
            and period["with_text"] == inventory["course_period_text_messages"]
        ),
        "selection_manifest_has_unique_rows": len(manifest_keys) == len(set(manifest_keys)),
        "personal_note_repeat_is_idempotent": note_repeat == note_state and note_repeat_stats["same_versions"] == 1,
        "active_note_matches_accepted_version": active_note["version_sha256"] == note_active["version_sha256"],
        "historical_reply_targets_preserved": not reply_mismatches,
        "reply_targets_keep_their_provenance": reply_provenance_valid,
        "private_modes_are_restricted": modes_ok,
    }

    extraction_diffs = [
        {
            "message_id": message_id,
            "source_file": current[message_id]["origins"][0]["source_file"],
            "old_text": previous[message_id].get("text", ""),
            "imported_text": current[message_id]["text"],
            "comparison": "old text SHA256 differs after stripping rendered Markdown link targets",
        }
        for message_id in content_mismatches
    ]
    report = {
        "snapshot_id": DEFAULT_SNAPSHOT_ID,
        "snapshot_date": DEFAULT_SNAPSHOT_DATE,
        "snapshot_ref": snapshot["snapshot_ref"],
        "parts": snapshot["parts"],
        "source_bytes": sum(row["bytes"] for row in snapshot["parts"]),
        "source_messages": len(source_ids),
        "period": dict(period),
        "assignments_expected": len(assignments),
        "selection_counts": dict(selection_counts),
        "selection_final": False,
        "volume_pages_measured": False,
        "repeat_import": repeat_stats,
        "historical_metadata_comparison": {
            "author_mismatch_ids": author_mismatches,
            "date_mismatch_ids": date_mismatches,
            "reply_mismatch_ids": reply_mismatches,
            "forwarded_reply_reclassified_ids": forwarded_reply_reclassified,
            "source_line_mismatch_ids": line_mismatches,
            "content_hash_matches_after_audit_only_link_target_removal": content_hash_matches,
            "content_hash_mismatch_ids": content_mismatches,
        },
        "checks": checks,
    }
    atomic_write_json(private / "import-validation.json", report)
    atomic_write_json(private / "extraction-diff-preview.json", extraction_diffs)

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print("FAIL: " + ", ".join(failed))
        return 1
    print(
        f"OK: {len(snapshot['parts'])} parts / {len(source_ids)} IDs; "
        f"{period['messages']} in-period messages / {period['with_text']} with text; "
        f"reimport idempotent; private modes 0700/0600"
    )
    print(
        f"REVIEW: {len(author_mismatches)} author differences, "
        f"{len(content_mismatches)} prior text-hash differences after removing rendered link targets "
        f"for this comparison only; corpus text and links are unchanged"
    )
    print(
        f"REVIEW: {len(forwarded_reply_reclassified)} prior reply targets are now stored as "
        "forwarded-source links; these are not thread edges"
    )
    print(
        f"PENDING: selection has {selection_counts['review']} discussion records for human review; "
        "final corpus volume is not measured"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
