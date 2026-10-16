"""Discovery и один tools/call через настоящий stdio MCP."""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path
from mcp import Client, StdioServerParameters
from jsonschema import Draft202012Validator
from day31.git_mcp_server import GitContext, resolve_repo


class McpError(RuntimeError):
    pass


class GitMcpClient:
    def __init__(self, repo: Path, timeout: float = 25):
        self.repo = resolve_repo(repo)
        self.timeout = timeout
        self.last_discovery = None

    async def _read(self):
        # AICODE-NOTE: API-ключ не нужен дочернему read-only Git-процессу.
        env = {key: os.environ[key] for key in ('PATH', 'HOME', 'SYSTEMROOT', 'TMPDIR') if key in os.environ}
        params = StdioServerParameters(command=sys.executable, args=['-m', 'day31.git_mcp_server', '--repo', str(self.repo)], cwd=str(Path(__file__).resolve().parents[1]), env=env)
        try:
            async with asyncio.timeout(self.timeout):
                async with Client(params) as client:
                    tools = await client.list_tools()
                    tool = next((t for t in tools.tools if t.name == 'git_context'), None)
                    if tool is None or len(tools.tools) != 1 or tool.input_schema.get('properties', {}):
                        raise McpError('MCP discovery вернул неожиданный контракт')
                    Draft202012Validator(tool.input_schema).validate({})
                    self.last_discovery = {'protocol_version': str(client.protocol_version), 'tools': [t.name for t in tools.tools]}
                    result = await client.call_tool('git_context', {})
                    if result.is_error or result.structured_content is None:
                        raise McpError('MCP не смог прочитать Git-контекст')
                    if tool.output_schema:
                        Draft202012Validator(tool.output_schema).validate(result.structured_content)
                    value = GitContext.model_validate(result.structured_content, strict=True)
                    if value.detached != (value.branch is None):
                        raise McpError('MCP вернул противоречивую ветку')
                    return value.model_dump()
        except Exception as error:
            raise McpError('Ошибка MCP: Git-контекст недоступен') from error

    def read(self) -> dict:
        return asyncio.run(self._read())
