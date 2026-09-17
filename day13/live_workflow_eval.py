"""Три реальных provider call для полного semi-autonomous workflow.

Fake/mock здесь запрещён: planning, execution и validation проходят через
OpenRouter. SDK retries отключены, а wrapper не позволяет отправить больше трёх
запросов. Credential загружается только в environment и не попадает в evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from openai import OpenAI

from agent import Agent, AgentCapabilities, AgentConfig
from base_agent import REQUEST_TIMEOUT_SECONDS
from models import DEFAULT_MODEL
from store import SqliteStore


MAX_PROVIDER_CALLS = 3
MAX_REPORTED_COST_USD = Decimal("0.005")
PINNED_PROVIDER = "open-inference"
EXPECTED_PROVIDER_NAME = "OpenInference"
OBJECTIVE = (
    "Создать готовый текстовый runbook безопасного выпуска обновления мобильного "
    "приложения: canary 10%, метрики ошибок и latency, критерии rollback, роли и "
    "пошаговые команды оператору. Ничего фактически не развёртывать."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_error(error: Exception, secret: str) -> str:
    return f"{type(error).__name__}: {error}".replace(secret, "[REDACTED]")[:1000]


class RecordingCompletions:
    def __init__(self, completions, traces: list[dict], secret: str):
        self.completions = completions
        self.traces = traces
        self.secret = secret

    def create(self, **kwargs):
        if len(self.traces) >= MAX_PROVIDER_CALLS:
            raise RuntimeError("live budget: больше трёх provider calls запрещено")
        request = dict(kwargs)
        supplied_extra = dict(request.get("extra_body") or {})
        supplied_extra["usage"] = {"include": True}
        supplied_extra["provider"] = {
            "only": [PINNED_PROVIDER],
            "allow_fallbacks": False,
            "require_parameters": True,
        }
        request["extra_body"] = supplied_extra
        trace = {
            "call": len(self.traces) + 1,
            "status": "in_flight",
            "requested_model": kwargs.get("model"),
            "message_count": len(kwargs.get("messages", [])),
            "max_tokens": kwargs.get("max_tokens"),
            "started_at": utc_now(),
        }
        self.traces.append(trace)
        started = time.monotonic()
        try:
            response = self.completions.create(**request)
        except Exception as error:
            trace.update({
                "status": "error",
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "error": clean_error(error, self.secret),
            })
            raise

        usage = getattr(response, "usage", None)
        choices = getattr(response, "choices", [])
        choice = choices[0] if choices else None
        content = (
            getattr(getattr(choice, "message", None), "content", None) or ""
        )
        trace.update({
            "status": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "response_id": getattr(response, "id", None),
            "response_model": getattr(response, "model", None),
            "provider": getattr(response, "provider", None),
            "finish_reason": getattr(choice, "finish_reason", None),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "reported_cost_usd": getattr(usage, "cost", None),
            "response": content,
        })
        return response


class RecordingClient:
    def __init__(self, client: OpenAI, secret: str):
        self.traces: list[dict] = []
        self.chat = SimpleNamespace(
            completions=RecordingCompletions(
                client.chat.completions, self.traces, secret
            )
        )


def make_agent(db: Path, session: str, client: RecordingClient) -> Agent:
    return Agent(
        name="semi-autonomous-live",
        config=AgentConfig(
            model=DEFAULT_MODEL,
            max_tokens=1600,
            reasoning_effort="none",
            temperature=0.1,
        ),
        store=SqliteStore(db, session, "semi-live", "roman"),
        client=client,
        capabilities=AgentCapabilities(recent_history_turns=2),
    )


def database_evidence(db: Path) -> dict:
    with sqlite3.connect(db) as connection:
        calls = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(prompt_tokens), 0), "
            "COALESCE(SUM(completion_tokens), 0), "
            "COALESCE(SUM(cost_reported), 0) FROM calls"
        ).fetchone()
        messages = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    return {
        "recorded_calls": calls[0],
        "prompt_tokens": calls[1],
        "completion_tokens": calls[2],
        "reported_cost_usd": calls[3],
        "chat_messages": messages,
    }


def write_report(output: Path, report: dict) -> None:
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Semi-autonomous workflow — real-provider live validation",
        "",
        f"- Result: `{'PASS' if report['passed'] else 'FAIL'}`",
        f"- Provenance: {report['provenance']}",
        f"- Model: `{report['model']}`",
        f"- Provider calls: {report['totals']['provider_calls']}/{MAX_PROVIDER_CALLS}",
        f"- Tokens: {report['totals']['prompt_tokens']} input + "
        f"{report['totals']['completion_tokens']} output",
        f"- Reported cost: `${report['totals']['reported_cost_usd']}`; cumulative "
        f"with precursors: `${report['totals']['cumulative_reported_cost_usd']}` "
        f"(limit `${MAX_REPORTED_COST_USD}`)",
        f"- Final FSM stage: `{report['workflow'].get('final_stage')}`",
        f"- Restart duplicate calls: {report['workflow'].get('restart_extra_calls')}",
        "- Automatic retries: 0",
        "",
        "Fake/mock responses are not accepted by this evaluator. Full sanitized "
        "provider traces and responses are stored in `report.json`; the API key "
        "and credential path are not stored.",
    ]
    if report.get("error"):
        lines.extend(["", f"- Error: `{report['error']}`"])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def require_boundary(condition: bool, label: str, reason: str) -> None:
    """Не тратить следующий provider call, если текущий checkpoint не достигнут."""
    if not condition:
        raise RuntimeError(f"{label} boundary failed: {reason}")


def run(output: Path, env_file: Path, prior_cost: Decimal) -> dict:
    if output.exists():
        raise FileExistsError(f"output уже существует: {output}")
    output.mkdir(parents=True)
    load_dotenv(env_file)
    secret = os.environ.get("OPENROUTER_API_KEY", "")
    if not secret:
        raise RuntimeError("OPENROUTER_API_KEY не задан")

    raw_client = OpenAI(
        api_key=secret,
        base_url="https://openrouter.ai/api/v1",
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )
    client = RecordingClient(raw_client, secret)
    db = output / "workflow.db"
    started = time.monotonic()
    report = {
        "provenance": "real OpenRouter provider responses; fake/mock forbidden",
        "started_at": utc_now(),
        "model": DEFAULT_MODEL,
        "limits": {
            "provider_calls": MAX_PROVIDER_CALLS,
            "reported_cost_usd": str(MAX_REPORTED_COST_USD),
            "automatic_retries": 0,
            "prior_reported_cost_usd": str(prior_cost),
        },
        "workflow": {},
        "traces": client.traces,
        "totals": {
            "provider_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reported_cost_usd": "0",
            "cumulative_reported_cost_usd": str(prior_cost),
        },
        "gates": {},
        "passed": False,
    }
    try:
        first = make_agent(db, "live-planning", client)
        first.start_task(OBJECTIVE)
        planning = first.run_to_boundary(max_model_turns=1)
        planning_proposal = first.workflow_state()["proposal"]
        require_boundary(
            planning.reason == "approval_required"
            and planning_proposal is not None
            and planning_proposal["action"] == "submit_plan",
            "planning",
            planning.reason,
        )

        restarted = make_agent(db, "live-restart", client)
        before_restart = len(client.traces)
        waiting = restarted.run_to_boundary(max_model_turns=1)
        restart_extra_calls = len(client.traces) - before_restart
        require_boundary(
            waiting.reason == "approval_required" and restart_extra_calls == 0,
            "restart",
            waiting.reason,
        )

        validation = restarted.approve_workflow(max_model_turns=2)
        validation_proposal = restarted.workflow_state()["proposal"]
        require_boundary(
            validation.reason == "approval_required"
            and validation_proposal is not None
            and validation_proposal["action"] == "approve",
            "validation",
            validation.reason,
        )
        final = restarted.approve_workflow(max_model_turns=1)
        state = restarted.task_state()
        db_evidence = database_evidence(db)

        costs = [
            Decimal(str(trace["reported_cost_usd"]))
            for trace in client.traces
            if trace.get("reported_cost_usd") is not None
        ]
        total_cost = sum(costs, Decimal("0"))
        cumulative_cost = prior_cost + total_cost
        completed = [trace for trace in client.traces if trace["status"] == "completed"]
        responses = [trace.get("response", "") for trace in completed]
        execution_text = responses[1].lower() if len(responses) > 1 else ""
        unsupported_claims = [
            claim for claim in (
                "развертывание выполнено",
                "развёртывание выполнено",
                "метрики в норме",
                "жалоб пользователей не поступало",
                "время начала эксперимента зафиксировано",
            ) if claim in execution_text
        ]
        gates = {
            "planning_boundary": (
                planning.reason == "approval_required"
                and planning.model_turns == 1
                and planning_proposal is not None
                and planning_proposal["action"] == "submit_plan"
            ),
            "restart_without_duplicate_call": (
                waiting.reason == "approval_required" and restart_extra_calls == 0
            ),
            "autonomous_execution_validation": (
                validation.reason == "approval_required"
                and validation.model_turns == 2
                and validation_proposal is not None
                and validation_proposal["action"] == "approve"
            ),
            "final_user_boundary": (
                final.status == "done" and state is not None and state.stage.value == "done"
            ),
            "exactly_three_real_calls": (
                len(client.traces) == MAX_PROVIDER_CALLS
                and len(completed) == MAX_PROVIDER_CALLS
                and db_evidence["recorded_calls"] == MAX_PROVIDER_CALLS
            ),
            "responses_nonempty": all(
                trace.get("response", "").strip() for trace in completed
            ),
            "responses_not_truncated": all(
                trace.get("finish_reason") == "stop" for trace in completed
            ),
            "text_deliverable_quality": (
                len(responses) == 3
                and "canary" in responses[0].lower()
                and ("rollback" in execution_text or "откат" in execution_text)
                and "canary" in execution_text
                and len(execution_text) >= 400
                and (
                    "провер" in responses[2].lower()
                    or "соответ" in responses[2].lower()
                )
            ),
            "no_unsupported_external_claims": not unsupported_claims,
            "provider_metadata": all(
                trace.get("provider") == EXPECTED_PROVIDER_NAME
                and trace.get("response_model")
                for trace in completed
            ),
            "usage_present": all(
                trace.get("prompt_tokens") is not None
                and trace.get("completion_tokens") is not None
                and trace.get("reported_cost_usd") is not None
                for trace in completed
            ),
            "reported_cost_budget": cumulative_cost <= MAX_REPORTED_COST_USD,
            "workflow_not_chat": db_evidence["chat_messages"] == 0,
        }
        report.update({
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "workflow": {
                "planning_reason": planning.reason,
                "restart_reason": waiting.reason,
                "restart_extra_calls": restart_extra_calls,
                "autonomous_model_turns": validation.model_turns,
                "validation_reason": validation.reason,
                "final_status": final.status,
                "final_stage": state.stage.value if state else None,
                "event_names": [row["event"] for row in restarted.store.task_events()],
            },
            "database": db_evidence,
            "totals": {
                "provider_calls": len(client.traces),
                "prompt_tokens": sum(trace.get("prompt_tokens") or 0 for trace in completed),
                "completion_tokens": sum(
                    trace.get("completion_tokens") or 0 for trace in completed
                ),
                "reported_cost_usd": str(total_cost),
                "prior_reported_cost_usd": str(prior_cost),
                "cumulative_reported_cost_usd": str(cumulative_cost),
            },
            "unsupported_external_claims": unsupported_claims,
            "gates": gates,
            "passed": all(gates.values()),
            "database_sha256": sha256(db),
        })
    except Exception as error:
        report.update({
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error": clean_error(error, secret),
            "totals": {
                "provider_calls": len(client.traces),
                "prompt_tokens": sum(t.get("prompt_tokens") or 0 for t in client.traces),
                "completion_tokens": sum(
                    t.get("completion_tokens") or 0 for t in client.traces
                ),
                "reported_cost_usd": str(sum(
                    (
                        Decimal(str(t["reported_cost_usd"]))
                        for t in client.traces
                        if t.get("reported_cost_usd") is not None
                    ),
                    Decimal("0"),
                )),
                "prior_reported_cost_usd": str(prior_cost),
                "cumulative_reported_cost_usd": str(prior_cost + sum(
                    (
                        Decimal(str(t["reported_cost_usd"]))
                        for t in client.traces
                        if t.get("reported_cost_usd") is not None
                    ),
                    Decimal("0"),
                )),
            },
        })
    write_report(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--prior-reported-cost", type=Decimal, default=Decimal("0"))
    args = parser.parse_args()
    if not args.env_file.is_file():
        parser.error("--env-file не существует")
    if args.prior_reported_cost < 0:
        parser.error("--prior-reported-cost не может быть отрицательным")
    report = run(args.output, args.env_file, args.prior_reported_cost)
    print(json.dumps({
        "passed": report["passed"],
        "provider_calls": report["totals"]["provider_calls"],
        "reported_cost_usd": report["totals"]["reported_cost_usd"],
        "gates": report["gates"],
        "error": report.get("error"),
    }, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
