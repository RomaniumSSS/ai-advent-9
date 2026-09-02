"""День 3: одна задача, четыре способа рассуждения.

Режимы:
    direct   прямой ответ без дополнительных инструкций
    steps    «решай пошагово»
    meta     модель сначала пишет промпт, затем решает по нему (два вызова)
    experts  группа экспертов в промпте: аналитик, инженер, критик

Инструкция про формат ответа дословно одинакова во всех режимах: иначе сравнивались
бы форматы, а не рассуждения.

Запуск:
    uv run day03/reasoning.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

sys.path.insert(0, str(Path(__file__).parent))

from build import ANSWER_FORMAT, parse_answer, task_text  # noqa: E402

load_dotenv()

MODEL = "deepseek-chat"
TEMPERATURE = 1.0

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

STEPS_HINT = "Решай пошагово. Рассуждай вслух, по одному правилу за раз."

EXPERTS_HINT = """Реши задачу силами группы экспертов. Каждый высказывается по очереди:
АНАЛИТИК — разбирает ограничения и отсекает заведомо негодные варианты.
ИНЖЕНЕР — считает вес, тягу, ток и время полёта для оставшихся.
КРИТИК — ищет ошибки в расчётах инженера и нарушенные правила.
После них выведи общий вывод группы."""

META_REQUEST = """Ниже задача. Не решай её.
Составь промпт, который поможет языковой модели решить эту задачу максимально точно.
Выведи только текст промпта.

ЗАДАЧА:
{task}"""


def call(prompt: str) -> tuple[str, str]:
    """Возвращает (текст ответа, причина остановки). При сбое API отдаёт ("", "error: ...")."""
    try:
        choice = client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
        ).choices[0]
    except OpenAIError as error:
        return "", f"error: {type(error).__name__}"
    return choice.message.content or "", choice.finish_reason or ""


def mode_direct(task: str) -> tuple[str, str, int]:
    answer, stop = call(f"{task}\n\n{ANSWER_FORMAT}")
    return answer, stop, 1


def mode_steps(task: str) -> tuple[str, str, int]:
    answer, stop = call(f"{task}\n\n{STEPS_HINT}\n\n{ANSWER_FORMAT}")
    return answer, stop, 1


def mode_experts(task: str) -> tuple[str, str, int]:
    answer, stop = call(f"{task}\n\n{EXPERTS_HINT}\n\n{ANSWER_FORMAT}")
    return answer, stop, 1


def mode_meta(task: str) -> tuple[str, str, int]:
    """Два вызова: сначала модель пишет промпт, затем решает по нему.

    Промпт генерируется заново на каждом прогоне. Если сгенерировать один раз
    и переиспользовать, у этого режима разброс окажется искусственно занижен,
    и сравнение с остальными тремя станет нечестным.

    Блок про формат ответа дописывается всегда: модель может его не включить,
    а без него ответ нечем разобрать.
    """
    generated, stop = call(META_REQUEST.format(task=task))
    if stop.startswith("error"):
        return "", stop, 1
    answer, stop = call(f"{generated}\n\n{task}\n\n{ANSWER_FORMAT}")
    return answer, stop, 2


MODES = {
    "direct": mode_direct,
    "steps": mode_steps,
    "meta": mode_meta,
    "experts": mode_experts,
}


def run_once(mode: str) -> dict:
    """Один прогон одного режима. Сырой ответ сохраняется целиком."""
    answer, stop, calls = MODES[mode](task_text())
    return {"mode": mode, "answer": answer, "stop": stop, "calls": calls}


if __name__ == "__main__":
    result = run_once("direct")
    print(result["answer"])
    print(f"\n{'=' * 60}")
    print(f"stop: {result['stop']}, вызовов: {result['calls']}")
    print(f"разобралось: {parse_answer(result['answer'])}")
