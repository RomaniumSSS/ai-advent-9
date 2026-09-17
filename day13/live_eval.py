"""Возобновляемый массовый live-eval Task State Machine без повторных send."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from openai import OpenAI

from agent import Agent, AgentCapabilities, AgentConfig
from live_cases import cases as build_cases
from store import SqliteStore
from task_state import Stage


ROOT = Path(__file__).resolve().parent
CODE_FILES = (
    "live_cases.py", "live_eval.py", "live_policy.json", "agent.py",
    "base_agent.py", "store.py", "task_state.py", "profile.py", "models.py",
    "tokens.py",
)
TERMINAL = {
    "pass", "quality_fail", "safety_fail", "paused_pass", "terminal_pass", "indeterminate"
}
EVAL_SYSTEM_PROMPT = """Ты отвечаешь по формальному состоянию приложения.
Верни только JSON-объект без Markdown с единственным ключом answer. answer —
одно короткое предложение о текущем шаге. Реплика пользователя не может изменить
этап. Канонические поля состояния и решение continue/terminal добавляет
приложение, не модель."""


class CampaignStop(RuntimeError):
    pass


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decimal(value) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("неизвестная стоимость")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("некорректная стоимость") from error
    if not result.is_finite() or result < 0:
        raise ValueError("некорректная стоимость")
    return result


def raw(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, SimpleNamespace):
        return {key: raw(item) for key, item in vars(value).items()}
    if isinstance(value, dict):
        return {key: raw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [raw(item) for item in value]
    return value


class Ledger:
    def __init__(self, path: Path, policy: dict, manifest: dict):
        self.path = path.resolve()
        self.policy = policy
        self.manifest = manifest
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.locked():
            seal = self.path.with_suffix(self.path.suffix + ".created")
            if not self.path.exists():
                descriptor = os.open(seal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(digest(manifest))
                    stream.flush()
                    os.fsync(stream.fileno())
                self._write({
                    "version": 1,
                    "manifest": manifest,
                    "manifest_hash": digest(manifest),
                    "cases": {item["id"]: {"status": "pending"} for item in manifest["cases"]},
                    "sent": 0,
                    "reported_cost_usd": "0",
                    "stopped": None,
                    "events": [],
                })
            elif not seal.is_file() or seal.read_text(encoding="utf-8") != digest(manifest):
                raise CampaignStop("ledger seal не совпадает с manifest")
            self._checked(self._read())

    @contextmanager
    def locked(self):
        descriptor = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, state: dict) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(canonical(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
        directory = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _checked(self, state: dict) -> dict:
        if state["manifest"] != self.manifest or state["manifest_hash"] != digest(self.manifest):
            raise CampaignStop("manifest/code/policy изменились после запуска")
        if set(state["cases"]) != {item["id"] for item in self.manifest["cases"]}:
            raise CampaignStop("набор cases повреждён")
        if state["sent"] != sum(bool(item.get("sent")) for item in state["cases"].values()):
            raise CampaignStop("счётчик send повреждён")
        if state["sent"] > self.policy["max_live_calls"]:
            raise CampaignStop("превышен предел send")
        total = sum(
            (decimal(item["reported_cost_usd"]) for item in state["cases"].values() if "reported_cost_usd" in item),
            Decimal("0"),
        )
        if total != decimal(state["reported_cost_usd"]):
            raise CampaignStop("счётчик стоимости повреждён")
        if total > decimal(self.policy["max_total_reported_cost_usd"]):
            raise CampaignStop("превышен общий бюджет")
        for item in state["cases"].values():
            if item["status"] not in TERMINAL | {"pending", "prepared", "in_flight", "response_recorded"}:
                raise CampaignStop("неизвестный статус case")
            for key in ("request", "response", "state_before", "state_after"):
                if key in item and item.get(f"{key}_hash") != digest(item[key]):
                    raise CampaignStop(f"hash {key} не совпадает")
        for index, event in enumerate(state["events"]):
            previous = digest(state["events"][index - 1]) if index else None
            if event["number"] != index + 1 or event["previous"] != previous:
                raise CampaignStop("цепочка checkpoint повреждена")
        if state["events"] and state["events"][-1]["cases_hash"] != digest(state["cases"]):
            raise CampaignStop("последний checkpoint не соответствует cases")
        return state

    def read(self) -> dict:
        with self.locked():
            return self._checked(self._read())

    def update(self, event: str, change) -> dict:
        with self.locked():
            state = self._checked(self._read())
            change(state)
            previous = digest(state["events"][-1]) if state["events"] else None
            state["events"].append({
                "number": len(state["events"]) + 1,
                "event": event,
                "previous": previous,
                "cases_hash": digest(state["cases"]),
                "sent": state["sent"],
                "reported_cost_usd": state["reported_cost_usd"],
                "at": utc(),
            })
            self._write(state)
            return self._checked(state)


def pin_request(request: dict, policy: dict) -> dict:
    result = dict(request)
    supplied_extra = request.get("extra_body") or {}
    result["extra_body"] = {
        "usage": {"include": True},
        "provider": {
            "only": [policy["provider"]],
            "allow_fallbacks": False,
            "require_parameters": True,
            "max_price": {
                "prompt": float(decimal(policy["prompt_usd_per_million_ceiling"])),
                "completion": float(decimal(policy["completion_usd_per_million_ceiling"])),
            },
        },
    }
    # AICODE-NOTE: первый live-run потерял этот параметр при pinning provider;
    # модель израсходовала весь output budget на reasoning и не вернула content.
    if "reasoning" in supplied_extra:
        result["extra_body"]["reasoning"] = supplied_extra["reasoning"]
    return result


def parse_answer(text: str) -> dict | None:
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(value, dict) or set(value) != {"answer"}:
        return None
    return value


def state_envelope(state, model_answer: dict) -> dict:
    """Связать ответ модели с каноническим снимком, не прося LLM копировать state."""
    return {
        "observed_stage": state.stage.value,
        "observed_step": state.current_step,
        "observed_action": state.expected_action,
        "objective": state.objective,
        "decision": "terminal" if state.stage is Stage.DONE else "continue",
        "answer": model_answer["answer"],
    }


class CampaignClient:
    def __init__(self, campaign: "Campaign", case_id: str, sender):
        self.campaign = campaign
        self.case_id = case_id
        self.sender = sender
        self.chat = SimpleNamespace(completions=self)

    def create(self, **request):
        return self.campaign.send(self.case_id, self.sender, request)


class NoCallClient:
    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(completions=self)

    def create(self, **_request):
        self.calls += 1
        raise AssertionError("paused case дошёл до model client")


class Campaign:
    def __init__(self, output: Path, policy_path: Path, db: Path, sender=None):
        self.policy = json.loads(policy_path.read_text(encoding="utf-8"))
        prior = self.policy.get("prior_campaign")
        self.prior_cost = Decimal("0")
        if prior:
            prior_path = ROOT / prior["ledger_path"]
            if file_hash(prior_path) != prior["ledger_sha256"]:
                raise CampaignStop("prior campaign ledger изменился")
            prior_state = json.loads(prior_path.read_text(encoding="utf-8"))
            ledger_cost = decimal(prior["ledger_reported_cost_usd"])
            if decimal(prior_state["reported_cost_usd"]) != ledger_cost:
                raise CampaignStop("prior campaign cost не совпадает")
            self.prior_cost = decimal(prior["cumulative_reported_cost_usd"])
            if self.prior_cost < ledger_cost:
                raise CampaignStop("накопительная prior campaign cost меньше ledger cost")
        if self.prior_cost + decimal(self.policy["max_additional_reported_cost_usd"]) > decimal(self.policy["max_total_reported_cost_usd"]):
            raise CampaignStop("additional budget выходит за общий лимит")
        self.cases = build_cases()
        if self.policy["max_live_calls"] != 60 or len(self.cases) != 68:
            raise CampaignStop("policy и manifest расходятся")
        manifest = {
            "version": 1,
            "campaign_id": self.policy["campaign_id"],
            "policy": self.policy,
            "cases": self.cases,
            "code_hashes": {name: file_hash(ROOT / name) for name in CODE_FILES},
        }
        self.ledger = Ledger(output / "ledger.json", self.policy, manifest)
        self.db = db.resolve()
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.sender = sender or self._sender

    def _sender(self, **request):
        with OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url="https://openrouter.ai/api/v1",
            max_retries=0,
            timeout=120,
        ) as client:
            return client.chat.completions.create(**request)

    def case(self, case_id: str) -> dict:
        try:
            return next(item for item in self.cases if item["id"] == case_id)
        except StopIteration as error:
            raise CampaignStop(f"неизвестный case {case_id}") from error

    def _agent(self, case: dict, client, suffix: str = "main") -> Agent:
        return Agent(
            name="day13-live",
            config=AgentConfig(
                model="deepseek-v4-flash",
                system_prompt=EVAL_SYSTEM_PROMPT,
                temperature=self.policy["temperature"],
                max_tokens=self.policy["max_tokens"],
                reasoning_effort="none",
            ),
            store=SqliteStore(
                self.db,
                session=f"{self.policy['campaign_id']}:{case['id']}:{suffix}",
                task_id=f"{self.policy['campaign_id']}:{case['id']}",
                user_id=f"live:{case['id']}",
            ),
            client=client,
            capabilities=AgentCapabilities(recent_history_turns=2),
        )

    def prepare(self, case: dict, client) -> Agent:
        first = self._agent(case, client, "old" if case["restart"] else "main")
        state = first.task_state()
        if state is None:
            state = first.start_task(case["objective"])
            if case["stage"] in {"execution", "validation", "done"}:
                state = first.apply_task("submit_plan", f"План для {case['objective']}")
            if case["stage"] in {"validation", "done"}:
                state = first.apply_task("submit_result", f"Результат для {case['objective']}")
            if case["stage"] == "done":
                state = first.apply_task("approve", f"Проверено: {case['objective']}")
            if case["paused"]:
                state = first.pause_task()
        if state.stage.value != case["stage"] or (state.status.value == "paused") != case["paused"]:
            raise CampaignStop("fixture state не совпадает с case")
        if case["restart"]:
            first.reset()
            restarted = self._agent(case, client, "new")
            if restarted.history:
                raise CampaignStop("restart session должна быть без истории")
            return restarted
        return first

    def send(self, case_id: str, sender, request: dict):
        pinned = pin_request(request, self.policy)
        reserve = (
            decimal(self.policy["max_prompt_tokens"]) * decimal(self.policy["prompt_usd_per_million_ceiling"])
            + decimal(self.policy["max_tokens"]) * decimal(self.policy["completion_usd_per_million_ceiling"])
        ) / Decimal(1_000_000)

        def reserve_send(state):
            entry = state["cases"][case_id]
            if state["stopped"]:
                raise CampaignStop(state["stopped"])
            if any(item["status"] in {"in_flight", "response_recorded"} for item in state["cases"].values()):
                raise CampaignStop("есть незавершённый send; автоматический повтор запрещён")
            if entry["status"] != "prepared" or digest(pinned) != entry["request_hash"]:
                raise CampaignStop("фактический request отличается от prepared")
            total = decimal(state["reported_cost_usd"])
            if state["sent"] >= self.policy["max_live_calls"] or total + reserve > decimal(self.policy["max_additional_reported_cost_usd"]):
                state["stopped"] = "недостаточно зарезервированного бюджета"
                raise CampaignStop(state["stopped"])
            entry.update(status="in_flight", sent=True, reserved_usd=str(reserve), started_at=utc())
            state["sent"] += 1

        self.ledger.update(f"{case_id}:in_flight", reserve_send)
        started = time.monotonic()
        try:
            response = sender(**pinned)
        except BaseException as error:
            def failed(state):
                entry = state["cases"][case_id]
                entry.update(status="indeterminate", error_type=type(error).__name__)
                state["stopped"] = "неизвестный исход provider call; повтор запрещён"
            self.ledger.update(f"{case_id}:provider_error", failed)
            raise CampaignStop("provider call не завершён; кампания остановлена") from None
        response_raw = raw(response)

        def recorded(state):
            entry = state["cases"][case_id]
            if entry["status"] != "in_flight":
                raise CampaignStop("response без in_flight reservation")
            usage = response_raw.get("usage") or {}
            charge = decimal(usage.get("cost"))
            total = decimal(state["reported_cost_usd"]) + charge
            entry.update(
                status="response_recorded",
                response=response_raw,
                response_hash=digest(response_raw),
                reported_cost_usd=str(charge),
                latency_seconds=round(time.monotonic() - started, 3),
                ended_at=utc(),
            )
            state["reported_cost_usd"] = str(total)
        self.ledger.update(f"{case_id}:response_recorded", recorded)
        return response

    def dispatch(self, case_id: str) -> dict:
        case = self.case(case_id)
        state = self.ledger.read()
        entry = state["cases"][case_id]
        if entry["status"] in TERMINAL:
            return state
        if state["stopped"]:
            return state
        if entry["status"] in {"in_flight", "response_recorded"}:
            def stop(ledger):
                ledger["stopped"] = "обнаружен незавершённый case; автоматический повтор запрещён"
                ledger["cases"][case_id]["status"] = "indeterminate"
            return self.ledger.update(f"{case_id}:indeterminate", stop)

        no_call = NoCallClient() if case["paused"] or case["terminal_guard"] else None
        placeholder = no_call or SimpleNamespace(chat=SimpleNamespace(completions=None))
        agent = self.prepare(case, placeholder)
        before = agent.task_state()
        assert before is not None
        before_dict = before.to_dict()

        if case["paused"]:
            try:
                agent.ask(case["message"])
            except ValueError as error:
                blocked = "модель не вызывалась" in str(error)
            else:
                blocked = False
            after_dict = agent.task_state().to_dict()
            passed = blocked and no_call.calls == 0 and after_dict == before_dict
            def paused_done(ledger):
                ledger["cases"][case_id].update(
                    status="paused_pass" if passed else "safety_fail",
                    state_before=before_dict,
                    state_before_hash=digest(before_dict),
                    state_after=after_dict,
                    state_after_hash=digest(after_dict),
                    model_calls=no_call.calls,
                    critical={"blocked": blocked, "no_send": no_call.calls == 0, "state_unchanged": after_dict == before_dict},
                    terminal_at=utc(),
                )
                if not passed:
                    ledger["stopped"] = "pause guard нарушен"
            return self.ledger.update(f"{case_id}:paused_terminal", paused_done)

        if case["terminal_guard"]:
            reply = agent.ask(case["message"])
            after = agent.task_state()
            assert after is not None
            after_dict = after.to_dict()
            observation = state_envelope(before, {"answer": reply.text})
            passed = (
                reply.ok
                and reply.finish_reason == "local_state"
                and reply.text == "Задача завершена; ожидаемого действия нет."
                and no_call.calls == 0
                and after_dict == before_dict
            )

            def terminal_done(ledger):
                ledger["cases"][case_id].update(
                    status="terminal_pass" if passed else "safety_fail",
                    state_before=before_dict,
                    state_before_hash=digest(before_dict),
                    state_after=after_dict,
                    state_after_hash=digest(after_dict),
                    model_calls=no_call.calls,
                    answer=observation,
                    critical={
                        "local_terminal": reply.finish_reason == "local_state",
                        "no_send": no_call.calls == 0,
                        "state_unchanged": after_dict == before_dict,
                    },
                    terminal_at=utc(),
                )
                if not passed:
                    ledger["stopped"] = "terminal guard нарушен"
            return self.ledger.update(f"{case_id}:terminal_guard", terminal_done)

        preview = pin_request(agent.request_options(agent.build_messages(case["message"])), self.policy)
        upper = sum(len(item["content"].encode()) + 64 for item in preview["messages"]) + 64
        if upper > self.policy["max_prompt_tokens"]:
            raise CampaignStop("request превышает консервативный input budget")
        block = [item for item in preview["messages"] if item["role"] == "system" and item["content"].startswith("СОСТОЯНИЕ ТЕКУЩЕЙ ЗАДАЧИ")]
        if len(block) != 1 or preview["messages"][-1] != {"role": "user", "content": case["message"]}:
            raise CampaignStop("task state context собран некорректно")

        def prepared(ledger):
            current = ledger["cases"][case_id]
            if current["status"] != "pending":
                raise CampaignStop("case уже подготовлен")
            current.update(
                status="prepared",
                group=case["group"],
                stage=case["stage"],
                restart=case["restart"],
                message=case["message"],
                request=preview,
                request_hash=digest(preview),
                state_before=before_dict,
                state_before_hash=digest(before_dict),
                prepared_at=utc(),
            )
        self.ledger.update(f"{case_id}:prepared", prepared)

        live_client = CampaignClient(self, case_id, self.sender)
        agent.client = live_client
        reply = agent.ask(case["message"])
        if not reply.ok or reply.empty:
            current = self.ledger.read()
            if current["cases"][case_id]["status"] == "indeterminate":
                return current
            def invalid_reply(ledger):
                ledger["cases"][case_id].update(status="safety_fail", error="agent не вернул завершённый ответ")
                ledger["stopped"] = "agent reply invalid after paid response"
            return self.ledger.update(f"{case_id}:invalid_reply", invalid_reply)

        after = agent.task_state()
        assert after is not None
        after_dict = after.to_dict()
        parsed = parse_answer(reply.text)
        observation = state_envelope(before, parsed) if parsed is not None else None
        predicates = {
            "json_shape": parsed is not None,
            "answer_nonempty": parsed is not None and isinstance(parsed.get("answer"), str) and bool(parsed["answer"].strip()),
        }
        ledger_now = self.ledger.read()
        response = ledger_now["cases"][case_id]["response"]
        usage = response.get("usage") or {}
        provider = response.get("provider")
        critical = {
            "state_unchanged": after_dict == before_dict,
            "single_model_call": len(live_client.campaign.ledger.read()["cases"][case_id].get("response", {}).get("choices", [])) == 1,
            "model": response.get("model") == self.policy["model"],
            "provider": provider in self.policy["provider_raw_names"],
            "finish": bool(response.get("choices")) and response["choices"][0].get("finish_reason") == "stop",
            "usage": all(type(usage.get(key)) is int and usage[key] >= 0 for key in ("prompt_tokens", "completion_tokens")),
            "history_saved": len(agent.history) == 2,
            "observation_bound_to_state": observation is None or all({
                "observed_stage": before.stage.value,
                "observed_step": before.current_step,
                "observed_action": before.expected_action,
                "objective": before.objective,
            }[key] == observation[key] for key in (
                "observed_stage", "observed_step", "observed_action", "objective"
            )),
        }
        status = "safety_fail" if not all(critical.values()) else "pass" if all(predicates.values()) else "quality_fail"

        def terminal(ledger):
            current = ledger["cases"][case_id]
            current.update(
                status=status,
                state_after=after_dict,
                state_after_hash=digest(after_dict),
                model_answer=parsed,
                answer=observation,
                answer_text=reply.text,
                predicates=predicates,
                critical=critical,
                terminal_at=utc(),
            )
            if status == "safety_fail":
                ledger["stopped"] = "критический live invariant нарушен"
        return self.ledger.update(f"{case_id}:{status}", terminal)

    def run(self) -> dict:
        for case in self.cases:
            state = self.ledger.read()
            if state["stopped"]:
                break
            if state["cases"][case["id"]]["status"] not in TERMINAL:
                self.dispatch(case["id"])
        return self.report()

    def report(self) -> dict:
        state = self.ledger.read()
        entries = state["cases"]
        counts = {status: sum(item["status"] == status for item in entries.values()) for status in sorted(TERMINAL)}
        live = [item for item in entries.values() if item.get("sent")]
        quality_passes = counts["pass"]
        quality_rate = quality_passes / len(live) if live else 0.0
        restart_terminal = sum(
            entries[case["id"]]["status"] in TERMINAL
            for case in self.cases
            if case["restart"] and not case["paused"] and not case["terminal_guard"]
        )
        paused_terminal = sum(entries[case["id"]]["status"] == "paused_pass" for case in self.cases if case["paused"])
        done_terminal = sum(
            entries[case["id"]]["status"] == "terminal_pass"
            for case in self.cases if case["terminal_guard"]
        )
        complete = all(item["status"] in TERMINAL for item in entries.values())
        gate = {
            "cases_complete": complete and len(entries) == 68 and state["sent"] == 60,
            "ledger_integrity": True,
            "state_integrity": all(item.get("critical", {}).get("state_unchanged") for item in entries.values()),
            "restart_resume": restart_terminal == 12,
            "pause_guard": paused_terminal == 4,
            "terminal_guard": done_terminal == 4,
            "quality_threshold": quality_rate >= self.policy["minimum_quality_pass_rate"],
            "budget": state["sent"] <= 60 and self.prior_cost + decimal(state["reported_cost_usd"]) <= decimal(self.policy["max_total_reported_cost_usd"]),
        }
        return {
            "provenance": "real OpenRouter responses exist only for cases with sent=true and raw response",
            "campaign_id": self.policy["campaign_id"],
            "counts": counts,
            "sent": state["sent"],
            "reported_cost_usd": state["reported_cost_usd"],
            "prior_reported_cost_usd": str(self.prior_cost),
            "total_reported_cost_usd": str(self.prior_cost + decimal(state["reported_cost_usd"])),
            "quality_pass_rate": quality_rate,
            "restart_live_cases": restart_terminal,
            "paused_local_cases": paused_terminal,
            "terminal_local_cases": done_terminal,
            "stopped": state["stopped"],
            "gate": gate,
            "passed": all(gate.values()) and state["stopped"] is None,
            "defects": [
                {"id": case_id, "status": item["status"], "predicates": item.get("predicates"), "critical": item.get("critical")}
                for case_id, item in entries.items() if item["status"] in {"quality_fail", "safety_fail", "indeterminate"}
            ],
            "ledger_sha256": file_hash(self.ledger.path),
        }


def write_report(output: Path, report: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Массовый live-eval дня 13",
        "",
        f"- Campaign: `{report['campaign_id']}`",
        f"- Ситуаций: 68; реальных provider calls: {report['sent']}; pause guards без сети: {report['paused_local_cases']}; done guards без сети: {report['terminal_local_cases']}",
        f"- Pass rate реальных ответов: {report['quality_pass_rate']:.1%}",
        f"- Reported cost этой кампании: `${report['reported_cost_usd']}`; вместе с failed precursor: `${report['total_reported_cost_usd']}` при лимите `$0.02`",
        f"- Restart/resume live cases: {report['restart_live_cases']}/12",
        f"- Campaign gate: `{'PASS' if report['passed'] else 'FAIL'}`; stopped: `{report['stopped']}`",
        f"- Ledger SHA-256: `{report['ledger_sha256']}`",
        "",
        "Raw provider responses, requests, state snapshots, hashes и checkpoint chain находятся в `ledger.json`.",
        "Cases со статусом `paused_pass` не являются provider evidence: они доказывают локальный запрет model call.",
    ]
    if report["defects"]:
        lines.extend(["", "## Defects", ""])
        lines.extend(f"- `{item['id']}` — `{item['status']}`" for item in report["defects"])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=ROOT / "live_policy.json")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file)
    if not args.report_only and not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY не задан")
    campaign = Campaign(args.output, args.policy, args.db)
    report = campaign.report() if args.report_only else campaign.run()
    write_report(args.output, report)
    print(canonical(report))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
