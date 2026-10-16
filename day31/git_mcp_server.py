"""Самостоятельный read-only MCP-сервер: текущий Git-контекст."""
from __future__ import annotations
import argparse
import hashlib
import re
import subprocess
from pathlib import Path
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict


class GitContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    repository_id: str
    branch: str | None
    detached: bool
    head: str


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE, timeout=10).decode('utf-8').strip()


def resolve_repo(path: Path) -> Path:
    try:
        requested = path.expanduser().resolve(strict=True)
        return Path(git(requested, 'rev-parse', '--show-toplevel')).resolve(strict=True)
    except (OSError, subprocess.SubprocessError, UnicodeError) as error:
        raise ValueError('Git-root недоступен или не является репозиторием') from error


def read_context(root: Path) -> GitContext:
    try:
        head = git(root, 'rev-parse', '--verify', 'HEAD')
        if not re.fullmatch(r'[0-9a-f]{40,64}', head):
            raise ValueError('Некорректный HEAD')
        branch = git(root, 'branch', '--show-current') or None
        return GitContext(repository_id=hashlib.sha256(str(root).encode()).hexdigest(), branch=branch, detached=branch is None, head=head)
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError) as error:
        raise ToolError('Не удалось прочитать Git HEAD/ветку') from error


class ReadOnlyServer(MCPServer):
    async def call_tool(self, name, arguments, context=None):
        # AICODE-NOTE: SDK по умолчанию игнорирует лишние аргументы функции.
        if name != 'git_context' or arguments:
            raise ToolError('git_context принимает только пустой объект аргументов')
        return await super().call_tool(name, arguments, context)


def build_server(repo: Path):
    root = resolve_repo(repo)
    server = ReadOnlyServer('day31-git', instructions='Только чтение текущей ветки фиксированного Git-root.')

    @server.tool(description='Прочитать ветку, detached HEAD и head фиксированного репозитория.', annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False), structured_output=True)
    def git_context() -> GitContext:
        return read_context(root)

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    build_server(args.repo).run('stdio')


if __name__ == '__main__':
    main()
