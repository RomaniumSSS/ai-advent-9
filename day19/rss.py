"""Ограниченное чтение фиксированного RSS Хабра."""
from __future__ import annotations
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from .config import MAX_FEED_BYTES, MAX_FEED_ITEMS, RSS_URL

ARTICLE = re.compile(r"^/ru/(?:companies/[A-Za-z0-9_-]{1,100}/)?articles/([0-9]+)/?$")
TOPIC = ("агент", "agent", "ии", " ai ", "llm", "нейросет", "бот", "автоматизац", "модел")
BIDI = {0x200e, 0x200f, *range(0x202a, 0x202f), *range(0x2066, 0x206a)}

class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ("style", "script") and self.hidden:
            self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

def sanitize(raw: str, limit: int) -> str:
    parser = Text()
    parser.feed(raw)
    value = html.unescape(" ".join("".join(parser.parts).split()))
    return "".join(c for c in value if ord(c) not in BIDI and ord(c) >= 32)[:limit]

def canonical_link(raw: str) -> tuple[str, str]:
    if len(raw) > 500:
        raise ValueError("invalid_url")
    parts = urllib.parse.urlsplit(raw.strip())
    if (parts.scheme != "https" or parts.hostname != "habr.com" or parts.username
            or parts.password or parts.port):
        raise ValueError("invalid_url")
    match = ARTICLE.fullmatch(parts.path)
    if not match:
        raise ValueError("invalid_url")
    return match.group(1), f"https://habr.com/ru/articles/{match.group(1)}/"

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlsplit(newurl)
        if parts.scheme != "https" or parts.hostname != "habr.com":
            raise ValueError("rss_redirect_outside_profile")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(*, fixture: Path | None = None) -> bytes:
    if fixture is not None:
        raw = Path(fixture).read_bytes()
    else:
        request = urllib.request.Request(RSS_URL, headers={"Accept": "application/rss+xml, application/xml",
                                                                  "User-Agent": "day19-agent/1"})
        with urllib.request.build_opener(SafeRedirect()).open(request, timeout=30) as response:
            if urllib.parse.urlsplit(response.url).hostname != "habr.com":
                raise ValueError("rss_unavailable")
            if "xml" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("rss_malformed")
            raw = response.read(MAX_FEED_BYTES + 1)
    if len(raw) > MAX_FEED_BYTES:
        raise ValueError("rss_oversize")
    return raw

def parse(raw: bytes, start: str, end: str) -> tuple[list[dict], dict, dict]:
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("rss_malformed")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ValueError("rss_malformed") from error
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("rss_malformed")
    elements = root.findall("./channel/item")
    results: list[dict] = []
    invalid = 0
    out_of_profile = 0
    oldest = None
    in_period = 0
    for element in elements[:MAX_FEED_ITEMS]:
        try:
            article_id, url = canonical_link(element.findtext("link") or "")
            title = sanitize(element.findtext("title") or "", 240)
            excerpt = sanitize(element.findtext("description") or "", 600)
            if not title:
                raise ValueError("empty_title")
        except ValueError:
            invalid += 1
            continue
        pub_raw = (element.findtext("pubDate") or "")[:128]
        try:
            parsed = parsedate_to_datetime(pub_raw)
            if parsed.tzinfo is None:
                raise ValueError("no_timezone")
            pub = parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError):
            invalid += 1
            continue
        if oldest is None or pub < oldest:
            oldest = pub
        if not start <= pub < end:
            continue
        in_period += 1
        if not any(word in f" {title.casefold()} {excerpt.casefold()} " for word in TOPIC):
            out_of_profile += 1
            continue
        results.append({"article_id": article_id, "url": url, "title": title,
                        "rss_excerpt": excerpt, "published_at_utc": pub})
    limit_hit = len(elements) >= MAX_FEED_ITEMS
    complete = not limit_hit and invalid == 0 and (not elements or oldest is not None and oldest <= start)
    coverage = {"kind": "complete_for_profile" if complete else "partial", "feed_limit_hit": limit_hit,
                "window_complete": complete, "oldest_entry_utc": oldest}
    counts = {"feed_seen": min(len(elements), MAX_FEED_ITEMS), "in_period": in_period,
              "invalid_entries": invalid, "out_of_profile": out_of_profile,
              "eligible_current": len(results)}
    return results, coverage, counts
