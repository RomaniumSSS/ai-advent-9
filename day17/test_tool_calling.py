"""Offline acceptance matrix for the bounded Day 17 chat tool loop."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

from agent import Agent, AgentConfig
from git_mcp_server import read_recent_commits
from mcp_client import (
    DiscoveredTool,
    McpDiscoveryError,
    McpDiscoveryResult,
    McpServerConfig,
    McpToolResult,
)
from store import SqliteStore
from tool_calling import ToolRuntime

SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "description": "Сколько последних коммитов вернуть.",
        },
    },
    "required": ["limit"],
    "additionalProperties": False,
}


def response(text="", *, calls=(), finish="stop"):
    tool_calls = [
        SimpleNamespace(
            id=item.get("id"),
            function=SimpleNamespace(
                name=item.get("name"),
                arguments=item.get("arguments"),
            ),
        )
        for item in calls
    ]
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=text, tool_calls=tool_calls),
            finish_reason=finish,
        )],
        usage=None,
        provider="offline-test",
    )


class SequenceClient:
    def __init__(self, responses, callbacks=None):
        self.responses = list(responses)
        self.callbacks = list(callbacks or [])
        self.requests = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.requests.append(kwargs)
        index = len(self.requests) - 1
        if index < len(self.callbacks) and self.callbacks[index] is not None:
            self.callbacks[index]()
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def init_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Day 17"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "day17@example.test"], check=True)
    (repo / "note.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "note.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture commit"], check=True)
    return repo


def discovery() -> McpDiscoveryResult:
    return McpDiscoveryResult(
        server="fixture",
        protocol_version="2025-11-25",
        tools=(DiscoveredTool(
            TOOL_NAME := "get_recent_commits",
            "Последние коммиты",
            "Прочитать последние коммиты настроенного Git repository.",
            SCHEMA,
        ),),
    )


def runtime(repo: Path, executions: list, *, discover=None, result=None) -> ToolRuntime:
    def execute(_config, name, arguments):
        executions.append((name, dict(arguments)))
        value = result
        if value is None:
            value = read_recent_commits(repo, arguments["limit"]).model_dump(mode="json")
        return McpToolResult("fixture", "2025-11-25", name, False, value, ())

    return ToolRuntime(
        McpServerConfig("fixture", "unused", ()),
        repo,
        discover=discover or (lambda _config: discovery()),
        execute=execute,
    )


def make_agent(db: Path, repo: Path, client: SequenceClient, executions: list, **runtime_options):
    return Agent(
        config=AgentConfig(),
        client=client,
        store=SqliteStore(db),
        tool_runtime=runtime(repo, executions, **runtime_options),
    )


def tool_call(call_id="call-1", arguments='{"limit":1}', name="get_recent_commits"):
    return {"id": call_id, "name": name, "arguments": arguments}


def test_success_and_direct(root: Path):
    repo = init_repo(root)
    commit = read_recent_commits(repo, 1).commits[0]
    client = SequenceClient([
        response(calls=[tool_call()], finish="tool_calls"),
        response(f"Последний коммит {commit.id}: {commit.subject}"),
    ])
    executions = []
    agent = make_agent(root / "success.db", repo, client, executions)
    reply = agent.ask("Покажи последний коммит Git")
    audit = agent.store.chat_turn(reply.turn_id)
    assert reply.ok and commit.id in reply.text
    assert executions == [("get_recent_commits", {"limit": 1})]
    assert [event["kind"] for event in audit["events"]] == [
        "provider_initial", "mcp_execution", "provider_final"
    ]
    assert len(client.requests) == 2 and "tools" in client.requests[0]
    assert "tools" not in client.requests[1]
    assert agent.history == [
        {"role": "user", "content": "Покажи последний коммит Git"},
        {"role": "assistant", "content": reply.text},
    ]

    direct_client = SequenceClient([response("Обычный ответ")])
    direct = make_agent(root / "direct.db", repo, direct_client, []).ask("Скажи привет")
    assert direct.text == "Обычный ответ" and len(direct_client.requests) == 1
    print("ok  direct и successful tool paths имеют точные call counts и audit")


def test_validation_and_false_success(root: Path):
    repo = init_repo(root)
    for name, first in (
        ("invalid", tool_call(arguments='{"limit":99}')),
        ("unknown", tool_call(name="other_tool")),
    ):
        client = SequenceClient([
            response(calls=[first], finish="tool_calls"),
            response("Успешно получил коммит deadbeef"),
        ])
        executions = []
        agent = make_agent(root / f"{name}.db", repo, client, executions)
        reply = agent.ask("Покажи коммиты Git")
        assert reply.finish_reason == "tool_error_safe_response"
        assert "deadbeef" not in reply.text and executions == []
        assert len(client.requests) == 2

    malformed = [
        tool_call(call_id=None),
        tool_call(call_id="same"),
        tool_call(call_id="same"),
    ]
    client = SequenceClient([
        response("mixed", calls=malformed, finish="tool_calls"),
        response("ложный успех"),
    ])
    executions = []
    agent = make_agent(root / "batch.db", repo, client, executions)
    reply = agent.ask("Покажи коммиты Git")
    audit = agent.store.chat_turn(reply.turn_id)
    denials = [event for event in audit["events"] if event["kind"] == "local_result"]
    assert len(denials) == 4  # три linked results плюс discarded final
    assert len({event["tool_call_id"] for event in denials[:3]}) == 3
    assert executions == []
    print("ok  invalid/mixed/multiple requests не исполняются и не создают false success")


def test_error_result_repeat_and_discovery(root: Path):
    repo = init_repo(root)
    client = SequenceClient([
        response(calls=[tool_call()], finish="tool_calls"),
        response("получил badc0de"),
    ])
    executions = []
    agent = make_agent(
        root / "malformed.db",
        repo,
        client,
        executions,
        result={"repository": "wrong", "commits": []},
    )
    reply = agent.ask("Покажи коммиты Git")
    assert reply.finish_reason == "tool_error_safe_response" and "badc0de" not in reply.text
    assert len(executions) == 1

    repeat_client = SequenceClient([
        response(calls=[tool_call()], finish="tool_calls"),
        response(calls=[tool_call("call-2")], finish="tool_calls"),
    ])
    repeat_exec = []
    repeat = make_agent(root / "repeat.db", repo, repeat_client, repeat_exec)
    repeated = repeat.ask("Покажи коммиты Git")
    assert not repeated.ok and len(repeat_exec) == 1 and repeat.history == []
    assert repeat.store.chat_turn(repeated.turn_id)["status"] == "failed"

    def fail_discovery(_config):
        raise McpDiscoveryError("list_tools")

    unavailable_client = SequenceClient([])
    unavailable = make_agent(
        root / "unavailable.db", repo, unavailable_client, [], discover=fail_discovery
    )
    local = unavailable.ask("Какие коммиты Git последние?")
    assert local.finish_reason == "tool_unavailable" and unavailable_client.requests == []

    ordinary_client = SequenceClient([response("Ответ без Git")])
    ordinary = make_agent(
        root / "ordinary.db", repo, ordinary_client, [], discover=fail_discovery
    )
    answer = ordinary.ask("Как дела?")
    assert answer.text == "Ответ без Git" and "tools" not in ordinary_client.requests[0]
    print("ok  malformed result, repeated LLM2 request и discovery failures fail closed")


def test_fsm_race_and_audit_failure(root: Path):
    repo = init_repo(root)
    executions = []
    holder = {}

    def pause_after_llm1():
        holder["agent"].pause_task()

    client = SequenceClient(
        [response(calls=[tool_call()], finish="tool_calls")],
        callbacks=[pause_after_llm1],
    )
    agent = make_agent(root / "race.db", repo, client, executions)
    holder["agent"] = agent
    agent.start_task("Проверить race")
    reply = agent.ask("Покажи коммиты Git")
    assert not reply.ok and executions == [] and len(client.requests) == 1
    assert agent.history == [] and agent.store.chat_turn(reply.turn_id)["status"] == "invalidated"

    audit_client = SequenceClient([response("Оплаченный ответ")])
    audit_agent = make_agent(root / "audit.db", repo, audit_client, [])
    original = audit_agent.store.record_provider_event

    def fail_audit(*_args, **_kwargs):
        raise OSError("audit unavailable")

    audit_agent.store.record_provider_event = fail_audit
    try:
        audit_agent.ask("Обычный вопрос")
    except OSError:
        pass
    else:
        raise AssertionError("mandatory audit failure должен остановить turn")
    finally:
        audit_agent.store.record_provider_event = original
    assert len(audit_client.requests) == 1 and audit_agent.history == []
    print("ok  FSM race и mandatory audit failure не применяют turn")


def test_all_audit_boundaries_and_provider_failures(root: Path):
    repo = init_repo(root)

    create_client = SequenceClient([response("не должен вызываться")])
    create_agent = make_agent(root / "audit-create.db", repo, create_client, [])
    create_agent.store.start_chat_turn = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        OSError("audit create failed")
    )
    try:
        create_agent.ask("Обычный вопрос")
    except OSError:
        pass
    else:
        raise AssertionError("audit-create failure должен остановить LLM1")
    assert create_client.requests == []

    mcp_client = SequenceClient([
        response(calls=[tool_call()], finish="tool_calls"),
        response("не должен вызываться"),
    ])
    mcp_exec = []
    mcp_agent = make_agent(root / "audit-mcp.db", repo, mcp_client, mcp_exec)
    original_event = mcp_agent.store.record_chat_event

    def fail_mcp_audit(turn_id, **kwargs):
        if kwargs.get("kind") == "mcp_execution":
            raise OSError("mcp audit failed")
        return original_event(turn_id, **kwargs)

    mcp_agent.store.record_chat_event = fail_mcp_audit
    try:
        mcp_agent.ask("Покажи коммиты Git")
    except OSError:
        pass
    else:
        raise AssertionError("MCP audit failure должен остановить LLM2")
    assert len(mcp_client.requests) == 1 and len(mcp_exec) == 1 and mcp_agent.history == []

    final_client = SequenceClient([
        response(calls=[tool_call()], finish="tool_calls"),
        response(read_recent_commits(repo, 1).commits[0].id),
    ])
    final_exec = []
    final_agent = make_agent(root / "audit-final.db", repo, final_client, final_exec)
    original_provider = final_agent.store.record_provider_event

    def fail_final_audit(turn_id, kind, reply):
        if kind == "provider_final":
            raise OSError("final audit failed")
        return original_provider(turn_id, kind, reply)

    final_agent.store.record_provider_event = fail_final_audit
    try:
        final_agent.ask("Покажи коммиты Git")
    except OSError:
        pass
    else:
        raise AssertionError("LLM2 audit failure должен остановить persistence")
    assert len(final_client.requests) == 2 and len(final_exec) == 1 and final_agent.history == []

    first_error = make_agent(
        root / "provider-first.db",
        repo,
        SequenceClient([RuntimeError("first failed")]),
        [],
    )
    reply = first_error.ask("Обычный вопрос")
    assert not reply.ok and first_error.history == []

    second_client = SequenceClient([
        response(calls=[tool_call()], finish="tool_calls"),
        RuntimeError("second failed"),
    ])
    second_agent = make_agent(root / "provider-second.db", repo, second_client, [])
    second = second_agent.ask("Покажи коммиты Git")
    assert not second.ok and second_agent.history == []
    print("ok  audit-create/MCP/LLM2 и оба provider failures fail closed")


def test_transactional_final_guard_and_terminal_states(root: Path):
    repo = init_repo(root)
    commit = read_recent_commits(repo, 1).commits[0]
    client = SequenceClient([
        response(calls=[tool_call()], finish="tool_calls"),
        response(commit.id),
    ])
    executions = []
    agent = make_agent(root / "final-race.db", repo, client, executions)
    agent.start_task("Проверить final commit")
    original_finalize = agent.store.finalize_chat_turn

    def pause_then_finalize(*args, **kwargs):
        agent.pause_task()
        return original_finalize(*args, **kwargs)

    agent.store.finalize_chat_turn = pause_then_finalize
    reply = agent.ask("Покажи коммиты Git")
    assert not reply.ok and len(client.requests) == 2 and len(executions) == 1
    assert agent.history == [] and agent.store.chat_turn(reply.turn_id)["status"] == "invalidated"

    paused_client = SequenceClient([response("не должен вызываться")])
    paused = make_agent(root / "paused.db", repo, paused_client, [])
    paused.start_task("Пауза")
    paused.pause_task()
    try:
        paused.ask("Покажи коммиты Git")
    except ValueError:
        pass
    else:
        raise AssertionError("paused chat должен быть локально запрещён")
    assert paused_client.requests == []
    print("ok  transactional final guard и initial paused дают ноль stale persistence")


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for index, test in enumerate((
            test_success_and_direct,
            test_validation_and_false_success,
            test_error_result_repeat_and_discovery,
            test_fsm_race_and_audit_failure,
            test_all_audit_boundaries_and_provider_failures,
            test_transactional_final_guard_and_terminal_states,
        )):
            case = root / str(index)
            case.mkdir()
            test(case)


if __name__ == "__main__":
    main()
