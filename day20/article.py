"""Полный текст одной статьи Хабра с ограниченной загрузкой."""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from .config import MAX_ARTICLE_BYTES, MAX_ARTICLE_CHARS
from .rss import canonical_link

GITHUB_REPO = re.compile(r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/.*)?$")
BLOCKS = {"p", "div", "br", "li", "ul", "ol", "pre", "blockquote", "h2", "h3", "h4", "tr"}
VOID = {"br", "hr", "img", "input", "meta", "link", "source", "wbr"}


def github_repo(raw: str) -> str | None:
    parts = urllib.parse.urlsplit(raw)
    if parts.scheme not in ("https", "http") or parts.hostname not in ("github.com", "www.github.com"):
        return None
    if parts.username or parts.password or parts.port or not GITHUB_REPO.fullmatch(parts.path):
        return None
    owner, repo = parts.path.strip("/").split("/")[:2]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return f"https://github.com/{owner}/{repo}"


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.body_depth = 0
        self.hidden = 0
        self.in_title = False
        self.title_parts: list[str] = []
        self.parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h1" and not self.title_parts:
            self.in_title = True
        if tag == "div" and "article-formatted-body" in (attributes.get("class") or "") and not self.body_depth:
            self.body_depth = 1
        elif self.body_depth and tag not in VOID:
            self.body_depth += 1
        if self.body_depth:
            if tag in ("script", "style", "noscript"):
                self.hidden += 1
            if tag in BLOCKS:
                self.parts.append("\n")
            if tag == "a":
                url = github_repo(html.unescape(attributes.get("href") or ""))
                if url and url not in self.links:
                    self.links.append(url)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_title = False
        if tag in VOID:
            return
        if self.body_depth:
            if tag in ("script", "style", "noscript") and self.hidden:
                self.hidden -= 1
            if tag in BLOCKS:
                self.parts.append("\n")
            self.body_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.body_depth and not self.hidden:
            self.parts.append(data)


def parse_article(raw: bytes) -> tuple[str, str, list[str], bool]:
    parser = ArticleParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    if not parser.parts:
        raise ValueError("article_body_missing")
    title = " ".join(" ".join(parser.title_parts).split())[:240]
    body = "\n".join(" ".join(line.split()) for line in "".join(parser.parts).splitlines() if line.strip())
    body = "".join(c for c in body if c == "\n" or ord(c) >= 32)
    if not title or len(body) < 80:
        raise ValueError("article_body_missing")
    truncated = len(body) > MAX_ARTICLE_CHARS
    return title, body[:MAX_ARTICLE_CHARS], parser.links, truncated


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        try:
            canonical_link(newurl)
        except ValueError as error:
            raise ValueError("article_redirect_outside_habr") from error
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def fetch_article(url: str, *, fixture: Path | None = None) -> bytes:
    article_id, canonical = canonical_link(url)
    if fixture is not None:
        raw = Path(fixture).read_bytes()
    else:
        request = urllib.request.Request(canonical, headers={
            "Accept": "text/html", "User-Agent": "day20-agent/1"})
        with urllib.request.build_opener(SafeRedirect()).open(request, timeout=20) as response:
            final_id, _ = canonical_link(response.url)
            if final_id != article_id or "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("article_unavailable")
            raw = response.read(MAX_ARTICLE_BYTES + 1)
    if len(raw) > MAX_ARTICLE_BYTES:
        raise ValueError("article_oversize")
    return raw
