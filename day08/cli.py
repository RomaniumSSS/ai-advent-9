"""День 8: чат с агентом в терминале, который считает токены вслух.

Файл намеренно тонкий, как и в дне 7. Здесь только ввод-вывод: ни сборки запроса,
ни счёта токенов, ни записи в базу. Терминал не знает ни что хранилище — SQLite,
ни что счётчик — tiktoken; он показывает то, что ему отдали.

Проверка задания дня 8 делается руками так:

    uv run day08/cli.py --session коротко --context-limit 6000
    /tokens                                # вес запроса ДО отправки
    ... несколько ходов ...
    /growth                                # как рос вход и деньги
    uv run day08/cli.py --session коротко --context-limit 3000
    ... пара ходов ...                     # упереться в окно и получить отказ

Запуск:
    uv run day08/cli.py
    uv run day08/cli.py --session работа --model kimi-k3
    uv run day08/cli.py --context-limit 4096   # искусственно тесное окно
    uv run day08/cli.py --sessions          # что вообще лежит в базе
    uv run day08/cli.py --forget            # начать сессию с нуля
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
  /tokens   из чего состоит следующий запрос и во что он упрётся
  /growth   как рос вход и деньги ход за ходом
  /exit     выход (или Ctrl+D)"""


def show_tokens(agent: Agent) -> None:
    """Вес следующего запроса ДО того, как он отправлен.

    Считается на пустой вопрос: интересна не цена конкретной фразы, а то, во
    что обходится сам факт продолжения разговора. Вопрос добавит десятки токенов,
    история — тысячи, и именно это соотношение человек должен увидеть до того,
    как удивится счёту.
    """
    budget = agent.budget("")
    print(f"  роль:        {budget.system}")
    print(f"  история:     {budget.history}  ({budget.history_share:.0%} входа)")
    print(f"  разметка:    {budget.overhead}  ({len(agent.history)} сообщений)")
    print(f"  вход всего:  {budget.prompt}")
    print(f"  на ответ:    {budget.reserved}  (max_tokens)")
    if budget.limit is None:
        print("  окно:        не задано, проверки нет (--context-limit)")
    else:
        print(f"  окно:        {budget.limit}, занято {budget.total}")
        print(f"  свободно:    {budget.free}")


def show_growth(store: SqliteStore) -> None:
    """Таблица, ради которой день 8 и затевался.

    Накопительный столбец обязателен: поход за походом числа выглядят мелкими и
    почти одинаковыми, и рост виден только в сумме. Оплачивается при этом каждый
    ход целиком — вся история заново, — так что складывать надо именно входы.
    """
    rows = store.growth()
    if not rows:
        print("  ходов с замерами пока нет")
        return
    print("   ход    вход  ответ      цена       вход всего     деньги всего")
    total_prompt = 0
    total_cost = 0.0
    for number, row in enumerate(rows, start=1):
        prompt = row["prompt_tokens"] or 0
        completion = row["completion_tokens"] or 0
        total_prompt += prompt
        total_cost += row["cost"] or 0.0
        print(
            f"  {number:>4}  {prompt:>6}  {completion:>5}  "
            f"{(row['cost'] or 0.0):>9.6f}  {total_prompt:>15}  {total_cost:>15.6f}"
        )


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
    limit = "не задано" if config.context_limit is None else config.context_limit
    print(f"  окно:        {limit}")
    print(f"  ходов:       {agent.turns}")
    print(f"  роль:        {config.system_prompt}")


def show_store(store: SqliteStore) -> None:
    stats = store.stats()
    spent = "неизвестно" if stats["cost"] is None else f"${stats['cost']:.6f}"
    print(f"  файл:        {store.path}")
    print(f"  сессия:      {stats['session']}")
    print(f"  ходов:       {stats['turns']}  (сообщений {stats['messages']})")
    print(
        f"  токенов:     вход {stats['prompt_tokens'] or 0}, "
        f"ответы {stats['completion_tokens'] or 0}"
    )
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
    parser = argparse.ArgumentParser(description="чат с агентом дня 8")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(MODELS))
    parser.add_argument("--system", default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument(
        "--context-limit",
        type=int,
        default=None,
        help="окно модели в токенах: вход и ответ вместе. "
        "Без него проверки нет — настоящие окна каталога не сверены",
    )
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
            context_limit=args.context_limit,
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
    run_prompt_tokens = 0
    run_completion_tokens = 0
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
        if question == "/tokens":
            show_tokens(agent)
            print()
            continue
        if question == "/growth":
            show_growth(store)
            print()
            continue
        if question.startswith("/"):
            print(HELP + "\n")
            continue

        reply = agent.ask(question)
        # Четыре разных «ничего» на экране выглядят по-разному, иначе человек не
        # поймёт, что делать: поднять потолок, повторить вопрос, чинить сеть или
        # расставаться с историей. Переполнение стоит первым: это единственный
        # случай, когда вызова не было вовсе и деньги не потрачены.
        if reply.overflow:
            print("\nвопрос не отправлен: разговор больше не влезает в окно.")
            print(f"  {reply.budget.line()}")
            print(
                "  что делать: --session другое-имя (начать заново), "
                "/reset (забыть всё)\n  или поднять --context-limit, "
                "если окно у модели на самом деле больше\n"
            )
        elif reply.empty and reply.truncated:
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
        if reply.prompt_tokens:
            run_prompt_tokens += reply.prompt_tokens
        if reply.completion_tokens:
            run_completion_tokens += reply.completion_tokens
        if reply.cost is not None:
            run_cost += reply.cost
            # Токены рядом с деньгами, а не вместо: деньги за ход почти не растут
            # и на глаз выглядят постоянными, а вход растёт заметно. Именно вход
            # и упрётся в окно — раньше, чем счёт станет страшным.
            print(
                f"  за этот запуск: ${run_cost:.6f}  "
                f"вход {run_prompt_tokens}, ответы {run_completion_tokens}\n"
            )
        else:
            print()
        warned_about_length = warn_if_long(agent, warned_about_length)

    stats = store.stats()
    print(f"ходов в сессии {args.session!r}: {agent.turns}")
    print(
        f"токенов за весь разговор: вход {stats['prompt_tokens'] or 0}, "
        f"ответы {stats['completion_tokens'] or 0}"
    )
    if stats["cost"] is not None:
        print(
            f"за весь разговор: ${stats['cost']:.6f}  (за этот запуск ${run_cost:.6f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
