"""Общий цикл model → validate → MCP → observation; порядок инструментов задаёт модель."""
from __future__ import annotations
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from jsonschema import Draft202012Validator, FormatChecker
from .config import (MAX_ARGS_BYTES, MAX_MCP_CALLS, MAX_MODEL_CALLS,
                     MAX_PROVIDER_REQUEST_BYTES, MAX_RESULT_BYTES, TOOL_NAMES, ModelProfile)
from .mcp_client import McpConfig, discover, execute
from .report import SCHEMA
from .store import Store, compact, digest, now

@dataclass(frozen=True)
class ModelResponse:
    message: object
    usage: dict | None = None
    finish_reason: str | None = None

class Provider(Protocol):
    def complete(self, messages: list[dict], *, tools: list[dict], max_tokens: int,
                 tool_choice: str) -> ModelResponse: ...

class OpenRouterProvider:
    def __init__(self, profile: ModelProfile):
        if profile.name != "deepseek" or profile.provider != "deepinfra":
            raise ValueError("live_profile_not_allowed")
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise ValueError("missing_OPENROUTER_API_KEY")
        from openai import OpenAI
        self.profile = profile
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key,
                             max_retries=0, timeout=180)

    def complete(self, messages: list[dict], *, tools: list[dict], max_tokens: int,
                 tool_choice: str) -> ModelResponse:
        result = self.client.chat.completions.create(
            model=self.profile.model_id, messages=messages, tools=tools,
            tool_choice=tool_choice, max_tokens=max_tokens,
            extra_body={"reasoning": {"effort": self.profile.reasoning_effort},
                        "provider": {"only": [self.profile.provider],
                                     "allow_fallbacks": False,"require_parameters": True}})
        choice = result.choices[0]
        usage = result.usage.model_dump() if result.usage else None
        if usage is not None:
            usage = {k: usage[k] for k in ("prompt_tokens","completion_tokens","total_tokens","cost") if k in usage}
        return ModelResponse(choice.message,usage,choice.finish_reason)

def get(value: object, key: str, default=None):
    return value.get(key,default) if isinstance(value,dict) else getattr(value,key,default)

def initial_messages(run: dict, request: str) -> list[dict]:
    instructions = (
        "Ты агент Day 19 по RSS Хабра. Используй только доступные инструменты MCP для запроса пользователя. "
        "Тебе доступны все три инструмента на каждом ходе; решай следующий вызов по observation. "
        "За ход вызывай ровно один инструмент. Не придумывай ID, URL, метрики, путь или содержимое файла. "
        "Для prepare_report_preview составь draft по каждому observation_id из model_seen ровно один раз. "
        "Важны реальные описанные случаи применения AI-агента для бизнеса или личных задач. "
        "confirmed_described_case требует одновременно контекст задачи, агента и явное действие агента "
        "в title или rss_excerpt: например, обрабатывает тикеты, написал фильм, нашёл сбой, пишет код "
        "или его запустили на тестовых БД. Тестовая среда допустима, но назови её в summary. "
        "Запуск MCP-сервера или API для агентов не доказывает применение самого агента; "
        "такое отмечай possible_case, если другая работа агента не описана. "
        "Все три признака должны быть в выбранных evidence_refs. Если слова агент/agent нет, "
        "не ставь ни confirmed_described_case, ни possible_case. "
        "possible_case ставь только для конкретного бизнес- или личного проекта с агентом, "
        "когда RSS не доказывает его действие; одно упоминание слова агент не делает новость кейсом. "
        "Если автор сообщает, что разработал agentic-инструмент для своей конкретной задачи, "
        "но RSS-выдержка не показывает работу агента, выбери possible_case; "
        "tool_news оставь для внешней новости о продукте. "
        "В summary для possible_case опиши только известный из RSS факт; не утверждай, что "
        "применения нет или что оно не описано во всей статье: у тебя есть только RSS-выдержка. "
        "В summary не приписывай эффект или внедрение, которых нет в RSS. "
        "summary до 90 символов, без URL; числа в summary и metric text бери только из rss_excerpt, "
        "не из одного заголовка; metric text до 65 символов. "
        "статью-инструкцию отмечай guide, новости tool_news, мнение opinion. "
        "Для evidence_refs выбирай title и/или rss_excerpt; metric_claims только для confirmed_described_case "
        "и только для дословного числового результата применения агента в rss_excerpt, иначе []. "
        "Доля кода, написанного агентами, описывает процесс, не измеренный результат — для неё metric_claims=[]. "
        "Если RSS partial, coverage_label=partial и не делай выводов обо всём периоде. "
        "proposed_text — краткая нейтральная вводная без ссылок. "
        "Перед prepare_report_preview проверь: каждый ID один раз, summary короче 90 символов, "
        "metric_claims=[] вне confirmed, новость/мнение не являются possible_case. "
        "Схема draft: " + compact(SCHEMA)
    )
    user = (f"{request}\nКонтекст: run_id={run['id']}, source_profile_id={run['profile']}, "
            f"period_start_utc={run['period_start_utc']}, period_end_utc={run['period_end_utc']}. "
            "Файл сохраняет только сервер; сообщи результат после проверки.")
    return [{"role":"system","content":instructions},{"role":"user","content":user}]

class Agent:
    def __init__(self, store: Store, config: McpConfig, provider: Provider, profile: ModelProfile,
                 *, trace_path: Path | None = None, preflight: dict | None = None):
        self.store = store
        self.config = config
        self.provider = provider
        self.profile = profile
        self.trace_path = trace_path
        self.preflight = preflight

    def run(self, run_id: str, request: str) -> dict:
        run = self.store.run(run_id)
        trace = {"run_id":run_id,"request":request,"model_profile":self.profile.name,
                 "model_id":self.profile.model_id,"provider":self.profile.provider,
                 "started_utc":now(),"model_calls":[],"tool_calls":[],"preflight":self.preflight}
        try:
            raw_tools = discover(self.config)
            if {t["name"] for t in raw_tools} != set(TOOL_NAMES) or len(raw_tools) != 3:
                raise ValueError("tool_catalog_mismatch")
            tools = [{"type":"function","function":{"name":t["name"],
                      "description":t["description"],"parameters":t["input_schema"]}} for t in raw_tools]
            schemas = {t["name"]:t["input_schema"] for t in raw_tools}
            messages = initial_messages(run,request)
            attempts = 0
            cost = 0.0
            for sequence in range(1,MAX_MODEL_CALLS+1):
                if len(compact({"messages":messages,"tools":tools}).encode()) > MAX_PROVIDER_REQUEST_BYTES:
                    raise ValueError("provider_request_too_large")
                if cost >= self.profile.max_cost_usd:
                    raise ValueError("cost_limit")
                started = time.monotonic()
                response = self.provider.complete(messages,tools=tools,max_tokens=self.profile.max_tokens,
                                                  tool_choice="auto")
                trace["model_calls"].append({"sequence":sequence,"at_utc":now(),
                     "elapsed_ms":round((time.monotonic()-started)*1000),
                     "finish_reason":response.finish_reason,"usage":response.usage})
                if response.usage and isinstance(response.usage.get("cost"),(float,int)):
                    cost += response.usage["cost"]
                raw_calls = get(response.message,"tool_calls",[]) or []
                if not raw_calls:
                    state = self.store.run(run_id)["state"]
                    if state == "saved" and self._verify_file(run_id):
                        return self._finish(trace,"saved",cost)
                    if state == "no_data":
                        return self._finish(trace,"no_data",cost)
                    raise ValueError("premature_final")
                assistant_calls = []
                parsed = []
                seen_ids: set[str] = set()
                for ordinal, call in enumerate(raw_calls,1):
                    ident = get(call,"id")
                    function = get(call,"function",{})
                    name = get(function,"name","")
                    arguments = get(function,"arguments","")
                    valid_id = (isinstance(ident,str) and
                                re.fullmatch(r"[A-Za-z0-9_-]{1,128}",ident) is not None and
                                ident not in seen_ids)
                    if not valid_id:
                        ident = f"day19-call-{sequence}-{ordinal}"
                    seen_ids.add(ident)
                    assistant_calls.append({"id":ident,"type":"function",
                                            "function":{"name":name,"arguments":arguments}})
                    parsed.append((ident,name,arguments,valid_id))
                messages.append({"role":"assistant","content":get(response.message,"content"),
                                 "tool_calls":assistant_calls})
                for ident,name,raw_args,valid_id in parsed:
                    attempts += 1
                    begun = time.monotonic()
                    try:
                        if attempts > MAX_MCP_CALLS:
                            raise ValueError("mcp_call_limit")
                        if len(parsed) != 1:
                            raise ValueError("multiple_tool_calls")
                        if not valid_id:
                            raise ValueError("invalid_call_id")
                        args = self._validate_args(name,raw_args,schemas,run_id)
                        result = execute(self.config,name,args)
                        if len(compact(result).encode()) > MAX_RESULT_BYTES:
                            raise ValueError("mcp_result_too_large")
                    except Exception as exc:
                        args = None
                        code = str(exc) if isinstance(exc,ValueError) else "mcp_execution_error"
                        result = {"status":"error","code":code}
                    trace["tool_calls"].append({"sequence":attempts,"call_id":ident,"name":name,
                        "arguments":args if args is not None else {"rejected":True},
                        "result":result,"at_utc":now(),
                        "elapsed_ms":round((time.monotonic()-begun)*1000)})
                    messages.append({"role":"tool","tool_call_id":ident,"content":compact(result)})
                    if attempts >= MAX_MCP_CALLS and result.get("status") != "saved":
                        raise ValueError("mcp_call_limit")
            raise ValueError("model_call_limit")
        except Exception as exc:
            reason = str(exc) if isinstance(exc,ValueError) else "agent_error"
            self.store.fail(run_id,reason)
            return self._finish(trace,"failed",cost if "cost" in locals() else 0.0,reason)

    @staticmethod
    def _validate_args(name: str, raw: object, schemas: dict, run_id: str) -> dict:
        if name not in schemas:
            raise ValueError("tool_not_allowed")
        if not isinstance(raw,str) or len(raw.encode()) > MAX_ARGS_BYTES:
            raise ValueError("invalid_arguments")
        try:
            args = json.loads(raw)
        except (TypeError,ValueError):
            raise ValueError("invalid_json")
        if not isinstance(args,dict):
            raise ValueError("schema_violation")
        errors = list(Draft202012Validator(schemas[name],format_checker=FormatChecker()).iter_errors(args))
        if errors:
            first = errors[0]
            path = ".".join(str(part) for part in first.absolute_path)
            raise ValueError("schema_violation:"+path+":"+str(first.validator))
        expected = {"collect_habr_agent_cases": {"run_id","source_profile_id","period_start_utc","period_end_utc"},
                    "prepare_report_preview": {"run_id","batch_id","draft"},
                    "save_report": {"run_id","preview_id","sha256"}}[name]
        if set(args) != expected:
            raise ValueError("schema_violation")
        if args.get("run_id") != run_id:
            raise ValueError("run_mismatch")
        if name == "prepare_report_preview":
            errors = list(Draft202012Validator(SCHEMA,format_checker=FormatChecker()).iter_errors(args["draft"]))
            if errors:
                first = errors[0]
                path = ".".join(str(part) for part in first.absolute_path)
                raise ValueError("draft_schema_violation:"+path+":"+str(first.validator))
        return args

    def _verify_file(self,run_id: str) -> bool:
        run = self.store.run(run_id)
        if not run["report_path"]:
            return False
        path = Path(run["report_path"])
        if path.is_symlink() or not path.is_file():
            return False
        with self.store.connect() as db:
            row = db.execute("SELECT sha256 FROM previews WHERE id=? AND run_id=?",
                             (run["preview_id"],run_id)).fetchone()
        return bool(row and digest(path.read_text(encoding="utf-8")) == row["sha256"])

    def _finish(self,trace: dict,status: str,cost: float,reason: str | None = None) -> dict:
        trace.update({"status":status,"finished_utc":now(),"reported_cost_usd":cost,
                      "reason":reason,"run_state":self.store.run(trace["run_id"])["state"]})
        if self.trace_path:
            self.trace_path.parent.mkdir(parents=True,exist_ok=True)
            self.trace_path.write_text(json.dumps(trace,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        return trace
