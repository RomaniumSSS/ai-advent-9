"""Глобальная очередь публикации; неизвестная доставка не повторяется."""

from __future__ import annotations

import json
import fcntl
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
import time
from datetime import date, datetime, timedelta, timezone
from typing import Protocol

from day18.config import MAX_PAYLOAD_CHARS, PROFILE
from day18.models import DeliveryOutcome
from day18.repository import Repository, digest
from day18.store import transition, utc_now

_HABR_LINK = re.compile(r"https://habr\.com/ru/articles/[0-9]+/")


class Transport(Protocol):
    def fingerprint(self) -> str: ...
    def prepare(self) -> None: ...
    def send(self, payload: str) -> DeliveryOutcome: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, "redirect rejected", headers, fp)


class TelegramTransport:
    def __init__(self, token_env: str = "DAY18_TELEGRAM_BOT_TOKEN",
                 chat_env: str = "DAY18_TELEGRAM_CHAT_ID"):
        self.token_env = token_env
        self.chat_env = chat_env
        self._token: str | None = None
        self._chat: str | None = None
        self._expected_fingerprint: str | None = None

    def fingerprint(self) -> str:
        import os
        chat = os.environ.get(self.chat_env, "")
        if not chat:
            raise ValueError("recipient_missing")
        self._expected_fingerprint = digest(chat)
        return self._expected_fingerprint

    def prepare(self) -> None:
        import os
        token = os.environ.get(self.token_env, "")
        chat = os.environ.get(self.chat_env, "")
        if not token or not chat:
            raise ValueError("telegram_config_missing")
        if digest(chat) != self._expected_fingerprint:
            raise ValueError("recipient_changed")
        self._token, self._chat = token, chat

    def send(self, payload: str) -> DeliveryOutcome:
        if not self._token or not self._chat:
            return DeliveryOutcome("pre_send", safe_reason="telegram_config_missing")
        data = urllib.parse.urlencode({"chat_id": self._chat, "text": payload,
                                        "disable_web_page_preview": "true"}).encode()
        request = urllib.request.Request(f"https://api.telegram.org/bot{self._token}/sendMessage", data=data)
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            with opener.open(request, timeout=15) as response:
                raw = response.read(32_768)
                if response.status >= 500:
                    return DeliveryOutcome("unknown", safe_reason="api_5xx")
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500:
                try:
                    response = json.loads(error.read(32_768))
                    if response.get("ok") is False and response.get("error_code") == error.code:
                        return DeliveryOutcome("definitive_rejection", safe_reason="api_rejection")
                except (ValueError, UnicodeDecodeError):
                    pass
            return DeliveryOutcome("unknown", safe_reason="api_uncertain")
        except (TimeoutError, urllib.error.URLError, OSError):
            return DeliveryOutcome("unknown", safe_reason="request_uncertain")
        try:
            response = json.loads(raw)
            message_id = response["result"]["message_id"]
            if response["ok"] is True and type(message_id) is int and message_id > 0:
                return DeliveryOutcome("receipt", message_id=message_id)
        except (ValueError, KeyError, TypeError):
            pass
        return DeliveryOutcome("unknown", safe_reason="receipt_missing")


def _attempt_count(db, report_id: str) -> int:
    return db.execute("SELECT COUNT(*) FROM delivery_attempts WHERE report_id=?", (report_id,)).fetchone()[0]


def _report_by_id(db, report_id: str):
    return db.execute("SELECT r.*,u.state,u.no_send,s.local_date,s.profile FROM reports r "
                      "JOIN runs u ON u.id=r.run_id LEFT JOIN slots s ON s.id=u.slot_id WHERE r.id=?", (report_id,)).fetchone()


def _validate_payload(db, report) -> None:
    payload = report["payload"]
    if digest(payload) != report["payload_hash"] or len(payload) > MAX_PAYLOAD_CHARS:
        raise ValueError("payload_hash_or_size")
    members = db.execute("SELECT m.*,a.canonical_url FROM report_members m JOIN observations o ON o.id=m.observation_id "
                         "JOIN articles a ON a.id=o.article_id WHERE m.report_id=?", (report["id"],)).fetchall()
    displayed = [row for row in members if row["displayed_in_payload"]]
    if len(displayed) != report["payload_displayed"] or len(displayed) > 2:
        raise ValueError("displayed_count")
    if any(row["category"] not in ("confirmed_described_case", "possible_case") for row in members):
        raise ValueError("invalid_membership")
    links = _HABR_LINK.findall(payload)
    expected = [row["canonical_url"] for row in displayed]
    all_urls = re.findall(r"https?://[^\s]+", payload)
    if len(links) != len(expected) or set(links) != set(expected) or set(all_urls) != set(expected):
        raise ValueError("unexpected_article_reference")
    if any(row["category"] == "possible_case" for row in displayed) and "Возможный кейс" not in payload:
        raise ValueError("possible_unmarked")


def _mark_receipt(db, report, attempt_id: str, message_id: int) -> None:
    db.execute("UPDATE delivery_attempts SET ended_utc=?,api_status='accepted',message_id=?,proof_class='receipt' WHERE id=?",
               (utc_now(), message_id, attempt_id))
    for row in db.execute("SELECT observation_id,displayed_in_payload FROM report_members WHERE report_id=?", (report["id"],)):
        state = "delivered" if row["displayed_in_payload"] else "released"
        db.execute("UPDATE claims SET state=?,changed_utc=?,evidence=? WHERE report_id=? AND observation_id=? AND state IN ('owned','quarantined')",
                   (state, utc_now(), f"message_id:{message_id}", report["id"], row["observation_id"]))
    transition(db, report["run_id"], "DELIVERED", stage="telegram", evidence_ref=f"message_id:{message_id}")
    _advance_checkpoint(db, report)


def _advance_checkpoint(db, report) -> None:
    if report["local_date"] is None:
        return
    fingerprint = db.execute("SELECT recipient_fingerprint FROM delivery_attempts WHERE report_id=? ORDER BY attempt_no DESC LIMIT 1",
                             (report["id"],)).fetchone()[0]
    current = db.execute("SELECT slot_date FROM delivery_checkpoints WHERE profile=? AND recipient_fingerprint=?",
                         (report["profile"], fingerprint)).fetchone()
    delivered = db.execute("SELECT s.local_date,r.id FROM reports r JOIN runs u ON u.id=r.run_id "
                           "JOIN slots s ON s.id=u.slot_id WHERE s.profile=? AND u.state='DELIVERED' "
                           "ORDER BY s.local_date", (report["profile"],)).fetchall()
    dates = {row["local_date"]: row["id"] for row in delivered}
    if not dates:
        return
    if current and current["slot_date"]:
        cursor = date.fromisoformat(current["slot_date"]) + timedelta(days=1)
        latest = current["slot_date"]
    else:
        earliest = db.execute("SELECT MIN(local_date) FROM slots WHERE profile=?", (report["profile"],)).fetchone()[0]
        cursor = date.fromisoformat(earliest)
        latest = None
    while cursor.isoformat() in dates:
        latest = cursor.isoformat()
        cursor += timedelta(days=1)
    if latest and (not current or latest != current["slot_date"]):
        db.execute("INSERT INTO delivery_checkpoints(profile,recipient_fingerprint,slot_date,report_id,changed_utc) "
                   "VALUES (?,?,?,?,?) ON CONFLICT(profile,recipient_fingerprint) DO UPDATE SET "
                   "slot_date=excluded.slot_date,report_id=excluded.report_id,changed_utc=excluded.changed_utc",
                   (report["profile"], fingerprint, latest, dates[latest], utc_now()))


class Dispatcher:
    def __init__(self, repo: Repository, transport: Transport):
        self.repo = repo
        self.transport = transport

    def recover_inflight(self) -> None:
        with self.repo.store.tx() as db:
            gate = db.execute("SELECT * FROM send_gate WHERE id=1").fetchone()
            if not gate["report_id"] or gate["lease_until_utc"] > utc_now():
                return
            report = _report_by_id(db, gate["report_id"])
            if report and report["state"] == "SENDING":
                attempt = db.execute("SELECT * FROM delivery_attempts WHERE report_id=? ORDER BY attempt_no DESC LIMIT 1",
                                     (report["id"],)).fetchone()
                target = "DELIVERY_UNKNOWN" if attempt["request_started_utc"] else "FAILED_BEFORE_SEND"
                proof = "unknown" if attempt["request_started_utc"] else "pre_send"
                db.execute("UPDATE delivery_attempts SET ended_utc=?,proof_class=?,reason_code='process_lost' WHERE id=?",
                           (utc_now(), proof, attempt["id"]))
                transition(db, report["run_id"], target, stage="recovery", reason="process_lost", evidence_ref=attempt["id"])
            db.execute("UPDATE send_gate SET report_id=NULL,owner=NULL,lease_until_utc=NULL WHERE id=1")

    def dispatch_once(self) -> str | None:
        lock_path = self.repo.store.path.with_name(self.repo.store.path.name + ".send.lock")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return None
            return self._dispatch_owned()
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _dispatch_owned(self) -> str | None:
        self.recover_inflight()
        fingerprint = self.transport.fingerprint()
        with self.repo.store.tx() as db:
            gate = db.execute("SELECT report_id FROM send_gate WHERE id=1").fetchone()
            if gate["report_id"]:
                return None
            pending = db.execute(
                "SELECT r.id,u.state FROM reports r JOIN runs u ON u.id=r.run_id "
                "JOIN slots s ON s.id=u.slot_id WHERE r.retired=0 AND u.no_send=0 "
                "AND u.state IN ('REPORT_READY','FAILED_BEFORE_SEND','DELIVERY_FAILED','DELIVERY_UNKNOWN') "
                "AND NOT EXISTS (SELECT 1 FROM operator_resolutions x WHERE x.run_id=u.id AND x.decision='quarantine') "
                "ORDER BY s.local_date,r.created_utc LIMIT 1"
            ).fetchone()
            if pending is None:
                return None
            pinned = db.execute("SELECT recipient_fingerprint FROM publication_config WHERE profile=?", (PROFILE,)).fetchone()
            if pinned and pinned["recipient_fingerprint"] != fingerprint:
                raise ValueError("recipient fingerprint changed")
            if pinned is None:
                db.execute("INSERT INTO publication_config(profile,recipient_fingerprint,recorded_utc) VALUES (?,?,?)",
                           (PROFILE, fingerprint, utc_now()))
            report = _report_by_id(db, pending["id"])
            prior = db.execute("SELECT recipient_fingerprint FROM delivery_attempts WHERE report_id=? LIMIT 1",
                               (report["id"],)).fetchone()
            if prior and prior["recipient_fingerprint"] != fingerprint:
                raise ValueError("retry recipient differs from frozen report")
            latest = db.execute("SELECT proof_class FROM delivery_attempts WHERE report_id=? ORDER BY attempt_no DESC LIMIT 1",
                                (report["id"],)).fetchone()
            if (report["state"] == "FAILED_BEFORE_SEND" and latest and latest["proof_class"] == "pre_send"
                and _attempt_count(db, report["id"]) < 2):
                transition(db, report["run_id"], "REPORT_READY", stage="auto_presend_retry", evidence_ref=report["id"])
                report = _report_by_id(db, report["id"])
            if report["state"] != "REPORT_READY":
                return None
            if _attempt_count(db, report["id"]) >= 2:
                return None
            if report["dispatch_active_ms"] + 15_000 > 60_000:
                return None
            try:
                _validate_payload(db, report)
            except ValueError:
                transition(db, report["run_id"], "FAILED_BEFORE_SEND", stage="adapter_guard", reason="invalid_payload")
                return None
            attempt_id = str(uuid.uuid4())
            number = _attempt_count(db, report["id"]) + 1
            db.execute("INSERT INTO delivery_attempts(id,report_id,attempt_no,recipient_fingerprint,payload_hash,started_utc) "
                       "VALUES (?,?,?,?,?,?)", (attempt_id, report["id"], number, fingerprint,
                                                 report["payload_hash"], utc_now()))
            db.execute("UPDATE reports SET dispatch_active_ms=dispatch_active_ms+15000 WHERE id=?", (report["id"],))
            deadline = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(timespec="seconds").replace("+00:00", "Z")
            db.execute("UPDATE send_gate SET report_id=?,owner=?,lease_until_utc=? WHERE id=1",
                       (report["id"], attempt_id, deadline))
            transition(db, report["run_id"], "SENDING", stage="telegram", evidence_ref=attempt_id)
        started = time.monotonic()
        try:
            self.transport.prepare()
        except Exception:
            outcome = DeliveryOutcome("pre_send", safe_reason="transport_prepare_failed")
        else:
            with self.repo.store.tx() as db:
                current = db.execute("SELECT report_id,owner FROM send_gate WHERE id=1").fetchone()
                state = db.execute("SELECT state FROM runs WHERE id=?", (report["run_id"],)).fetchone()[0]
                if current["owner"] != attempt_id or current["report_id"] != report["id"] or state != "SENDING":
                    return None
                db.execute("UPDATE delivery_attempts SET request_started_utc=? WHERE id=?", (utc_now(), attempt_id))
            try:
                outcome = self.transport.send(report["payload"])
            except Exception:
                outcome = DeliveryOutcome("unknown", safe_reason="transport_uncertain")
            if outcome.kind == "pre_send":
                outcome = DeliveryOutcome("unknown", safe_reason="transport_uncertain")
        with self.repo.store.tx() as db:
            report = _report_by_id(db, report["id"])
            settled = min(15_000, max(0, int((time.monotonic() - started) * 1000)))
            db.execute("UPDATE delivery_attempts SET settled_ms=? WHERE id=?", (settled, attempt_id))
            db.execute("UPDATE reports SET dispatch_active_ms=dispatch_active_ms-? WHERE id=?",
                       (15_000 - settled, report["id"]))
            if outcome.kind == "receipt" and type(outcome.message_id) is int and outcome.message_id > 0:
                _mark_receipt(db, report, attempt_id, outcome.message_id)
            else:
                target = {"pre_send": "FAILED_BEFORE_SEND", "definitive_rejection": "DELIVERY_FAILED",
                          "unknown": "DELIVERY_UNKNOWN"}.get(outcome.kind, "DELIVERY_UNKNOWN")
                db.execute("UPDATE delivery_attempts SET ended_utc=?,api_status=?,proof_class=?,reason_code=? WHERE id=?",
                           (utc_now(), target, outcome.kind, outcome.safe_reason, attempt_id))
                if report["state"] != target:
                    transition(db, report["run_id"], target, stage="telegram", reason=outcome.safe_reason,
                               evidence_ref=attempt_id)
            db.execute("UPDATE send_gate SET report_id=NULL,owner=NULL,lease_until_utc=NULL WHERE id=1 AND owner=?",
                       (attempt_id,))
        return outcome.kind

    def resolve_unknown(self, run_id: str, *, actor: str, reason: str, evidence: str,
                        decision: str, message_id: int | None = None) -> None:
        if not actor.strip() or not reason.strip() or not evidence.strip():
            raise ValueError("Operator evidence обязателен")
        with self.repo.store.tx() as db:
            report = db.execute("SELECT * FROM reports WHERE run_id=?", (run_id,)).fetchone()
            run = db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
            if not report or not run or run["state"] != "DELIVERY_UNKNOWN":
                raise ValueError("Нет unresolved unknown")
            attempt = db.execute("SELECT * FROM delivery_attempts WHERE report_id=? ORDER BY attempt_no DESC LIMIT 1", (report["id"],)).fetchone()
            if decision == "delivered":
                if type(message_id) is not int or message_id <= 0 or not evidence.startswith("telegram:message_id:"):
                    raise ValueError("Нужен verified Telegram message_id")
                full = _report_by_id(db, report["id"])
                _mark_receipt(db, full, attempt["id"], message_id)
            elif decision == "negative":
                if not evidence.startswith(f"telegram:negative:{attempt['id']}:{attempt['payload_hash']}"):
                    raise ValueError("Нужен authoritative linked negative acknowledgement")
                db.execute("INSERT INTO operator_resolutions(id,run_id,attempt_id,actor,at_utc,reason,evidence,decision) "
                           "VALUES (?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), run_id, attempt["id"], actor,
                                                       utc_now(), reason, evidence, decision))
                transition(db, run_id, "DELIVERY_FAILED", stage="operator", reason="negative_proof", evidence_ref=attempt["id"])
            elif decision == "quarantine":
                db.execute("UPDATE claims SET state='quarantined',changed_utc=?,evidence=? WHERE report_id=? AND state='owned'",
                           (utc_now(), "operator_quarantine", report["id"]))
            else:
                raise ValueError("Недопустимое resolution")
            if decision != "negative":
                db.execute("INSERT INTO operator_resolutions(id,run_id,attempt_id,actor,at_utc,reason,evidence,decision) "
                           "VALUES (?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), run_id, attempt["id"], actor,
                                                       utc_now(), reason, evidence, decision))

    def retry_definitive(self, run_id: str, *, actor: str, reason: str, evidence: str) -> None:
        if not actor or not reason or not evidence:
            raise ValueError("Operator proof обязателен")
        with self.repo.store.tx() as db:
            report = db.execute("SELECT * FROM reports WHERE run_id=?", (run_id,)).fetchone()
            run = db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
            if not report or run["state"] != "DELIVERY_FAILED" or _attempt_count(db, report["id"]) >= 2:
                raise ValueError("Retry запрещён")
            attempt = db.execute("SELECT * FROM delivery_attempts WHERE report_id=? ORDER BY attempt_no DESC LIMIT 1", (report["id"],)).fetchone()
            if attempt["proof_class"] != "definitive_rejection" and not db.execute(
                "SELECT 1 FROM operator_resolutions WHERE run_id=? AND decision='negative'", (run_id,)
            ).fetchone():
                raise ValueError("Нет definitive proof")
            db.execute("INSERT INTO operator_resolutions(id,run_id,attempt_id,actor,at_utc,reason,evidence,decision) "
                       "VALUES (?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), run_id, attempt["id"], actor,
                                                   utc_now(), reason, evidence, "retry"))
            transition(db, run_id, "REPORT_READY", stage="operator_retry", evidence_ref=attempt["id"])

    def retire(self, run_id: str, *, actor: str, reason: str, evidence: str) -> None:
        if not actor or not reason or not evidence:
            raise ValueError("Operator evidence обязателен")
        with self.repo.store.tx() as db:
            report = db.execute("SELECT * FROM reports WHERE run_id=?", (run_id,)).fetchone()
            run = db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
            if not report or run["state"] not in ("FAILED_BEFORE_SEND", "DELIVERY_FAILED"):
                raise ValueError("Retirement запрещён")
            db.execute("UPDATE reports SET retired=1 WHERE id=?", (report["id"],))
            db.execute("UPDATE claims SET state='released',changed_utc=?,evidence=? WHERE report_id=? AND state IN ('owned','quarantined')",
                       (utc_now(), "operator_retirement", report["id"]))
            db.execute("INSERT INTO operator_resolutions(id,run_id,actor,at_utc,reason,evidence,decision) "
                       "VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), run_id, actor, utc_now(), reason, evidence, "retire"))
