"""Два управляемых stdio MCP для проверки адресации без сети."""
from __future__ import annotations

import argparse
import time
from typing import Any

from mcp.server import MCPServer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    server = MCPServer("day20-test-" + args.name)

    @server.tool(structured_output=True)
    def echo(value: str) -> dict[str, Any]:
        return {"status": "ok", "server": args.name, "value": value}

    @server.tool(structured_output=True)
    def large() -> dict[str, Any]:
        return {"status": "ok", "text": "x" * 40_000}

    @server.tool()
    def fail() -> str:
        raise ValueError("test_failure")

    @server.tool(structured_output=True)
    def slow() -> dict[str, Any]:
        time.sleep(0.5)
        return {"status": "ok"}

    @server.tool()
    def write_data() -> str:
        return "should_never_execute"

    server.run("stdio")


if __name__ == "__main__":
    main()
