"""День 4: одна и та же пара запросов на трёх температурах.

temperature = 0 / 0.7 / 1.2, каждая прогоняется 10 раз на двух запросах:
    letter   капкан на подсчёт букв, эталон точный, точность считается кодом
    gadget   открытый запрос с зашитыми требованиями; точность и разнообразие
             считаются кодом, креативность — отдельным вызовом-судьёй

Запуск:
    uv run day04/temperature.py
    uv run day04/temperature.py --runs 5
    uv run day04/temperature.py --report
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

sys.path.insert(0, str(Path(__file__).parent))

from traps import (  # noqa: E402
    GADGET_PROMPT,
    HUMAN_EXAMPLE,
    LETTER_QUESTION,
    check_gadget,
    normalize,
    score_letter,
)

load_dotenv()

MODEL = "deepseek-chat"
TEMPERATURES = (0, 0.7, 1.2)
MAX_TOKENS = 2000
RESULTS = Path(__file__).parent / "results.json"

TASKS = {"letter": LETTER_QUESTION, "gadget": GADGET_PROMPT}

JUDGE_PROMPT = """Оцени оригинальность этого питча гаджета по шкале от 1 до 10, где 1 — банально,
10 — очень оригинально. Ответь только числом.

{answer}"""

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)


def ask(prompt: str, temperature: float) -> tuple[str, str]:
    """Возвращает (текст ответа, причина остановки). При сбое API — ("", "error: ...")."""
    try:
        choice = client.chat.completions.create(
            model=MODEL,
            temperature=temperature,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ).choices[0]
    except OpenAIError as error:
        return "", f"error: {type(error).__name__}"
    return choice.message.content or "", choice.finish_reason or ""


def judge(answer: str) -> int | None:
    """Оценка оригинальности 1-10 отдельным вызовом. None, если не распарсилось.

    Оценивает каждый ответ по отдельности, не видя остальные — иначе оценка
    сместилась бы относительно порядка показа, а не самого текста.
    """
    text, stop = ask(JUDGE_PROMPT.format(answer=answer), temperature=0)
    if stop.startswith("error"):
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    value = int(match.group())
    return value if 1 <= value <= 10 else None


def run_once(task: str, temperature: float) -> dict:
    answer, stop = ask(TASKS[task], temperature)
    return {"task": task, "temperature": temperature, "answer": answer, "stop": stop}


def measure(runs: int) -> list[dict]:
    """Оба запроса, все три температуры, параллельно. Судья — отдельным проходом,
    только после того как есть что судить."""
    jobs = [
        (task, temperature)
        for task in TASKS
        for temperature in TEMPERATURES
        for _ in range(runs)
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(lambda job: run_once(*job), jobs))

    gadget_records = [
        r
        for r in records
        if r["task"] == "gadget" and not r["stop"].startswith("error")
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        judged = list(pool.map(lambda r: judge(r["answer"]), gadget_records))
    for record, score in zip(gadget_records, judged):
        record["judge"] = score

    return records


def annotate(data: dict) -> list[dict]:
    """Каждая сырая запись плюс её проверка. Используется и отчётом, и панелью."""
    out = []
    for r in data["records"]:
        if r["stop"].startswith("error"):
            out.append({**r, "score": None})
            continue
        if r["task"] == "letter":
            score = score_letter(r["answer"])
        else:
            score = check_gadget(r["answer"])
            score["judge"] = r.get("judge")
        out.append({**r, "score": score})
    return out


def summarize(data: dict) -> dict:
    """Агрегаты по температуре для обоих запросов."""
    annotated = annotate(data)

    letter_rows = []
    for temperature in TEMPERATURES:
        rows = [
            r
            for r in annotated
            if r["task"] == "letter" and r["temperature"] == temperature
        ]
        errors = [r for r in rows if r["score"] is None]
        scored = [r["score"] for r in rows if r["score"] is not None]
        parsed = [s for s in scored if s["parsed"]]
        letter_rows.append(
            {
                "temperature": temperature,
                "total": len(scored),
                "parsed": len(parsed),
                "correct": sum(s["correct"] for s in parsed),
                "errors": len(errors),
            }
        )

    gadget_rows = []
    for temperature in TEMPERATURES:
        rows = [
            r
            for r in annotated
            if r["task"] == "gadget" and r["temperature"] == temperature
        ]
        errors = [r for r in rows if r["score"] is None]
        oks = [r for r in rows if r["score"] is not None]
        checks = [r["score"] for r in oks]
        accuracy = (
            sum(c["score"] for c in checks) / (4 * len(checks)) * 100 if checks else 0
        )
        unique = (
            len({normalize(r["answer"]) for r in oks}) / len(oks) * 100 if oks else 0
        )
        judged = [c["judge"] for c in checks if c.get("judge") is not None]
        creativity = sum(judged) / len(judged) if judged else 0
        gadget_rows.append(
            {
                "temperature": temperature,
                "total": len(oks),
                "accuracy": round(accuracy, 1),
                "unique": round(unique, 1),
                "creativity": round(creativity, 1),
                "errors": len(errors),
            }
        )

    return {"letter": letter_rows, "gadget": gadget_rows}


def report(data: dict) -> None:
    summary = summarize(data)
    human_judge = data["human_judge"]

    print("=== капкан: буквы «с» в «рассредоточенность» (эталон 3) ===")
    print(f"{'температура':<12} {'разобралось':>12} {'верно':>8}")
    for row in summary["letter"]:
        line = f"{row['temperature']:<12} {row['parsed']:>7}/{row['total']:<4} {row['correct']:>8}"
        if row["errors"]:
            line += f"   не дошло: {row['errors']}"
        print(line)

    print("\n=== открытый: гаджет с 4 требованиями ===")
    print(
        f"{'температура':<12} {'точность':>9} {'уникальных':>11} {'креативность':>13}"
    )
    for row in summary["gadget"]:
        line = (
            f"{row['temperature']:<12} {row['accuracy']:>8.0f}% "
            f"{row['unique']:>10.0f}% {row['creativity']:>13.1f}"
        )
        if row["errors"]:
            line += f"   не дошло: {row['errors']}"
        print(line)

    print(f"\nчеловеческий эталон: {HUMAN_EXAMPLE!r}")
    print(f"  проверка кодом: {check_gadget(HUMAN_EXAMPLE)}")
    print(f"  оценка судьи: {human_judge}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument(
        "--report",
        action="store_true",
        help="напечатать отчёт из results.json без обращений к API",
    )
    args = parser.parse_args()

    if args.report:
        if not RESULTS.exists():
            sys.exit(f"нет файла {RESULTS} — сначала запусти замер")
        report(json.loads(RESULTS.read_text(encoding="utf-8")))
        return

    records = measure(args.runs)
    human_judge = judge(HUMAN_EXAMPLE)
    data = {"records": records, "human_judge": human_judge}
    RESULTS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"сырые ответы сохранены в {RESULTS.name}")
    report(data)


if __name__ == "__main__":
    main()
