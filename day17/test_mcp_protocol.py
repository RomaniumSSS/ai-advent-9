"""Настоящий MCP Client/Server: discovery schema и tools/call Day 17."""

import subprocess
import tempfile
from pathlib import Path

from mcp import Client

from git_mcp_server import build_server, read_recent_commits
from mcp_client import McpServerConfig, discover_tools, execute_tool


def init_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Protocol"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "protocol@example.test"], check=True)
    for index in range(2):
        (repo / "data.txt").write_text(f"{index}\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "data.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", f"commit {index}"], check=True)
    return repo


def test_real_sdk_protocol():
    with tempfile.TemporaryDirectory() as directory:
        repo = init_repo(Path(directory))
        server = build_server(repo)
        factory = lambda _parameters: Client(server, raise_exceptions=True)
        config = McpServerConfig("Fixture Git", "unused", ())

        discovery = discover_tools(config, client_factory=factory)
        assert [tool.name for tool in discovery.tools] == ["get_recent_commits"]
        tool = discovery.tools[0]
        assert tool.description and tool.input_schema["properties"]["limit"]["maximum"] == 10

        result = execute_tool(
            config,
            "get_recent_commits",
            {"limit": 2},
            client_factory=factory,
        )
        expected = read_recent_commits(repo, 2).model_dump(mode="json")
        assert not result.is_error and result.structured_content == expected
        print("ok  настоящий MCP SDK discovery и tools/call совпадают с Git oracle")


if __name__ == "__main__":
    test_real_sdk_protocol()
