"""День 5: один вопрос трём моделям через OpenRouter.

Все модели зовутся одним ключом через общий OpenAI-совместимый эндпоинт.
Провайдер закреплён полем provider в теле запроса: это убирает различия между
компаниями, хотя не гарантирует одинаковый тип ускорителя внутри инфраструктуры
провайдера.

OpenRouter вдобавок возвращает фактически списанную сумму в usage.cost. Мы её
сохраняем рядом со своим расчётом по прайсу, не подменяя его: расхождение между
двумя числами — единственный способ заметить, что наша арифметика врёт. Тесты
такое поймать не могут, они сверяют формулу с той же формулой.

Запуск:
    uv run day05/compare.py --question "Объясни рекурсию простыми словами"
    uv run day05/compare.py --question "..." --runs 5 --temperature 0.7 --judge
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

sys.path.insert(0, str(Path(__file__).parent))

from models import (  # noqa: E402
    DEFAULT_TRIO,
    JUDGE_OUTPUT_TOKENS,
    MAX_TOKENS,
    MODELS,
    PROVIDER,
    cheapest_key,
    cost,
    sampling_args,
)

load_dotenv()

RESULTS = Path(__file__).parent / "results"
# Граница взята от измеренного, а не на глаз: самый долгий зафиксированный ответ —
# 243.7 секунды у Kimi K3, при этом её пропускная способность гуляет между прогонами
# в 7 раз. Двукратный запас нужен затем, чтобы таймаут не начал обрывать законные
# ответы: обрыв записался бы как ошибка модели и попал бы в выводы как её свойство.
REQUEST_TIMEOUT_SECONDS = 600.0

JUDGE_PROMPT = """Оцени ответ на исходный вопрос по шкале от 1 до 10, где 1 — ответ
неверный или бесполезный, 10 — правильный, исчерпывающий и понятный. Ответь только
целым числом от 1 до 10.

Исходный вопрос:
<question>
{question}
</question>

Проверяемый ответ:
<answer>
{answer}
</answer>"""

_client = None


def get_client() -> OpenAI:
    """Клиент создаётся при первом вызове, а не при импорте.

    Иначе модуль нельзя импортировать без ключа — и офлайн-тесты чистых функций
    отсюда падали бы на строке импорта, ещё ничего не проверив.
    """
    global _client
    if _client is None:
        token = os.environ.get("OPENROUTER_API_KEY")
        if not token:
            raise RuntimeError("не задан OPENROUTER_API_KEY")
        _client = OpenAI(
            api_key=token,
            base_url="https://openrouter.ai/api/v1",
            # Для замера один логический прогон должен означать один сетевой вызов.
            # Стандартные два повтора SDK незаметно смешали бы время нескольких попыток:
            # elapsed включил бы обе, а по записи этого было бы не видно.
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _client


def blank_record(
    key: str, temperature: float | None, elapsed: float, error: str
) -> dict:
    return {
        "model": key,
        "answer": "",
        "answer_chars": 0,
        "finish_reason": "",
        "elapsed": elapsed,
        "prompt_tokens": None,
        "completion_tokens": None,
        "reasoning_tokens": None,
        "cost": None,
        "cost_reported": None,
        "served_by": None,
        "temperature": temperature,
        "error": error,
    }


def ask(
    question: str,
    key: str,
    temperature: float | None = None,
    max_tokens: int = MAX_TOKENS,
) -> dict:
    """Один вызов. При сбое возвращает запись с error, а не бросает исключение.

    temperature=None означает, что параметр не отправляется вообще и модель отвечает
    на своём умолчании. Подставленный ноль был бы не «умолчанием», а конкретной
    настройкой, которая меняет поведение.
    """
    started = time.monotonic()
    try:
        response = get_client().chat.completions.create(
            model=MODELS[key]["id"],
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": question}],
            extra_body={"provider": PROVIDER, "usage": {"include": True}},
            **sampling_args(temperature),
        )
    except (OpenAIError, RuntimeError) as error:
        elapsed = round(time.monotonic() - started, 3)
        return blank_record(
            key, temperature, elapsed, f"{type(error).__name__}: {error}"
        )

    elapsed = round(time.monotonic() - started, 3)
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else None
    completion_tokens = usage.completion_tokens if usage else None

    # deepinfra отдаёт reasoning_tokens не для всех моделей: на разведке 05.09 его
    # прислал только DeepSeek, и то нулём. Отсутствие поля — не ошибка.
    details = getattr(usage, "completion_tokens_details", None) if usage else None
    reasoning_tokens = getattr(details, "reasoning_tokens", None) if details else None

    # Фактически списанное и имя обслужившего провайдера — из ответа, а не из наших
    # предположений. Второе поле есть ровно затем, чтобы закрепление провайдера можно
    # было проверить, а не принять на веру: молча уехавший запрос выглядит как удачный.
    cost_reported = getattr(usage, "cost", None) if usage else None
    served_by = getattr(response, "provider", None)

    answer = response.choices[0].message.content or ""
    return {
        "model": key,
        "answer": answer,
        # Длина видимого ответа. Нужна затем, что completion_tokens считает и то,
        # чего на экране нет: GLM выставила 139 токенов за фразу из трёх слов,
        # а провайдер эти рассуждения отдельной строкой не показывает.
        "answer_chars": len(answer),
        "finish_reason": response.choices[0].finish_reason or "",
        "elapsed": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cost": cost(prompt_tokens, completion_tokens, key),
        "cost_reported": cost_reported,
        "served_by": served_by,
        "temperature": temperature,
        "error": None,
    }


def judge_answer(question: str, answer: str) -> dict:
    """Оценка 1-10 и метрики отдельного вызова самой дешёвой модели каталога.

    Каждый ответ оценивается по отдельности, не видя остальные: иначе оценка
    сместилась бы от порядка показа, а не от самого текста.
    """
    if not answer.strip():
        return {"score": None, "cost": None, "error": "пустой ответ"}
    record = ask(
        JUDGE_PROMPT.format(question=question, answer=answer),
        cheapest_key(),
        temperature=0,
        max_tokens=JUDGE_OUTPUT_TOKENS,
    )
    if record["error"]:
        return {"score": None, "cost": record["cost"], "error": record["error"]}
    match = re.fullmatch(r"\s*(10|[1-9])\s*", record["answer"])
    return {
        "score": int(match.group(1)) if match else None,
        "cost": record["cost"],
        "error": None if match else "судья вернул не целое число от 1 до 10",
    }


def is_complete(record: dict) -> bool:
    """Модель не только ответила на уровне API, но и закончила видимый ответ."""
    return (
        not record.get("error")
        and record.get("finish_reason") == "stop"
        and bool((record.get("answer") or "").strip())
    )


def summarize(records: list[dict]) -> dict:
    """Агрегаты по API-вызовам и число полностью завершённых ответов."""
    api_good = [r for r in records if not r.get("error")]
    complete = [r for r in api_good if is_complete(r)]
    if not api_good:
        return {"runs": len(records), "api_ok": 0, "ok": 0}

    times = [r["elapsed"] for r in api_good]
    costs = [r["cost"] for r in api_good]
    prompt = [r["prompt_tokens"] for r in api_good if r["prompt_tokens"] is not None]
    completion = [
        r["completion_tokens"] for r in api_good if r["completion_tokens"] is not None
    ]
    chars = [r["answer_chars"] for r in api_good]
    judges = [r["judge"] for r in api_good if r.get("judge") is not None]
    judge_attempts = [r for r in api_good if r.get("judge_attempted")]
    judge_costs = [r.get("judge_cost") for r in judge_attempts]

    model_cost_total = None if any(value is None for value in costs) else sum(costs)
    judge_cost_total = (
        None
        if judge_attempts and any(value is None for value in judge_costs)
        else sum(judge_costs)
        if judge_attempts
        else 0.0
    )
    total_cost = (
        None
        if model_cost_total is None or judge_cost_total is None
        else model_cost_total + judge_cost_total
    )

    return {
        "runs": len(records),
        "api_ok": len(api_good),
        "ok": len(complete),
        "time_avg": round(sum(times) / len(times), 3),
        "time_min": min(times),
        "time_max": max(times),
        "prompt_avg": round(sum(prompt) / len(prompt), 1) if prompt else None,
        "completion_avg": round(sum(completion) / len(completion), 1)
        if completion
        else None,
        "chars_avg": round(sum(chars) / len(chars), 1),
        "model_cost_total": round(model_cost_total, 8)
        if model_cost_total is not None
        else None,
        "judge_cost_total": round(judge_cost_total, 8)
        if judge_attempts and judge_cost_total is not None
        else None,
        "cost_total": round(total_cost, 8) if total_cost is not None else None,
        "judge_avg": round(sum(judges) / len(judges), 1) if judges else None,
    }


def compare(
    question: str,
    model_keys: list[str],
    runs: int = 3,
    temperature: float | None = None,
    judge: bool = False,
) -> dict:
    by_model = {}
    for key in model_keys:
        records = []
        for _ in range(runs):
            record = ask(question, key, temperature)
            if judge and is_complete(record):
                judgment = judge_answer(question, record["answer"])
                record["judge"] = judgment["score"]
                record["judge_cost"] = judgment["cost"]
                record["judge_error"] = judgment["error"]
                record["judge_attempted"] = True
            elif judge:
                record.update(
                    judge=None,
                    judge_cost=None,
                    judge_error="ответ не завершён",
                    judge_attempted=False,
                )
            records.append(record)
        by_model[key] = {"records": records, "summary": summarize(records)}

    return {
        "question": question,
        "models": model_keys,
        "runs": runs,
        "temperature": temperature,
        "judge": judge,
        "at": datetime.now().isoformat(timespec="seconds"),
        "by_model": by_model,
    }


TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def session_name(question: str) -> str:
    """Имя файла сессии: метка времени плюс начало вопроса латиницей.

    Кириллица переводится вручную, всё непонятное выбрасывается. Пустой результат
    заменяется на 'question', иначе имя выродилось бы в одну метку времени, а из
    вопроса вроде '../../etc/passwd' могло бы получиться имя, уводящее из папки.
    """
    lowered = unicodedata.normalize("NFC", question.lower())
    slug = "".join(TRANSLIT.get(ch, ch) for ch in lowered)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:40].strip("-")
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return f"{stamp}-{slug or 'question'}-{uuid4().hex[:8]}.json"


def save_session(result: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    temporary = RESULTS / f".{uuid4().hex}.tmp"
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        while True:
            path = RESULTS / session_name(result["question"])
            try:
                os.link(temporary, path)
                return path
            except FileExistsError:
                continue
    finally:
        temporary.unlink(missing_ok=True)


def load_sessions() -> list[dict]:
    """Все сохранённые сравнения, новые сверху.

    Битый файл пропускается молча: одна испорченная сессия не должна ронять всю историю.
    """
    if not RESULTS.exists():
        return []
    sessions = []
    for path in sorted(RESULTS.glob("*.json"), reverse=True):
        try:
            session = json.loads(path.read_text(encoding="utf-8"))
            for key in session.get("models", []):
                data = session.get("by_model", {}).get(key)
                if data and isinstance(data.get("records"), list):
                    data["summary"] = summarize(data["records"])
            sessions.append(session)
        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
            continue
    return sessions


def report(result: dict) -> None:
    print(f"\nвопрос: {result['question']}")
    temp = (
        "умолчание модели" if result["temperature"] is None else result["temperature"]
    )
    print(f"прогонов: {result['runs']}   температура: {temp}\n")
    head = (
        f"{'модель':<20} {'параметры':>10} {'время':>8} "
        f"{'вход':>7} {'выход':>7} {'знаков':>8} {'$':>10}"
    )
    print(head)
    print("-" * len(head))
    for key in result["models"]:
        summary = result["by_model"][key]["summary"]
        if not summary.get("api_ok"):
            first = result["by_model"][key]["records"][0]
            print(
                f"{key:<20} {MODELS[key]['params']:>10}   всё упало: {first['error'][:60]}"
            )
            continue
        completed = f"{summary['ok']}/{summary['runs']} завершено"
        # прочерк вместо нуля: провайдер мог не вернуть usage, и ноль соврал бы
        money = (
            f"{summary['cost_total']:.6f}" if summary["cost_total"] is not None else "—"
        )
        prompt = summary["prompt_avg"] if summary["prompt_avg"] is not None else "—"
        completion = (
            summary["completion_avg"] if summary["completion_avg"] is not None else "—"
        )
        print(
            f"{key:<20} {MODELS[key]['params']:>10} {summary['time_avg']:>7.2f}с "
            f"{prompt:>7} {completion:>7} {summary['chars_avg']:>8} {money:>10}"
        )
        if summary["ok"] != summary["runs"]:
            print(f"{'':<20} {'':>10}   {completed}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--models", nargs=3, default=list(DEFAULT_TRIO))
    args = parser.parse_args()

    for key in args.models:
        if key not in MODELS:
            parser.error(f"неизвестная модель {key!r}, есть: {', '.join(MODELS)}")
    if len(set(args.models)) != 3:
        parser.error("нужно выбрать три разные модели")
    if args.runs < 1 or args.runs > 10:
        parser.error("прогонов должно быть от 1 до 10")
    if args.temperature is not None and not 0 <= args.temperature <= 2:
        parser.error("температура должна быть в диапазоне 0..2")

    result = compare(
        args.question, args.models, args.runs, args.temperature, args.judge
    )
    report(result)
    print(f"\nсохранено: {save_session(result)}")


if __name__ == "__main__":
    main()
