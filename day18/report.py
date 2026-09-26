"""Проверка модельного draft, выбор двух статей и atomic report commit."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from day18.config import MAX_DRAFT_BYTES, MAX_MODEL_SEEN, MAX_PAYLOAD_CHARS
from day18.models import RunContext
from day18.repository import Repository, compact, digest
from day18.store import transition, utc_now

DRAFT_SCHEMA = json.loads((Path(__file__).parent / "schemas/draft.json").read_text(encoding="utf-8"))


def _provider_schema(value):
    # AICODE-NOTE: совместимый с provider поднабор задаёт форму JSON;
    # полный контракт с форматами и лимитами всё равно проверяется локально.
    if isinstance(value, dict):
        return {key: _provider_schema(item) for key, item in value.items()
                if key not in {"$schema", "format", "minItems", "maxItems"}}
    if isinstance(value, list):
        return [_provider_schema(item) for item in value]
    return value


PROVIDER_DRAFT_SCHEMA = _provider_schema(DRAFT_SCHEMA)
# AICODE-NOTE: provider ограничивает длину в символах с запасом относительно
# локального лимита escaped UTF-8 bytes; URL и точность проверяет harness.
PROVIDER_DRAFT_SCHEMA["properties"]["entries"]["items"]["properties"]["summary"].update(
    maxLength=90,
    description="Короткое описание до 90 символов без ссылок; для нерелевантной статьи пустая строка.",
)
_PROVIDER_METRIC = (PROVIDER_DRAFT_SCHEMA["properties"]["entries"]["items"]
                    ["properties"]["metric_claims"]["items"]["properties"])
_PROVIDER_METRIC["text"].update(maxLength=65,
                                description="До 65 символов; точный фрагмент RSS, без пересказа.")
_PROVIDER_METRIC["attribution"].update(maxLength=45,
                                       description="До 45 символов; короткая атрибуция источника.")
RELEVANT = {"confirmed_described_case", "possible_case"}
BUSINESS_SIGNALS = ("компан", "бизнес", "клиент", "банк", "предприяти", "корпорат",
                    "поддерж", "продаж", "производ", "логист", "сотрудник", "отдел",
                    "заказ", "финанс", "маркетинг", "бухгалтер", "найм")
PERSONAL_SIGNALS = ("личн", "домаш", "семейн", "пет-проект", "для себя", "хобби",
                    "повседнев", "путешеств", "моих задач", "своих задач")
_FIRST_PERSON = re.compile(r"\b(?:я|мне|мой|моя|моё|мои|свой|своя|своё|свои)\b")
AGENT_SIGNALS = ("агент", "agent")
_LINK = re.compile(r"https?://|www\.|habr\.com", re.IGNORECASE)


def escaped_bytes(value: str) -> int:
    return len(json.dumps(value, ensure_ascii=False)[1:-1].encode("utf-8"))


def safe_text(value: str, *, multiline: bool = False) -> bool:
    forbidden = {0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}
    return all(ord(ch) not in forbidden and (ord(ch) >= 32 or multiline and ch == "\n") for ch in value)


def worst_case_bytes(count: int) -> int:
    entry = {"observation_id": "f" * 36, "category": "confirmed_described_case",
             "evidence_refs": ["rss_excerpt"] * 3, "summary": "x" * 256,
             "metric_claims": [{"text": "x" * 160, "attribution": "x" * 120}]}
    value = {"run_id": "f" * 36, "outcome": "no_confirmed_cases", "coverage_label": "complete_for_profile",
             "entries": [entry] * count, "proposed_text": "x" * 1024}
    return len(compact(value).encode("utf-8"))


@dataclass(frozen=True)
class Selection:
    rows: tuple[dict, ...]
    pool_total: int
    analysis_omitted: int
    worst_case_bytes: int


def select_pool(repo: Repository, run_id: str, visible_budget: int | None) -> Selection:
    if visible_budget is None or visible_budget <= 0:
        raise ValueError("Не измерен visible-token budget")
    new_all, backlog_all = repo.report_pool(run_id)
    total = len(new_all) + len(backlog_all)
    # AICODE-NOTE: оставляем пять мест старой очереди, но даём новым статьям
    # достаточно места, чтобы свежий кейс не терялся за первыми десятью.
    new_count = min(MAX_MODEL_SEEN - 5, len(new_all))
    backlog_count = min(5, len(backlog_all))
    remaining = MAX_MODEL_SEEN - new_count - backlog_count
    if remaining:
        add_backlog = min(remaining, len(backlog_all) - backlog_count)
        backlog_count += add_backlog
        remaining -= add_backlog
    if remaining:
        new_count += min(remaining, len(new_all) - new_count)
    new = new_all[:new_count]
    backlog = backlog_all[:backlog_count]
    interleaved: list[dict] = []
    while new or backlog:
        if backlog:
            interleaved.append(backlog.pop(0))
        if new:
            interleaved.append(new.pop(0))
    chosen: list[dict] = []
    for item in interleaved:
        size = worst_case_bytes(len(chosen) + 1)
        # Консервативный путь: 1 UTF-8 byte/token + 1024 на ответный overhead.
        if size > MAX_DRAFT_BYTES or size + 1024 > visible_budget:
            break
        chosen.append(item)
    if total and not chosen:
        raise ValueError("budget_exhausted")
    return Selection(tuple(chosen), total, total - len(chosen), worst_case_bytes(len(chosen)))


def _source_text(row: dict) -> str:
    return f"{row['title']} {row['rss_excerpt']}".casefold()


def _has_application_context(text: str) -> bool:
    return (any(token in text for token in BUSINESS_SIGNALS + PERSONAL_SIGNALS)
            or bool(_FIRST_PERSON.search(text)))


def validate_draft(raw: str | dict, context: RunContext, selected: Selection,
                   tool_result: dict) -> dict:
    if isinstance(raw, str):
        if len(raw.encode("utf-8")) > MAX_DRAFT_BYTES:
            raise ValueError("draft too large")
        try:
            draft = json.loads(raw)
        except ValueError as error:
            raise ValueError("draft invalid JSON") from error
    else:
        draft = raw
        if len(compact(draft).encode("utf-8")) > MAX_DRAFT_BYTES:
            raise ValueError("draft too large")
    errors = list(Draft202012Validator(DRAFT_SCHEMA, format_checker=FormatChecker()).iter_errors(draft))
    if errors:
        # AICODE-NOTE: пишем лишь имя стандартного validator, без фрагмента
        # модельного ответа, чтобы live отказ можно было диагностировать безопасно.
        validator = errors[0].validator
        safe = validator if validator in {"type", "required", "additionalProperties",
                                           "enum", "format", "maxItems", "minItems"} else "other"
        raise ValueError("draft schema " + safe)
    if draft["run_id"] != context.run_id or escaped_bytes(draft["proposed_text"]) > 1024:
        raise ValueError("draft context/intro invalid")
    if not draft["proposed_text"].strip():
        raise ValueError("empty draft intro")
    if not safe_text(draft["proposed_text"], multiline=True):
        raise ValueError("unsafe draft intro")
    if _LINK.search(draft["proposed_text"]):
        raise ValueError("intro contains article link")
    if draft["coverage_label"] == "partial" and draft["outcome"] == "no_confirmed_cases":
        intro = draft["proposed_text"].casefold()
        if (re.search(r"\bза\s+(?:все\s+)?(?:сутки|день|весь\s+период)\b", intro) or
                (re.search(r"(?:\bнет\b|не\s+нашл|не\s+обнаруж|отсутств|не\s+выяв)", intro) and
                 not re.search(r"обработан|проанализирован|рассмотрен|в\s+этом\s+выпуске", intro))):
            raise ValueError("intro overstates partial coverage")
    observed = {row["observation_id"]: row for row in selected.rows}
    entries = draft["entries"]
    if len(entries) != len(observed) or {entry["observation_id"] for entry in entries} != set(observed):
        raise ValueError("draft entries do not cover model_seen")
    for entry in entries:
        row = observed[entry["observation_id"]]
        cited_text = " ".join(row[field] for field in dict.fromkeys(entry["evidence_refs"])).casefold()
        if escaped_bytes(entry["summary"]) > 256 or _LINK.search(entry["summary"]):
            raise ValueError("summary too large or contains URL")
        if entry["category"] in RELEVANT and not entry["summary"].strip():
            raise ValueError("empty relevant summary")
        if not safe_text(entry["summary"]):
            raise ValueError("unsafe summary")
        if entry["category"] == "possible_case":
            # AICODE-NOTE: possible_case помечается как неопределённый; здесь
            # механически требуем тему агента, а конкретную задачу оценивает модель.
            if not any(token in cited_text for token in AGENT_SIGNALS):
                raise ValueError("possible case lacks agent RSS evidence")
        if entry["category"] == "confirmed_described_case":
            # AICODE-NOTE: три признака проверяются как нижняя механическая граница;
            # семантическую точность утверждения отдельно проверяет live eval.
            used = ("внедр", "запуст", "пилот", "использ", "примен", "работает",
                    "эксплуатац", "испроб")
            if not (_has_application_context(cited_text) and
                    any(token in cited_text for token in AGENT_SIGNALS) and
                    any(token in cited_text for token in used)):
                raise ValueError("confirmed case lacks RSS evidence")
        for metric in entry["metric_claims"]:
            if escaped_bytes(metric["text"]) > 160 or escaped_bytes(metric["attribution"]) > 120:
                raise ValueError("metric too large")
            if not safe_text(metric["text"]) or not safe_text(metric["attribution"]):
                raise ValueError("unsafe metric")
            if metric["text"].casefold() not in cited_text or not metric["attribution"].strip():
                raise ValueError("metric lacks RSS attribution")
    confirmed = sum(entry["category"] == "confirmed_described_case" for entry in entries)
    if draft["outcome"] == "cases_found" and confirmed == 0:
        raise ValueError("cases_found without confirmed case")
    if draft["outcome"] == "no_confirmed_cases" and confirmed:
        raise ValueError("no_confirmed_cases with confirmed case")
    if draft["outcome"] == "empty_feed" and not (tool_result["status"] == "success_empty" and selected.pool_total == 0):
        raise ValueError("false empty_feed")
    if selected.pool_total and draft["outcome"] == "empty_feed":
        raise ValueError("false empty_feed")
    expected_coverage = tool_result["coverage"]["kind"]
    if selected.analysis_omitted:
        expected_coverage = "partial"
    if draft["coverage_label"] != expected_coverage:
        raise ValueError("coverage mismatch")
    if any(re.search(r"(?<!\d)" + re.escape(row["article_id"]) + r"(?!\d)", draft["proposed_text"])
           for row in selected.rows):
        raise ValueError("intro contains article id")
    return draft


def _display_order(entry: dict, row: dict) -> tuple:
    published = row["published_at_utc"] or ""
    return (0 if entry["category"] == "confirmed_described_case" else 1,
            0 if row["first_batch_id"] != row.get("current_batch_id") else 1,
            row["origin_slot"] or "9999-12-31", row["published_at_utc"] is None,
            tuple(-ord(ch) for ch in published), row["article_id"])


def render(context: RunContext, draft: dict, selected: Selection, tool_result: dict) -> tuple[str, list[tuple[dict, dict]], int]:
    rows = {row["observation_id"]: row for row in selected.rows}
    relevant = [(entry, rows[entry["observation_id"]]) for entry in draft["entries"] if entry["category"] in RELEVANT]
    for _, row in relevant:
        row["current_batch_id"] = tool_result["batch_id"]
    relevant.sort(key=lambda pair: _display_order(*pair))
    displayed = relevant[:2]
    omitted = len(relevant) - len(displayed)
    lines = [f"ИИ-агенты · {context.slot.local_date}"]
    if not displayed:
        lines.append(draft["proposed_text"].strip())
        lines.append("Новых материалов нет." if draft["outcome"] == "empty_feed"
                     else "В разобранных материалах подходящих кейсов нет.")
    for number, (entry, row) in enumerate(displayed, 1):
        label = ("Описанный кейс" if entry["category"] == "confirmed_described_case"
                 else "Возможный кейс (применение по RSS не подтверждено)")
        lines.append(f"{number}. {label}: {entry['summary']}")
        for metric in entry["metric_claims"]:
            lines.append(f"Результат, по словам автора: {metric['text']}")
        lines.append(row["url"])
    if omitted:
        lines.append(f"Не показано подходящих материалов: {omitted}.")
    if draft["coverage_label"] != "complete_for_profile":
        lines.append(f"Охват неполный: проанализировано {len(selected.rows)} из "
                     f"{selected.pool_total} материалов очереди."
                     + (" RSS может быть неполным." if tool_result["coverage"]["kind"] != "complete_for_profile" else ""))
    payload = "\n".join(line for line in lines if line)
    if len(payload) > MAX_PAYLOAD_CHARS or len(re.findall(r"https://habr\.com/ru/articles/[0-9]+/", payload)) > 2:
        raise ValueError("payload size/article limit")
    return payload, relevant, omitted


def commit_report(repo: Repository, context: RunContext, draft: dict, selected: Selection,
                  tool_result: dict) -> str:
    payload, relevant, omitted = render(context, draft, selected, tool_result)
    displayed_ids = {entry["observation_id"] for entry, _ in relevant[:2]}
    report_id = str(uuid.uuid4())
    entries = {entry["observation_id"]: entry for entry in draft["entries"]}
    with repo.store.tx() as db:
        if db.execute("SELECT state FROM runs WHERE id=?", (context.run_id,)).fetchone()[0] != "REPORT_PENDING":
            raise ValueError("report commit requires REPORT_PENDING")
        db.execute(
            "INSERT INTO reports(id,run_id,payload,payload_hash,period_start_utc,period_end_utc,coverage_json,"
            "pool_total,model_seen,analysis_omitted,payload_displayed,payload_omitted,created_utc) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (report_id, context.run_id, payload, digest(payload), context.slot.period_start_utc,
             context.slot.period_end_utc, compact(tool_result["coverage"]), selected.pool_total,
             len(selected.rows), selected.analysis_omitted, len(displayed_ids), omitted, utc_now()),
        )
        for row in selected.rows:
            if db.execute("SELECT 1 FROM claims WHERE observation_id=? AND state IN ('owned','delivered','quarantined')",
                          (row["observation_id"],)).fetchone():
                raise ValueError("observation became claimed")
            entry = entries[row["observation_id"]]
            category = entry["category"]
            disposition = ("diagnostic" if context.no_send else
                           "relevant_queued" if category in RELEVANT else "processed_out_of_scope")
            db.execute(
                "INSERT INTO classifications(id,run_id,observation_id,category,confidence,evidence_refs_json,"
                "metric_json,evidence_hash,disposition) VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), context.run_id, row["observation_id"], category, "model_claim",
                 compact(entry["evidence_refs"]), compact(entry["metric_claims"]),
                 digest(_source_text(row)), disposition),
            )
            if category in RELEVANT:
                db.execute("INSERT INTO report_members(report_id,observation_id,category,displayed_in_payload) VALUES (?,?,?,?)",
                           (report_id, row["observation_id"], category, int(row["observation_id"] in displayed_ids)))
                if not context.no_send:
                    db.execute("INSERT INTO claims(observation_id,report_id,state,changed_utc) VALUES (?,?,?,?)",
                               (row["observation_id"], report_id, "owned", utc_now()))
        transition(db, context.run_id, "REPORT_READY", stage="report", evidence_ref=report_id)
    return report_id
