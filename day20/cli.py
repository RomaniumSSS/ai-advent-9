"""Локальное исследование, аудит trace и единственный Telegram poller."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .agent import ResearchAgent
from .chat import BotApi, ChatService, run_poller
from .config import DATA, DB, GITHUB_TOOLS
from .mcp_router import McpConfig, Router
from .model import OpenRouterProvider, preflight
from .rss import canonical_link
from .store import Store


def github_token() -> str:
    token = os.environ.get("DAY20_GITHUB_TOKEN")
    if token:
        return token
    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                            timeout=10, check=False)
    if result.returncode or not result.stdout.strip():
        raise ValueError("github_token_missing")
    return result.stdout.strip()


def build_router(github_bin: Path, db: Path) -> Router:
    if not github_bin.is_file():
        raise ValueError("github_mcp_binary_missing")
    # AICODE-NOTE: секрет GitHub нужен только дочернему процессу GitHub MCP;
    # Habr получает очищенное окружение и никогда не читает старые БД.
    habr_env = {key: value for key, value in os.environ.items()
                if not (key.startswith("GITHUB_") or key.startswith("DAY20_GITHUB_")
                        or key.startswith("OPENROUTER_") or key.startswith("DAY18_TELEGRAM_")
                        or key.startswith("DAY20_TELEGRAM_"))}
    token = github_token()
    return Router((
        McpConfig("habr", sys.executable, ("-m", "day20.habr_server", "--db", str(db)),
                  ("search_habr_articles", "read_habr_article"), habr_env),
        McpConfig("github", str(github_bin), ("stdio", "--read-only", "--tools", ",".join(GITHUB_TOOLS)),
                  GITHUB_TOOLS, {"GITHUB_PERSONAL_ACCESS_TOKEN": token}),
    ))


def build_agent(store: Store, github_bin: Path, db: Path) -> ResearchAgent:
    profile = preflight()
    return ResearchAgent(store, build_router(github_bin, db), OpenRouterProvider(), profile)


class RefreshingAgent:
    def __init__(self, store: Store, github_bin: Path, db: Path):
        self.store, self.github_bin, self.db = store, github_bin, db

    def run(self, request_id: str) -> dict:
        # Poller может жить долго; цену и endpoint проверяем заново для каждого запроса.
        return build_agent(self.store,self.github_bin,self.db).run(request_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 20: Habr + public GitHub research")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--github-bin", type=Path,
                        default=Path(os.environ.get("DAY20_GITHUB_MCP_COMMAND", "")))
    commands = parser.add_subparsers(dest="command", required=True)
    research = commands.add_parser("research")
    research.add_argument("question")
    research.add_argument("--article")
    research.add_argument("--goal")
    commands.add_parser("poll")
    audit = commands.add_parser("audit")
    audit.add_argument("request_id")
    args = parser.parse_args()
    store = Store(args.db)
    if args.command == "audit":
        path = DATA / "traces" / f"{args.request_id}.json"
        if path.name != f"{args.request_id}.json" or not path.is_file():
            raise ValueError("trace_not_found")
        print(path.read_text())
        return
    if args.command == "research":
        article = canonical_link(args.article)[1] if args.article else None
        ident = store.create_request(args.question,article_url=article,goal=args.goal)
        result = build_agent(store,args.github_bin,args.db).run(ident)
        print(result["answer"])
        print(f"\nrequest_id={ident} fullness={result['fullness']}")
        return
    bot_token = os.environ.get("DAY18_TELEGRAM_BOT_TOKEN", "")
    chat_id = int(os.environ["DAY20_TELEGRAM_CHAT_ID"])
    user_id = int(os.environ["DAY20_TELEGRAM_USER_ID"])
    bot = BotApi(bot_token)
    service = ChatService(store, RefreshingAgent(store,args.github_bin,args.db), bot,
                          chat_id=chat_id,user_id=user_id,bot_id=bot.identity())
    run_poller(service)


if __name__ == "__main__":
    main()
