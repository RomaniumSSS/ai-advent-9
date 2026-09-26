"""Один MCP tool: фиксированный RSS Хабра, atomic ingestion, bounded aggregate."""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator, FormatChecker
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

from day18.config import MAX_FEED_BYTES, MAX_FEED_ITEMS, PROFILE, RSS_URL, TOOL_NAME
from day18.models import RunContext
from day18.repository import Repository, compact, digest
from day18.store import Store

INPUT_SCHEMA = __import__("json").loads((Path(__file__).parent / "schemas/collect_input.json").read_text())
# AICODE-NOTE: RSS отдаёт и /ru/articles/ID, и /ru/companies/slug/articles/ID;
# обе формы ведут к одной статье, поэтому identity остаётся числовым ID.
_ARTICLE_PATH = re.compile(r"^/ru/(?:companies/[A-Za-z0-9_-]{1,100}/)?articles/([0-9]+)/?$")
_BIDI = set(chr(value) for value in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))
_TOPIC = ("агент", "agent", "ии", " ai ", "llm", "нейросет", "бот", "автоматизац", "модел")


class Counts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feed_seen: int
    in_period: int
    new_observations: int
    repeated_articles: int
    eligible_candidates: int
    omitted_candidates: int
    invalid_entries: int
    out_of_profile: int


class Coverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    feed_limit_hit: bool
    window_complete: bool
    oldest_entry_utc: str | None


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    article_id: str
    observation_id: str
    url: str
    title: str
    rss_excerpt: str
    published_at_utc: str | None


class CollectResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    run_id: str
    batch_id: str | None
    source_profile_id: str
    period_start_utc: str
    period_end_utc: str
    read_at_utc: str | None
    counts: Counts
    coverage: Coverage
    candidates: list[Candidate]
    reason_code: str


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def sanitize(value: str, limit: int) -> str:
    parser = _Text()
    parser.feed(value)
    cleaned = " ".join("".join(parser.parts).split())
    cleaned = html.unescape(cleaned)
    cleaned = "".join(ch for ch in cleaned if ch not in _BIDI and (ch >= " " or ch == "\n"))
    return cleaned[:limit]


def canonical_link(raw: str) -> tuple[str, str]:
    if len(raw) > 500:
        raise ValueError("invalid_habr_url")
    parts = urllib.parse.urlsplit(raw.strip())
    if parts.scheme != "https" or parts.hostname != "habr.com" or parts.username or parts.password or parts.port:
        raise ValueError("invalid_habr_url")
    match = _ARTICLE_PATH.fullmatch(parts.path)
    if not match:
        raise ValueError("invalid_article_path")
    if len(match.group(1)) > 100:
        raise ValueError("invalid_article_path")
    return match.group(1), f"https://habr.com/ru/articles/{match.group(1)}/"


def parse_feed(raw: bytes, context: RunContext) -> tuple[list[dict], list[dict], dict, int]:
    if len(raw) > MAX_FEED_BYTES:
        raise ValueError("oversize")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("rss_malformed")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ValueError("rss_malformed") from error
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("rss_malformed")
    elements = root.findall("./channel/item")
    feed_seen = min(len(elements), MAX_FEED_ITEMS)
    items: list[dict] = []
    rejections: list[dict] = []
    oldest: str | None = None
    for ordinal, element in enumerate(elements[:MAX_FEED_ITEMS]):
        link_raw = (element.findtext("link") or "").strip()
        title_raw = element.findtext("title") or ""
        excerpt_raw = element.findtext("description") or ""
        pub_raw = (element.findtext("pubDate") or "").strip()[:128]
        try:
            article_id, url = canonical_link(link_raw)
            title = sanitize(title_raw, 240)
            excerpt = sanitize(excerpt_raw, 1000)
            if not title:
                raise ValueError("empty_title")
        except ValueError as error:
            rejections.append({"ordinal": ordinal, "reason_code": "invalid_article",
                               "evidence_hash": digest(f"{ordinal}|{link_raw[:500]}|{type(error).__name__}")})
            continue
        try:
            parsed = parsedate_to_datetime(pub_raw)
            if parsed.tzinfo is None:
                raise ValueError("pubDate без зоны")
            published = parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError):
            published = None
        if published and (oldest is None or published < oldest):
            oldest = published
        text = f" {title.lower()} {excerpt.lower()} "
        eligibility = "eligible" if any(word in text for word in _TOPIC) else "out_of_profile"
        items.append({"article_id": article_id, "url": url, "title": title, "rss_excerpt": excerpt,
                      "original_pubdate": pub_raw or None, "published_at_utc": published,
                      "eligibility": eligibility})
    feed_limit_hit = len(elements) >= MAX_FEED_ITEMS
    # AICODE-NOTE: если RSS не доходит до начала окна, пустота feed не доказывает полный охват периода.
    window_complete = not feed_limit_hit and (not elements or oldest is not None and oldest <= context.slot.period_start_utc)
    coverage = {"kind": "complete_for_profile" if window_complete and not rejections else "partial",
                "feed_limit_hit": feed_limit_hit, "window_complete": window_complete and not rejections,
                "oldest_entry_utc": oldest}
    return items, rejections, coverage, feed_seen


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlsplit(newurl)
        if parts.scheme != "https" or parts.hostname != "habr.com":
            raise urllib.error.HTTPError(newurl, code, "redirect outside profile", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_rss() -> bytes:
    opener = urllib.request.build_opener(_SafeRedirect())
    request = urllib.request.Request(RSS_URL, headers={"Accept": "application/rss+xml, application/xml", "User-Agent": "day18-agent/1"})
    deadline = time.monotonic() + 60
    for attempt in range(2):
        try:
            response = opener.open(request, timeout=max(0.1, deadline - time.monotonic()))
            break
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError:
            if attempt or time.monotonic() >= deadline:
                raise
    with response:
        if urllib.parse.urlsplit(response.url).hostname != "habr.com":
            raise ValueError("rss_unavailable")
        content_type = response.headers.get("Content-Type", "").lower()
        if "rss+xml" not in content_type and "xml" not in content_type:
            raise ValueError("rss_malformed")
        socket = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if socket is None or not hasattr(socket, "settimeout") or not hasattr(response, "read1"):
            raise ValueError("rss_unavailable")
        chunks: list[bytes] = []
        size = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("RSS active budget")
            socket.settimeout(min(15.0, remaining))
            chunk = response.read1(min(65_536, MAX_FEED_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_FEED_BYTES:
                raise ValueError("oversize")
        raw = b"".join(chunks)
    if len(raw) > MAX_FEED_BYTES:
        raise ValueError("oversize")
    return raw


def error_result(context: RunContext, status: str, reason: str) -> dict:
    return {"status": status, "run_id": context.run_id, "batch_id": None,
            "source_profile_id": PROFILE, "period_start_utc": context.slot.period_start_utc,
            "period_end_utc": context.slot.period_end_utc, "read_at_utc": None,
            "counts": {key: 0 for key in ("feed_seen", "in_period", "new_observations", "repeated_articles",
                                          "eligible_candidates", "omitted_candidates", "invalid_entries", "out_of_profile")},
            "coverage": {"kind": "unknown", "feed_limit_hit": False, "window_complete": False, "oldest_entry_utc": None},
            "candidates": [], "reason_code": reason}


def collect(repo: Repository, arguments: dict, fetch: Callable[[], bytes] = fetch_rss,
            tool_call_id: str = "direct-mcp") -> dict:
    errors = list(Draft202012Validator(INPUT_SCHEMA, format_checker=FormatChecker()).iter_errors(arguments))
    if errors:
        raise ValueError("invalid_request")
    context = repo.context(arguments["run_id"])
    if arguments != context.tool_arguments():
        return error_result(context, "invalid_request", "context_mismatch")
    if repo.run(context.run_id)["state"] != "MCP_PENDING":
        return error_result(context, "invalid_request", "tool_not_allowed")
    saved = repo.batch_for(context.run_id, context.idempotency_key)
    if saved is not None:
        return saved
    try:
        reservation = repo.reserve_phase(context.run_id, "mcp", 60_000)
    except ValueError:
        return error_result(context, "invalid_request", "budget_exhausted")
    started = time.monotonic()
    try:
        repo.increment_mcp_execution(context.run_id)
        raw = fetch()
        items, rejections, coverage, seen = parse_feed(raw, context)
        return repo.ingest(context, tool_call_id, items, rejections, coverage, seen)
    except TimeoutError:
        return error_result(context, "source_error", "timeout")
    except urllib.error.URLError:
        return error_result(context, "source_error", "rss_unavailable")
    except ValueError as error:
        reason = str(error)
        if reason == "oversize":
            coverage = {"kind": "partial", "feed_limit_hit": False,
                        "window_complete": False, "oldest_entry_utc": None}
            return repo.ingest(context, tool_call_id, [], [], coverage, 0, reason_override="oversize")
        return error_result(context, "source_error", reason if reason in ("oversize", "rss_malformed") else "rss_unavailable")
    except Exception:
        return error_result(context, "storage_error", "storage_failure")
    finally:
        repo.settle_phase(reservation, int((time.monotonic() - started) * 1000))


def build_server(db_path: Path, fetch: Callable[[], bytes] = fetch_rss,
                 tool_call_id: str = "direct-mcp") -> MCPServer:
    store = Store(db_path)
    store.migrate()
    repo = Repository(store)
    server = MCPServer("day18-habr-rss", title="Day 18 Habr RSS", instructions="Только фиксированный RSS profile.")

    @server.tool(title="Собрать публикации о ИИ-агентах", description="Прочитать фиксированный RSS Хабра и сохранить batch.",
                 annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True),
                 structured_output=True)
    def collect_habr_agent_cases(run_id: str, scheduled_slot: str, period_start_utc: str,
                                 period_end_utc: str, timezone: str, source_profile_id: str,
                                 idempotency_key: str) -> CollectResult:
        return CollectResult.model_validate(collect(repo, {"run_id": run_id, "scheduled_slot": scheduled_slot,
                              "period_start_utc": period_start_utc, "period_end_utc": period_end_utc,
                              "timezone": timezone, "source_profile_id": source_profile_id,
                              "idempotency_key": idempotency_key}, fetch, tool_call_id))

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--tool-call-id", default="direct-mcp")
    args = parser.parse_args()
    build_server(args.db, tool_call_id=args.tool_call_id).run("stdio")


if __name__ == "__main__":
    main()
