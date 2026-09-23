"""Read-only proof for the custom Git MCP tool."""

import asyncio
import hashlib
import subprocess
import tempfile
from pathlib import Path

from mcp import Client

from git_mcp_server import build_server
from test_mcp_protocol import init_repo


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(repo: Path) -> dict:
    refs = subprocess.run(
        ["git", "-C", str(repo), "show-ref"],
        check=True,
        capture_output=True,
    ).stdout
    index = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "index"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    index_path = Path(index)
    if not index_path.is_absolute():
        index_path = repo / index_path
    manifest = {
        str(path.relative_to(repo)): digest(path)
        for path in sorted(repo.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(repo).parts
    }
    return {
        "refs": hashlib.sha256(refs).hexdigest(),
        "index": digest(index_path),
        "worktree": manifest,
    }


async def exercise(repo: Path):
    async with Client(build_server(repo), raise_exceptions=True) as client:
        before = snapshot(repo)
        result = await client.call_tool("get_recent_commits", {"limit": 2})
        after = snapshot(repo)
        assert not result.is_error and before == after
        ignored_override = await client.call_tool(
            "get_recent_commits", {"limit": 1, "repo": "/tmp/other"}
        )
        assert (
            ignored_override.structured_content["repository"]
            == result.structured_content["repository"]
        ), "необъявленный argument не должен менять configured repository"
        assert snapshot(repo) == after


def main():
    with tempfile.TemporaryDirectory() as directory:
        repo = init_repo(Path(directory))
        (repo / "ignored.tmp").write_text("untracked evidence\n", encoding="utf-8")
        asyncio.run(exercise(repo))
    print("ok  refs, index и полный worktree неизменны; repo override не меняет scope")


if __name__ == "__main__":
    main()
