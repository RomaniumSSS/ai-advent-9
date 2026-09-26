"""Локальные contract/fault проверки без внешней модели, RSS и Telegram."""

from __future__ import annotations

import json
import io
import fcntl
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path

from day18.agent import Agent, ModelResponse
from day18.cli import main as cli_main
from day18.delivery import Dispatcher, TelegramTransport
from day18.config import MAX_FEED_BYTES
from day18.mcp_client import McpConfig
from day18.mcp_client import discover, execute
from day18.models import DeliveryOutcome
from day18.repository import Repository, compact
from day18.report import commit_report, render, select_pool, validate_draft, worst_case_bytes
from day18.rss_mcp_server import collect, parse_feed
from day18.scheduler import slot_for
from day18.store import Store, transition, utc_now
from day18.tool_calling import INPUT_SCHEMA, ToolRuntime, proposals


def fixture_feed(count: int = 3) -> bytes:
    items = [
        ("101", "Компания внедрила ИИ-агента для поддержки клиентов",
         "Компания запустила пилот: агент обрабатывает обращения клиентов.", "Sat, 26 Sep 2026 12:00:00 GMT"),
        ("102", "Банк использует ИИ-агента для продаж",
         "Банк внедрил агента: агент анализирует заявки клиентов.", "Sat, 26 Sep 2026 11:00:00 GMT"),
        ("103", "Предприятие запустило ИИ-агента в логистике",
         "Предприятие использует агента: агент планирует маршруты.", "Sat, 26 Sep 2026 10:00:00 GMT"),
    ][:count]
    items.append(("100", "Старая публикация об агенте", "Старый материал об агенте.", "Fri, 25 Sep 2026 15:00:00 GMT"))
    body = "".join(f"<item><title>{title}</title><link>https://habr.com/ru/articles/{number}/</link>"
                   f"<description>{description}</description><pubDate>{published}</pubDate></item>"
                   for number, title, description, published in items)
    return f"<rss version='2.0'><channel>{body}</channel></rss>".encode()


class FakeProvider:
    visible_budget = 8192

    def __init__(self, repo: Repository, context):
        self.repo, self.context = repo, context
        self.calls = 0
        self.second_messages = None
        self.second_max_tokens = None

    def complete(self, messages, *, tools, max_tokens, tool_choice):
        self.calls += 1
        if self.calls == 1:
            return ModelResponse({"tool_calls": [{"id": "call-1", "function": {
                "name": "collect_habr_agent_cases", "arguments": compact(self.context.tool_arguments())}}]})
        self.second_messages = messages
        self.second_max_tokens = max_tokens
        request = json.loads(messages[-1]["content"])
        selected = request["model_seen"]
        entries = [{"observation_id": row["observation_id"], "category": "confirmed_described_case",
                    "evidence_refs": ["title", "rss_excerpt"], "summary": "Пилот описан в RSS.",
                    "metric_claims": []} for row in selected]
        draft = {"run_id": self.context.run_id, "outcome": "cases_found",
                 "coverage_label": "partial" if request["analysis_omitted"] else "complete_for_profile", "entries": entries,
                 "proposed_text": "Обзор описанных применений."}
        return ModelResponse({"content": compact(draft)})


class DraftOnlyProvider:
    visible_budget = 8192

    def __init__(self, context):
        self.context = context
        self.calls = 0

    def complete(self, messages, *, tools, max_tokens, tool_choice):
        self.calls += 1
        if tools:
            raise AssertionError("MCP/model call 1 must not repeat")
        selected = json.loads(messages[-1]["content"])["model_seen"]
        entries = [{"observation_id": row["observation_id"], "category": "confirmed_described_case",
                    "evidence_refs": ["title", "rss_excerpt"], "summary": "Кейс описан.",
                    "metric_claims": []} for row in selected]
        return ModelResponse({"content": compact({"run_id": self.context.run_id,
                            "outcome": "cases_found", "coverage_label": "complete_for_profile",
                            "entries": entries, "proposed_text": "Сводка после восстановления."})})


class FakeTransport:
    def __init__(self, outcome="receipt"):
        self.outcome = outcome
        self.payloads = []

    def fingerprint(self):
        return "f" * 64

    def prepare(self):
        return None

    def send(self, payload):
        self.payloads.append(payload)
        return DeliveryOutcome(self.outcome, 123 if self.outcome == "receipt" else None)


class PreSendOnce(FakeTransport):
    def __init__(self):
        super().__init__()
        self.prepares = 0

    def prepare(self):
        self.prepares += 1
        if self.prepares == 1:
            raise ValueError("no bytes left process")


class SlowTransport(FakeTransport):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def send(self, payload):
        self.entered.set()
        if not self.release.wait(3):
            raise TimeoutError("fixture timeout")
        return super().send(payload)


class Day18OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "day18.sqlite3")
        self.store.migrate()
        self.repo = Repository(self.store)
        self.context = self.repo.get_or_create_run(slot_for(date(2026, 9, 26)))

    def tearDown(self):
        self.tmp.cleanup()

    def make_agent(self, transport=None):
        provider = FakeProvider(self.repo, self.context)
        tools = ToolRuntime(self.repo, McpConfig("unused", ()),
                            discover_fn=lambda _: [{"name": "collect_habr_agent_cases",
                                                    "description": "fixed RSS", "input_schema": INPUT_SCHEMA}],
                            execute_fn=lambda _, __, args: collect(self.repo, args, lambda: fixture_feed()))
        dispatcher = Dispatcher(self.repo, transport) if transport else None
        return Agent(self.repo, provider, tools, dispatcher), provider

    def test_scheduled_identity_and_batch_replay(self):
        same = self.repo.get_or_create_run(self.context.slot)
        self.assertEqual(self.context.run_id, same.run_id)
        feed = fixture_feed()
        items, rejected, coverage, seen = parse_feed(feed, self.context)
        first = self.repo.ingest(self.context, "call-a", items, rejected, coverage, seen)
        second = self.repo.ingest(self.context, "call-b", [], [], coverage, 0)
        self.assertEqual(first, second)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batches").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 3)

    def test_company_article_rss_link_uses_same_canonical_id(self):
        feed = fixture_feed(1).replace(b"https://habr.com/ru/articles/101/",
                                       b"https://habr.com/ru/companies/tbank/articles/101/")
        items, rejected, _, _ = parse_feed(feed, self.context)
        self.assertEqual(rejected, [])
        self.assertEqual(items[0]["article_id"], "101")
        self.assertEqual(items[0]["url"], "https://habr.com/ru/articles/101/")

    def test_batch_failure_rolls_back_articles_observations_and_coverage(self):
        items, rejected, coverage, seen = parse_feed(fixture_feed(1), self.context)
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER fixture_batch_abort BEFORE INSERT ON batch_members "
                       "BEGIN SELECT RAISE(ABORT,'simulated crash'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)
        with self.store.connect() as db:
            for table in ("batches", "articles", "observations", "batch_members"):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
            db.execute("DROP TRIGGER fixture_batch_abort")
        self.assertEqual(self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)["status"],
                         "success_with_items")

    def test_repeated_article_in_next_period_is_not_new(self):
        items, rejected, coverage, seen = parse_feed(fixture_feed(1), self.context)
        self.assertEqual(self.repo.ingest(self.context, "first", items, rejected, coverage, seen)["status"],
                         "success_with_items")
        later = self.repo.get_or_create_run(slot_for(date(2026, 9, 27)))
        items2, rejected2, coverage2, seen2 = parse_feed(fixture_feed(1), later)
        result = self.repo.ingest(later, "second", items2, rejected2, coverage2, seen2)
        self.assertEqual((result["status"], result["reason_code"]), ("success_empty", "no_new_entries"))
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 1)

    def test_agent_linked_result_and_two_article_cap(self):
        transport = FakeTransport()
        agent, provider = self.make_agent(transport)
        self.assertEqual(agent.run(self.context), "DELIVERED")
        self.assertEqual(provider.calls, 2)
        self.assertEqual([m["role"] for m in provider.second_messages], ["system", "user", "assistant", "tool", "user"])
        self.assertIn('"required":["run_id","outcome","coverage_label","entries","proposed_text"]',
                      provider.second_messages[0]["content"])
        self.assertIn("ровно одну entries-запись", provider.second_messages[0]["content"])
        self.assertEqual(len(transport.payloads), 1)
        self.assertEqual(transport.payloads[0].count("https://habr.com/ru/articles/"), 2)
        with self.store.connect() as db:
            report = db.execute("SELECT * FROM reports").fetchone()
            self.assertEqual(report["payload_displayed"], 2)
            self.assertEqual(report["payload_omitted"], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM report_members").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM claims WHERE state='released'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM claim_events").fetchone()[0], 6)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE reports SET payload='tampered' WHERE id=?", (report["id"],))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE batches SET result_json='{}'")
        self.assertEqual(agent.run(self.context), "DELIVERED")
        self.assertEqual(provider.calls, 2)

    def test_invalid_real_style_draft_keeps_safe_failure_code(self):
        agent, provider = self.make_agent()
        original = provider.complete

        def bad_second(messages, *, tools, max_tokens, tool_choice):
            response = original(messages, tools=tools, max_tokens=max_tokens, tool_choice=tool_choice)
            return ModelResponse({"content": "not JSON"}) if not tools else response

        provider.complete = bad_second
        self.assertEqual(agent.run(self.context), "FAILED_AFTER_DATA")
        self.assertEqual(self.repo.run(self.context.run_id)["reason_code"], "draft_invalid_json")

    def test_schema_failure_records_validator_only(self):
        agent, provider = self.make_agent()
        original = provider.complete

        def bad_second(messages, *, tools, max_tokens, tool_choice):
            response = original(messages, tools=tools, max_tokens=max_tokens,
                                tool_choice=tool_choice)
            if tools:
                return response
            draft = json.loads(response.message["content"])
            del draft["entries"][0]["metric_claims"]
            return ModelResponse({"content": compact(draft)})

        provider.complete = bad_second
        self.assertEqual(agent.run(self.context), "FAILED_AFTER_DATA")
        self.assertEqual(self.repo.run(self.context.run_id)["reason_code"], "draft_schema_required")

    def test_cli_manual_resume_needs_no_telegram_recipient(self):
        manual = self.repo.get_or_create_run(
            self.context.slot, manual_invocation_id="00000000-0000-4000-8000-000000000001")
        self.repo.set_state(manual.run_id, "MCP_PENDING")
        self.repo.set_state(manual.run_id, "FAILED_BEFORE_DATA", reason="fixture")
        argv = ["--db", str(self.store.path), "--model", "deepseek/deepseek-v4.1-flash",
                "resume", manual.run_id, "--actor", "test"]
        with patch("day18.cli.OpenRouterProvider"), \
             patch("day18.cli.Agent.run", return_value="MCP_PENDING"), \
             patch.object(Dispatcher, "dispatch_once", side_effect=AssertionError("unexpected dispatch")), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(cli_main(argv), 0)
        resumed = self.repo.run(manual.run_id)
        self.assertEqual(resumed["generation_attempt"], 2)
        self.assertEqual(resumed["state"], "MCP_PENDING")

    def test_unknown_blocks_and_does_not_retry(self):
        transport = FakeTransport("unknown")
        agent, provider = self.make_agent(transport)
        self.assertEqual(agent.run(self.context), "DELIVERY_UNKNOWN")
        dispatcher = agent.dispatcher
        self.assertIsNone(dispatcher.dispatch_once())
        self.assertEqual(len(transport.payloads), 1)
        self.assertEqual(provider.calls, 2)
        with self.assertRaises(ValueError):
            dispatcher.resolve_unknown(self.context.run_id, actor="operator", reason="нет receipt",
                                       evidence="UI пуст", decision="negative")
        dispatcher.resolve_unknown(self.context.run_id, actor="operator", reason="нет proof",
                                   evidence="manual review", decision="quarantine")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM claims WHERE state='quarantined'").fetchone()[0], 3)

    def test_definitive_rejection_requires_explicit_retry_with_global_cap(self):
        transport = FakeTransport("definitive_rejection")
        agent, _ = self.make_agent(transport)
        self.assertEqual(agent.run(self.context), "DELIVERY_FAILED")
        self.assertIsNone(agent.dispatcher.dispatch_once())
        agent.dispatcher.retry_definitive(self.context.run_id, actor="operator", reason="полный 400 ответ",
                                          evidence="local:api_rejection")
        transport.outcome = "receipt"
        self.assertEqual(agent.dispatcher.dispatch_once(), "receipt")
        with self.assertRaises(ValueError):
            agent.dispatcher.retry_definitive(self.context.run_id, actor="operator", reason="ещё раз",
                                              evidence="local:api_rejection")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM delivery_attempts").fetchone()[0], 2)

    def test_unknown_verified_receipt_or_negative_proof(self):
        transport = FakeTransport("unknown")
        agent, _ = self.make_agent(transport)
        self.assertEqual(agent.run(self.context), "DELIVERY_UNKNOWN")
        agent.dispatcher.resolve_unknown(self.context.run_id, actor="operator", reason="проверил Telegram",
                                         evidence="telegram:message_id:456", decision="delivered", message_id=456)
        self.assertEqual(self.repo.run(self.context.run_id)["state"], "DELIVERED")
        self.assertEqual(len(transport.payloads), 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT slot_date FROM delivery_checkpoints").fetchone()[0], "2026-09-26")
        later = self.repo.get_or_create_run(slot_for(date(2026, 9, 27)))
        self.repo.set_state(later.run_id, "MCP_PENDING")
        # Следующий unknown создаём на новом отчёте через пустой подтверждённый batch.
        aggregate = self.repo.ingest(later, "empty", [], [],
                                     {"kind": "complete_for_profile", "feed_limit_hit": False,
                                      "window_complete": True, "oldest_entry_utc": None}, 0)
        self.repo.set_state(later.run_id, "DATA_READY")
        self.repo.set_state(later.run_id, "REPORT_PENDING")
        selected = select_pool(self.repo, later.run_id, 8192)
        self.assertEqual(selected.pool_total, 1)
        draft = {"run_id": later.run_id, "outcome": "cases_found",
                 "coverage_label": "complete_for_profile",
                 "entries": [{"observation_id": selected.rows[0]["observation_id"],
                              "category": "confirmed_described_case", "evidence_refs": ["title", "rss_excerpt"],
                              "summary": "Кейс из backlog.", "metric_claims": []}],
                 "proposed_text": "Материал из накопленной очереди."}
        commit_report(self.repo, later, validate_draft(draft, later, selected, aggregate), selected, aggregate)
        self.assertEqual(agent.dispatcher.dispatch_once(), "unknown")
        with self.store.connect() as db:
            attempt = db.execute("SELECT id,payload_hash FROM delivery_attempts WHERE report_id=(SELECT id FROM reports WHERE run_id=?)",
                                 (later.run_id,)).fetchone()
        proof = f"telegram:negative:{attempt['id']}:{attempt['payload_hash']}:authoritative"
        agent.dispatcher.resolve_unknown(later.run_id, actor="operator", reason="Telegram подтвердил отказ",
                                         evidence=proof, decision="negative")
        self.assertEqual(self.repo.run(later.run_id)["state"], "DELIVERY_FAILED")
        agent.dispatcher.retry_definitive(later.run_id, actor="operator", reason="повтор после proof",
                                          evidence=proof)
        transport.outcome = "receipt"
        self.assertEqual(agent.dispatcher.dispatch_once(), "receipt")
        self.assertEqual(self.repo.run(later.run_id)["state"], "DELIVERED")

    def test_manual_identity_separate(self):
        manual_id = "123e4567-e89b-12d3-a456-426614174000"
        manual = self.repo.get_or_create_run(self.context.slot, manual_invocation_id=manual_id)
        self.assertNotEqual(manual.run_id, self.context.run_id)
        self.assertTrue(manual.no_send)
        self.assertEqual(manual.run_id, self.repo.get_or_create_run(self.context.slot, manual_invocation_id=manual_id).run_id)
        with self.assertRaises(ValueError):
            self.repo.get_or_create_run(self.context.slot, manual_invocation_id="")

    def test_fsm_requires_evidence(self):
        self.repo.set_state(self.context.run_id, "MCP_PENDING")
        with self.assertRaises(ValueError):
            self.repo.set_state(self.context.run_id, "DATA_READY")
        self.assertEqual(self.repo.run(self.context.run_id)["state"], "MCP_PENDING")

    def test_real_local_mcp_protocol(self):
        fixture = Path(self.tmp.name) / "feed.xml"
        fixture.write_bytes(fixture_feed(1))
        self.repo.set_state(self.context.run_id, "MCP_PENDING")
        config = McpConfig(sys.executable, ("-m", "day18.offline_mcp_server", "--db",
                                                str(self.store.path), "--fixture", str(fixture)))
        listed = discover(config)
        self.assertEqual([tool["name"] for tool in listed], ["collect_habr_agent_cases"])
        self.assertFalse(ToolRuntime(self.repo, config).model_tools()[0]["function"]["parameters"]["additionalProperties"])
        first = execute(config, "collect_habr_agent_cases", self.context.tool_arguments())
        second = execute(config, "collect_habr_agent_cases", self.context.tool_arguments())
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "success_with_items")
        self.assertEqual(self.repo.run(self.context.run_id)["mcp_executions"], 1)

    def test_fake_model_through_real_local_mcp(self):
        fixture = Path(self.tmp.name) / "feed.xml"
        fixture.write_bytes(fixture_feed())
        config = McpConfig(sys.executable, ("-m", "day18.offline_mcp_server", "--db",
                                                str(self.store.path), "--fixture", str(fixture)))
        provider = FakeProvider(self.repo, self.context)
        agent = Agent(self.repo, provider, ToolRuntime(self.repo, config))
        self.assertEqual(agent.run(self.context), "REPORT_READY")
        self.assertEqual(provider.calls, 2)
        self.assertEqual(self.repo.run(self.context.run_id)["mcp_executions"], 1)
        self.assertEqual(provider.second_messages[3]["role"], "tool")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT tool_call_id FROM batches").fetchone()[0], "call-1")

    def test_model_sees_only_preflight_selected_candidates(self):
        items = "".join(
            f"<item><title>Компания внедрила ИИ-агента {i}</title>"
            f"<link>https://habr.com/ru/articles/{600+i}/</link>"
            f"<description>Компания запустила пилот: агент обрабатывает заявки.</description>"
            f"<pubDate>Sat, 26 Sep 2026 12:{i:02d}:00 GMT</pubDate></item>"
            for i in range(8)
        )
        items += "<item><title>Старый агент</title><link>https://habr.com/ru/articles/699/</link>"
        items += "<description>Старый агент.</description><pubDate>Fri, 25 Sep 2026 15:00:00 GMT</pubDate></item>"
        raw = f"<rss><channel>{items}</channel></rss>".encode()
        provider = FakeProvider(self.repo, self.context)
        tools = ToolRuntime(self.repo, McpConfig("unused", ()),
                            discover_fn=lambda _: [{"name": "collect_habr_agent_cases",
                                                    "description": "fixed RSS", "input_schema": INPUT_SCHEMA}],
                            execute_fn=lambda _, __, args: collect(self.repo, args, lambda: raw))
        self.assertEqual(Agent(self.repo, provider, tools).run(self.context), "REPORT_READY")
        visible = json.loads(provider.second_messages[3]["content"])["candidates"]
        selected = json.loads(provider.second_messages[-1]["content"])["model_seen"]
        self.assertEqual(len(visible), 7)
        self.assertEqual(len(selected), 7)
        self.assertEqual(len(self.repo.batch_for(self.context.run_id, self.context.idempotency_key)["candidates"]), 8)

    def test_twenty_articles_are_classified_in_one_draft_with_two_displayed(self):
        items = "".join(
            f"<item><title>Компания внедрила ИИ-агента {i}</title>"
            f"<link>https://habr.com/ru/articles/{800+i}/</link>"
            "<description>Компания использует агента в поддержке клиентов.</description>"
            f"<pubDate>Sat, 26 Sep 2026 12:{i:02d}:00 GMT</pubDate></item>"
            for i in range(21)
        )
        raw = f"<rss><channel>{items}</channel></rss>".encode()
        provider = FakeProvider(self.repo, self.context)
        provider.visible_budget = 20_000
        tools = ToolRuntime(self.repo, McpConfig("unused", ()),
                            discover_fn=lambda _: [{"name": "collect_habr_agent_cases",
                                                    "description": "fixed RSS", "input_schema": INPUT_SCHEMA}],
                            execute_fn=lambda _, __, args: collect(self.repo, args, lambda: raw))
        self.assertEqual(Agent(self.repo, provider, tools).run(self.context), "REPORT_READY")
        self.assertEqual(provider.calls, 2)
        self.assertEqual(provider.second_max_tokens, 20_000)
        self.assertLessEqual(worst_case_bytes(20) + 1024, provider.visible_budget)
        self.assertEqual(len(json.loads(provider.second_messages[-1]["content"])["model_seen"]), 20)
        with self.store.connect() as db:
            report = db.execute("SELECT model_seen,analysis_omitted,payload_displayed,payload_omitted,payload FROM reports").fetchone()
            self.assertEqual(tuple(report[:4]), (20, 1, 2, 18))
            self.assertEqual(report["payload"].count("https://habr.com/ru/articles/"), 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM classifications").fetchone()[0], 20)

    def test_twenty_article_pool_keeps_five_oldest_backlog_places(self):
        previous = self.repo.get_or_create_run(slot_for(date(2026, 9, 25)))
        for context, start_id, count, published in (
            (previous, 7000, 8, "Fri, 25 Sep 2026 12:00:00 GMT"),
            (self.context, 8000, 21, "Sat, 26 Sep 2026 12:00:00 GMT"),
        ):
            items = "".join(
                f"<item><title>Компания внедрила ИИ-агента {i}</title>"
                f"<link>https://habr.com/ru/articles/{start_id+i}/</link>"
                "<description>Компания использует агента в поддержке клиентов.</description>"
                f"<pubDate>{published}</pubDate></item>"
                for i in range(count)
            )
            parsed, rejected, coverage, seen = parse_feed(f"<rss><channel>{items}</channel></rss>".encode(), context)
            self.repo.ingest(context, "fixture", parsed, rejected, coverage, seen)
        selected = select_pool(self.repo, self.context.run_id, 20_000)
        ids = {int(row["article_id"]) for row in selected.rows}
        self.assertEqual((selected.pool_total, len(selected.rows), selected.analysis_omitted), (29, 20, 9))
        self.assertEqual(sum(8000 <= article_id < 9000 for article_id in ids), 15)
        self.assertEqual(sum(7000 <= article_id < 8000 for article_id in ids), 5)
        self.assertIn(8011, ids)

    def test_committed_batch_reconciles_pending_tool_after_crash(self):
        self.repo.set_state(self.context.run_id, "MCP_PENDING")
        self.repo.begin_model_call(self.context.run_id, 1)
        self.repo.begin_tool_attempt(self.context.run_id, 1, 1, raw_call_id="call-1",
                                     audit_call_id="call-1", name="collect_habr_agent_cases",
                                     arguments=self.context.tool_arguments())
        self.repo.increment_mcp_execution(self.context.run_id)
        items, rejected, coverage, seen = parse_feed(fixture_feed(), self.context)
        self.repo.ingest(self.context, "call-1", items, rejected, coverage, seen)
        provider = DraftOnlyProvider(self.context)
        tools = ToolRuntime(self.repo, McpConfig("unused", ()),
                            discover_fn=lambda _: (_ for _ in ()).throw(AssertionError("rediscovery")),
                            execute_fn=lambda *_: (_ for _ in ()).throw(AssertionError("RSS reread")))
        self.assertEqual(Agent(self.repo, provider, tools).run(self.context), "REPORT_READY")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(self.repo.run(self.context.run_id)["mcp_executions"], 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT outcome FROM tool_attempts").fetchone()[0], "accepted")
            self.assertEqual(db.execute("SELECT outcome FROM model_attempts WHERE call_sequence=1").fetchone()[0], "interrupted")

    def test_concurrent_slot_and_dst(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(lambda _: self.repo.get_or_create_run(self.context.slot).run_id, range(8)))
        self.assertEqual(set(ids), {self.context.run_id})
        spring = slot_for(date(2026, 3, 29))
        autumn = slot_for(date(2026, 10, 25))
        from datetime import datetime
        def duration(slot):
            return (datetime.fromisoformat(slot.period_end_utc.replace("Z", "+00:00")) -
                    datetime.fromisoformat(slot.period_start_utc.replace("Z", "+00:00"))).total_seconds()
        self.assertEqual(duration(spring), 23 * 3600)
        self.assertEqual(duration(autumn), 25 * 3600)

    def test_unknown_date_kept_as_partial(self):
        raw = ("<rss><channel><item><title>Компания внедрила ИИ-агента</title>"
               "<link>https://habr.com/ru/articles/999/</link>"
               "<description>Компания использует агента в поддержке.</description>"
               "</item></channel></rss>").encode()
        items, rejected, coverage, seen = parse_feed(raw, self.context)
        result = self.repo.ingest(self.context, "date-missing", items, rejected, coverage, seen)
        self.assertEqual(result["status"], "partial_coverage")
        self.assertEqual(result["reason_code"], "invalid_entries")
        with self.store.connect() as db:
            self.assertIsNone(db.execute("SELECT published_at_utc FROM observations").fetchone()[0])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batch_members").fetchone()[0], 1)

    def test_invalid_link_does_not_hide_valid_sibling(self):
        raw = ("<rss><channel><item><title>Компания внедрила агента</title>"
               "<link>https://evil.example/1</link><description>Сбой ссылки</description>"
               "<pubDate>Sat, 26 Sep 2026 12:00:00 GMT</pubDate></item>"
               "<item><title>Банк внедрил ИИ-агента</title><link>https://habr.com/ru/articles/222/</link>"
               "<description>Банк использует агента для клиентов.</description>"
               "<pubDate>Sat, 26 Sep 2026 11:00:00 GMT</pubDate></item></channel></rss>").encode()
        items, rejected, coverage, seen = parse_feed(raw, self.context)
        result = self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)
        self.assertEqual(result["status"], "partial_coverage")
        self.assertEqual(result["counts"]["invalid_entries"], 1)
        self.assertEqual(result["counts"]["eligible_candidates"], 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM source_rejections").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 1)

    def test_no_matching_and_feed_limit_are_distinct(self):
        recipe = ("<rss><channel><item><title>Рецепт яблочного пирога</title>"
                  "<link>https://habr.com/ru/articles/777/</link>"
                  "<description>Кулинарный рецепт.</description>"
                  "<pubDate>Sat, 26 Sep 2026 12:00:00 GMT</pubDate></item>"
                  "<item><title>Старый рецепт</title><link>https://habr.com/ru/articles/778/</link>"
                  "<description>Кулинария.</description><pubDate>Fri, 25 Sep 2026 15:00:00 GMT</pubDate>"
                  "</item></channel></rss>").encode()
        items, rejected, coverage, seen = parse_feed(recipe, self.context)
        result = self.repo.ingest(self.context, "recipe", items, rejected, coverage, seen)
        self.assertEqual(result["status"], "success_no_matching_cases")
        self.assertEqual(result["counts"]["out_of_profile"], 1)
        many = "".join(f"<item><title>Агент {i}</title><link>https://habr.com/ru/articles/{1000+i}/</link>"
                       f"<description>ИИ-агент</description><pubDate>Sat, 26 Sep 2026 12:00:00 GMT</pubDate></item>"
                       for i in range(100))
        _, _, cap_coverage, cap_seen = parse_feed(f"<rss><channel>{many}</channel></rss>".encode(), self.context)
        self.assertEqual(cap_seen, 100)
        self.assertEqual(cap_coverage["kind"], "partial")
        self.assertTrue(cap_coverage["feed_limit_hit"])

    def test_rss_outage_malformed_and_oversize_have_distinct_evidence(self):
        for index, (fetch, expected_status, expected_reason) in enumerate((
            (lambda: (_ for _ in ()).throw(urllib.error.URLError("offline")), "source_error", "rss_unavailable"),
            (lambda: b"<!DOCTYPE rss><rss><channel/></rss>", "source_error", "rss_malformed"),
            (lambda: b"x" * (MAX_FEED_BYTES + 1), "partial_coverage", "oversize"),
        )):
            context = self.repo.get_or_create_run(slot_for(date(2026, 9, 27) + timedelta(days=index)))
            self.repo.set_state(context.run_id, "MCP_PENDING")
            result = collect(self.repo, context.tool_arguments(), fetch)
            self.assertEqual((result["status"], result["reason_code"]), (expected_status, expected_reason))
            saved = self.repo.batch_for(context.run_id, context.idempotency_key)
            self.assertEqual(saved is not None, expected_status == "partial_coverage")

    def test_telegram_http_adapter_classifies_receipt_rejection_and_uncertainty(self):
        transport = TelegramTransport()
        transport._token = "fixture-token"
        transport._chat = "fixture-chat"

        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _): return b'{"ok":true,"result":{"message_id":45}}'

        class Opener:
            def __init__(self, result): self.result = result
            def open(self, *_args, **_kwargs):
                if isinstance(self.result, Exception):
                    raise self.result
                return self.result

        with patch("day18.delivery.urllib.request.build_opener", return_value=Opener(Response())):
            self.assertEqual(transport.send("fixture").kind, "receipt")
        definitive = urllib.error.HTTPError("https://api.telegram.org", 400, "bad", {},
                                             io.BytesIO(b'{"ok":false,"error_code":400}'))
        with patch("day18.delivery.urllib.request.build_opener", return_value=Opener(definitive)):
            self.assertEqual(transport.send("fixture").kind, "definitive_rejection")
        uncertain = urllib.error.HTTPError("https://api.telegram.org", 503, "unavailable", {}, io.BytesIO(b""))
        with patch("day18.delivery.urllib.request.build_opener", return_value=Opener(uncertain)):
            self.assertEqual(transport.send("fixture").kind, "unknown")
        with patch("day18.delivery.urllib.request.build_opener", return_value=Opener(TimeoutError())):
            self.assertEqual(transport.send("fixture").kind, "unknown")

    def test_seven_new_candidates_fit_old_visible_budget(self):
        text = "x" * 160
        items = "".join(
            f"<item><title>Компания внедрила ИИ-агента {i}</title>"
            f"<link>https://habr.com/ru/articles/{300+i}/</link>"
            f"<description>Компания использует агента в поддержке клиентов. {text}</description>"
            f"<pubDate>Sat, 26 Sep 2026 12:{i:02d}:00 GMT</pubDate></item>"
            for i in range(8)
        )
        items += "<item><title>Старый агент</title><link>https://habr.com/ru/articles/399/</link>"
        items += "<description>Старый агент.</description><pubDate>Fri, 25 Sep 2026 15:00:00 GMT</pubDate></item>"
        raw = f"<rss><channel>{items}</channel></rss>".encode()
        parsed, rejected, coverage, seen = parse_feed(raw, self.context)
        aggregate = self.repo.ingest(self.context, "fixture", parsed, rejected, coverage, seen)
        selected = select_pool(self.repo, self.context.run_id, 8192)
        self.assertEqual(selected.pool_total, 8)
        self.assertEqual(len(selected.rows), 7)
        self.assertLessEqual(worst_case_bytes(7) + 1024, 8192)
        self.assertGreater(worst_case_bytes(8) + 1024, 8192)
        draft = {"run_id": self.context.run_id, "outcome": "cases_found",
                 "coverage_label": "partial", "proposed_text": "p" * 1024,
                 "entries": [{"observation_id": row["observation_id"],
                              "category": "confirmed_described_case", "evidence_refs": ["title", "rss_excerpt", "title"],
                              "summary": "s" * 256, "metric_claims": [{"text": text, "attribution": "a" * 120}]}
                             for row in selected.rows]}
        self.assertLessEqual(len(compact(draft).encode()), 18 * 1024)
        self.assertEqual(validate_draft(draft, self.context, selected, aggregate), draft)

    def test_confirmed_cases_come_before_possible(self):
        items, rejected, coverage, seen = parse_feed(fixture_feed(), self.context)
        aggregate = self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)
        selected = select_pool(self.repo, self.context.run_id, 8192)
        entries = [{"observation_id": row["observation_id"],
                    "category": "possible_case" if index == 0 else "confirmed_described_case",
                    "evidence_refs": ["title", "rss_excerpt"], "summary": "Краткая сводка.",
                    "metric_claims": []} for index, row in enumerate(selected.rows)]
        draft = {"run_id": self.context.run_id, "outcome": "cases_found",
                 "coverage_label": "complete_for_profile", "entries": entries,
                 "proposed_text": "Три материала."}
        validated = validate_draft(draft, self.context, selected, aggregate)
        payload, relevant, omitted = render(self.context, validated, selected, aggregate)
        self.assertEqual(omitted, 1)
        self.assertEqual([item[0]["category"] for item in relevant[:2]],
                         ["confirmed_described_case", "confirmed_described_case"])
        self.assertEqual(payload.count("https://habr.com/ru/articles/"), 2)

    def test_personal_agent_project_can_be_marked_possible(self):
        raw = ("<rss><channel><item><title>Мой ИИ-агент рисует фильм</title>"
               "<link>https://habr.com/ru/articles/501/</link>"
               "<description>Я сделал агента для домашнего фильма на Canvas.</description>"
               "<pubDate>Sat, 26 Sep 2026 12:00:00 GMT</pubDate>"
               "</item></channel></rss>").encode()
        items, rejected, coverage, seen = parse_feed(raw, self.context)
        aggregate = self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)
        selected = select_pool(self.repo, self.context.run_id, 8192)
        draft = {"run_id": self.context.run_id, "outcome": "no_confirmed_cases",
                 "coverage_label": aggregate["coverage"]["kind"],
                 "proposed_text": "В обработанных материалах подтверждённых кейсов нет.",
                 "entries": [{"observation_id": selected.rows[0]["observation_id"],
                              "category": "possible_case", "evidence_refs": ["title", "rss_excerpt"],
                              "summary": "Личный проект с агентом.", "metric_claims": []}]}
        self.assertEqual(validate_draft(draft, self.context, selected, aggregate), draft)

    def test_actual_personal_use_can_be_confirmed(self):
        raw = ("<rss><channel><item><title>Я использую ИИ-агента для поездок</title>"
               "<link>https://habr.com/ru/articles/502/</link>"
               "<description>Мой агент сравнивает билеты и планирует маршрут; "
               "я использую его для семейных поездок.</description>"
               "<pubDate>Sat, 26 Sep 2026 12:00:00 GMT</pubDate>"
               "</item></channel></rss>").encode()
        items, rejected, coverage, seen = parse_feed(raw, self.context)
        aggregate = self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)
        selected = select_pool(self.repo, self.context.run_id, 8192)
        draft = {"run_id": self.context.run_id, "outcome": "cases_found",
                 "coverage_label": aggregate["coverage"]["kind"],
                 "proposed_text": "Описано личное применение агента.",
                 "entries": [{"observation_id": selected.rows[0]["observation_id"],
                              "category": "confirmed_described_case", "evidence_refs": ["title", "rss_excerpt"],
                              "summary": "Агент помогает с маршрутом поездки.", "metric_claims": []}]}
        self.assertEqual(validate_draft(draft, self.context, selected, aggregate), draft)
        self.assertIn("https://habr.com/ru/articles/502/",
                      render(self.context, draft, selected, aggregate)[0])

    def test_possible_case_requires_agent_in_rss_evidence(self):
        raw = ("<rss><channel><item><title>Мой ИИ-помощник для поездок</title>"
               "<link>https://habr.com/ru/articles/503/</link>"
               "<description>Я планирую семейные маршруты.</description>"
               "<pubDate>Sat, 26 Sep 2026 12:00:00 GMT</pubDate>"
               "</item></channel></rss>").encode()
        items, rejected, coverage, seen = parse_feed(raw, self.context)
        aggregate = self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)
        selected = select_pool(self.repo, self.context.run_id, 8192)
        draft = {"run_id": self.context.run_id, "outcome": "no_confirmed_cases",
                 "coverage_label": aggregate["coverage"]["kind"],
                 "proposed_text": "В обработанных материалах подтверждённых кейсов нет.",
                 "entries": [{"observation_id": selected.rows[0]["observation_id"],
                              "category": "possible_case", "evidence_refs": ["title", "rss_excerpt"],
                              "summary": "Идея личного помощника.", "metric_claims": []}]}
        with self.assertRaisesRegex(ValueError, "possible case lacks agent RSS evidence"):
            validate_draft(draft, self.context, selected, aggregate)

    def test_partial_report_cannot_claim_no_cases_for_whole_day(self):
        items, rejected, coverage, seen = parse_feed(fixture_feed(1), self.context)
        aggregate = self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)
        selected = select_pool(self.repo, self.context.run_id, 8192)
        partial = dict(aggregate)
        partial["coverage"] = {**aggregate["coverage"], "kind": "partial"}
        draft = {"run_id": self.context.run_id, "outcome": "no_confirmed_cases",
                 "coverage_label": "partial", "proposed_text": "За сутки кейсов не нашлось.",
                 "entries": [{"observation_id": row["observation_id"], "category": "guide",
                              "evidence_refs": ["title"], "summary": "", "metric_claims": []}
                             for row in selected.rows]}
        with self.assertRaisesRegex(ValueError, "intro overstates partial coverage"):
            validate_draft(draft, self.context, selected, partial)

    def test_invalid_and_multiple_calls_never_reach_mcp(self):
        count = [0]
        def execute_fake(*_):
            count[0] += 1
            raise AssertionError("MCP must not execute")
        tools = ToolRuntime(self.repo, McpConfig("unused", ()), execute_fn=execute_fake)
        bad = proposals({"tool_calls": [{"id": "a", "function": {
            "name": "collect_habr_agent_cases", "arguments": compact({**self.context.tool_arguments(), "url": "https://evil"})}}]})
        result = tools.run_proposals(self.context, 1, bad)
        self.assertEqual(result[0].result["reason_code"], "schema_violation")
        unknown = proposals({"tool_calls": [{"id": "unknown", "function": {
            "name": "send_telegram", "arguments": compact(self.context.tool_arguments())}}]})
        result = tools.run_proposals(self.context, 3, unknown)
        self.assertEqual(result[0].result["reason_code"], "tool_not_allowed")
        multiple = proposals({"tool_calls": [{"id": "b", "function": {"name": "collect_habr_agent_cases",
            "arguments": compact(self.context.tool_arguments())}}, {"id": "c", "function": {
            "name": "collect_habr_agent_cases", "arguments": compact(self.context.tool_arguments())}}]})
        result = tools.run_proposals(self.context, 2, multiple)
        self.assertEqual([r.result["reason_code"] for r in result], ["multiple_calls", "multiple_calls"])
        self.assertEqual(count[0], 0)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM tool_attempts").fetchone()[0], 4)

    def test_second_model_call_cannot_execute_another_tool(self):
        class LateToolProvider(FakeProvider):
            def complete(self, messages, *, tools, max_tokens, tool_choice):
                if self.calls == 1:
                    self.calls += 1
                    return ModelResponse({"tool_calls": [{"id": "late-call", "function": {
                        "name": "collect_habr_agent_cases", "arguments": compact(self.context.tool_arguments())}}]})
                return super().complete(messages, tools=tools, max_tokens=max_tokens, tool_choice=tool_choice)

        provider = LateToolProvider(self.repo, self.context)
        tools = ToolRuntime(self.repo, McpConfig("unused", ()),
                            discover_fn=lambda _: [{"name": "collect_habr_agent_cases",
                                                    "description": "fixed RSS", "input_schema": INPUT_SCHEMA}],
                            execute_fn=lambda _, __, args: collect(self.repo, args, lambda: fixture_feed()))
        self.assertEqual(Agent(self.repo, provider, tools).run(self.context), "FAILED_AFTER_DATA")
        self.assertEqual(self.repo.run(self.context.run_id)["mcp_executions"], 1)
        with self.store.connect() as db:
            rows = db.execute("SELECT outcome,reason_code FROM tool_attempts ORDER BY call_sequence").fetchall()
            self.assertEqual([(row["outcome"], row["reason_code"]) for row in rows],
                             [("accepted", "none"), ("denied", "tool_not_allowed")])

    def test_truncated_draft_never_becomes_ready_report(self):
        class TruncatedProvider(FakeProvider):
            def complete(self, messages, *, tools, max_tokens, tool_choice):
                response = super().complete(messages, tools=tools, max_tokens=max_tokens, tool_choice=tool_choice)
                return ModelResponse(response.message, response.usage,
                                     "length" if self.calls == 2 else response.finish_reason)

        provider = TruncatedProvider(self.repo, self.context)
        tools = ToolRuntime(self.repo, McpConfig("unused", ()),
                            discover_fn=lambda _: [{"name": "collect_habr_agent_cases",
                                                    "description": "fixed RSS", "input_schema": INPUT_SCHEMA}],
                            execute_fn=lambda _, __, args: collect(self.repo, args, lambda: fixture_feed()))
        self.assertEqual(Agent(self.repo, provider, tools).run(self.context), "FAILED_AFTER_DATA")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reports").fetchone()[0], 0)

    def test_presend_retry_uses_same_payload_and_cap(self):
        transport = PreSendOnce()
        agent, provider = self.make_agent(transport)
        self.assertEqual(agent.run(self.context), "FAILED_BEFORE_SEND")
        self.assertEqual(len(transport.payloads), 0)
        self.assertEqual(agent.dispatcher.dispatch_once(), "receipt")
        self.assertEqual(self.repo.run(self.context.run_id)["state"], "DELIVERED")
        self.assertEqual(len(transport.payloads), 1)
        self.assertEqual(provider.calls, 2)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM delivery_attempts").fetchone()[0], 2)

    def test_retry_cannot_change_recipient(self):
        agent, _ = self.make_agent()
        self.assertEqual(agent.run(self.context), "REPORT_READY")
        self.assertEqual(Dispatcher(self.repo, PreSendOnce()).dispatch_once(), "pre_send")
        other = FakeTransport()
        other.fingerprint = lambda: "a" * 64
        with self.assertRaises(ValueError):
            Dispatcher(self.repo, other).dispatch_once()
        self.assertEqual(other.payloads, [])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM delivery_attempts").fetchone()[0], 1)

    def test_two_dispatchers_cannot_send_same_report(self):
        agent, _ = self.make_agent()
        self.assertEqual(agent.run(self.context), "REPORT_READY")
        slow = SlowTransport()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(Dispatcher(self.repo, slow).dispatch_once)
            self.assertTrue(slow.entered.wait(2))
            second = pool.submit(Dispatcher(self.repo, FakeTransport()).dispatch_once)
            self.assertIsNone(second.result(timeout=2))
            slow.release.set()
            self.assertEqual(first.result(timeout=3), "receipt")
        self.assertEqual(len(slow.payloads), 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM delivery_attempts").fetchone()[0], 1)

    def test_ready_report_recovered_without_model(self):
        agent, provider = self.make_agent()
        self.assertEqual(agent.run(self.context), "REPORT_READY")
        reopened = Repository(Store(self.store.path))
        transport = FakeTransport()
        self.assertEqual(Dispatcher(reopened, transport).dispatch_once(), "receipt")
        self.assertEqual(reopened.run(self.context.run_id)["state"], "DELIVERED")
        self.assertEqual(provider.calls, 2)

    def test_old_ready_queue_does_not_charge_generation_budget(self):
        agent, provider = self.make_agent()
        with patch("day18.report.utc_now", return_value="2020-01-01T00:00:00Z"):
            self.assertEqual(agent.run(self.context), "REPORT_READY")
        before = self.repo.run(self.context.run_id)["active_ms"]
        self.assertEqual(Dispatcher(self.repo, FakeTransport()).dispatch_once(), "receipt")
        self.assertEqual(self.repo.run(self.context.run_id)["active_ms"], before)
        self.assertEqual(provider.calls, 2)

    def test_unknown_queues_later_empty_report_then_quarantine(self):
        transport = FakeTransport("unknown")
        agent, _ = self.make_agent(transport)
        self.assertEqual(agent.run(self.context), "DELIVERY_UNKNOWN")
        later = self.repo.get_or_create_run(slot_for(date(2026, 9, 27)))
        self.repo.set_state(later.run_id, "MCP_PENDING")
        aggregate = self.repo.ingest(later, "empty", [], [],
                                     {"kind": "complete_for_profile", "feed_limit_hit": False,
                                      "window_complete": True, "oldest_entry_utc": None}, 0)
        self.repo.set_state(later.run_id, "DATA_READY")
        self.repo.set_state(later.run_id, "REPORT_PENDING")
        selected = select_pool(self.repo, later.run_id, 8192)
        self.assertEqual(selected.pool_total, 0)
        draft = {"run_id": later.run_id, "outcome": "empty_feed", "coverage_label": "complete_for_profile",
                 "entries": [], "proposed_text": "За период новых материалов нет."}
        validated = validate_draft(draft, later, selected, aggregate)
        commit_report(self.repo, later, validated, selected, aggregate)
        transport.outcome = "receipt"
        self.assertIsNone(agent.dispatcher.dispatch_once())
        self.assertEqual(len(transport.payloads), 1)
        agent.dispatcher.resolve_unknown(self.context.run_id, actor="operator", reason="нет proof",
                                         evidence="manual review", decision="quarantine")
        self.assertEqual(agent.dispatcher.dispatch_once(), "receipt")
        self.assertEqual(self.repo.run(later.run_id)["state"], "DELIVERED")
        self.assertEqual(len(transport.payloads), 2)
        with self.store.connect() as db:
            self.assertIsNone(db.execute("SELECT slot_date FROM delivery_checkpoints").fetchone())

    def test_retired_old_report_releases_only_to_future_unfrozen_report(self):
        agent, _ = self.make_agent()
        self.assertEqual(agent.run(self.context), "REPORT_READY")
        later = self.repo.get_or_create_run(slot_for(date(2026, 9, 27)))
        self.repo.set_state(later.run_id, "MCP_PENDING")
        aggregate = self.repo.ingest(later, "empty", [], [],
                                     {"kind": "complete_for_profile", "feed_limit_hit": False,
                                      "window_complete": True, "oldest_entry_utc": None}, 0)
        self.repo.set_state(later.run_id, "DATA_READY")
        self.repo.set_state(later.run_id, "REPORT_PENDING")
        frozen = select_pool(self.repo, later.run_id, 8192)
        self.assertEqual(frozen.pool_total, 0)
        draft = {"run_id": later.run_id, "outcome": "empty_feed",
                 "coverage_label": "complete_for_profile", "entries": [], "proposed_text": "Новых материалов нет."}
        commit_report(self.repo, later, validate_draft(draft, later, frozen, aggregate), frozen, aggregate)
        transport = PreSendOnce()
        dispatcher = Dispatcher(self.repo, transport)
        self.assertEqual(dispatcher.dispatch_once(), "pre_send")
        dispatcher.retire(self.context.run_id, actor="operator", reason="не отправлять старый выпуск",
                          evidence="local:pre_send_proof")
        self.assertEqual(dispatcher.dispatch_once(), "receipt")
        self.assertEqual(self.repo.run(later.run_id)["state"], "DELIVERED")
        future = self.repo.get_or_create_run(slot_for(date(2026, 9, 28)))
        _, backlog = self.repo.report_pool(future.run_id)
        self.assertEqual(len(backlog), 3)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM report_members WHERE report_id=(SELECT id FROM reports WHERE run_id=?)",
                                        (later.run_id,)).fetchone()[0], 0)

    def test_two_queued_reports_can_send_same_day_each_with_own_cap(self):
        agent, _ = self.make_agent()
        self.assertEqual(agent.run(self.context), "REPORT_READY")
        later = self.repo.get_or_create_run(slot_for(date(2026, 9, 27)))
        self.repo.set_state(later.run_id, "MCP_PENDING")
        case = {"article_id": "888", "url": "https://habr.com/ru/articles/888/",
                "title": "Компания внедрила ИИ-агента для поддержки клиентов",
                "rss_excerpt": "Компания запустила пилот: агент обрабатывает заявки.",
                "original_pubdate": None, "published_at_utc": "2026-09-27T12:00:00Z",
                "eligibility": "eligible"}
        aggregate = self.repo.ingest(later, "case", [case], [],
                                     {"kind": "complete_for_profile", "feed_limit_hit": False,
                                      "window_complete": True, "oldest_entry_utc": None}, 1)
        self.repo.set_state(later.run_id, "DATA_READY")
        self.repo.set_state(later.run_id, "REPORT_PENDING")
        selected = select_pool(self.repo, later.run_id, 8192)
        self.assertEqual(selected.pool_total, 1)
        draft = {"run_id": later.run_id, "outcome": "cases_found",
                 "coverage_label": "complete_for_profile", "proposed_text": "Новый выпуск.",
                 "entries": [{"observation_id": selected.rows[0]["observation_id"],
                              "category": "confirmed_described_case", "evidence_refs": ["title", "rss_excerpt"],
                              "summary": "Кейс описан.", "metric_claims": []}]}
        commit_report(self.repo, later, validate_draft(draft, later, selected, aggregate), selected, aggregate)
        transport = FakeTransport()
        dispatcher = Dispatcher(self.repo, transport)
        self.assertEqual(dispatcher.dispatch_once(), "receipt")
        self.assertEqual(dispatcher.dispatch_once(), "receipt")
        self.assertEqual(len(transport.payloads), 2)
        self.assertEqual([payload.count("https://habr.com/ru/articles/") for payload in transport.payloads], [2, 1])

    def test_phase_reservation_survives_reopen(self):
        reservation = self.repo.reserve_phase(self.context.run_id, "provider", 180_000)
        self.assertEqual(Repository(Store(self.store.path)).run(self.context.run_id)["active_ms"], 180_000)
        self.repo.settle_phase(reservation, 250)
        self.assertEqual(self.repo.run(self.context.run_id)["active_ms"], 250)

    def test_oversized_provider_request_stops_before_attempt(self):
        agent, provider = self.make_agent()
        with self.assertRaisesRegex(ValueError, "provider input budget exhausted"):
            agent._call(self.context, [{"role": "user", "content": "x" * 80_001}],
                        tools=[], max_tokens=1000, tool_choice="none")
        self.assertEqual(provider.calls, 0)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM model_attempts").fetchone()[0], 0)

    def test_one_run_lease(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda index: self.repo.acquire_run_lease(self.context.run_id, str(index)), range(4)))
        self.assertEqual(claims.count(True), 1)
        owner = str(claims.index(True))
        self.repo.release_run_lease(self.context.run_id, owner)
        self.assertTrue(self.repo.acquire_run_lease(self.context.run_id, "next"))

    def test_agent_process_lock_prevents_second_model_turn(self):
        agent, provider = self.make_agent()
        path = self.store.path.with_name(self.store.path.name + f".run-{self.context.run_id}.lock")
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            self.assertEqual(agent.run(self.context), "IN_PROGRESS")
            self.assertEqual(provider.calls, 0)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        self.assertEqual(agent.run(self.context), "REPORT_READY")

    def test_migration_backup_and_gap_status(self):
        fresh = Path(self.tmp.name) / "parallel.sqlite3"
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: Store(fresh).migrate(), range(3)))
        self.repo.get_or_create_run(slot_for(date(2026, 9, 28)))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli_main(["--db", str(self.store.path), "status"]), 0)
        status = json.loads(output.getvalue())
        self.assertEqual(status["missing_slot_dates"], ["2026-09-27"])
        backup = Path(self.tmp.name) / "backup.sqlite3"
        self.store.backup(backup)
        with Store(backup).connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 2)
        self.assertEqual(backup.stat().st_mode & 0o077, 0)

    def test_crash_after_request_marker_becomes_unknown(self):
        agent, provider = self.make_agent()
        self.assertEqual(agent.run(self.context), "REPORT_READY")
        with self.store.tx() as db:
            report = db.execute("SELECT * FROM reports").fetchone()
            db.execute("INSERT INTO delivery_attempts(id,report_id,attempt_no,recipient_fingerprint,payload_hash,started_utc,request_started_utc) "
                       "VALUES (?,?,?,?,?,?,?)", ("attempt-crash", report["id"], 1, "f" * 64,
                                                    report["payload_hash"], utc_now(), utc_now()))
            db.execute("UPDATE send_gate SET report_id=?,owner=?,lease_until_utc='2020-01-01T00:00:00Z' WHERE id=1",
                       (report["id"], "attempt-crash"))
            transition(db, self.context.run_id, "SENDING")
        transport = FakeTransport()
        self.assertIsNone(Dispatcher(self.repo, transport).dispatch_once())
        self.assertEqual(self.repo.run(self.context.run_id)["state"], "DELIVERY_UNKNOWN")
        self.assertEqual(transport.payloads, [])
        self.assertEqual(provider.calls, 2)

    def test_third_article_link_in_intro_rejected(self):
        items, rejected, coverage, seen = parse_feed(fixture_feed(), self.context)
        aggregate = self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)
        selected = select_pool(self.repo, self.context.run_id, 8192)
        draft = {"run_id": self.context.run_id, "outcome": "cases_found",
                 "coverage_label": "complete_for_profile",
                 "entries": [{"observation_id": row["observation_id"], "category": "confirmed_described_case",
                              "evidence_refs": ["title", "rss_excerpt"], "summary": "Пилот описан в RSS.",
                              "metric_claims": []} for row in selected.rows],
                 "proposed_text": "Третья ссылка: https://habr.com/ru/articles/103/"}
        with self.assertRaises(ValueError):
            validate_draft(draft, self.context, selected, aggregate)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reports").fetchone()[0], 0)

    def test_report_commit_rolls_back_dispositions_claims_and_state(self):
        self.repo.set_state(self.context.run_id, "MCP_PENDING")
        items, rejected, coverage, seen = parse_feed(fixture_feed(1), self.context)
        aggregate = self.repo.ingest(self.context, "fixture", items, rejected, coverage, seen)
        self.repo.set_state(self.context.run_id, "DATA_READY")
        self.repo.set_state(self.context.run_id, "REPORT_PENDING")
        selected = select_pool(self.repo, self.context.run_id, 8192)
        draft = {"run_id": self.context.run_id, "outcome": "cases_found",
                 "coverage_label": "complete_for_profile", "proposed_text": "Сводка.",
                 "entries": [{"observation_id": row["observation_id"], "category": "confirmed_described_case",
                              "evidence_refs": ["title", "rss_excerpt"], "summary": "Кейс описан.",
                              "metric_claims": []} for row in selected.rows]}
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER fixture_abort BEFORE INSERT ON classifications "
                       "BEGIN SELECT RAISE(ABORT,'simulated crash'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            commit_report(self.repo, self.context,
                          validate_draft(draft, self.context, selected, aggregate), selected, aggregate)
        self.assertEqual(self.repo.run(self.context.run_id)["state"], "REPORT_PENDING")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reports").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM classifications").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 0)

    def test_manual_report_does_not_claim_scheduled_pool(self):
        manual = self.repo.get_or_create_run(self.context.slot,
                                             manual_invocation_id="123e4567-e89b-12d3-a456-426614174000")
        self.repo.set_state(manual.run_id, "MCP_PENDING")
        items, rejected, coverage, seen = parse_feed(fixture_feed(1), manual)
        aggregate = self.repo.ingest(manual, "manual", items, rejected, coverage, seen)
        self.repo.set_state(manual.run_id, "DATA_READY")
        self.repo.set_state(manual.run_id, "REPORT_PENDING")
        selected = select_pool(self.repo, manual.run_id, 8192)
        draft = {"run_id": manual.run_id, "outcome": "cases_found", "coverage_label": "complete_for_profile",
                 "entries": [{"observation_id": row["observation_id"], "category": "confirmed_described_case",
                              "evidence_refs": ["title", "rss_excerpt"], "summary": "Кейс описан.",
                              "metric_claims": []} for row in selected.rows],
                 "proposed_text": "Диагностический отчёт."}
        commit_report(self.repo, manual, validate_draft(draft, manual, selected, aggregate), selected, aggregate)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 0)
        _, backlog = self.repo.report_pool(self.context.run_id)
        self.assertEqual(len(backlog), 1)

    def test_forty_guides_do_not_starve_new_case(self):
        dispatcher = Dispatcher(self.repo, FakeTransport())
        first_date = date(2026, 9, 26)
        for index in range(7):
            context = self.repo.get_or_create_run(slot_for(first_date + timedelta(days=index)))
            self.repo.set_state(context.run_id, "MCP_PENDING")
            items = ([{"article_id": str(500 + number),
                       "url": f"https://habr.com/ru/articles/{500 + number}/",
                       "title": f"Гайд об ИИ-агентах {number}",
                       "rss_excerpt": "Руководство по настройке агентов.",
                       "original_pubdate": None, "published_at_utc": "2026-09-26T12:00:00Z",
                       "eligibility": "eligible"} for number in range(40)] if index == 0 else [])
            aggregate = self.repo.ingest(context, "fixture", items, [],
                                         {"kind": "complete_for_profile", "feed_limit_hit": False,
                                          "window_complete": True, "oldest_entry_utc": None}, len(items))
            self.repo.set_state(context.run_id, "DATA_READY")
            self.repo.set_state(context.run_id, "REPORT_PENDING")
            selected = select_pool(self.repo, context.run_id, 8192)
            draft = {"run_id": context.run_id, "outcome": "no_confirmed_cases",
                     "coverage_label": "partial" if selected.analysis_omitted else "complete_for_profile",
                     "entries": [{"observation_id": row["observation_id"], "category": "guide",
                                  "evidence_refs": ["title"], "summary": "Это руководство.",
                                  "metric_claims": []} for row in selected.rows],
                     "proposed_text": "Описанных бизнес-кейсов в обработанном наборе нет."}
            commit_report(self.repo, context, validate_draft(draft, context, selected, aggregate), selected, aggregate)
            self.assertEqual(dispatcher.dispatch_once(), "receipt")
        next_context = self.repo.get_or_create_run(slot_for(first_date + timedelta(days=7)))
        self.repo.set_state(next_context.run_id, "MCP_PENDING")
        case = {"article_id": "999", "url": "https://habr.com/ru/articles/999/",
                "title": "Компания внедрила ИИ-агента для поддержки клиентов",
                "rss_excerpt": "Компания запустила пилот: агент обрабатывает заявки.",
                "original_pubdate": None, "published_at_utc": "2026-10-03T12:00:00Z",
                "eligibility": "eligible"}
        self.repo.ingest(next_context, "new-case", [case], [],
                         {"kind": "complete_for_profile", "feed_limit_hit": False,
                          "window_complete": True, "oldest_entry_utc": None}, 1)
        selected = select_pool(self.repo, next_context.run_id, 8192)
        self.assertEqual(selected.pool_total, 1)
        self.assertEqual(selected.rows[0]["article_id"], "999")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM classifications WHERE disposition='processed_out_of_scope'").fetchone()[0], 40)


if __name__ == "__main__":
    unittest.main()
