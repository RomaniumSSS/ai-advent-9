"""Терминал дня 12: явная запись в слой и разговор с агентом."""

import argparse
import json
import sqlite3
from profile import UserProfile
from offline import OfflineClient
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig  # noqa: E402
from store import DEFAULT_DB, LAYERS, SqliteStore  # noqa: E402


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--db", type=Path, default=DEFAULT_DB)
    result.add_argument("--env-file", type=Path)
    result.add_argument("--user", default="roman")
    result.add_argument("--task", default="project")
    result.add_argument("--session", default="main")
    result.add_argument("--recent-turns", type=int, default=6)
    result.add_argument("--max-tokens", type=int, default=4000)
    result.add_argument("--context-limit", type=int)
    result.add_argument("--offline", action="store_true")
    return result


def display_memory(agent: Agent) -> None:
    state = agent.memory_state()
    scope = state["scope"]
    print(
        f"Области: разговор={scope['session']}, "
        f"задача={scope['task']}, пользователь={scope['user']}"
    )
    print(f"Архив: {state['archive_size']} сообщений; в запросе видны "
          f"последние {len(state['short_history'])}")
    for layer in LAYERS:
        print(f"{layer}:")
        notes = state["notes"][layer]
        if not notes:
            print("  (пусто)")
        for key, value in notes.items():
            print(f"  {key}: {value}")


def command(agent: Agent, line: str) -> bool:
    """True — команда обработана; False — обычный вопрос модели."""
    if line == "/profile":
        print(json.dumps(agent.store.load_profile().to_dict(), ensure_ascii=False))
        return True
    if line.startswith("/profile "):
        agent.store.save_profile(UserProfile.from_dict(json.loads(line[9:])))
        print("Профиль сохранён; применяется со следующего запроса")
        return True
    if line == "/help":
        print('/profile [JSON] — прочитать или сохранить style, format, constraints')
        print("/save short|working|long КЛЮЧ ЗНАЧЕНИЕ — запомнить")
        print("/forget short|working|long КЛЮЧ — удалить заметку")
        print("/memory — посмотреть три слоя; /context ВОПРОС — показать запрос")
        print("/reset — очистить только текущий разговор; /exit — закончить")
        return True
    if line == "/memory":
        display_memory(agent)
        return True
    if line.startswith("/save "):
        parts = line.split(maxsplit=3)
        if len(parts) != 4:
            print("Формат: /save СЛОЙ КЛЮЧ ЗНАЧЕНИЕ")
        else:
            agent.save(parts[1], parts[2], parts[3])
            print(f"Сохранено в {parts[1]}: {parts[2]}")
        return True
    if line.startswith("/forget "):
        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            print("Формат: /forget СЛОЙ КЛЮЧ")
        else:
            print("Удалено" if agent.forget(parts[1], parts[2]) else "Такой записи нет")
        return True
    if line == "/reset":
        agent.reset()
        print("Текущий разговор очищен. Рабочая и долговременная память остались.")
        return True
    if line.startswith("/context "):
        question = line.removeprefix("/context ").strip()
        if not question:
            print("Укажите вопрос после /context")
        else:
            for message in agent.build_messages(question):
                print(f"[{message['role']}] {message['content']}")
            print(agent.budget(question).line())
        return True
    return False


def main() -> None:
    args = parser().parse_args()
    if args.env_file:
        if not args.env_file.is_file():
            raise FileNotFoundError(f"нет env-файла {args.env_file}")
        load_dotenv(args.env_file)
    agent = Agent(
        name="Агент дня 12",
        config=AgentConfig(
            max_tokens=args.max_tokens,
            context_limit=args.context_limit,
        ),
        store=SqliteStore(args.db, args.session, args.task, args.user),
        recent_turns=args.recent_turns,
        client=OfflineClient() if args.offline else None,
    )
    display_memory(agent)
    print("Введите /help для команд, /exit для выхода.")
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
            print("Пустой ответ" if reply.empty else reply.text or reply.error)
            print(reply.debug_line())
        except (ValueError, RuntimeError, sqlite3.Error, OSError) as error:
            print(f"Ошибка: {error}")


if __name__ == "__main__":
    main()
