"""Literal user evidence, separate from corpus citations and assistant proposals."""

import copy
import json
import re
from answers import check_answer
from common import packed
from structured_evidence import check_response

USER_FACT_BYTES = 4000
ATTRIBUTION_NOTICE = "ссылка на выбор пользователя не доказана"
# ошибки атрибуции мягчают при наличии хотя бы одной linked-ссылки (вариант A, Изменение 3);
# остальные проверки (схема, отсутствующий факт, дубликат, снимок/каталог, корпусные) жёсткие всегда.
SOFT_IF_LINKED = {"unsupported_user_attribution", "user_fact_not_linked"}

USER_ASSERTION = re.compile(
    r"\b(?:мы|ты|вы)\s+(?:\w+\s+){0,3}(?:выбра\w*|выбира\w*|реши\w*|предпоч\w*|отказа\w*|запрети\w*|хочешь|хотите|хотим|планиру\w*)\b"
    r"|\b(?:ваш\w*|тво\w*|наш\w*)\s+(?:(?:явно|уже)\s+)?(?:выбор|решени\w*|цел\w*|запрет\w*|выбран\w*)\b"
    r"|\b(?:выбран\w*|решени\w*)\s+(?:вами|тобой|нами)\b"
    r"|\bдля\s+(?:примера|показа)\s+выбрано\b",
    re.I,
)
# без якоря ^: реплика-факт не обязана начинать предложение («Для напоминалки я выбираю…»);
# \b перед каждой веткой не даёт словам-хвостам («семья выбираю») ложно войти в декларацию.
DECLARATION = re.compile(
    r"\bя\s+(?:выбра\w*|выбираю|реши\w*|предпочитаю|хочу)\b"
    r"|\bмы\s+(?:выбра\w*|выбираем|реши\w*)\b"
    r"|\bмо[яю]\s+цел\w*"
    r"|\bне\s+(?:используй|добавляй|меняй|предлагай)\b",
    re.I,
)
HYPOTHETICAL = re.compile(r"\b(?:если|допустим|возможно|может|бы)\b", re.I)
# стоп-слова: местоимения/союзы/предлоги, через которые идёт сама форма атрибуции,
# их пересечение ничего не доказывает про содержание факта.
TOKEN_STOPWORDS = {
    "это",
    "тобой",
    "вами",
    "нами",
    "твой",
    "твоя",
    "твоё",
    "твои",
    "ваш",
    "ваша",
    "ваше",
    "ваши",
    "наш",
    "наша",
    "наше",
    "наши",
    "мы",
    "вы",
    "ты",
    "он",
    "она",
    "они",
    "для",
    "что",
    "как",
    "или",
    "если",
    "есть",
    "быть",
    "уже",
    "явно",
}


def significant_tokens(text):
    # усечение до 5 букв — грубый стемминг-заглушка без внешних зависимостей,
    # покрывает основные русские словоформы одного корня (выбрал/выбрала/выбрали).
    return {
        w[:5]
        for w in re.findall(r"[a-zа-яё0-9]+", text.lower())
        if len(w) >= 4 and w not in TOKEN_STOPWORDS
    }


def covers(fact_statement, sentence):
    fact_tokens = significant_tokens(fact_statement)
    sentence_tokens = significant_tokens(sentence)
    if not fact_tokens or not sentence_tokens:
        return False
    overlap = fact_tokens & sentence_tokens
    union = fact_tokens | sentence_tokens
    # Jaccard >= 3/4, а не «общее слово нашлось»: перефразировка («вариант хранения»)
    # добавляет мало лишних токенов и проходит, а приписанный лишний выбор (другая СУБД)
    # ощутимо снижает долю пересечения в объединении и блокируется.
    return len(overlap) * 4 >= len(union) * 3


def user_fact_catalog(state, history, question):
    facts = []
    for field in ("goal", "clarifications", "constraints"):
        values = [state[field]] if field == "goal" else state[field]
        for index, text in enumerate(values):
            if text:
                facts.append(
                    {
                        "fact_id": f"state.{field}.{index}",
                        "version": state["version"],
                        "origin": "explicit_task_state",
                        "field": field,
                        "statement": text,
                    }
                )
    utterances = [
        m
        for m in history
        if m["role"] == "user" and m.get("task_state_version") == state["version"]
    ]
    utterances.append(
        {
            "content": question,
            "request_id": "current",
            "task_state_version": state["version"],
        }
    )
    for message in utterances:
        for index, sentence in enumerate(
            re.split(r"(?<=[.!?])\s+|\n", message["content"])
        ):
            text = sentence.strip()
            if (
                text
                and "?" not in text
                and DECLARATION.search(text)
                and not HYPOTHETICAL.search(text)
            ):
                facts.append(
                    {
                        "fact_id": f"user.{message['request_id']}.{index}",
                        "version": state["version"],
                        "origin": "explicit_user_statement",
                        "request_id": message["request_id"],
                        "statement": text,
                    }
                )
    bounded = []
    for fact in facts:
        if len(packed(bounded + [fact])) <= USER_FACT_BYTES:
            bounded.append(fact)
    return bounded


def user_fact_contract(facts):
    return {
        "allowed_facts": facts,
        "response_field": "user_fact_refs",
        "reference_shape": {
            "fact_id": "exact allowed fact_id",
            "version": "exact integer task state version",
        },
        "rules": "Only these literal user records can support a claim about user choices/goals/prohibitions. "
        "Put selected references in user_fact_refs: UI renders their exact statements separately. "
        "Do not paraphrase a user decision as a fact in answer/comparison prose; either copy its exact statement with its reference, "
        "or use conditional language/ask clarification. A question about what we chose is not proof we chose it. "
        "Assistant suggestions and fresh_rag_context are never user facts. "
        "If explicit user statements conflict with task state, ask clarification rather than selecting a hidden current decision. "
        "User fact refs never replace required corpus sources/quotes.",
    }


def narrative_fields(data):
    if isinstance(data.get("answer"), str):
        yield data["answer"]
    for row in (
        data.get("comparison", []) if isinstance(data.get("comparison"), list) else []
    ):
        if isinstance(row, dict):
            for field in ("aspect", "analysis", "reason"):
                if isinstance(row.get(field), str):
                    yield row[field]


def check_user_response(content, chunks, question, state, conversation):
    parsed = check_answer(content, chunks)
    data = parsed.get("answer")
    if not isinstance(data, dict):
        return check_response(content, chunks, question, state)
    data = copy.deepcopy(data)
    refs = data.pop("user_fact_refs", [])
    checked = check_response(
        json.dumps(data, ensure_ascii=False), chunks, question, state
    )
    checked["normalization"] = parsed.get("normalization", "none")
    errors = []
    rendered = []
    from conversation import bounded_state

    effective_state = bounded_state(state)[0]
    if conversation.get("task_state") != effective_state:
        errors.append("user_fact_state_snapshot_mismatch")
    facts = user_fact_catalog(
        effective_state, conversation.get("history", []), question
    )
    if conversation.get("user_facts") != facts:
        errors.append("user_fact_catalog_mismatch")
    allowed = {f["fact_id"]: f for f in facts}
    linked = set()
    if not isinstance(refs, list):
        errors.append("user_fact_refs_schema")
    else:
        for ref in refs:
            if (
                not isinstance(ref, dict)
                or set(ref) != {"fact_id", "version"}
                or not isinstance(ref.get("fact_id"), str)
                or type(ref.get("version")) is not int
            ):
                errors.append("user_fact_refs_schema")
                continue
            fact = allowed.get(ref["fact_id"])
            if not fact or ref["version"] != fact["version"]:
                errors.append("user_fact_not_in_context")
                continue
            if ref["fact_id"] in linked:
                errors.append("duplicate_user_fact_ref")
                continue
            linked.add(ref["fact_id"])
            rendered.append(fact)
    # AICODE-NOTE: guard проверяет покрытие значимых токенов linked-факта предложением
    # (significant_tokens/covers), не буквальное равенство и не свободную семантику prose —
    # explicit attribution forms остаются единственным покрытием, порог сам по себе не ослаблен.
    # Изменение 3 (вариант A): токенная метрика не даёт надёжного порога на реальных данных,
    # поэтому недоказанная атрибуция (unsupported_user_attribution/user_fact_not_linked) не
    # прячет ответ, если привязана хотя бы одна typed-ссылка — она уходит в SOFT_IF_LINKED
    # и превращается в пометку, а не в unverified. Без единой ссылки поведение прежнее, жёсткое.
    for text in narrative_fields(data):
        for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
            assertions = list(USER_ASSERTION.finditer(sentence))
            if not assertions:
                continue
            matching = [f for f in facts if covers(f["statement"], sentence)]
            if matching:
                if not any(f["fact_id"] in linked for f in matching):
                    errors.append("user_fact_not_linked")
                continue
            # Uncertainty must modify this attribution, not a later consequence.
            prefix = re.sub(
                r"^\s*(?:\d+[.)]|[-*•])\s+", "", sentence[: assertions[0].start()]
            ).strip()
            conditional = len(assertions) == 1 and re.fullmatch(
                r"(?:если|допустим|возможно|может быть)[,\s]*", prefix, re.I
            )
            clarification = len(assertions) == 1 and re.search(
                r"^(?:не знаю|уточни(?:те)?)[^.!?;\n]*\b(?:что|како\w*|ли)\b[^.!?;\n]*$",
                prefix,
                re.I,
            )
            if not conditional and not clarification:
                errors.append("unsupported_user_attribution")
    if isinstance(checked.get("answer"), dict) and "user_fact_refs" in parsed["answer"]:
        checked["answer"]["user_fact_refs"] = refs
    # мягкими становятся только ошибки атрибуции, и только если есть хотя бы одна linked-ссылка;
    # без неё (linked пуст) они остаются жёсткими — выдумка без опоры по-прежнему блокируется.
    soft = sorted(set(e for e in errors if e in SOFT_IF_LINKED and linked))
    hard = sorted(set(e for e in errors if e not in SOFT_IF_LINKED or not linked))
    if hard:
        checked.update(
            errors=sorted(set(checked.get("errors", []) + hard)),
            valid=False,
            structure_valid=False,
            outcome="unverified",
            structured_evidence=None,
        )
    elif checked.get("structured_evidence") is not None:
        checked["structured_evidence"]["user_facts"] = rendered
        if soft:
            checked["errors"] = sorted(set(checked.get("errors", []) + soft))
            checked["structured_evidence"]["attribution_notice"] = ATTRIBUTION_NOTICE
    checked["user_facts_validation"] = {
        "version": state["version"],
        "errors": sorted(set(errors)),
        "soft_errors": soft,
        "coverage": "typed literal references and token-covered explicit attribution forms; unrestricted semantics NOT_PROVEN",
    }
    return checked
