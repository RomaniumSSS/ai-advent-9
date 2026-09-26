"""Модель предлагает MCP call; harness проверяет и связывает каждый результат."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from day18.config import MAX_CANDIDATE_BYTES, MAX_RESULT_BYTES, TOOL_NAME
from day18.mcp_client import McpBoundaryError, McpConfig, discover, execute
from day18.models import LinkedResult, RunContext, ToolProposal
from day18.repository import Repository, compact
from day18.rss_mcp_server import error_result

SCHEMA_DIR = Path(__file__).parent / "schemas"
INPUT_SCHEMA = json.loads((SCHEMA_DIR / "collect_input.json").read_text(encoding="utf-8"))
OUTPUT_SCHEMA = json.loads((SCHEMA_DIR / "collect_output.json").read_text(encoding="utf-8"))


def _get(value: object, key: str, default: object = None) -> object:
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def proposals(message: object) -> tuple[ToolProposal, ...]:
    raw = _get(message, "tool_calls", []) or []
    seen: set[str] = set()
    parsed: list[ToolProposal] = []
    for ordinal, item in enumerate(raw):
        raw_id = _get(item, "id")
        function = _get(item, "function", {})
        name = _get(function, "name", "")
        arguments = _get(function, "arguments")
        valid_id = (isinstance(raw_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", raw_id) is not None
                    and raw_id not in seen)
        call_id = raw_id if valid_id else f"day18-call-{ordinal + 1}"
        while call_id in seen:
            call_id += "-duplicate"
        seen.add(call_id)
        parsed.append(ToolProposal(ordinal + 1, call_id, raw_id if isinstance(raw_id, str) else None,
                                   name if isinstance(name, str) else "", arguments, valid_id))
    return tuple(parsed)


def parse_args(proposal: ToolProposal, context: RunContext) -> dict:
    if not proposal.valid_id or proposal.name != TOOL_NAME:
        raise ValueError("tool_not_allowed")
    try:
        args = json.loads(proposal.arguments) if isinstance(proposal.arguments, str) else proposal.arguments
    except (ValueError, TypeError) as error:
        raise ValueError("schema_violation") from error
    if not isinstance(args, dict):
        raise ValueError("schema_violation")
    if list(Draft202012Validator(INPUT_SCHEMA, format_checker=FormatChecker()).iter_errors(args)):
        raise ValueError("schema_violation")
    if args != context.tool_arguments():
        raise ValueError("context_mismatch")
    return args


class ToolRuntime:
    def __init__(self, repo: Repository, config: McpConfig, *,
                 discover_fn: Callable = discover, execute_fn: Callable = execute):
        self.repo = repo
        self.config = config
        self.discover_fn = discover_fn
        self.execute_fn = execute_fn
        self._tool: dict | None = None

    def model_tools(self) -> list[dict]:
        if self._tool is None:
            tools = self.discover_fn(self.config)
            if len(tools) != 1 or tools[0]["name"] != TOOL_NAME or not tools[0].get("description"):
                raise McpBoundaryError("catalog")
            discovered = tools[0].get("input_schema")
            if not isinstance(discovered, dict) or set(discovered.get("properties", {})) != set(INPUT_SCHEMA["properties"]):
                raise McpBoundaryError("schema")
            self._tool = tools[0]
        # Discovery определяет доступный tool; локальный policy schema ужесточает
        # generated MCP signature (в текущем SDK нет additionalProperties:false).
        return [{"type": "function", "function": {"name": TOOL_NAME,
                "description": self._tool["description"], "parameters": INPUT_SCHEMA}}]

    def run_proposals(self, context: RunContext, call_sequence: int, requests: tuple[ToolProposal, ...]) -> tuple[LinkedResult, ...]:
        output: list[LinkedResult] = []
        for request in requests:
            self.repo.begin_tool_attempt(context.run_id, call_sequence, request.ordinal,
                                         raw_call_id=request.raw_call_id, audit_call_id=request.call_id,
                                         name=request.name, arguments=request.arguments)
            reason = "none"
            try:
                if len(requests) != 1:
                    raise ValueError("multiple_calls")
                args = parse_args(request, context)
                if self._tool is None:
                    raise ValueError("protocol_error")
                try:
                    execution_config = McpConfig(self.config.command,
                                                 (*self.config.args, "--tool-call-id", request.call_id))
                    result = self.execute_fn(execution_config, TOOL_NAME, args)
                except McpBoundaryError:
                    result = self.repo.batch_for(context.run_id, context.idempotency_key)
                    if result is None:
                        raise ValueError("protocol_error")
                self.validate_result(context, result)
            except Exception as error:
                reason = str(error) if isinstance(error, ValueError) else "protocol_error"
                if reason not in ("multiple_calls", "tool_not_allowed", "schema_violation",
                                  "context_mismatch", "protocol_error", "budget_exhausted"):
                    reason = "protocol_error"
                result = error_result(context, "invalid_request", reason)
            self.repo.finish_tool_attempt(context.run_id, call_sequence, request.ordinal, result,
                                          "accepted" if reason == "none" else "denied", reason)
            output.append(LinkedResult(request.call_id, request.ordinal, result))
        return tuple(output)

    def deny_proposals(self, context: RunContext, call_sequence: int,
                       requests: tuple[ToolProposal, ...], reason: str = "tool_not_allowed") -> tuple[LinkedResult, ...]:
        output: list[LinkedResult] = []
        for request in requests:
            result = error_result(context, "invalid_request", reason)
            self.repo.begin_tool_attempt(context.run_id, call_sequence, request.ordinal,
                                         raw_call_id=request.raw_call_id, audit_call_id=request.call_id,
                                         name=request.name, arguments=request.arguments)
            self.repo.finish_tool_attempt(context.run_id, call_sequence, request.ordinal,
                                          result, "denied", reason)
            output.append(LinkedResult(request.call_id, request.ordinal, result))
        return tuple(output)

    def validate_result(self, context: RunContext, result: dict) -> None:
        if not isinstance(result, dict) or list(Draft202012Validator(OUTPUT_SCHEMA, format_checker=FormatChecker()).iter_errors(result)):
            raise ValueError("schema_violation")
        if len(compact(result).encode("utf-8")) > MAX_RESULT_BYTES or len(compact(result["candidates"]).encode("utf-8")) > MAX_CANDIDATE_BYTES:
            raise ValueError("budget_exhausted")
        if (result["run_id"] != context.run_id or result["source_profile_id"] != context.slot.profile
            or result["period_start_utc"] != context.slot.period_start_utc
            or result["period_end_utc"] != context.slot.period_end_utc):
            raise ValueError("context_mismatch")
        if result["status"].startswith("success_") or result["status"] == "partial_coverage":
            saved = self.repo.batch_for(context.run_id, context.idempotency_key)
            if saved is None or saved != result or not result["batch_id"] or not result["read_at_utc"]:
                raise ValueError("protocol_error")


def provider_tool_messages(requests: tuple[ToolProposal, ...], results: tuple[LinkedResult, ...]) -> list[dict]:
    assistant = {"role": "assistant", "content": None, "tool_calls": [
        {"id": request.call_id, "type": "function", "function": {"name": request.name,
            "arguments": request.arguments if isinstance(request.arguments, str) else compact(request.arguments)}}
        for request in requests]}
    linked = [{"role": "tool", "tool_call_id": item.call_id, "content": compact(item.result)} for item in results]
    return [assistant, *linked]
