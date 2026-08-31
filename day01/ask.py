"""День 1 — минимальный запрос к LLM через API.

Запуск:
    uv run day01/ask.py "твой вопрос"
    uv run day01/ask.py            # спросит вопрос в консоли
"""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "deepseek-chat"

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)


def ask(question: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": question}],
        temperature=0,
    )
    return response.choices[0].message.content or ""


def main() -> None:
    question = " ".join(sys.argv[1:]) or input("Вопрос: ")
    if not question.strip():
        sys.exit("Пустой вопрос — нечего спрашивать.")

    print(f"\n→ {MODEL}\n")
    print(ask(question))


if __name__ == "__main__":
    main()
