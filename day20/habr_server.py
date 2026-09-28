"""Отдельный Habr MCP Day 20: ограниченный RSS и полная статья частями."""
from __future__ import annotations

import argparse
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import rss
from .article import fetch_article, parse_article
from .config import ARTICLE_CHUNK_CHARS, DB, PROFILE
from .store import Store


class HabrOperations:
    def __init__(self, store: Store, rss_fetcher: Callable[[], bytes],
                 article_fetcher: Callable[[str], bytes]):
        self.store = store
        self.rss_fetcher = rss_fetcher
        self.article_fetcher = article_fetcher

    def search(self, query: str = "", days: int = 14, limit: int = 10) -> dict:
        try:
            if not 1 <= days <= 30 or not 1 <= limit <= 20 or len(query) > 120:
                raise ValueError("search_limit")
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            items, coverage, counts = rss.parse(self.rss_fetcher(), start.strftime(fmt), end.strftime(fmt))
            words = [part.casefold() for part in query.split() if part]
            if words:
                items = [item for item in items if all(word in (item["title"] + " " + item["rss_excerpt"]).casefold()
                                                       for word in words)]
            return {"status": "ok", "source_profile_id": PROFILE, "coverage": coverage,
                    "counts": counts, "query": query, "articles": items[:limit],
                    "returned": min(len(items), limit)}
        except Exception as error:
            return {"status": "error", "code": str(error) if isinstance(error, ValueError) else "rss_unavailable"}

    def read(self, run_id: str, url: str, cursor: str = "") -> dict:
        try:
            uuid.UUID(run_id)
            _, canonical = rss.canonical_link(url)
            record = self.store.article(run_id, canonical)
            if record is None:
                if cursor:
                    raise ValueError("unknown_article_cursor")
                title, body, links, truncated = parse_article(self.article_fetcher(canonical))
                record = self.store.save_article(run_id, canonical, title, body, links, truncated)
            index = 0
            if cursor:
                prefix = record["id"] + ":"
                if not cursor.startswith(prefix) or not cursor[len(prefix):].isdigit():
                    raise ValueError("invalid_article_cursor")
                index = int(cursor[len(prefix):])
            total = max(1, math.ceil(len(record["body"]) / ARTICLE_CHUNK_CHARS))
            if index >= total:
                raise ValueError("invalid_article_cursor")
            complete = self.store.mark_chunk(run_id, canonical, index, total)
            return {"status": "ok", "url": canonical, "title": record["title"],
                    "snapshot_id": record["id"], "body_sha256": record["body_sha256"],
                    "read_at_utc": record["read_at_utc"], "github_repos": json.loads(record["links_json"]),
                    "part": index + 1, "parts_total": total,
                    "text": record["body"][index * ARTICLE_CHUNK_CHARS:(index + 1) * ARTICLE_CHUNK_CHARS],
                    "next_cursor": f"{record['id']}:{index + 1}" if index + 1 < total else None,
                    "complete_read": complete, "truncated": bool(record["truncated"])}
        except Exception as error:
            return {"status": "error", "code": str(error) if isinstance(error, ValueError) else "article_unavailable"}


def build_server(store: Store, rss_fetcher: Callable[[], bytes],
                 article_fetcher: Callable[[str], bytes]) -> MCPServer:
    operations = HabrOperations(store, rss_fetcher, article_fetcher)
    server = MCPServer("day20-habr", title="Day 20 Habr",
                       instructions="Поиск только по фиксированной RSS-ленте и чтение статьи по HTTPS URL.")

    @server.tool(description="Искать статьи только в фиксированной RSS-ленте Хабра об ИИ-агентах.",
                 annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True), structured_output=True)
    def search_habr_articles(query: str = "", days: int = 14, limit: int = 10) -> dict[str, Any]:
        return operations.search(query, days, limit)

    @server.tool(description="Читать полную статью Хабра частями. Передай next_cursor для следующей части; complete_read подтверждает полный охват.",
                 annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True), structured_output=True)
    def read_habr_article(run_id: str, url: str, cursor: str = "") -> dict[str, Any]:
        return operations.read(run_id, url, cursor)

    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--rss-file", type=Path)
    parser.add_argument("--article-file", type=Path)
    args = parser.parse_args()
    build_server(Store(args.db), lambda: rss.fetch(fixture=args.rss_file),
                 lambda url: fetch_article(url, fixture=args.article_file)).run("stdio")


if __name__ == "__main__":
    main()
