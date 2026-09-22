"""Проверки MCP discovery внутри приложения дня 16."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from mcp_client import (
    DiscoveredTool,
    McpDiscoveryError,
    McpDiscoveryResult,
    McpServerConfig,
)
from web import Handler, Runtime


def dispatch(runtime, path, body=None):
    controller = SimpleNamespace(runtime=runtime)
    return Handler._dispatch(controller, path, body or {})


def make_runtime(db, discover):
    return Runtime(
        db,
        mcp_config=McpServerConfig("Fixture MCP", "fixture", ()),
        mcp_discover=discover,
    )


def test_discovery_does_not_touch_agent_state(db):
    calls = []

    def discover(config):
        calls.append(config)
        return McpDiscoveryResult(
            server=config.name,
            protocol_version="2026-07-28",
            tools=(DiscoveredTool("dangerous-name", "Проверка", "Только описание"),),
        )

    runtime = make_runtime(db, discover)
    dispatch(runtime, "/api/task/start", {"objective": "Сохранить baseline"})
    dispatch(runtime, "/api/save", {"layer": "working", "key": "факт", "value": "не менять"})
    before = json.dumps(runtime.state(), ensure_ascii=False, sort_keys=True)
    model_calls = len(runtime.agent.client.requests)

    result = dispatch(runtime, "/api/mcp/discover")

    assert result == {
        "server": "Fixture MCP",
        "protocol_version": "2026-07-28",
        "tool_count": 1,
        "tools": [{
            "name": "dangerous-name",
            "title": "Проверка",
            "description": "Только описание",
        }],
    }
    assert "input_schema" not in result["tools"][0]
    assert len(calls) == 1
    assert len(runtime.agent.client.requests) == model_calls
    assert json.dumps(runtime.state(), ensure_ascii=False, sort_keys=True) == before

    reply = dispatch(runtime, "/api/chat", {"text": "Какой следующий шаг?"})
    payload = json.dumps(reply["context"], ensure_ascii=False)
    assert "dangerous-name" not in payload and "Только описание" not in payload
    print("ok  MCP discovery не вызывает модель и не меняет state или следующий prompt")


def test_discovery_failure_is_safe(db):
    def fail(_config):
        raise McpDiscoveryError("list_tools", detail="секретный stderr")

    runtime = make_runtime(db, fail)
    before = json.dumps(runtime.state(), ensure_ascii=False, sort_keys=True)
    try:
        dispatch(runtime, "/api/mcp/discover")
    except McpDiscoveryError as error:
        assert error.phase == "list_tools"
        assert "секретный stderr" not in str(error)
    else:
        raise AssertionError("ошибка MCP должна дойти до HTTP boundary")
    assert json.dumps(runtime.state(), ensure_ascii=False, sort_keys=True) == before
    assert runtime.agent.store.load() == []
    print("ok  ошибка MCP безопасна и не пишет tool metadata в SQLite")


def test_missing_server_config(db):
    runtime = Runtime(db)
    try:
        dispatch(runtime, "/api/mcp/discover")
    except McpDiscoveryError as error:
        assert error.phase == "connect_or_negotiate"
    else:
        raise AssertionError("discovery без конфигурации не должен запускаться")
    print("ok  приложение явно сообщает об отсутствии MCP-конфигурации")


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        test_discovery_does_not_touch_agent_state(root / "success.db")
        test_discovery_failure_is_safe(root / "failure.db")
        test_missing_server_config(root / "missing.db")


if __name__ == "__main__":
    main()
