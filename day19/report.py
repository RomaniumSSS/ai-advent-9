"""Проверки draft Day 18, привязанные к сохранённому model_seen Day 19."""
from __future__ import annotations
import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from .config import MAX_DRAFT_BYTES
from .store import compact

SCHEMA = json.loads((Path(__file__).parent / "draft_schema.json").read_text(encoding="utf-8"))
RELEVANT = {"confirmed_described_case", "possible_case"}
BUSINESS = ("компан", "бизнес", "клиент", "банк", "предприяти", "корпорат", "поддерж",
            "продаж", "производ", "логист", "сотрудник", "отдел", "заказ", "финанс",
            "маркетинг", "бухгалтер", "найм")
PERSONAL = ("личн", "домаш", "семейн", "пет-проект", "для себя", "хобби", "повседнев",
            "путешеств", "моих задач", "своих задач", "фильм", "кино", "ролик", "анимац")
# AICODE-NOTE: маркер действия связывается с агентом; запуск сервера *для* агентов
# сам по себе не доказывает, что агент решал описанную задачу.
AGENT_ACTION = re.compile(
    r"\b(?:агент[а-я]*|agents?)\b[^.!?\n]{0,110}\b"
    r"(?:обрабатыва[а-я]*|выполня[а-я]*|пишут|пишет|написал[а-я]*|снима[а-я]*|"
    r"рендер[а-я]*|проверя[а-я]*|разобрал[а-я]*|наш[её]л|закрыва[а-я]*|"
    r"работа[а-я]*|запустил[а-я]*|внедрил[а-я]*)\b"
    r"|\b(?:код|фильм|задач[а-я]*|поломк[а-я]*|тикет[а-я]*)\b[^.!?\n]{0,80}\b"
    r"(?:написал[а-я]*|пишут|разобрал[а-я]*|наш[её]л|обработал[а-я]*)\b"
    r"[^.!?\n]{0,40}\b(?:агент[а-я]*|agents?)\b"
    r"|\b(?:использу[а-я]*|внедрил[а-я]*|запустил[а-я]*|применил[а-я]*)\s+"
    r"(?:ИИ[-‑ ]?)?(?:агент[а-я]*|agents?)\b"
    r"|\bиспроб[а-я]*\b[^.!?\n]{0,100}\b(?:с помощью|при помощи|через)\s+"
    r"(?:ИИ[-‑ ]?)?(?:агент[а-я]*|agents?)\b", re.I)
LINK = re.compile(r"https?://|www\.|habr\.com", re.I)
UNSCOPED_ABSENCE = re.compile(
    r"(?:применени|использовани|работ[ауыеы]|действи)[^.!?]{0,55}"
    r"(?:не\s+(?:описан|показан|детализирован|подтвержд)|нет\b|отсутств)", re.I)
BIDI = {0x200e, 0x200f, *range(0x202a, 0x202f), *range(0x2066, 0x206a)}

class ValidationIssue(ValueError):
    def __init__(self, code: str, observation_id: str):
        super().__init__(code)
        self.observation_id = observation_id

def safe_text(value: str, multiline=False) -> bool:
    return all(ord(c) not in BIDI and (ord(c) >= 32 or multiline and c == "\n") for c in value)

def unsupported_summary_number(summary: str, excerpt: str) -> bool:
    ordinal_roots = {"1": "перв", "2": "втор", "3": "трет", "4": "четв", "5": "пят"}
    for match in re.finditer(r"\d+(?:[.,]\d+)?", summary.casefold()):
        number = match.group()
        if number in excerpt:
            continue
        following = summary[match.end():match.end()+4].casefold()
        if (number in ordinal_roots and re.match(r"[-‑](?:й|я|е|го|ой)\b", following)
                and ordinal_roots[number] in excerpt):
            continue
        return True
    return False

def validate(draft: dict, run_id: str, rows: list[dict], coverage: dict, total: int) -> None:
    if len(compact(draft).encode()) > MAX_DRAFT_BYTES:
        raise ValueError("draft_too_large")
    errors = list(Draft202012Validator(SCHEMA, format_checker=FormatChecker()).iter_errors(draft))
    if errors:
        raise ValueError("draft_schema_" + errors[0].validator)
    if draft["run_id"] != run_id:
        raise ValueError("run_mismatch")
    expected = {row["id"]: row for row in rows}
    entries = draft["entries"]
    if len(entries) != len(expected) or {e["observation_id"] for e in entries} != set(expected):
        raise ValueError("model_seen_mismatch")
    expected_coverage = "partial" if total > len(rows) else coverage["kind"]
    if draft["coverage_label"] != expected_coverage:
        raise ValueError("coverage_mismatch")
    if draft["outcome"] == "empty_feed":
        raise ValueError("false_empty_feed")
    intro = draft["proposed_text"]
    if len(intro.encode()) > 1024 or not intro.strip() or not safe_text(intro, True) or LINK.search(intro):
        raise ValueError("invalid_intro")
    confirmed = 0
    for entry in entries:
        row = expected[entry["observation_id"]]
        cited = "\n".join(row[field] for field in dict.fromkeys(entry["evidence_refs"])).casefold()
        summary = entry["summary"]
        if len(summary.encode()) > 256 or not safe_text(summary) or LINK.search(summary):
            raise ValidationIssue("invalid_summary",row["id"])
        category = entry["category"]
        # AICODE-NOTE: без подтверждённого применения число из контекста RSS
        # нельзя подписывать как результат работы агента.
        if category != "confirmed_described_case" and entry["metric_claims"]:
            raise ValidationIssue("metric_without_confirmed_case",row["id"])
        if category in RELEVANT and not summary.strip():
            raise ValidationIssue("empty_relevant_summary",row["id"])
        if category == "possible_case" and not any(t in cited for t in ("агент", "agent")):
            raise ValidationIssue("possible_lacks_agent_evidence",row["id"])
        if category == "possible_case" and UNSCOPED_ABSENCE.search(summary) and "rss" not in summary.casefold():
            raise ValidationIssue("unscoped_absence_claim",row["id"])
        if category == "confirmed_described_case":
            confirmed += 1
            if not (any(t in cited for t in BUSINESS + PERSONAL)
                    or re.search(r"\b(?:я|мне|мой|моя|моё|мои|свой|своя|своё|свои)\b", cited)):
                raise ValidationIssue("confirmed_lacks_context",row["id"])
            if not AGENT_ACTION.search(cited):
                raise ValidationIssue("confirmed_lacks_usage_evidence",row["id"])
        # Число только из заголовка может быть рекламной агрегацией; в кратком
        # пересказе используем лишь числа, присутствующие и в RSS-выдержке.
        excerpt = row["rss_excerpt"].casefold()
        if category in RELEVANT and unsupported_summary_number(summary, excerpt):
            raise ValidationIssue("summary_number_not_in_excerpt",row["id"])
        for metric in entry["metric_claims"]:
            if (len(metric["text"].encode()) > 160 or len(metric["attribution"].encode()) > 120
                    or not safe_text(metric["text"]) or not safe_text(metric["attribution"])
                    or not metric["attribution"].strip() or not re.search(r"\d", metric["text"])
                    or metric["text"].casefold() not in excerpt):
                raise ValidationIssue("unsupported_metric",row["id"])
    if (draft["outcome"] == "cases_found") != bool(confirmed):
        raise ValueError("outcome_mismatch")
    if expected_coverage == "partial" and draft["outcome"] == "no_confirmed_cases":
        # AICODE-NOTE: при неполном RSS нельзя утверждать отсутствие кейсов за весь период.
        lowered = intro.casefold()
        if re.search(r"\bза\s+(?:все\s+)?(?:сутки|день|весь\s+период)\b", lowered):
            raise ValueError("intro_overstates_coverage")

def render(draft: dict, rows: list[dict], coverage: dict, total: int, date: str) -> tuple[str, list[str], list[str]]:
    lookup = {r["id"]: r for r in rows}
    relevant = [(e, lookup[e["observation_id"]]) for e in draft["entries"] if e["category"] in RELEVANT]
    relevant.sort(key=lambda pair: (pair[0]["category"] != "confirmed_described_case",
                                    pair[1]["first_batch_id"] == pair[1].get("current_batch_id"),
                                    pair[1]["published_at_utc"] or "", pair[1]["article_id"]))
    shown = relevant[:2]
    lines = [f"ИИ-агенты · {date}"]
    if not shown:
        lines.append(draft["proposed_text"].strip() if draft["coverage_label"] == "complete_for_profile"
                     else "Проверка просмотренных материалов RSS Хабра.")
        lines.append("В разобранных материалах подходящих кейсов нет.")
    for index, (entry, row) in enumerate(shown, 1):
        label = ("Описанный кейс" if entry["category"] == "confirmed_described_case"
                 else "Возможный кейс (применение по RSS не подтверждено)")
        lines.append(f"{index}. {label}: {entry['summary']}")
        for metric in entry["metric_claims"]:
            lines.append("Результат, по словам автора: " + metric["text"])
        lines.append(row["url"])
    if len(relevant) > 2:
        lines.append(f"Не показано подходящих материалов: {len(relevant) - 2}.")
    if draft["coverage_label"] != "complete_for_profile":
        if coverage["kind"] != "complete_for_profile":
            lines.append("Охват неполный: RSS не подтверждает полноту публикаций за период.")
        if total > len(rows):
            lines.append(f"Из очереди рассмотрено {len(rows)} из {total} материалов.")
    payload = "\n".join(lines) + "\n"
    if len(payload) > 3500:
        raise ValueError("report_too_large")
    return payload, [row["id"] for _, row in shown], [row["url"] for _, row in shown]
