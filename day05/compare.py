"""День 5: один вопрос трём моделям через роутер HuggingFace.

Все модели зовутся одним токеном через общий OpenAI-совместимый эндпоинт.
Провайдер закреплён в идентификаторе модели, поэтому железо у всех одинаковое
и разница во времени говорит про модели, а не про чужие чипы.

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

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

sys.path.insert(0, str(Path(__file__).parent))

from models import (  # noqa: E402
    DEFAULT_TRIO,
    MAX_TOKENS,
    MODELS,
    cheapest_key,
    cost,
    sampling_args,
)

load_dotenv()

RESULTS = Path(__file__).parent / "results"

JUDGE_PROMPT = """Оцени качество этого ответа по шкале от 1 до 10, где 1 — бесполезно,
10 — исчерпывающе и понятно. Ответь только числом.

{answer}"""

_client = None


def get_client() -> OpenAI:
    """Клиент создаётся при первом вызове, а не при импорте.

    Иначе модуль нельзя импортировать без HF_TOKEN — и офлайн-тесты чистых функций
    отсюда падали бы на строке импорта, ещё ничего не проверив.
    """
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["HF_TOKEN"],
            base_url="https://router.huggingface.co/v1",
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
        "temperature": temperature,
        "error": error,
    }


def ask(question: str, key: str, temperature: float | None = None) -> dict:
    """Один вызов. При сбое возвращает запись с error, а не бросает исключение.

    temperature=None означает, что параметр не отправляется вообще и модель отвечает
    на своём умолчании. Подставленный ноль был бы не «умолчанием», а конкретной
    настройкой, которая меняет поведение.
    """
    started = time.monotonic()
    try:
        response = get_client().chat.completions.create(
            model=MODELS[key]["id"],
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": question}],
            **sampling_args(temperature),
        )
    except OpenAIError as error:
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
        "temperature": temperature,
        "error": None,
    }


def judge_answer(answer: str) -> int | None:
    """Оценка 1-10 отдельным вызовом самой дешёвой модели каталога.

    Каждый ответ оценивается по отдельности, не видя остальные: иначе оценка
    сместилась бы от порядка показа, а не от самого текста.
    """
    if not answer.strip():
        return None
    record = ask(JUDGE_PROMPT.format(answer=answer), cheapest_key(), temperature=0)
    if record["error"]:
        return None
    match = re.search(r"\d+", record["answer"])
    return int(match.group()) if match else None


def summarize(records: list[dict]) -> dict:
    """Агрегаты по одной модели. Считаются только по успешным вызовам."""
    good = [r for r in records if not r["error"]]
    if not good:
        return {"runs": len(records), "ok": 0}

    times = [r["elapsed"] for r in good]
    costs = [r["cost"] for r in good if r["cost"] is not None]
    prompt = [r["prompt_tokens"] for r in good if r["prompt_tokens"] is not None]
    completion = [
        r["completion_tokens"] for r in good if r["completion_tokens"] is not None
    ]
    chars = [r["answer_chars"] for r in good]
    judges = [r["judge"] for r in good if r.get("judge") is not None]

    return {
        "runs": len(records),
        "ok": len(good),
        "time_avg": round(sum(times) / len(times), 3),
        "time_min": min(times),
        "time_max": max(times),
        "prompt_avg": round(sum(prompt) / len(prompt), 1) if prompt else None,
        "completion_avg": round(sum(completion) / len(completion), 1)
        if completion
        else None,
        "chars_avg": round(sum(chars) / len(chars), 1),
        "cost_total": round(sum(costs), 8) if costs else None,
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
            if judge:
                record["judge"] = judge_answer(record["answer"])
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
    return f"{stamp}-{slug or 'question'}.json"


def save_session(result: dict) -> Path:
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / session_name(result["question"])
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_sessions() -> list[dict]:
    """Все сохранённые сравнения, новые сверху.

    Битый файл пропускается молча: одна испорченная сессия не должна ронять всю историю.
    """
    if not RESULTS.exists():
        return []
    sessions = []
    for path in sorted(RESULTS.glob("*.json"), reverse=True):
        try:
            sessions.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
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
        if not summary.get("ok"):
            first = result["by_model"][key]["records"][0]
            print(
                f"{key:<20} {MODELS[key]['params']:>10}   всё упало: {first['error'][:60]}"
            )
            continue
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

    result = compare(
        args.question, args.models, args.runs, args.temperature, args.judge
    )
    report(result)
    print(f"\nсохранено: {save_session(result)}")


if __name__ == "__main__":
    main()
