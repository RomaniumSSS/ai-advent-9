"""Собственный read-only MCP server: последние коммиты одного Git repository."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

MIN_COMMITS = 1
MAX_COMMITS = 10
GIT_TIMEOUT_SECONDS = 10.0


class CommitInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    subject: str
    author: str
    timestamp: str


class RecentCommits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str
    commits: list[CommitInfo]


def _git(repo: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=GIT_TIMEOUT_SECONDS,
        shell=False,
    )
    return completed.stdout


def resolve_repo(path: Path) -> Path:
    """Разрешить trusted startup config до canonical Git worktree root."""

    requested = path.expanduser().resolve(strict=True)
    try:
        root = _git(requested, "rev-parse", "--show-toplevel").decode().strip()
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as error:
        raise ValueError("настроенный путь не является доступным Git repository") from error
    return Path(root).resolve(strict=True)


def repository_identity(repo: Path) -> str:
    return hashlib.sha256(str(repo.resolve(strict=True)).encode()).hexdigest()


def read_recent_commits(repo: Path, limit: int) -> RecentCommits:
    if type(limit) is not int or not MIN_COMMITS <= limit <= MAX_COMMITS:
        raise ValueError(f"limit должен быть целым числом {MIN_COMMITS}..{MAX_COMMITS}")
    try:
        raw = _git(
            repo,
            "log",
            "-z",
            "-n",
            str(limit),
            "--format=%H%x00%s%x00%an%x00%aI",
        )
        values = raw.decode("utf-8", errors="strict").split("\0")
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as error:
        raise RuntimeError("не удалось прочитать Git history") from error
    if values and values[-1] == "":
        values.pop()
    if not values or len(values) % 4:
        raise RuntimeError("Git history вернула пустой или malformed result")
    commits = []
    for offset in range(0, len(values), 4):
        commit_id, subject, author, timestamp = values[offset : offset + 4]
        if not all(item.strip() for item in (commit_id, subject, author, timestamp)):
            raise RuntimeError("Git history содержит пустое обязательное поле")
        commits.append(CommitInfo(
            id=commit_id,
            subject=subject,
            author=author,
            timestamp=timestamp,
        ))
    return RecentCommits(repository=repository_identity(repo), commits=commits)


def build_server(repo: Path) -> MCPServer:
    root = resolve_repo(repo)
    server = MCPServer(
        "day17-git",
        title="Day 17 read-only Git MCP",
        instructions="Только чтение последних коммитов настроенного repository.",
    )

    @server.tool(
        title="Последние Git-коммиты",
        description=(
            "Прочитать последние коммиты настроенного Git repository. "
            "Использовать только когда ответу нужны актуальные данные истории Git."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    def get_recent_commits(
        limit: int = Field(
            ge=MIN_COMMITS,
            le=MAX_COMMITS,
            description="Сколько последних коммитов вернуть.",
        ),
    ) -> RecentCommits:
        return read_recent_commits(root, limit)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    build_server(args.repo).run("stdio")


if __name__ == "__main__":
    main()
