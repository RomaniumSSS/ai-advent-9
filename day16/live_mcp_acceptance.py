"""Живая приёмка Day 16 с официальным Everything MCP Server."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from mcp_client import load_mcp_server_config
from web import Handler, ROOT, Runtime


def dispatch(runtime: Runtime, path: str, body: dict | None = None) -> dict:
    controller = SimpleNamespace(runtime=runtime)
    return Handler._dispatch(controller, path, body or {})


def main() -> None:
    config = load_mcp_server_config(ROOT / "mcp-everything.json")
    with tempfile.TemporaryDirectory() as directory:
        runtime = Runtime(Path(directory) / "acceptance.db", mcp_config=config)
        dispatch(runtime, "/api/task/start", {"objective": "Проверить MCP discovery"})
        before_state = json.dumps(runtime.state(), ensure_ascii=False, sort_keys=True)
        before_calls = len(runtime.agent.client.requests)

        result = dispatch(runtime, "/api/mcp/discover")

        assert result["protocol_version"], "MCP protocol version не получена"
        assert result["tool_count"] >= 1, "Everything Server вернул пустой список tools"
        assert result["tool_count"] == len(result["tools"])
        assert all(tool["name"] for tool in result["tools"])
        assert len(runtime.agent.client.requests) == before_calls
        assert json.dumps(runtime.state(), ensure_ascii=False, sort_keys=True) == before_state

        reply = dispatch(runtime, "/api/chat", {"text": "Назови следующий шаг задачи"})
        prompt = json.dumps(reply["context"], ensure_ascii=False)
        for tool in result["tools"]:
            assert tool["name"] not in prompt

        print(json.dumps({
            "server": result["server"],
            "protocol_version": result["protocol_version"],
            "tool_count": result["tool_count"],
            "tools": [tool["name"] for tool in result["tools"]],
            "model_calls_during_discovery": 0,
            "agent_state_unchanged": True,
            "tool_metadata_in_next_prompt": False,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
