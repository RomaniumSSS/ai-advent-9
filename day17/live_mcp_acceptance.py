"""Live Day 17 probe and bounded comparative evaluation.

The provider always receives ``tool_choice=auto``. The script never forces a
specific function call and writes reports only after the read-only snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

from mcp_client import McpToolResult, load_mcp_server_config
from web import Handler, ROOT, Runtime


TOOL_QUESTION = (
    "Покажи 3 последних коммита текущего Git-репозитория. "
    "Используй доступный Git-инструмент и для каждого коммита укажи полный id и subject."
)
DIRECT_QUESTION = "Ответь одним словом: сколько будет два плюс два?"


def dispatch(runtime: Runtime, text: str) -> dict:
    controller = SimpleNamespace(runtime=runtime)
    return Handler._dispatch(controller, "/api/chat", {"text": text})


def git_root(repo: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def git_history(repo: Path, limit: int) -> list[dict[str, str]]:
    result = subprocess.run(
        [
            "git", "-C", str(repo), "log", "-z", "-n", str(limit),
            "--format=%H%x00%s%x00%an%x00%aI",
        ],
        check=True,
        capture_output=True,
    )
    fields = result.stdout.decode("utf-8").rstrip("\0").split("\0")
    if not fields or fields == [""] or len(fields) % 4:
        raise AssertionError("independent Git oracle returned malformed/empty history")
    return [
        {"id": fields[index], "subject": fields[index + 1],
         "author": fields[index + 2], "timestamp": fields[index + 3]}
        for index in range(0, len(fields), 4)
    ]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_snapshot(repo: Path) -> dict[str, object]:
    refs = subprocess.run(
        ["git", "-C", str(repo), "show-ref"],
        check=True,
        capture_output=True,
    ).stdout
    index_name = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "index"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    index_path = Path(index_name)
    if not index_path.is_absolute():
        index_path = repo / index_path
    worktree = {
        str(path.relative_to(repo)): digest(path)
        for path in sorted(repo.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(repo).parts
    }
    return {
        "refs": hashlib.sha256(refs).hexdigest(),
        "index": digest(index_path),
        "worktree": worktree,
    }


def event_kinds(result: dict) -> list[str]:
    return [event["kind"] for event in result["audit"]["events"]]


def provider_metrics(result: dict) -> dict[str, object]:
    events = [
        event for event in result["audit"]["events"]
        if event["kind"] in {"provider_initial", "provider_final"}
    ]
    return {
        "calls": len(events),
        "prompt_tokens": sum(event["prompt_tokens"] or 0 for event in events),
        "completion_tokens": sum(event["completion_tokens"] or 0 for event in events),
        "reported_cost_usd": sum(event["cost_reported"] or 0 for event in events),
    }


def run_probe(repo: Path, config_path: Path) -> dict[str, object]:
    before = repository_snapshot(repo)
    with tempfile.TemporaryDirectory() as directory:
        runtime = Runtime(
            Path(directory) / "probe.db",
            offline=False,
            mcp_config=load_mcp_server_config(config_path),
            git_repo=repo,
        )
        result = dispatch(runtime, TOOL_QUESTION)
    after = repository_snapshot(repo)

    assert result["ok"] and result["saved"], result["message"]
    assert result["audit"]["status"] == "completed"
    assert event_kinds(result) == ["provider_initial", "mcp_execution", "provider_final"]
    mcp_event = result["audit"]["events"][1]
    assert mcp_event["status"] == "success"
    assert mcp_event["tool_name"] == "get_recent_commits"
    limit = mcp_event["arguments"]["limit"]
    oracle = git_history(repo, limit)
    observed_ids = mcp_event["result"]["commit_ids"]
    assert observed_ids == [item["id"] for item in oracle]
    assert any(
        item["id"] in result["message"] or item["subject"] in result["message"]
        for item in oracle
    )
    assert before == after, "MCP tool changed refs, index, or worktree"
    metrics = provider_metrics(result)
    assert metrics["calls"] == 2
    return {
        "status": "pass",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": runtime.agent.config.model,
        "question": TOOL_QUESTION,
        "model_selected_tool": True,
        "tool_choice": "auto",
        "tool_name": mcp_event["tool_name"],
        "validated_arguments": mcp_event["arguments"],
        "mcp_executions": 1,
        "provider": metrics,
        "trace": event_kinds(result),
        "git_oracle_ids": [item["id"] for item in oracle],
        "observation_ids": observed_ids,
        "final_grounded": True,
        "git_unchanged": True,
        "final_response": result["message"],
    }


def run_comparison(repo: Path, config_path: Path, probe: dict) -> dict[str, object]:
    config = load_mcp_server_config(config_path)
    before = repository_snapshot(repo)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        direct_runtime = Runtime(
            root / "direct.db", offline=False, mcp_config=config, git_repo=repo,
        )
        direct = dispatch(direct_runtime, DIRECT_QUESTION)

        def fail_execution(_config, name, _arguments):
            return McpToolResult(
                server="Day 17 Git",
                protocol_version="2025-11-25",
                name=name,
                is_error=True,
                structured_content=None,
                text_content=("injected evaluation failure",),
            )

        failure_runtime = Runtime(
            root / "failure.db",
            offline=False,
            mcp_config=config,
            mcp_execute=fail_execution,
            git_repo=repo,
        )
        failure = dispatch(failure_runtime, TOOL_QUESTION)
    after = repository_snapshot(repo)

    assert direct["ok"] and direct["saved"]
    assert event_kinds(direct) == ["provider_initial"]
    assert failure["ok"] and failure["saved"]
    assert event_kinds(failure) == [
        "provider_initial", "mcp_execution", "provider_final", "local_result"
    ]
    assert failure["audit"]["events"][1]["status"] == "error"
    assert "Не удалось получить проверенные данные Git" in failure["message"]
    assert not any(commit_id in failure["message"] for commit_id in probe["git_oracle_ids"])
    assert before == after
    return {
        "status": "pass",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": direct_runtime.agent.config.model,
        "scenarios": {
            "direct_chat": {
                "trace": event_kinds(direct),
                "provider": provider_metrics(direct),
                "mcp_executions": 0,
                "persisted": direct["saved"],
            },
            "tool_success": {
                "trace": probe["trace"],
                "provider": probe["provider"],
                "mcp_executions": probe["mcp_executions"],
                "grounded": probe["final_grounded"],
                "persisted": True,
            },
            "tool_failure": {
                "trace": event_kinds(failure),
                "provider": provider_metrics(failure),
                "mcp_executions": 1,
                "false_success": False,
                "persisted": failure["saved"],
            },
        },
        "git_unchanged": True,
        "conclusion": (
            "Direct chat used one provider call and no MCP execution; successful tool "
            "chat used two provider calls and one grounded execution; failed execution "
            "used two provider calls but persisted only the canonical safe response."
        ),
    }


def write_report(output: Path, report: dict[str, object]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Day 17 live evidence", "", f"Status: **{report['status']}**",
        f"Model: `{report['model']}`", f"UTC: `{report['timestamp_utc']}`", "",
        "Machine-readable evidence: `report.json`.",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("probe", "compare"))
    parser.add_argument("--repo", type=Path, default=ROOT.parent)
    parser.add_argument("--config", type=Path, default=ROOT / "mcp-git.json")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe-report", type=Path)
    args = parser.parse_args()
    load_dotenv(args.env_file)
    repo = git_root(args.repo)
    if args.mode == "probe":
        report = run_probe(repo, args.config)
    else:
        if args.probe_report is None:
            parser.error("compare требует --probe-report")
        probe = json.loads(args.probe_report.read_text(encoding="utf-8"))
        if probe.get("status") != "pass":
            parser.error("probe report не подтверждает successful E2E")
        report = run_comparison(repo, args.config, probe)
    write_report(args.output, report)
    print(json.dumps({
        "status": report["status"], "mode": args.mode, "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
