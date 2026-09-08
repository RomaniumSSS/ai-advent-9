"""День 7: чат с агентом в терминале, переживающий перезапуск.

Файл намеренно тонкий, как и в дне 6. Здесь только ввод-вывод: ни сборки запроса,
ни истории, ни записи в базу. Терминал даже не знает, что хранилище — SQLite;
он его создаёт и отдаёт агенту.

Проверка задания делается руками ровно так:

    uv run day07/cli.py --session demo     # «меня зовут Роман», потом Ctrl+D
    uv run day07/cli.py --session demo     # «как меня зовут» → помнит

Запуск:
    uv run day07/cli.py
    uv run day07/cli.py --session работа --model kimi-k3
    uv run day07/cli.py --sessions          # что вообще лежит в базе
    uv run day07/cli.py --forget            # начать сессию с нуля
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent import DEFAULT_SYSTEM_PROMPT, Agent, AgentConfig  # noqa: E402
from models import DEFAULT_MODEL, MAX_TOKENS, MODELS  # noqa: E402
from store import DEFAULT_DB, DEFAULT_SESSION, SqliteStore  # noqa: E402

# Порог, с которого разговор пора считать длинным. Число не измерено и не может
# быть точным: в токенах ход весит по-разному, а окна у моделей разные. Смысл не
# в точности, а в том, чтобы предупреждение пришло ЗАДОЛГО до отказа — история
# уезжает в модель целиком на каждом ходу, и упереться в окно она может внезапно,
# посреди разговора, отказом вместо ответа. Обрезки и сжатия здесь нет сознательно,
# см. «Чего здесь нет» в README.
LONG_HISTORY_TURNS = 100

HELP = """команды:
  /reset    забыть разговор — и в памяти, и в базе; роль остаётся
  /history  показать, что агент помнит
  /config   показать конфиг агента
  /store    показать, что лежит в базе
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


def show_store(store: SqliteStore) -> None:
    stats = store.stats()
    spent = "неизвестно" if stats["cost"] is None else f"${stats['cost']:.6f}"
    print(f"  файл:        {store.path}")
    print(f"  сессия:      {stats['session']}")
    print(f"  ходов:       {stats['turns']}  (сообщений {stats['messages']})")
    print(f"  первый ход:  {stats['first_at'] or '—'}")
    print(f"  последний:   {stats['last_at'] or '—'}")
    print(f"  всего денег: {spent}")


def show_sessions(store: SqliteStore) -> None:
    rows = store.sessions()
    if not rows:
        print(f"в базе {store.path} пока пусто")
        return
    print(f"сессии в {store.path}:")
    for row in rows:
        print(
            f"  {row['session']:<20} ходов {row['turns']:<5} последний {row['last_at']}"
        )


def turns_word(count: int) -> str:
    """«1 ход», «2 хода», «5 ходов». Мелочь, но строка про восстановление —
    первое, что человек читает при запуске, и рваная грамматика в ней читается
    как небрежность во всём остальном."""
    if 11 <= count % 100 <= 14:
        return "ходов"
    return {1: "ход", 2: "хода", 3: "хода", 4: "хода"}.get(count % 10, "ходов")


def announce_restore(agent: Agent) -> None:
    """Сказать вслух, что разговор не новый.

    Молча подложенная история — тот случай, когда всё работает, а человек не
    понимает почему: агент отвечает с оглядкой на реплики, которых на экране нет.
    """
    if agent.restored_turns == 0:
        print("новый разговор\n")
        return
    restored = agent.restored_turns
    print(f"продолжаю разговор: {restored} {turns_word(restored)} из базы")
    last = agent.history[-1]["content"].replace("\n", " ")
    print(f"последним было: «{last[:120]}{'…' if len(last) > 120 else ''}»")

    # Сверка с тем, чем сессию писали в прошлый раз. История, снятая под другой
    # ролью, остаётся валидной перепиской, но объясняет странности в ответах —
    # и человек должен узнать об этом до того, как начнёт искать их в коде.
    was = agent.restored_config or {}
    if was.get("model") and was["model"] != agent.config.model:
        print(f"  ВНИМАНИЕ: прошлый раз сессия шла на {was['model']}")
    if was.get("system_prompt") and was["system_prompt"] != agent.config.system_prompt:
        print("  ВНИМАНИЕ: роль агента изменилась с прошлого запуска")
    print()


def warn_if_long(agent: Agent, already_warned: bool) -> bool:
    """Сказать один раз за запуск, что разговор стал длинным. Возвращает новое
    значение флага: повторять на каждом ходу — верный способ перестать читать."""
    if already_warned or agent.turns < LONG_HISTORY_TURNS:
        return already_warned
    print(
        f"  ВНИМАНИЕ: в разговоре {agent.turns} ходов, и каждый следующий вопрос\n"
        f"  отправляет их все заново. Дальше растут деньги и риск упереться\n"
        f"  в контекстное окно. Начать новый разговор: --session другое-имя\n"
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="чат с агентом дня 7")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(MODELS))
    parser.add_argument("--system", default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--db", default=DEFAULT_DB, help="файл базы с историей")
    parser.add_argument("--session", default=DEFAULT_SESSION, help="имя разговора")
    parser.add_argument(
        "--sessions", action="store_true", help="показать разговоры в базе и выйти"
    )
    parser.add_argument(
        "--forget", action="store_true", help="стереть эту сессию перед стартом"
    )
    args = parser.parse_args()

    store = SqliteStore(args.db, args.session)
    if args.sessions:
        show_sessions(store)
        return 0
    # Стирать надо ДО создания агента: агент читает базу в момент создания, и
    # стирание после подняло бы разговор в память и убрало бы его только с диска.
    if args.forget:
        store.clear()
        print(f"сессия {args.session!r} стёрта")

    agent = Agent(
        config=AgentConfig(
            model=args.model,
            system_prompt=args.system,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        ),
        store=store,
    )
    print(f"агент на {agent.config.model}, сессия {args.session!r} → {store.path}")
    print(f"{HELP}\n")
    announce_restore(agent)

    # Два счётчика денег, и это не дублирование. Первый — сколько стоил этот
    # запуск, второй — сколько стоил весь разговор с самого начала. Второй считает
    # база: счётчик в процессе обнулялся бы при каждом перезапуске и врал бы
    # правдоподобно, а такая ошибка не бросается в глаза.
    run_cost = 0.0
    warned_about_length = warn_if_long(agent, False)
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
            print("  история очищена, база тоже\n")
            continue
        if question == "/history":
            show_history(agent)
            print()
            continue
        if question == "/config":
            show_config(agent)
            print()
            continue
        if question == "/store":
            show_store(store)
            print()
            continue
        if question.startswith("/"):
            print(HELP + "\n")
            continue

        reply = agent.ask(question)
        # Три разных «ничего» на экране выглядят по-разному, иначе человек не
        # поймёт, что делать: поднять потолок, повторить вопрос или чинить сеть.
        if reply.empty and reply.truncated:
            print("\nагент промолчал: потолок токенов ушёл на рассуждения.")
            print(f"попробуй --max-tokens больше {agent.config.max_tokens}\n")
        elif reply.empty:
            print("\nагент промолчал сам, без обрыва. переспроси иначе\n")
        elif reply.ok:
            print(f"\nагент: {reply.text}\n")
        else:
            print("\nагент не ответил\n")
        if not reply.saved:
            # Ответ есть, но в базу не лёг. Сказать надо сейчас: разговор идёт
            # дальше как ни в чём не бывало, и обнаружить потерю иначе можно
            # только при следующем запуске, когда восстанавливать уже нечего.
            print("  ВНИМАНИЕ: этот ход не записан в базу и не переживёт выход")
        # Строка дебага печатается всегда, в том числе при сбое: при неизменном
        # интерфейсе это единственное видимое доказательство, что работает коробка,
        # а не один вызов API.
        print(f"  {reply.debug_line()}")
        if reply.cost is not None:
            run_cost += reply.cost
            print(f"  за этот запуск: ${run_cost:.6f}\n")
        else:
            print()
        warned_about_length = warn_if_long(agent, warned_about_length)

    total = store.stats()["cost"]
    print(f"ходов в сессии {args.session!r}: {agent.turns}")
    if total is not None:
        print(f"за весь разговор: ${total:.6f}  (за этот запуск ${run_cost:.6f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
