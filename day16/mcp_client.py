"""Изолированный MCP-клиент дня 16: discovery без выполнения tools."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
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
            raise ValueError("Day 16 поддерживает только MCP transport stdio")
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

    def to_dict(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
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
            if isinstance(exc_value, McpDiscoveryError):
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


__all__ = [
    "DEFAULT_DISCOVERY_TIMEOUT_SECONDS",
    "DiscoveredTool",
    "McpClient",
    "McpDiscoveryError",
    "McpDiscoveryResult",
    "McpServerConfig",
    "discover_tools",
    "discover_tools_async",
    "load_mcp_server_config",
]
