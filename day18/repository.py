"""Единственная граница записи durable evidence Day 18."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from day18.config import PROFILE, MAX_CANDIDATE_BYTES, MAX_RESULT_BYTES
from day18.models import RunContext, Slot
from day18.store import Store, transition, utc_now

OUTPUT_SCHEMA = json.loads((Path(__file__).parent / "schemas/collect_output.json").read_text(encoding="utf-8"))
OUTPUT_VALIDATOR = Draft202012Validator(OUTPUT_SCHEMA, format_checker=FormatChecker())


def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def clip_bytes(value: str, limit: int) -> str:
    raw = value.encode("utf-8")[:limit]
    return raw.decode("utf-8", errors="ignore")


def _id() -> str:
    return str(uuid.uuid4())


def _validate_item(item: dict) -> None:
    if not isinstance(item, dict):
        raise ValueError("invalid RSS item")
    article_id = item.get("article_id")
    url = item.get("url")
    title = item.get("title")
    excerpt = item.get("rss_excerpt")
    if (not isinstance(article_id, str) or re.fullmatch(r"[0-9]{1,100}", article_id) is None
        or url != f"https://habr.com/ru/articles/{article_id}/"
        or not isinstance(title, str) or not title.strip() or len(title) > 240
        or not isinstance(excerpt, str) or len(excerpt) > 1000
        or item.get("eligibility") not in ("eligible", "out_of_profile")):
        raise ValueError("invalid RSS item")
    published = item.get("published_at_utc")
    if published is not None:
        if not isinstance(published, str) or not published.endswith("Z"):
            raise ValueError("invalid RSS date")
        try:
            datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("invalid RSS date") from error


def key_for(run_id: str, slot: Slot) -> str:
    return digest(f"{run_id}|{slot.profile}|{slot.period_start_utc}|{slot.period_end_utc}")


class Repository:
    def __init__(self, store: Store):
        self.store = store

    def get_or_create_run(self, slot: Slot, *, manual_invocation_id: str | None = None) -> RunContext:
        origin = "manual" if manual_invocation_id is not None else "scheduled"
        if origin == "manual":
            try:
                manual_invocation_id = str(uuid.UUID(manual_invocation_id))
            except (TypeError, ValueError) as error:
                raise ValueError("manual_invocation_id должен быть UUID") from error
        with self.store.tx() as db:
            if origin == "scheduled":
                db.execute(
                    "INSERT OR IGNORE INTO slots(profile,local_date,zone,instant_utc,period_start_utc,period_end_utc) "
                    "VALUES (?,?,?,?,?,?)",
                    (slot.profile, slot.local_date, slot.timezone, slot.instant_utc, slot.period_start_utc, slot.period_end_utc),
                )
                slot_id = db.execute(
                    "SELECT id,instant_utc,period_start_utc,period_end_utc FROM slots WHERE profile=? AND local_date=? AND zone=?",
                    (slot.profile, slot.local_date, slot.timezone),
                ).fetchone()
                if tuple(slot_id[k] for k in ("instant_utc", "period_start_utc", "period_end_utc")) != (
                    slot.instant_utc, slot.period_start_utc, slot.period_end_utc
                ):
                    raise RuntimeError("Slot identity изменена")
                row = db.execute("SELECT id,context_json FROM runs WHERE slot_id=?", (slot_id["id"],)).fetchone()
            else:
                slot_id = None
                row = db.execute("SELECT id,context_json FROM runs WHERE manual_invocation_id=?", (manual_invocation_id,)).fetchone()
            if row:
                saved = Slot(**json.loads(row["context_json"]))
                if saved != slot:
                    raise ValueError("Run identity нельзя использовать для другого slot")
                return RunContext(row["id"], saved, key_for(row["id"], saved), origin, origin == "manual")
            run_id = _id()
            now = utc_now()
            db.execute(
                "INSERT INTO runs(id,slot_id,origin,manual_invocation_id,no_send,context_json,state,created_utc,updated_utc) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (run_id, slot_id["id"] if slot_id else None, origin, manual_invocation_id,
                 int(origin == "manual"), compact(asdict(slot)), "STARTED", now, now),
            )
            return RunContext(run_id, slot, key_for(run_id, slot), origin, origin == "manual")

    def context(self, run_id: str) -> RunContext:
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            slot = Slot(**json.loads(row["context_json"]))
            return RunContext(run_id, slot, key_for(run_id, slot), row["origin"], bool(row["no_send"]))

    def run(self, run_id: str) -> sqlite3.Row:
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            return row

    def acquire_run_lease(self, run_id: str, owner: str, seconds: int = 600,
                          *, force_after_process_lock: bool = False) -> bool:
        with self.store.tx() as db:
            row = db.execute("SELECT lease_owner,lease_until_utc FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            if (not force_after_process_lock and row["lease_owner"] and row["lease_until_utc"]
                and row["lease_until_utc"] > utc_now()):
                return False
            deadline = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds").replace("+00:00", "Z")
            db.execute("UPDATE runs SET lease_owner=?,lease_until_utc=? WHERE id=?", (owner, deadline, run_id))
            return True

    def release_run_lease(self, run_id: str, owner: str) -> None:
        with self.store.tx() as db:
            db.execute("UPDATE runs SET lease_owner=NULL,lease_until_utc=NULL WHERE id=? AND lease_owner=?",
                       (run_id, owner))

    def set_state(self, run_id: str, target: str, *, stage: str | None = None,
                  reason: str | None = None, evidence: str | None = None) -> None:
        with self.store.tx() as db:
            transition(db, run_id, target, stage=stage, reason=reason, evidence_ref=evidence)

    def batch_for(self, run_id: str, key: str) -> dict | None:
        with self.store.connect() as db:
            row = db.execute("SELECT result_json FROM batches WHERE run_id=? AND idempotency_key=?", (run_id, key)).fetchone()
            return json.loads(row["result_json"]) if row else None

    def linked_tool_result(self, run_id: str) -> tuple[str, dict] | None:
        with self.store.connect() as db:
            row = db.execute("SELECT audit_call_id,result_json,outcome FROM tool_attempts WHERE run_id=? "
                             "AND tool_name='collect_habr_agent_cases' ORDER BY call_sequence DESC,request_ordinal DESC LIMIT 1",
                             (run_id,)).fetchone()
            if row is None or row["outcome"] != "accepted":
                return None
            return row["audit_call_id"], json.loads(row["result_json"])

    def reconcile_pending_tool(self, run_id: str, result: dict) -> None:
        with self.store.tx() as db:
            db.execute("UPDATE tool_attempts SET result_json=?,outcome='accepted',reason_code='reconciled' "
                       "WHERE run_id=? AND outcome='pending' AND tool_name='collect_habr_agent_cases'",
                       (compact(result), run_id))

    def interrupt_pending_model(self, run_id: str) -> None:
        with self.store.tx() as db:
            db.execute("UPDATE model_attempts SET outcome='interrupted',reason_code='process_lost',ended_utc=? "
                       "WHERE run_id=? AND outcome='pending'", (utc_now(), run_id))

    def begin_model_call(self, run_id: str, sequence: int) -> None:
        with self.store.tx() as db:
            row = db.execute("SELECT generation_attempt,model_calls FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None or row["model_calls"] >= 4 or row["model_calls"] + 1 != sequence:
                raise ValueError("Model call budget/sequence исчерпан")
            db.execute("UPDATE runs SET model_calls=model_calls+1 WHERE id=?", (run_id,))
            db.execute(
                "INSERT INTO model_attempts(id,run_id,generation_attempt,call_sequence,outcome,reason_code,usage_json,started_utc,ended_utc) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (_id(), run_id, row["generation_attempt"], sequence, "pending", None,
                 None, utc_now(), None),
            )

    def finish_model_call(self, run_id: str, sequence: int, outcome: str, *,
                          reason: str = "none", usage: dict | None = None) -> None:
        with self.store.tx() as db:
            changed = db.execute("UPDATE model_attempts SET outcome=?,reason_code=?,usage_json=?,ended_utc=? "
                                 "WHERE run_id=? AND call_sequence=? AND outcome='pending'",
                                 (outcome, reason, compact(usage) if usage is not None else None,
                                  utc_now(), run_id, sequence)).rowcount
            if changed != 1:
                raise ValueError("Model attempt не в pending")

    def begin_tool_attempt(self, run_id: str, sequence: int, ordinal: int, *, raw_call_id: str | None,
                           audit_call_id: str, name: str, arguments: object) -> None:
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO tool_attempts(id,run_id,call_sequence,request_ordinal,raw_call_id,audit_call_id,"
                "tool_name,arguments_digest,result_json,outcome,reason_code,at_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (_id(), run_id, sequence, ordinal, raw_call_id, audit_call_id, name,
                 digest(compact(arguments)), "{}", "pending", "none", utc_now()),
            )

    def finish_tool_attempt(self, run_id: str, sequence: int, ordinal: int,
                            result: dict, outcome: str, reason: str) -> None:
        with self.store.tx() as db:
            changed = db.execute("UPDATE tool_attempts SET result_json=?,outcome=?,reason_code=? "
                                 "WHERE run_id=? AND call_sequence=? AND request_ordinal=? AND outcome='pending'",
                                 (compact(result), outcome, reason, run_id, sequence, ordinal)).rowcount
            if changed != 1:
                raise ValueError("Tool attempt не в pending")

    def reserve_phase(self, run_id: str, phase: str, cap_ms: int) -> str:
        with self.store.tx() as db:
            run = db.execute("SELECT active_ms,attempt_active_ms,generation_attempt FROM runs WHERE id=?", (run_id,)).fetchone()
            if run is None:
                raise KeyError(run_id)
            if phase == "validation":
                used = db.execute("SELECT COALESCE(SUM(COALESCE(settled_ms,reserved_ms)),0) FROM phase_reservations "
                                  "WHERE run_id=? AND attempt=? AND phase='validation'",
                                  (run_id, run["generation_attempt"])).fetchone()[0]
                cap_ms = min(cap_ms, 60_000 - used)
            remaining = min(cap_ms, 960_000 - run["active_ms"], 480_000 - run["attempt_active_ms"])
            if remaining <= 0:
                raise ValueError("Active generation budget exhausted")
            reservation = _id()
            # AICODE-NOTE: списываем резерв до внешнего действия; crash не обнулит уже начатую фазу.
            db.execute("UPDATE runs SET active_ms=active_ms+?,attempt_active_ms=attempt_active_ms+? WHERE id=?",
                       (remaining, remaining, run_id))
            db.execute("INSERT INTO phase_reservations(id,run_id,phase,attempt,reserved_ms,started_utc) VALUES (?,?,?,?,?,?)",
                       (reservation, run_id, phase, run["generation_attempt"], remaining, utc_now()))
            return reservation

    def settle_phase(self, reservation: str, elapsed_ms: int) -> None:
        with self.store.tx() as db:
            row = db.execute("SELECT * FROM phase_reservations WHERE id=?", (reservation,)).fetchone()
            if row is None or row["settled_ms"] is not None:
                raise ValueError("Phase reservation неактивна")
            settled = min(max(0, elapsed_ms), row["reserved_ms"])
            refund = row["reserved_ms"] - settled
            db.execute("UPDATE phase_reservations SET settled_ms=?,ended_utc=? WHERE id=?", (settled, utc_now(), reservation))
            db.execute("UPDATE runs SET active_ms=active_ms-?,attempt_active_ms=attempt_active_ms-? WHERE id=?",
                       (refund, refund, row["run_id"]))

    def record_operator_action(self, run_id: str, *, actor: str, decision: str,
                               reason: str, evidence: str) -> None:
        if not actor.strip() or not reason.strip() or not evidence.strip():
            raise ValueError("Operator action требует actor/reason/evidence")
        with self.store.tx() as db:
            db.execute("INSERT INTO operator_resolutions(id,run_id,actor,at_utc,reason,evidence,decision) "
                       "VALUES (?,?,?,?,?,?,?)", (_id(), run_id, actor, utc_now(), reason, evidence, decision))

    def begin_generation_resume(self, run_id: str, *, actor: str) -> None:
        if not actor.strip():
            raise ValueError("Operator actor обязателен")
        with self.store.tx() as db:
            row = db.execute("SELECT state,generation_attempt FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None or row["state"] not in ("FAILED_BEFORE_DATA", "FAILED_AFTER_DATA") or row["generation_attempt"] != 1:
                raise ValueError("Generation resume не разрешён")
            db.execute("UPDATE runs SET generation_attempt=2,attempt_active_ms=0 WHERE id=?", (run_id,))
            db.execute("INSERT INTO operator_resolutions(id,run_id,actor,at_utc,reason,evidence,decision) "
                       "VALUES (?,?,?,?,?,?,?)", (_id(), run_id, actor, utc_now(), "explicit_resume",
                                             row["state"], "resume"))
            transition(db, run_id, "MCP_PENDING" if row["state"] == "FAILED_BEFORE_DATA" else "REPORT_PENDING",
                       stage="operator_resume", evidence_ref="explicit")

    def increment_mcp_execution(self, run_id: str) -> None:
        with self.store.tx() as db:
            row = db.execute("SELECT mcp_executions,generation_attempt FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None or row["mcp_executions"] >= min(2, row["generation_attempt"]):
                raise ValueError("MCP execution budget exhausted")
            db.execute("UPDATE runs SET mcp_executions=mcp_executions+1 WHERE id=?", (run_id,))

    def ingest(self, context: RunContext, tool_call_id: str, items: list[dict],
               rejections: list[dict], coverage: dict, feed_seen: int,
               reason_override: str | None = None) -> dict:
        """Один committed batch; повтор по key не читает RSS и не меняет evidence."""
        if feed_seen > 100 or len(items) + len(rejections) > 100:
            raise ValueError("RSS item cap")
        with self.store.tx() as db:
            existing = db.execute("SELECT result_json FROM batches WHERE run_id=? AND idempotency_key=?",
                                  (context.run_id, context.idempotency_key)).fetchone()
            if existing:
                return json.loads(existing[0])
            batch_id = _id()
            read_at = utc_now()
            counts = dict(feed_seen=feed_seen, in_period=0, new_observations=0,
                          repeated_articles=0, eligible_candidates=0, omitted_candidates=0,
                          invalid_entries=len(rejections), out_of_profile=0)
            db.execute(
                "INSERT INTO batches(id,run_id,idempotency_key,tool_call_id,period_start_utc,period_end_utc,"
                "read_at_utc,coverage_json,counts_json,result_json,committed_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (batch_id, context.run_id, context.idempotency_key, tool_call_id,
                 context.slot.period_start_utc, context.slot.period_end_utc, read_at,
                 compact(coverage), compact(counts), "{}", utc_now()),
            )
            candidates: list[dict] = []
            seen_ids: set[str] = set()
            for position, item in enumerate(items):
                _validate_item(item)
                canonical_id = item["article_id"]
                if canonical_id in seen_ids:
                    counts["repeated_articles"] += 1
                    continue
                seen_ids.add(canonical_id)
                published = item.get("published_at_utc")
                if published is None:
                    counts["invalid_entries"] += 1
                elif context.slot.period_start_utc <= published < context.slot.period_end_utc:
                    counts["in_period"] += 1
                else:
                    continue
                if item["eligibility"] == "out_of_profile":
                    counts["out_of_profile"] += 1
                article = db.execute("SELECT id FROM articles WHERE profile=? AND canonical_id=?",
                                     (PROFILE, canonical_id)).fetchone()
                rss_hash = digest(compact(item))
                if article is None:
                    db.execute("INSERT INTO articles(profile,canonical_id,canonical_url,first_seen_utc,latest_seen_utc,latest_rss_hash) "
                               "VALUES (?,?,?,?,?,?)",
                               (PROFILE, canonical_id, item["url"], read_at, read_at, rss_hash))
                    article_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                else:
                    article_id = article["id"]
                    db.execute("UPDATE articles SET latest_seen_utc=?,latest_rss_hash=? WHERE id=?",
                               (read_at, rss_hash, article_id))
                observation = db.execute("SELECT id FROM observations WHERE article_id=?", (article_id,)).fetchone()
                if observation is None:
                    observation_id = _id()
                    db.execute(
                        "INSERT INTO observations(id,article_id,first_batch_id,title,rss_excerpt,original_pubdate,"
                        "published_at_utc,seen_at_utc,evidence_hash,eligibility) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (observation_id, article_id, batch_id, item["title"], item["rss_excerpt"],
                         item.get("original_pubdate"), published, read_at, rss_hash, item["eligibility"]),
                    )
                    counts["new_observations"] += 1
                    if item["eligibility"] == "eligible":
                        counts["eligible_candidates"] += 1
                        candidates.append({
                            "article_id": canonical_id, "observation_id": observation_id,
                            "url": item["url"], "title": clip_bytes(item["title"], 512),
                            "rss_excerpt": clip_bytes(item["rss_excerpt"], 512), "published_at_utc": published,
                        })
                else:
                    observation_id = observation["id"]
                    counts["repeated_articles"] += 1
                db.execute("INSERT OR IGNORE INTO batch_members(batch_id,observation_id,ordinal) VALUES (?,?,?)",
                           (batch_id, observation_id, position))
            for rejection in rejections:
                db.execute("INSERT INTO source_rejections(batch_id,feed_ordinal,reason_code,evidence_hash) VALUES (?,?,?,?)",
                           (batch_id, rejection["ordinal"], rejection["reason_code"], rejection["evidence_hash"]))
            if counts["invalid_entries"] or coverage["kind"] != "complete_for_profile":
                status = "partial_coverage"
                reason = reason_override or ("invalid_entries" if counts["invalid_entries"] else
                                             "feed_limit" if coverage["feed_limit_hit"] else "oversize")
                coverage["kind"] = "partial"
                coverage["window_complete"] = False
            elif counts["new_observations"] == 0:
                status = "success_empty"
                reason = "no_feed_entries" if feed_seen == 0 else "no_new_entries"
            elif counts["eligible_candidates"] == 0:
                status = "success_no_matching_cases"
                reason = "no_eligible_candidates"
            else:
                status = "success_with_items"
                reason = "none"
            candidates = candidates[:10]
            while candidates and len(compact(candidates).encode("utf-8")) > MAX_CANDIDATE_BYTES:
                candidates.pop()
            counts["omitted_candidates"] = max(0, counts["eligible_candidates"] - len(candidates))
            result = {
                "status": status, "run_id": context.run_id, "batch_id": batch_id,
                "source_profile_id": PROFILE, "period_start_utc": context.slot.period_start_utc,
                "period_end_utc": context.slot.period_end_utc, "read_at_utc": read_at,
                "counts": counts, "coverage": coverage, "candidates": candidates,
                "reason_code": reason,
            }
            if list(OUTPUT_VALIDATOR.iter_errors(result)):
                raise ValueError("invalid committed MCP result")
            if len(compact(result).encode("utf-8")) > MAX_RESULT_BYTES:
                raise ValueError("MCP result exceeds size cap")
            db.execute("UPDATE batches SET coverage_json=?,counts_json=?,result_json=? WHERE id=?",
                       (compact(coverage), compact(counts), compact(result), batch_id))
            return result

    def report_pool(self, run_id: str) -> tuple[list[dict], list[dict]]:
        """Новые и oldest backlog, без чужих claims и обработанного мусора."""
        with self.store.connect() as db:
            row = db.execute("SELECT id FROM batches WHERE run_id=? ORDER BY committed_utc DESC LIMIT 1", (run_id,)).fetchone()
            batch_id = row["id"] if row else None
            query = """
                SELECT o.id AS observation_id,o.title,o.rss_excerpt,o.published_at_utc,
                       a.canonical_id AS article_id,a.canonical_url AS url,
                       s.local_date AS origin_slot,o.first_batch_id
                  FROM observations o JOIN articles a ON a.id=o.article_id
                  JOIN batches b ON b.id=o.first_batch_id
                  LEFT JOIN runs r ON r.id=b.run_id LEFT JOIN slots s ON s.id=r.slot_id
                 WHERE o.eligibility='eligible'
                   AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.observation_id=o.id
                                   AND c.state IN ('owned','delivered','quarantined'))
                   AND NOT EXISTS (SELECT 1 FROM classifications c WHERE c.observation_id=o.id
                                   AND c.disposition='processed_out_of_scope')
            """
            rows = [dict(row) for row in db.execute(query)]
        new = [r for r in rows if r["first_batch_id"] == batch_id]
        backlog = [r for r in rows if r["first_batch_id"] != batch_id]
        new.sort(key=lambda r: (r["published_at_utc"] is None,
                                -datetime.fromisoformat(r["published_at_utc"].replace("Z", "+00:00")).timestamp()
                                if r["published_at_utc"] else 0, r["article_id"]))
        backlog.sort(key=lambda r: (r["origin_slot"] or "9999-12-31",
                                    r["published_at_utc"] is None,
                                    -datetime.fromisoformat(r["published_at_utc"].replace("Z", "+00:00")).timestamp()
                                    if r["published_at_utc"] else 0, r["article_id"]))
        return new, backlog
