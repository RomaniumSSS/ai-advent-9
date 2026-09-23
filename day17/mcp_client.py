"""MCP boundary дня 17: schema-aware discovery и один tools/call."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters

DEFAULT_DISCOVERY_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class McpServerConfig:
    """Локальная конфигурация одного stdio MCP-сервера."""

    name: str
    command: str
    args: tuple[str, ...]
    transport: str = "stdio"

    @classmethod
    def from_dict(cls, value: object) -> "McpServerConfig":
        if not isinstance(value, dict):
            raise ValueError("MCP-конфигурация должна быть JSON-объектом")
        name = value.get("name")
        transport = value.get("transport")
        command = value.get("command")
        args = value.get("args")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("поле name должно быть непустой строкой")
        if transport != "stdio":
            raise ValueError("Day 17 поддерживает только MCP transport stdio")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("поле command должно быть непустой строкой")
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ValueError("поле args должно быть списком строк")
        return cls(name=name.strip(), command=command.strip(), args=tuple(args))

    def server_parameters(self) -> StdioServerParameters:
        return StdioServerParameters(command=self.command, args=list(self.args))


@dataclass(frozen=True)
class DiscoveredTool:
    name: str
    title: str | None
    description: str | None
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


@dataclass(frozen=True)
class McpDiscoveryResult:
    server: str
    protocol_version: str
    tools: tuple[DiscoveredTool, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "server": self.server,
            "protocol_version": self.protocol_version,
            "tool_count": len(self.tools),
            "tools": [tool.to_dict() for tool in self.tools],
        }


class McpDiscoveryError(RuntimeError):
    """Безопасная ошибка discovery с фазой и отдельной ошибкой cleanup."""

    _MESSAGES = {
        "connect_or_negotiate": "Не удалось подключиться к MCP-серверу или согласовать протокол",
        "list_tools": "Не удалось получить список MCP tools",
        "close": "Не удалось корректно закрыть MCP-соединение",
        "timeout": "MCP discovery превысил лимит времени",
    }

    def __init__(
        self,
        phase: str,
        *,
        detail: str | None = None,
        cleanup_detail: str | None = None,
    ):
        self.phase = phase
        self.detail = detail
        self.cleanup_detail = cleanup_detail
        message = self._MESSAGES.get(phase, "Ошибка MCP discovery")
        if cleanup_detail is not None and phase != "close":
            message += "; кроме того, не удалось корректно закрыть соединение"
        super().__init__(message)

    def with_cleanup(self, detail: str) -> "McpDiscoveryError":
        return McpDiscoveryError(
            self.phase,
            detail=self.detail,
            cleanup_detail=detail,
        )


class McpExecutionError(RuntimeError):
    _MESSAGES = {
        "connect_or_negotiate": "Не удалось подключиться к MCP-серверу или согласовать протокол",
        "call_tool": "Не удалось выполнить MCP tool",
        "close": "Не удалось корректно закрыть MCP-соединение",
        "timeout": "MCP tool execution превысил лимит времени",
    }

    def __init__(
        self,
        phase: str,
        *,
        detail: str | None = None,
        cleanup_detail: str | None = None,
    ):
        self.phase = phase
        self.detail = detail
        self.cleanup_detail = cleanup_detail
        message = self._MESSAGES.get(phase, "Ошибка MCP tool execution")
        if cleanup_detail is not None and phase != "close":
            message += "; кроме того, не удалось корректно закрыть соединение"
        super().__init__(message)

    def with_cleanup(self, detail: str) -> "McpExecutionError":
        return McpExecutionError(
            self.phase,
            detail=self.detail,
            cleanup_detail=detail,
        )


@dataclass(frozen=True)
class McpToolResult:
    server: str
    protocol_version: str
    name: str
    is_error: bool
    structured_content: object
    text_content: tuple[str, ...]

    def safe_summary(self) -> dict[str, object]:
        value = self.structured_content
        if not isinstance(value, dict):
            return {"is_error": self.is_error, "structured": False}
        commits = value.get("commits")
        ids = []
        if isinstance(commits, list):
            ids = [item.get("id") for item in commits if isinstance(item, dict)]
        return {
            "is_error": self.is_error,
            "repository": value.get("repository"),
            "count": len(commits) if isinstance(commits, list) else None,
            "commit_ids": ids,
        }


def load_mcp_server_config(path: Path) -> McpServerConfig:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"не удалось прочитать MCP-конфигурацию: {error}") from error
    return McpServerConfig.from_dict(value)


class McpClient:
    """Session boundary, к которой Day 17 сможет добавить новую операцию."""

    def __init__(
        self,
        config: McpServerConfig,
        *,
        client_factory: Callable[[StdioServerParameters], Any] = Client,
    ):
        self.config = config
        self._client = client_factory(config.server_parameters())

    async def __aenter__(self) -> "McpClient":
        try:
            await self._client.__aenter__()
        except Exception as error:
            raise McpDiscoveryError(
                "connect_or_negotiate", detail=str(error)
            ) from error
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            await self._client.__aexit__(exc_type, exc_value, traceback)
        except Exception as close_error:
            if isinstance(exc_value, (McpDiscoveryError, McpExecutionError)):
                raise exc_value.with_cleanup(str(close_error)) from close_error
            raise McpDiscoveryError("close", detail=str(close_error)) from close_error
        return False

    async def list_tools(self) -> McpDiscoveryResult:
        tools: list[DiscoveredTool] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        try:
            while True:
                page = await self._client.list_tools(cursor=cursor)
                for tool in page.tools:
                    tools.append(DiscoveredTool(
                        name=tool.name,
                        title=getattr(tool, "title", None),
                        description=getattr(tool, "description", None),
                        input_schema=dict(tool.input_schema),
                        output_schema=(
                            None if tool.output_schema is None else dict(tool.output_schema)
                        ),
                    ))
                cursor = page.next_cursor
                if cursor is None:
                    break
                if cursor in seen_cursors:
                    raise RuntimeError("MCP-сервер повторил cursor списка tools")
                seen_cursors.add(cursor)
        except McpDiscoveryError:
            raise
        except Exception as error:
            raise McpDiscoveryError("list_tools", detail=str(error)) from error
        return McpDiscoveryResult(
            server=self.config.name,
            protocol_version=str(self._client.protocol_version),
            tools=tuple(tools),
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        try:
            result = await self._client.call_tool(name, arguments)
        except Exception as error:
            raise McpExecutionError("call_tool", detail=str(error)) from error
        text = tuple(
            item.text for item in result.content
            if getattr(item, "type", None) == "text" and isinstance(item.text, str)
        )
        return McpToolResult(
            server=self.config.name,
            protocol_version=str(self._client.protocol_version),
            name=name,
            is_error=bool(result.is_error),
            structured_content=result.structured_content,
            text_content=text,
        )


async def discover_tools_async(
    config: McpServerConfig,
    *,
    timeout_seconds: float = DEFAULT_DISCOVERY_TIMEOUT_SECONDS,
    client_factory: Callable[[StdioServerParameters], Any] = Client,
) -> McpDiscoveryResult:
    if timeout_seconds <= 0:
        raise ValueError("MCP timeout должен быть положительным")
    try:
        async with asyncio.timeout(timeout_seconds):
            async with McpClient(config, client_factory=client_factory) as client:
                return await client.list_tools()
    except TimeoutError as error:
        raise McpDiscoveryError("timeout", detail=str(error)) from error


def discover_tools(
    config: McpServerConfig,
    *,
    timeout_seconds: float = DEFAULT_DISCOVERY_TIMEOUT_SECONDS,
    client_factory: Callable[[StdioServerParameters], Any] = Client,
) -> McpDiscoveryResult:
    """Синхронная граница для ThreadingHTTPServer дня 15."""

    return asyncio.run(discover_tools_async(
        config,
        timeout_seconds=timeout_seconds,
        client_factory=client_factory,
    ))


async def execute_tool_async(
    config: McpServerConfig,
    name: str,
    arguments: dict[str, Any],
    *,
    timeout_seconds: float = DEFAULT_DISCOVERY_TIMEOUT_SECONDS,
    client_factory: Callable[[StdioServerParameters], Any] = Client,
) -> McpToolResult:
    if timeout_seconds <= 0:
        raise ValueError("MCP timeout должен быть положительным")
    try:
        async with asyncio.timeout(timeout_seconds):
            async with McpClient(config, client_factory=client_factory) as client:
                return await client.call_tool(name, arguments)
    except TimeoutError as error:
        raise McpExecutionError("timeout", detail=str(error)) from error
    except McpDiscoveryError as error:
        raise McpExecutionError(error.phase, detail=error.detail) from error


def execute_tool(
    config: McpServerConfig,
    name: str,
    arguments: dict[str, Any],
    *,
    timeout_seconds: float = DEFAULT_DISCOVERY_TIMEOUT_SECONDS,
    client_factory: Callable[[StdioServerParameters], Any] = Client,
) -> McpToolResult:
    return asyncio.run(execute_tool_async(
        config,
        name,
        arguments,
        timeout_seconds=timeout_seconds,
        client_factory=client_factory,
    ))


__all__ = [
    "DEFAULT_DISCOVERY_TIMEOUT_SECONDS",
    "DiscoveredTool",
    "McpClient",
    "McpDiscoveryError",
    "McpDiscoveryResult",
    "McpExecutionError",
    "McpServerConfig",
    "McpToolResult",
    "discover_tools",
    "discover_tools_async",
    "execute_tool",
    "execute_tool_async",
    "load_mcp_server_config",
]
