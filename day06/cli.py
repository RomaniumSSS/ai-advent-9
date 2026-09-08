"""День 6: чат с агентом в терминале.

Файл намеренно тонкий. Здесь только ввод-вывод: ни сборки запроса, ни истории,
ни разбора ответа — всё это внутри Agent. Если бы что-то из перечисленного
понадобилось написать здесь, значит коробка дырявая.

Запуск:
    uv run day06/cli.py
    uv run day06/cli.py --model kimi-k3 --temperature 0.9
    uv run day06/cli.py --system "Ты бухгалтер. Отвечай сухо."
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent import DEFAULT_SYSTEM_PROMPT, Agent, AgentConfig  # noqa: E402
from models import DEFAULT_MODEL, MAX_TOKENS, MODELS  # noqa: E402

HELP = """команды:
  /reset    забыть разговор, роль остаётся
  /history  показать, что агент помнит
  /config   показать конфиг агента
  /exit     выход (или Ctrl+D)"""


def show_history(agent: Agent) -> None:
    if not agent.history:
        print("  история пуста")
        return
    for message in agent.history:
        who = "вы" if message["role"] == "user" else "агент"
        text = message["content"].replace("\n", " ")
        print(f"  {who}: {text[:100]}{'…' if len(text) > 100 else ''}")


def show_config(agent: Agent) -> None:
    config = agent.config
    temperature = (
        "по умолчанию модели" if config.temperature is None else config.temperature
    )
    print(f"  модель:      {config.model} ({MODELS[config.model]['params']})")
    print(f"  температура: {temperature}")
    print(f"  max_tokens:  {config.max_tokens}")
    print(f"  ходов:       {agent.turns}")
    print(f"  роль:        {config.system_prompt}")


def main() -> int:
    parser = argparse.ArgumentParser(description="чат с агентом дня 6")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(MODELS))
    parser.add_argument("--system", default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    args = parser.parse_args()

    agent = Agent(
        config=AgentConfig(
            model=args.model,
            system_prompt=args.system,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    )
    print(f"агент на {agent.config.model}. {HELP}\n")

    total_cost = 0.0
    while True:
        try:
            question = input("вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question in ("/exit", "/quit"):
            break
        if question == "/reset":
            agent.reset()
            print("  история очищена\n")
            continue
        if question == "/history":
            show_history(agent)
            print()
            continue
        if question == "/config":
            show_config(agent)
            print()
            continue
        if question.startswith("/"):
            print(HELP + "\n")
            continue

        reply = agent.ask(question)
        if reply.ok:
            print(f"\nагент: {reply.text}\n")
        else:
            print("\nагент не ответил\n")
        # Строка дебага печатается всегда, в том числе при сбое: при неизменном
        # интерфейсе это единственное видимое доказательство, что работает коробка,
        # а не один вызов API.
        print(f"  {reply.debug_line()}")
        if reply.cost is not None:
            total_cost += reply.cost
            print(f"  за сессию: ${total_cost:.6f}\n")
        else:
            print()

    if total_cost:
        print(f"итого за сессию: ${total_cost:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
