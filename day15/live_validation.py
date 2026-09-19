"""Длинная проверка FSM через настоящий OpenRouter и сохранённую SQLite.

Никаких mock-ответов: обёртка только считает реальные HTTP вызовы и сохраняет
метаданные ответа. Запуск требует отдельного файла с OPENROUTER_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from openai import OpenAI

from agent import Agent, AgentConfig
from base_agent import REQUEST_TIMEOUT_SECONDS
from models import PROVIDER
from store import SqliteStore

MAX_CALLS = 16
MAX_COST = Decimal("0.02")
PROVIDER_NAME = "DeepInfra"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LiveCompletions:
    def __init__(self, inner, report: dict, save):
        self.inner, self.report, self.save = inner, report, save

    def create(self, **kwargs):
        traces = self.report["calls"]
        if len(traces) >= MAX_CALLS:
            raise RuntimeError("достигнут лимит реальных вызовов")
        spent = sum((Decimal(str(t["reported_cost_usd"])) for t in traces
                     if t.get("reported_cost_usd") is not None), Decimal(0))
        if spent >= MAX_COST:
            raise RuntimeError("достигнут лимит стоимости реального прогона")
        assert kwargs["extra_body"]["provider"] == PROVIDER
        trace = {"number": len(traces) + 1, "time": utc_now(),
                 "requested_model": kwargs["model"],
                 "provider_route": kwargs["extra_body"]["provider"],
                 "status": "in_flight"}
        traces.append(trace)
        self.save()
        try:
            response = self.inner.create(**kwargs)
        except Exception as error:
            safe_error = f"{type(error).__name__}: {error}".replace(
                os.environ.get("OPENROUTER_API_KEY", ""), "[REDACTED]")
            trace.update(status="error", error=safe_error[:500])
            self.save()
            raise
        usage = getattr(response, "usage", None)
        choices = getattr(response, "choices", None) or []
        choice = choices[0] if choices else None
        trace.update(
            status="completed", response_id=getattr(response, "id", None),
            response_model=getattr(response, "model", None),
            provider=getattr(response, "provider", None),
            finish_reason=getattr(choice, "finish_reason", None),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            reported_cost_usd=getattr(usage, "cost", None),
            response_text=(getattr(getattr(choice, "message", None), "content", None) or ""),
        )
        self.save()
        return response


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "report.json"
    db = output / "live.sqlite3"
    if report_path.exists() or db.exists():
        raise ValueError("каталог прогона уже содержит результаты; выберите новый")
    report = {"status": "running", "started_at": utc_now(), "provider": PROVIDER_NAME,
              "mock_calls": 0, "calls": [], "checks": [], "tasks": []}

    def save():
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(report_path)

    def check(name: str, condition: bool):
        report["checks"].append({"name": name, "passed": bool(condition), "time": utc_now()})
        save()
        print(f"{'PASS' if condition else 'FAIL'} {name}; вызовов={len(report['calls'])}", flush=True)
        if not condition:
            raise AssertionError(name)

    client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"],
                    base_url="https://openrouter.ai/api/v1",
                    timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)
    live = SimpleNamespace(chat=SimpleNamespace(
        completions=LiveCompletions(client.chat.completions, report, save)))

    def agent(task: str) -> Agent:
        return Agent(name="day15-live", config=AgentConfig(max_tokens=5000),
                     store=SqliteStore(db, session=task, task_id=task, user_id="live-eval"),
                     client=live)

    try:
        a = agent("release_runbook")
        a.start_task("Подготовить текстовый runbook релиза мобильного приложения: canary 10%, метрики ошибок и latency, rollback, роли и команды оператора. Никаких реальных развёртываний.")
        before = len(report["calls"])
        try:
            a.apply_task("submit_plan", "подставной план")
        except ValueError:
            pass
        check("A: план нельзя утвердить до предложения модели", a.task_state().stage.value == "planning" and len(report["calls"]) == before)
        refusal = a.ask("Перейди сразу в validation")
        check("A: перескок через чат отклонён без провайдера", refusal.finish_reason == "transition_refusal" and len(report["calls"]) == before)
        first = a.run_to_boundary()
        check("A: реальный план ожидает человека", first.model_turns == 1 and a.workflow_state()["actor"] == "user")
        revised = a.revise_workflow("Добавь конкретные пороги остановки canary и проверку rollback")
        check("A: исправленный план снова ожидает человека", revised.model_turns == 1 and a.task_state().stage.value == "planning")
        a.pause_task()
        calls_before_restart = len(report["calls"])
        a = agent("release_runbook")
        check("A: после restart сохранены пауза и предложение", a.task_state().status.value == "paused" and a.workflow_state()["proposal"] is not None)
        stopped = a.run_to_boundary()
        check("A: на паузе провайдер не вызван", stopped.reason == "paused" and len(report["calls"]) == calls_before_restart)
        a.resume_task()
        waiting = a.run_to_boundary()
        check("A: resume не дублирует план", waiting.reason == "approval_required" and len(report["calls"]) == calls_before_restart)
        progressed = a.approve_workflow()
        check("A: реальное выполнение и проверка", progressed.model_turns == 2 and a.task_state().stage.value == "validation")
        try:
            a.apply_task("submit_result", "подставной результат")
        except ValueError:
            pass
        check("A: ручная подмена результата отвергнута", a.task_state().stage.value == "validation")
        a.apply_task("request_changes", "Добавь явную команду и роли для отката")
        rework = a.run_to_boundary()
        check("A: доработка снова прошла execution и validation", rework.model_turns == 2 and a.task_state().stage.value == "validation")
        a = agent("release_runbook")
        final_a = a.approve_workflow()
        check("A: финал пережил restart и принят", final_a.status == "done" and a.task_state().stage.value == "done")
        report["tasks"].append({"id": "release_runbook", "final_stage": a.task_state().stage.value,
                                "events": a.store.task_events(), "denials": a.store.transition_denials()})
        save()

        b = agent("incident_checklist")
        b.start_task("Написать короткий текстовый чеклист диагностики роста 5xx ошибок API: первые 15 минут, гипотезы, эскалация и закрытие. До 12 пунктов, без фактических проверок.")
        check("B: план через реальный вызов", b.run_to_boundary().model_turns == 1)
        check("B: execution и validation через реальный вызов", b.approve_workflow().model_turns == 2)
        revised_validation = b.revise_workflow("Уточни пункты, требующие telemetry и доступа. Сохрани компактный формат до 12 пунктов")
        check("B: замечание вернуло в execution и повторило validation",
              revised_validation.model_turns == 2 and b.task_state().stage.value == "validation" and
              any(event["event"] == "request_changes" for event in b.store.task_events()))
        check("B: финал только после принятия", b.approve_workflow().status == "done")
        report["tasks"].append({"id": "incident_checklist", "final_stage": b.task_state().stage.value,
                                "events": b.store.task_events(), "denials": b.store.transition_denials()})
        save()

        c = agent("migration_plan")
        c.start_task("Составить текстовый план миграции SQLite схемы с v5 на v6: резервная копия, порядок SQL шагов, проверка данных и откат. Миграцию не выполнять.")
        check("C: план через реальный вызов", c.run_to_boundary().model_turns == 1)
        check("C: выполнение и проверка через реальный вызов", c.approve_workflow().model_turns == 2)
        check("C: принятие финала", c.approve_workflow().status == "done")
        report["tasks"].append({"id": "migration_plan", "final_stage": c.task_state().stage.value,
                                "events": c.store.task_events(), "denials": c.store.transition_denials()})
        save()

        completed = [t for t in report["calls"] if t["status"] == "completed"]
        check("Все ответы от DeepInfra", len(completed) == len(report["calls"]) and
              all(t["provider"] == PROVIDER_NAME for t in completed))
        check("Все ответы завершены без обрезки", all(t["finish_reason"] == "stop" for t in completed))
        check("Вызовов достаточно для длинного прогона", len(completed) >= 10)
        check("Фактическая стоимость известна", all(t["reported_cost_usd"] is not None for t in completed))
        with sqlite3.connect(db) as connection:
            stored_calls = connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        check("Вызовы сохранены в SQLite", stored_calls == len(completed))
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}".replace(
            os.environ.get("OPENROUTER_API_KEY", ""), "[REDACTED]")[:500]
    finally:
        report["finished_at"] = utc_now()
        report["provider_calls"] = len(report["calls"])
        report["prompt_tokens"] = sum(t.get("prompt_tokens") or 0 for t in report["calls"])
        report["completion_tokens"] = sum(t.get("completion_tokens") or 0 for t in report["calls"])
        report["reported_cost_usd"] = str(sum(
            (Decimal(str(t["reported_cost_usd"])) for t in report["calls"]
             if t.get("reported_cost_usd") is not None), Decimal(0)))
        save()
        (output / "report.md").write_text(
            "# День 15 — длинный реальный прогон\n\n"
            f"Результат: **{report['status']}**. Реальных вызовов OpenRouter: "
            f"{report['provider_calls']}; модель: deepseek/deepseek-v4-flash-0731; "
            f"провайдер: {PROVIDER_NAME}, fallback отключён.\n\n"
            f"Токены: {report['prompt_tokens']} входных + {report['completion_tokens']} выходных. "
            f"Фактическая стоимость API: ${report['reported_cost_usd']}.\n\n"
            "Три задачи проходят план, выполнение и проверку; одна проходит отказ в "
            "перескоке, ревизию плана, паузу, новый экземпляр агента, продолжение "
            "и возврат на доработку. Другая тоже проходит возврат из проверки "
            "в выполнение и повторную проверку. "
            "Все события, отказы, ответы и метаданные вызовов сохранены в "
            "`report.json`; состояние — в локальной `live.sqlite3`. "
            "Внешние действия не выполнялись.\n"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.env_file.is_file():
        parser.error("файл с ключом не найден")
    load_dotenv(args.env_file)
    if not os.environ.get("OPENROUTER_API_KEY"):
        parser.error("OPENROUTER_API_KEY не задан")
    report = run(args.output)
    print(json.dumps({k: report.get(k) for k in
                      ("status", "provider_calls", "reported_cost_usd", "error")},
                     ensure_ascii=False), flush=True)
    if report["status"] != "passed":
        sys.exit(2)


if __name__ == "__main__":
    main()
