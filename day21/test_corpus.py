"""Офлайн-проверки импорта Day21 на синтетических сообщениях."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sqlite3
import tempfile

from corpus import (
    accept_proposal, build_documents, build_manifest, connect, content_digest, decide,
    import_note, import_snapshot, inert_markdown, migrate_parser, parse_export,
)


TITLE = "<html><head><title>Telegram</title></head><body><div class=\"page_header\"><div class=\"text bold\">AI Advent Challenge #9</div></div>"
END = "</body></html>"


def message(ident: int, text: str, *, author: str = "Участник", reply: int | None = None,
            date: str = "02.10.2026 12:00:00 UTC+00:00", joined: bool = False) -> str:
    classes = "message default clearfix joined" if joined else "message default clearfix"
    name = "" if joined else f'<div class="from_name">{author}</div>'
    link = f'<div class="reply_to details"><a href="#go_to_message{reply}">ответ</a></div>' if reply else ""
    return (f'<div class="{classes}" id="message{ident}"><div class="body">'
            f'<div class="pull_right date details" title="{date}"></div>{name}{link}'
            f'<div class="text">{text}</div></div></div>')


def write_parts(folder: Path, parts: list[str]) -> None:
    for index, body in enumerate(parts, 1):
        name = "messages" + (str(index) if index > 1 else "") + ".html"
        (folder / name).write_text(TITLE + body + END, encoding="utf-8")


def test_forwarded_and_migration(root: Path) -> None:
    source = root / "forwarded"
    source.mkdir()
    forwarded = (
        '<div class="message default clearfix joined" id="message7001"><div class="body">'
        '<div class="pull_right date details" title="03.10.2026 12:00:00 UTC+00:00"></div>'
        '<div class="forwarded body"><div class="from_name">Forwarded'
        '<span class="date details" title="01.10.2026 09:00:00 UTC+00:00">earlier</span></div>'
        '<div class="reply_to details"><a href="#go_to_message999">reply</a></div>'
        '<div class="text">Пересланный API пример</div></div></div></div>'
    )
    service = '<div class="message service" id="message7003"><div class="body details">событие</div></div>'
    write_parts(source, [
        message(7000, "Начало", author="Outer"),
        forwarded,
        message(7002, "После пересылки", joined=True),
        service,
        message(7004, "После события", joined=True),
    ])
    records, _ = parse_export(source)
    by_id = {record["message_id"]: record for record in records}
    assert by_id[7001]["author"] == by_id[7002]["author"] == "Outer"
    assert by_id[7001]["author_context"] == "joined_inherited"
    assert by_id[7001]["reply_to"] is None
    assert by_id[7001]["forwarded"][0]["author"] == "Forwarded"
    assert by_id[7001]["forwarded"][0]["reply_to"] == 999
    assert by_id[7001]["date"].startswith("2026-10-03")
    assert by_id[7001]["forwarded"][0]["date"].startswith("01.10.2026")
    assert by_id[7004]["author"] is None
    assert parse_export(source, ["messages2.html"])[0][0]["author"] is None
    assert parse_export(source, ["messages.html", "messages3.html"])[0][-1]["author"] is None
    print("ok: внешний автор/reply, пересылка, границы частей и неизвестный автор")

    conn = connect(root / "migration.sqlite3")
    try:
        import_snapshot(conn, source, "legacy", 1, "2026-10-03")
        decide(conn, "telegram:7001", "include", "Синтетический пример", "synthetic-test")
        corrected = by_id[7001]
        legacy = dict(corrected, author="Forwarded", reply_to=999, forwarded=[])
        legacy_hash = content_digest(legacy)
        with conn:
            conn.execute("DELETE FROM parser_migrations WHERE snapshot_id='legacy'")
            conn.execute("UPDATE observations SET version_hash=?,record_json=? WHERE snapshot_id='legacy' AND message_id=7001",
                         (legacy_hash, json.dumps(legacy, ensure_ascii=False)))
            conn.execute("UPDATE accepted SET version_hash=?,record_json=? WHERE source_key='telegram:7001'",
                         (legacy_hash, json.dumps(legacy, ensure_ascii=False)))
        result = migrate_parser(conn, source, "legacy")
        assert result["archived"] == 5 and result["changed_hash"] == 1 and result["proposals"] == 1
        assert migrate_parser(conn, source, "legacy")["repeat"] == 1
        old = conn.execute("SELECT version_hash FROM legacy_observations WHERE snapshot_id='legacy' AND message_id=7001").fetchone()
        assert old[0] == legacy_hash
        active = conn.execute("SELECT version_hash FROM accepted WHERE source_key='telegram:7001'").fetchone()[0]
        assert active == legacy_hash
        pending = conn.execute("SELECT version_hash FROM proposals WHERE source_key='telegram:7001' AND status='pending'").fetchone()[0]
        assert pending == content_digest(corrected)
        entry = next(item for item in build_manifest(conn) if item["source_key"] == "telegram:7001")
        assert entry["reply_to"] == 999 and entry["pending_proposals"][0]["reply_to"] is None
        print("ok: миграция парсера архивирует прежнюю запись и не переключает active")
    finally:
        conn.close()


def run() -> None:
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent / "private") as temp:
        root = Path(temp)
        source = root / "source"
        source.mkdir()
        write_parts(source, [
            message(5001, "🔹 День 25<br>Новое условие", author="Mobile Developer Manager")
            + message(5002, 'Вопрос <a href="https://example.invalid/guide">документация</a><br>Вторая строка', reply=5001)
            + message(5003, "Ответ", reply=5002)
            + message(5004, "Старая реплика", date="30.08.2026 12:00:00 UTC+00:00"),
            message(5005, "Продолжение", joined=True), "", "", "",
        ])
        records, files = parse_export(source)
        assert len(records) == 5 and len(files) == 5
        by_id = {row["message_id"]: row for row in records}
        assert by_id[5002]["reply_to"] == 5001
        assert by_id[5002]["text"] == "Вопрос документация\nВторая строка"
        assert by_id[5002]["links"][0]["href"] == "https://example.invalid/guide"
        assert by_id[5005]["author"] == "Участник"
        print("ok: пять частей, абзац, ссылка, reply, joined")

        first_file = source / "messages.html"
        original = first_file.read_text(encoding="utf-8")
        first_file.write_text(original.replace('class="text bold">AI Advent Challenge #9', 'class="text bold">Другой чат'), encoding="utf-8")
        try:
            parse_export(source)
            raise AssertionError("чужой чат принят")
        except ValueError:
            pass
        first_file.write_text(original, encoding="utf-8")
        print("ok: точная проверка заголовка чата")

        conn = connect(root / "private" / "test.sqlite3")
        try:
            first = import_snapshot(conn, source, "full", 1, "2026-10-02T00:00:00+00:00")
            assert first["new"] == 5
            assert import_snapshot(conn, source, "full", 1, "2026-10-02T00:00:00+00:00")["repeat"] == 1
            statuses = dict(conn.execute("SELECT source_key,status FROM decisions"))
            assert statuses["telegram:5001"] == "include"
            assert statuses["telegram:5004"] == "exclude"
            assert statuses["telegram:5002"] == "review"
            decide(conn, "telegram:5002", "include", "Проверенный технический вопрос", "synthetic-test", day=25)
            decide(conn, "telegram:5003", "include", "Проверенный ответ", "synthetic-test", day=25)
            docs, report = build_documents(conn)
            assert len(docs) == 2 and report["messages"] == 3
            assert {doc["source"] for doc in docs} == {"assignment", "discussion"}
            print("ok: повтор, условие Day25, отбор и отдельная ветка")

            # Частичный снимок не удаляет старые ID; исправление не меняет принятый текст.
            write_parts(source, [message(5002, "Исправленный вопрос", reply=7002)
                                 + message(5006, "Новое сообщение"), "", "", "", ""])
            second = import_snapshot(conn, source, "partial", 2, "2026-10-03T00:00:00+00:00", ["messages.html"])
            assert second["new"] == 1 and second["proposals"] == 1
            active = json.loads(conn.execute("SELECT record_json FROM accepted WHERE source_key='telegram:5002'").fetchone()[0])
            assert active["text"] == by_id[5002]["text"]
            docs, report = build_documents(conn)
            assert report["messages"] == 3 and report["pending_replacements"] == 1
            assert not any("Исправленный вопрос" in doc["text"] for doc in docs)
            assert dict(conn.execute("SELECT source_key,status FROM decisions"))["telegram:5006"] == "review"
            item = next(row for row in build_manifest(conn) if row["source_key"] == "telegram:5002")
            assert item["reply_to"] == 5001 and item["selected_version_hash"] == item["accepted_hash"]
            assert item["text_hash"] == hashlib.sha256(active["text"].encode()).hexdigest()
            assert item["pending_proposals"][0]["reply_to"] == 7002
            discussion = next(doc for doc in docs if doc["source"] == "discussion")
            assert discussion["assignment_link"] == 5001
            assert discussion["members"][0]["version_hash"] == item["accepted_hash"]
            try:
                decide(conn, "telegram:5002", "exclude", "Повторный фильтр", "synthetic-test")
                raise AssertionError("принятый текст исключён")
            except ValueError:
                pass
            print("ok: частичный снимок, старая версия и предложение замены")

            proposal = conn.execute("SELECT version_hash FROM proposals WHERE source_key='telegram:5002' AND status='pending'").fetchone()[0]
            try:
                accept_proposal(conn, "telegram:5002", proposal, "")
                raise AssertionError("замена принята без решения")
            except ValueError:
                pass
            accept_proposal(conn, "telegram:5002", proposal, "synthetic-user-decision")
            docs, report = build_documents(conn)
            assert any("Исправленный вопрос" in doc["text"] for doc in docs)
            assert report["pending_replacements"] == 0
            item = next(row for row in build_manifest(conn) if row["source_key"] == "telegram:5002")
            assert item["reply_to"] == 7002 and item["selected_version_hash"] == proposal
            assert item["pending_proposals"] == []
            discussion = next(doc for doc in docs if doc["source"] == "discussion")
            assert discussion["assignment_link"] is None
            assert discussion["members"][0]["version_hash"] == proposal
            print("ok: явное принятие замены")

            # Искусственный сбой после первой записи откатывает весь снимок.
            write_parts(source, [message(5007, "Новая запись") + message(5008, "Ещё запись"), "", "", "", ""])
            before = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            try:
                import_snapshot(conn, source, "interrupted", 3, "2026-10-04T00:00:00+00:00", ["messages.html"], fail_after=1)
                raise AssertionError("сбой не сработал")
            except RuntimeError:
                pass
            assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == before
            assert conn.execute("SELECT COUNT(*) FROM snapshots WHERE snapshot_id='interrupted'").fetchone()[0] == 0
            conn.close()
            conn = connect(root / "private" / "test.sqlite3")
            after = import_snapshot(conn, source, "interrupted", 3, "2026-10-04T00:00:00+00:00", ["messages.html"])
            assert after["new"] == 2
            print("ok: прерванный импорт, повторное открытие и восстановление")

            note = root / "MCP-STUDY.md"
            note.write_text("# Учёба\n## Понимание и полезные поправки для практики\nПервая заметка.\n## Следующее\n", encoding="utf-8")
            assert import_note(conn, note) == "added"
            first_note_hash = conn.execute("SELECT version_hash FROM accepted WHERE source_key='note:mcp-study:understanding'").fetchone()[0]
            note.write_text("# Учёба\n## Понимание и полезные поправки для практики\nИсправленная заметка.\n## Следующее\n", encoding="utf-8")
            assert import_note(conn, note) == "proposal"
            docs, _ = build_documents(conn)
            assert any(doc["source"] == "personal_note" and doc["text"] == "Первая заметка." for doc in docs)
            second_note_hash = conn.execute("SELECT version_hash FROM proposals WHERE source_key='note:mcp-study:understanding' AND status='pending'").fetchone()[0]
            accept_proposal(conn, "note:mcp-study:understanding", second_note_hash, "synthetic-user-decision")
            conn.close()
            conn = connect(root / "private" / "test.sqlite3")
            versions = dict(conn.execute("SELECT version_hash,record_json FROM note_versions WHERE source_key='note:mcp-study:understanding'"))
            assert len(versions) == 2 and first_note_hash in versions and second_note_hash in versions
            assert json.loads(versions[first_note_hash])["text"] == "Первая заметка."
            assert conn.execute("SELECT version_hash FROM accepted WHERE source_key='note:mcp-study:understanding'").fetchone()[0] == second_note_hash
            assert conn.execute("SELECT version_hash FROM accepted_history WHERE source_key='note:mcp-study:understanding'").fetchone()[0] == first_note_hash
            print("ok: обе версии заметки доступны после принятия и повторного открытия")
        finally:
            conn.close()

        test_forwarded_and_migration(root)
        attack = "![pixel](https://example.invalid/pixel)\n<script>unsafe</script>\n``````\nТекст целиком"
        rendered = inert_markdown(attack)
        fence = rendered.splitlines()[0][:-4]
        assert len(fence) > 6 and rendered == f"{fence}text\n{attack}\n{fence}"
        print("ok: Markdown preview инертен при ссылках, HTML и длинных backticks")


if __name__ == "__main__":
    run()
