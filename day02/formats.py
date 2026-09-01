"""День 2: контроль формата ответа.

Один и тот же запрос в трёх режимах:
    raw:    без ограничений вообще
    soft:   формат, длина и завершение заданы словами в промпте
    strict: то же самое, но параметрами запроса (response_format, max_tokens, stop)

Запуск:
    uv run day02/formats.py --chat          # диалог, режим переключается на лету
    uv run day02/formats.py                 # сравнить все три режима
    uv run day02/formats.py --mode strict   # один режим
    uv run day02/formats.py --runs 5        # проверка стабильности формата
"""

import argparse
import json
import os
from collections.abc import Sequence

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

load_dotenv()

MODEL = "deepseek-chat"
MODES = ("raw", "soft", "strict")

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

QUESTION = "Составь зарядку на 10 минут для того, кто много сидит за компьютером."

RULES = """Ты составляешь зарядку и разминку. Отвечай только на вопросы про упражнения,
разминку, растяжку и зарядку. Если вопрос не об этом — верни ровно
{"error": "вопрос вне темы"} и больше ничего.

Ответ верни JSON-объектом с единственным ключом "exercises" — массивом упражнений.
Каждое упражнение — объект с полями:
  name     — строка, название упражнения
  minutes  — число, сколько минут занимает
  reps     — строка, количество повторов или длительность
  target   — строка, какую часть тела разминает
Не более 5 упражнений и не более 80 слов суммарно.
Никакого текста до и после объекта, без markdown-разметки.
Закончи ответ словом КОНЕЦ.

ПРИМЕР ОТВЕТА В ФОРМАТЕ JSON:
{
  "exercises": [
    {"name": "Наклоны головы", "minutes": 1, "reps": "10 раз", "target": "шея"},
    {"name": "Вращения плечами", "minutes": 2, "reps": "15 раз", "target": "плечи"}
  ]
}"""


def ask(question: str, mode: str, temperature: float) -> tuple[str, str]:
    """Возвращает (текст ответа, причина остановки). При сбое API отдаёт ("", "error")."""
    prompt = question if mode == "raw" else f"{RULES}\n\n{question}"

    params = {
        "model": MODEL,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    # soft: те же требования, только словами в промпте, без параметров

    if mode == "strict":
        params["response_format"] = {"type": "json_object"}
        params["max_tokens"] = 400
        params["stop"] = [STOP_WORD]

    try:
        choice = client.chat.completions.create(**params).choices[0]
    except OpenAIError as error:
        print(f"  сбой запроса: {type(error).__name__}: {error}")
        return "", "error"

    return choice.message.content or "", choice.finish_reason or ""


FIELDS = {"name", "minutes", "reps", "target"}
LIMIT_WORDS = 80
LIMIT_ITEMS = 5
STOP_WORD = "КОНЕЦ"


def parse(answer: str):
    """Разбирает ответ один раз. Возвращает данные или None."""
    try:
        return json.loads(answer)
    except json.JSONDecodeError:
        return None


def is_refusal(data) -> bool:
    """Отказ по теме тоже правильное поведение, а не поломка формата."""
    return isinstance(data, dict) and set(data) == {"error"}


def exercises_of(data) -> list | None:
    """Список упражнений, если схема ровно та, что просили. Иначе None."""
    if not isinstance(data, dict):
        return None

    items = data.get("exercises")
    if not isinstance(items, list) or not items:
        return None
    if not all(isinstance(item, dict) and FIELDS <= set(item) for item in items):
        return None
    return items


def content_words(value) -> int:
    """Считает слова в содержимом, не в разметке: строки и числа, без имён полей."""
    if isinstance(value, str):
        return len(value.split())
    if isinstance(value, (int, float)):  # bool сюда же, он подкласс int
        return 1
    if isinstance(value, list):
        return sum(content_words(item) for item in value)
    if isinstance(value, dict):
        return sum(content_words(item) for item in value.values())
    return 0


def count_words(answer: str, data) -> int:
    return len(answer.split()) if data is None else content_words(data)


def stop_verdict(answer: str, stop_reason: str) -> str:
    """Что на самом деле оборвало ответ. Порядок проверок важен.

    Обрезанный по лимиту ответ не содержит стоп-слова, и наивная проверка
    записала бы это в заслугу stop. Поэтому лимит проверяется первым.
    """
    if stop_reason == "length":
        return "упёрся в max_tokens, формат мог сломаться"
    if STOP_WORD in answer:
        return f"маркер {STOP_WORD} остался в тексте, значит завершение не сработало"
    if stop_reason == "stop":
        return "чисто: маркера нет, обрыва нет"
    return f"неожиданная причина остановки: {stop_reason or 'пусто'}"


def verdict(answer: str, stop_reason: str) -> dict:
    """Разбор одного ответа. Чистая функция, тестируется без обращения к API."""
    data = parse(answer)
    items = exercises_of(data)
    words = count_words(answer, data)
    refused = is_refusal(data)
    return {
        "json_ok": data is not None,
        "refusal": refused,
        "schema_ok": items is not None,
        "items": len(items) if items else 0,
        "words": words,
        "fits": items is not None
        and len(items) <= LIMIT_ITEMS
        and words <= LIMIT_WORDS,
        "stop": stop_verdict(answer, stop_reason),
    }


def report(question: str, modes: Sequence[str], runs: int, temperature: float) -> None:
    for mode in modes:
        print(f"\n{'=' * 70}")
        print(f"РЕЖИМ: {mode}    температура: {temperature}")
        print("=" * 70)

        valid_json, valid_schema, in_limits, refusals, failed = 0, 0, 0, 0, 0
        for run in range(runs):
            answer, stop_reason = ask(question, mode, temperature)

            if stop_reason == "error":
                failed += 1
                continue

            v = verdict(answer, stop_reason)

            valid_json += v["json_ok"]
            refusals += v["refusal"]
            if not v["refusal"]:
                valid_schema += v["schema_ok"]
                in_limits += v["fits"]

            if runs == 1:
                print(answer or "(пустой ответ)")
                print(f"\n  stop_reason: {stop_reason}, {v['stop']}")
            elif v["refusal"]:
                print(f"  прогон {run + 1}: отказ по теме (в статистику схемы не идёт)")
            else:
                print(
                    f"  прогон {run + 1}: слов {v['words']:4}  "
                    f"упражнений {v['items'] or '-':>2}  "
                    f"JSON {'да ' if v['json_ok'] else 'НЕТ'}  "
                    f"схема {'да ' if v['schema_ok'] else 'НЕТ'}  "
                    f"в лимитах {'да' if v['fits'] else 'НЕТ'}  "
                    f"stop_reason: {stop_reason}"
                )

        if runs > 1:
            total = runs - failed
            scored = total - refusals
            print(f"\n  валидный JSON:      {valid_json} из {total}")
            print(f"  совпала схема:      {valid_schema} из {scored}")
            print(f"  уложился в лимиты:  {in_limits} из {scored}")
            if refusals:
                print(f"  отказов по теме:    {refusals} (схема не проверяется)")
            if failed:
                print(f"  запросов не дошло:  {failed} (в статистику не считаются)")


HELP = """Команды:
  /mode raw|soft|strict|all   переключить режим (сейчас: {mode})
  /runs N                     сколько прогонов на режим (сейчас: {runs})
  /help                       эта справка
  /exit                       выход
Любой другой текст считается вопросом к модели.
Агент отвечает только про зарядку и разминку, на остальное вернёт
{{"error": "вопрос вне темы"}}."""


def handle_command(line: str, mode: str, runs: int) -> tuple[str, int]:
    """Разбирает команду, возвращает новые (mode, runs)."""
    parts = line.split()
    name, args = parts[0], parts[1:]

    if name == "/help":
        print(HELP.format(mode=mode, runs=runs))
    elif name == "/mode":
        if args and args[0] in MODES + ("all",):
            mode = args[0]
            print(f"режим: {mode}")
        else:
            print("режимы: raw, soft, strict, all")
    elif name == "/runs":
        if args and args[0].isdigit() and int(args[0]) > 0:
            runs = int(args[0])
            print(f"прогонов: {runs}")
        else:
            print("нужно целое число больше нуля, например /runs 5")
    else:
        print(f"неизвестная команда {name}, список команд в /help")

    return mode, runs


def chat(runs: int, temperature: float) -> None:
    mode = "all"
    print("Режим диалога. /help для списка команд, /exit для выхода.\n")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not line:
            continue
        if line == "/exit":
            return
        if line.startswith("/"):
            mode, runs = handle_command(line, mode, runs)
            continue

        report(line, list(MODES) if mode == "all" else [mode], runs, temperature)


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("нужно целое число больше нуля")
    return number


def temperature(value: str) -> float:
    number = float(value)
    if not 0 <= number <= 2:
        raise argparse.ArgumentTypeError("температура задаётся от 0 до 2")
    return number


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat", action="store_true", help="режим диалога")
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--runs", type=positive, default=1)
    parser.add_argument("--temperature", type=temperature, default=1.0)
    args = parser.parse_args()

    if args.chat:
        chat(args.runs, args.temperature)
        return

    modes = [args.mode] if args.mode else list(MODES)
    report(QUESTION, modes, args.runs, args.temperature)


if __name__ == "__main__":
    main()
