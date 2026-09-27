"""Узкий stdio MCP client с раздельными discovery и execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from mcp import Client, StdioServerParameters


@dataclass(frozen=True)
class McpConfig:
    command: str
    args: tuple[str, ...]

    def parameters(self) -> StdioServerParameters:
        return StdioServerParameters(command=self.command, args=list(self.args))


class McpBoundaryError(RuntimeError):
    def __init__(self, phase: str):
        self.phase = phase
        super().__init__(phase)


async def _discover(config: McpConfig) -> list[dict]:
    async with asyncio.timeout(60):
        async with Client(config.parameters()) as client:
            tools: list[dict] = []
            cursor = None
            seen: set[str] = set()
            while True:
                page = await client.list_tools(cursor=cursor)
                tools.extend({"name": tool.name, "description": tool.description,
                              "input_schema": dict(tool.input_schema)} for tool in page.tools)
                cursor = page.next_cursor
                if cursor is None:
                    return tools
                if cursor in seen:
                    raise McpBoundaryError("pagination")
                seen.add(cursor)


def discover(config: McpConfig) -> list[dict]:
    try:
        return asyncio.run(_discover(config))
    except Exception as error:
        raise McpBoundaryError("discovery") from error


async def _execute(config: McpConfig, name: str, args: dict) -> dict:
    async with asyncio.timeout(60):
        async with Client(config.parameters()) as client:
            result = await client.call_tool(name, args)
            if result.is_error or not isinstance(result.structured_content, dict):
                raise McpBoundaryError("result")
            return dict(result.structured_content)


def execute(config: McpConfig, name: str, args: dict) -> dict:
    try:
        return asyncio.run(_execute(config, name, args))
    except Exception as error:
        raise McpBoundaryError("execution") from error
