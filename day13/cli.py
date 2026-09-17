"""CLI дня 13: накопительный агент и отдельное управление Task State Machine."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent import Agent, AgentConfig
from offline import OfflineClient
from store import DEFAULT_DB, SqliteStore


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--db", type=Path, default=DEFAULT_DB)
    result.add_argument("--env-file", type=Path)
    result.add_argument("--user", default="roman")
    result.add_argument("--task", default="project")
    result.add_argument("--session", default="main")
    result.add_argument("--offline", action="store_true")
    return result


def show(agent: Agent) -> None:
    state = agent.task_state()
    print("Нет формализованной задачи" if state is None else json.dumps(
        state.to_dict(), ensure_ascii=False, indent=2
    ))


def command(agent: Agent, line: str) -> bool:
    if line == "/state":
        show(agent)
    elif line.startswith("/start "):
        agent.start_task(line.removeprefix("/start "))
        show(agent)
    elif line.startswith("/act "):
        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            raise ValueError("формат: /act СОБЫТИЕ РЕЗУЛЬТАТ")
        agent.apply_task(parts[1], parts[2])
        show(agent)
    elif line == "/pause":
        agent.pause_task()
        show(agent)
    elif line == "/resume":
        agent.resume_task()
        show(agent)
    elif line == "/clear":
        agent.reset()
        print("Диалог очищен; FSM задачи сохранена.")
    elif line == "/events":
        print(json.dumps(agent.store.task_events(), ensure_ascii=False, indent=2))
    elif line == "/help":
        print("/start ЦЕЛЬ · /state · /act СОБЫТИЕ РЕЗУЛЬТАТ")
        print("/pause · /resume · /events · /clear · /exit")
    else:
        return False
    return True


def main() -> None:
    args = parser().parse_args()
    if args.env_file:
        load_dotenv(args.env_file)
    agent = Agent(
        name="Агент дня 13",
        config=AgentConfig(),
        store=SqliteStore(args.db, args.session, args.task, args.user),
        client=OfflineClient() if args.offline else None,
    )
    show(agent)
    print("Введите /help для команд.")
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        if line == "/exit":
            break
        try:
            if command(agent, line):
                continue
            reply = agent.ask(line)
            print(reply.text or reply.error or "Пустой ответ")
            print(reply.debug_line())
        except (ValueError, RuntimeError, sqlite3.Error, OSError) as error:
            print(f"Ошибка: {error}")


if __name__ == "__main__":
    main()
