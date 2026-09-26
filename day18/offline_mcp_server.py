"""Только локальная protocol fixture: RSS читается из тестового файла."""

from __future__ import annotations

import argparse
from pathlib import Path

from day18.rss_mcp_server import build_server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--tool-call-id", default="direct-mcp")
    args = parser.parse_args()
    build_server(args.db, lambda: args.fixture.read_bytes(), args.tool_call_id).run("stdio")


if __name__ == "__main__":
    main()
