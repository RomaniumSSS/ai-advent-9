"""Unit-проверки MCP discovery boundary без процессов и сети."""

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

from mcp_client import (
    McpDiscoveryError,
    McpServerConfig,
    discover_tools,
    load_mcp_server_config,
)


def tool(name, *, title=None, description=None, input_schema=None, output_schema=None):
    return SimpleNamespace(
        name=name,
        title=title,
        description=description,
        input_schema=input_schema or {"type": "object", "properties": {}},
        output_schema=output_schema,
    )


class FakeClient:
    def __init__(
        self,
        parameters,
        *,
        pages=None,
        enter_error=None,
        list_error=None,
        close_error=None,
        wait_forever=False,
    ):
        self.parameters = parameters
        self.pages = list(pages or [(None, [])])
        self.enter_error = enter_error
        self.list_error = list_error
        self.close_error = close_error
        self.wait_forever = wait_forever
        self.protocol_version = "2026-07-28"
        self.entered = 0
        self.closed = 0
        self.cursors = []

    async def __aenter__(self):
        self.entered += 1
        if self.enter_error:
            raise self.enter_error
        return self

    async def __aexit__(self, *_args):
        self.closed += 1
        if self.close_error:
            raise self.close_error

    async def list_tools(self, *, cursor=None):
        self.cursors.append(cursor)
        if self.wait_forever:
            await asyncio.sleep(3600)
        if self.list_error:
            raise self.list_error
        next_cursor, tools = self.pages.pop(0)
        return SimpleNamespace(next_cursor=next_cursor, tools=tools)


def factory(holder, **kwargs):
    def build(parameters):
        client = FakeClient(parameters, **kwargs)
        holder.append(client)
        return client
    return build


def config():
    return McpServerConfig("Тестовый MCP", "test-server", ("stdio",))


def test_config():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "mcp.json"
        path.write_text(
            '{"name":"Сервер","transport":"stdio","command":"run","args":["x"]}',
            encoding="utf-8",
        )
        loaded = load_mcp_server_config(path)
        parameters = loaded.server_parameters()
        assert loaded.name == "Сервер"
        assert parameters.command == "run" and parameters.args == ["x"]
    for invalid in (
        {},
        {"name": "x", "transport": "http", "command": "run", "args": []},
        {"name": "x", "transport": "stdio", "command": "", "args": []},
        {"name": "x", "transport": "stdio", "command": "run", "args": [1]},
    ):
        try:
            McpServerConfig.from_dict(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"невалидная конфигурация принята: {invalid}")
    print("ok  MCP-конфигурация ограничена transport stdio и списком строк")


def test_success_pagination_and_empty():
    clients = []
    result = discover_tools(
        config(),
        client_factory=factory(clients, pages=[
            ("page-2", [tool("alpha", title="Alpha", description="Первый")]),
            (None, [tool("beta")]),
        ]),
    )
    assert result.protocol_version == "2026-07-28"
    assert [item.name for item in result.tools] == ["alpha", "beta"]
    assert result.to_dict()["tool_count"] == 2
    assert result.to_dict()["tools"][0]["input_schema"]["type"] == "object"
    assert clients[0].cursors == [None, "page-2"]
    assert clients[0].entered == clients[0].closed == 1

    empty_clients = []
    empty = discover_tools(config(), client_factory=factory(empty_clients))
    assert empty.tools == () and empty_clients[0].closed == 1
    print("ok  discovery возвращает protocol version, все страницы и допустимый empty")


def test_failures_and_cleanup():
    cases = [
        ("connect_or_negotiate", {"enter_error": OSError("connect secret")}, 0),
        ("list_tools", {"list_error": RuntimeError("list secret")}, 1),
        ("close", {"close_error": RuntimeError("close secret")}, 1),
    ]
    for expected_phase, options, expected_closes in cases:
        clients = []
        try:
            discover_tools(config(), client_factory=factory(clients, **options))
        except McpDiscoveryError as error:
            assert error.phase == expected_phase
            assert "secret" not in str(error)
            assert clients[0].closed == expected_closes
        else:
            raise AssertionError(f"ошибка {expected_phase} не была возвращена")

    clients = []
    try:
        discover_tools(
            config(),
            client_factory=factory(
                clients,
                list_error=RuntimeError("list failed"),
                close_error=RuntimeError("close failed"),
            ),
        )
    except McpDiscoveryError as error:
        assert error.phase == "list_tools"
        assert error.detail == "list failed" and error.cleanup_detail == "close failed"
        assert "закрыть" in str(error)
    else:
        raise AssertionError("двойная ошибка не была возвращена")
    print("ok  ошибки фаз безопасны, cleanup выполняется и двойная ошибка не теряется")


def test_timeout_and_new_session_after_failure():
    clients = []
    try:
        discover_tools(
            config(),
            timeout_seconds=0.01,
            client_factory=factory(clients, wait_forever=True),
        )
    except McpDiscoveryError as error:
        assert error.phase == "timeout"
        assert clients[0].closed == 1
    else:
        raise AssertionError("зависший discovery не остановлен timeout")

    next_clients = []
    result = discover_tools(
        config(),
        client_factory=factory(next_clients, pages=[(None, [tool("recovered")])]),
    )
    assert [item.name for item in result.tools] == ["recovered"]
    assert next_clients[0] is not clients[0]
    print("ok  timeout закрывает session, следующий discovery создаёт новую")


def test_repeated_cursor_is_protocol_error():
    clients = []
    try:
        discover_tools(
            config(),
            client_factory=factory(clients, pages=[("same", []), ("same", [])]),
        )
    except McpDiscoveryError as error:
        assert error.phase == "list_tools" and clients[0].closed == 1
    else:
        raise AssertionError("повтор cursor должен останавливать discovery")
    print("ok  повторяющийся cursor не создаёт бесконечный discovery")


def main():
    test_config()
    test_success_pagination_and_empty()
    test_failures_and_cleanup()
    test_timeout_and_new_session_after_failure()
    test_repeated_cursor_is_protocol_error()


if __name__ == "__main__":
    main()
