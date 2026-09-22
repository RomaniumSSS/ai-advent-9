"""Интеграция discovery boundary с настоящими MCP client и server."""

from mcp import Client
from mcp.server import MCPServer

from mcp_client import McpServerConfig, discover_tools


def test_real_sdk_protocol():
    server = MCPServer("day16-test-server")
    calls = []

    @server.tool(title="Сложить числа")
    def add(left: int, right: int) -> int:
        """Сложить два целых числа."""

        calls.append((left, right))
        return left + right

    result = discover_tools(
        McpServerConfig("Fixture MCP", "unused", ()),
        client_factory=lambda _parameters: Client(server, raise_exceptions=True),
    )

    assert result.protocol_version
    assert [tool.name for tool in result.tools] == ["add"]
    assert result.tools[0].title == "Сложить числа"
    assert result.tools[0].description == "Сложить два целых числа."
    assert calls == [], "Day 16 не должен выполнять обнаруженный tool"
    print("ok  настоящий MCP SDK согласует протокол и только перечисляет tool")


if __name__ == "__main__":
    test_real_sdk_protocol()
