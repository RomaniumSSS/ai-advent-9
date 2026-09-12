"""День 10: один и тот же сценарий на каждой стратегии, с учётом расхода.

Сравнение честно ровно настолько, насколько одинаков вход: вопросы берутся из
`scenarios.py` списком и не зависят от того, что ответила модель. Ответы при этом
расходятся, а с ними расходится и история — поэтому числа сравнивают три реальных
разговора, а не эффект обрезки одного и того же текста. Это оговорка, а не изъян:
другого способа сравнить стратегии на живой модели нет.

Прогон без сети:   uv run day10/run_strategies.py --dry-run
Живой прогон:      uv run day10/run_strategies.py --env-file .env --all
"""

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig, DEFAULT_SYSTEM_PROMPT, StrategyConfig  # noqa: E402
from branches import branch_list, checkpoint, fork, switch  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402
from store import SqliteStore  # noqa: E402
from strategies import STRATEGIES, STRATEGY_LABELS  # noqa: E402

RESULTS = Path(__file__).parent / "results"

# Ходы, на которых сценарий сам просит агента назвать факты. По ним и видно,
# что стратегия потеряла: остальные ответы — обычная беседа, и проверять в них
# память не на чем.
CONTROL_TURNS = (9, 14, 16)

# Вопросы веток. Разные намеренно: две ветки с одинаковым продолжением показали
# бы только то, что модель недетерминирована, а не то, что ветки независимы.
BRANCH_QUESTIONS = {
    "a": [
        "Идём по варианту с ручным подтверждением. Опиши, что должен видеть администратор.",
        "Что в этом варианте сломается при двадцати заявках в день?",
    ],
    "b": [
        "Идём по варианту с автоматическим подтверждением. Опиши, что изменится в состояниях заявки.",
        "Что в этом варианте сломается при двадцати заявках в день?",
    ],
}


class OfflineClient:
    """Подставная модель для `--dry-run`: ни сети, ни денег.

    Отвечает заглушкой, а на служебный вызов памяти — правдоподобным JSON.
    Нужна затем, чтобы проверить сам прогон: порядок ходов, запись результатов,
    ветвление. Чем именно ответила модель, здесь не важно.
    """

    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls += 1
        is_facts = kwargs["messages"][0]["content"].startswith("Ты — модуль памяти")
        text = (
            '{"проект": "Маяк", "бюджет": "1200 евро", "срок": "25 октября"}'
            if is_facts
            else f"Ответ без сети №{self.calls}."
        )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=text), finish_reason="stop"
                )
            ],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, cost=0.0),
            provider="offline",
            id=f"offline-{self.calls}",
        )


def make_agent(db_path, session, strategy, recent, client):
    return Agent(
        config=AgentConfig(
            model="deepseek-v4-flash", system_prompt=DEFAULT_SYSTEM_PROMPT
        ),
        name=STRATEGY_LABELS[strategy],
        strategy=StrategyConfig(name=strategy, recent_messages=recent),
        store=SqliteStore(db_path, session),
        client=client,
    )


# Временные беды провайдера: их лечит пауза, а не изменение запроса. Провайдер
# закреплён и fallback выключен намеренно (иначе поехало бы сравнение), так что
# при 429 из общего пула остаётся только подождать. Повторы считаются отдельно:
# ход, удавшийся с третьей попытки, — не то же самое, что удавшийся сразу.
TRANSIENT_CODES = ("429", "502", "503", "504")
RETRY_PAUSE_SECONDS = 20
MAX_RETRIES = 3


def is_transient(error: str | None) -> bool:
    return bool(error) and any(code in error for code in TRANSIENT_CODES)


def run_turn(agent, question, turn, retries_log=None):
    """Один ход с замерами. Бросает, если ход не состоялся.

    Продолжать прогон после неудачного хода нельзя: у стратегий разъедется
    число сообщений, и сравнение перестанет быть сравнением.
    """
    estimate = agent.budget(question)
    sent = len(agent.context_history())
    started = time.monotonic()
    reply = agent.ask(question)
    attempt = 0
    while not reply.ok and is_transient(reply.error) and attempt < MAX_RETRIES:
        attempt += 1
        if retries_log is not None:
            retries_log.append({"turn": turn, "attempt": attempt, "error": reply.error})
        print(
            f"    ход {turn}: временная ошибка провайдера, повтор {attempt} "
            f"через {RETRY_PAUSE_SECONDS} с"
        )
        time.sleep(RETRY_PAUSE_SECONDS)
        reply = agent.ask(question)
    if not reply.ok:
        raise RuntimeError(f"ход {turn} не состоялся: {reply.error}")
    if reply.empty:
        raise RuntimeError(f"ход {turn}: модель промолчала, прогон остановлен")
    if reply.store_error:
        raise RuntimeError(f"ход {turn}: ответ не сохранён — {reply.store_error}")
    return {
        "turn": turn,
        "question": question,
        "answer": reply.text,
        "elapsed": round(time.monotonic() - started, 2),
        "sent_messages": sent,
        "archived_messages": len(agent.history) - 2,
        "estimated_prompt": estimate.prompt,
        "prompt_tokens": reply.prompt_tokens,
        "completion_tokens": reply.completion_tokens,
        "cost_reported": reply.cost_reported,
        "facts_event": agent.facts_event,
        "facts": dict(agent.facts.values),
        "control": turn in CONTROL_TURNS,
    }


def run_scenario(
    db_path, strategy, recent, client, scenario="project", turns=16, label=None
):
    session = label or f"{scenario}-{strategy}"
    store_path = Path(db_path)
    SqliteStore(store_path, session).clear()
    agent = make_agent(store_path, session, strategy, recent, client)
    questions = SCENARIOS[scenario]["questions"][:turns]
    retries: list[dict] = []
    rows = [
        run_turn(agent, question, index + 1, retries)
        for index, question in enumerate(questions)
    ]
    usage = agent.store.usage_by_kind()
    return {
        "strategy": strategy,
        "strategy_label": STRATEGY_LABELS[strategy],
        "scenario": scenario,
        "session": session,
        "recent_messages": recent,
        "turns": len(rows),
        "usage": usage,
        "facts": dict(agent.facts.values),
        "history_messages": len(agent.history),
        # Повторы сохраняются рядом с результатом: без них прогон, дважды
        # упиравшийся в 429, выглядел бы таким же гладким, как прошедший сразу.
        "retries": retries,
        "rows": rows,
    }


def run_branching(db_path, strategy, recent, client, scenario="project", before=8):
    """Ветвление: общий разговор, затем две независимые ветки от одной точки."""
    session = f"{scenario}-branching"
    store_path = Path(db_path)
    for name in (session, f"{session}/a", f"{session}/b"):
        SqliteStore(store_path, name).clear()
    agent = make_agent(store_path, session, strategy, recent, client)

    questions = SCENARIOS[scenario]["questions"][:before]
    retries: list[dict] = []
    common = [
        run_turn(agent, question, index + 1, retries)
        for index, question in enumerate(questions)
    ]
    point = checkpoint(agent)
    for name in ("a", "b"):
        fork(agent, name, point)

    branches = {}
    for name, extra in BRANCH_QUESTIONS.items():
        switch(agent, f"{session}/{name}")
        branches[name] = {
            "session": agent.store.session,
            "inherited_messages": len(agent.history),
            "rows": [
                run_turn(agent, question, before + index + 1, retries)
                for index, question in enumerate(extra)
            ],
            "usage": agent.store.usage_by_kind(),
        }
    switch(agent, session)
    return {
        "strategy": strategy,
        "scenario": scenario,
        "checkpoint": point,
        "common_turns": len(common),
        "common": common,
        "branches": branches,
        "root_messages_after": len(agent.history),
        "retries": retries,
        "known_sessions": [row["session"] for row in branch_list(agent)],
        "usage_root": agent.store.usage_by_kind(),
    }


def save(name: str, payload) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--budget", type=float, default=0.50)
    parser.add_argument("--db", type=Path, default=RESULTS / "runs.db")
    parser.add_argument(
        "--strategy",
        action="append",
        choices=STRATEGIES,
        help="можно повторять; по умолчанию все три",
    )
    parser.add_argument("--turns", type=int, default=16)
    parser.add_argument("--recent", type=int, default=6)
    parser.add_argument("--scenario", default="project", choices=sorted(SCENARIOS))
    parser.add_argument("--branching", action="store_true", help="только прогон веток")
    parser.add_argument("--all", action="store_true", help="три стратегии и ветвление")
    parser.add_argument("--dry-run", action="store_true", help="без сети и без денег")
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        client = OfflineClient()
    else:
        from dotenv import load_dotenv
        from experiment import BudgetLedger, MeasuredClient, real_client, DEFAULT_LEDGER

        load_dotenv(args.env_file) if args.env_file else load_dotenv()
        ledger = BudgetLedger(args.ledger or DEFAULT_LEDGER, args.budget)
        client = MeasuredClient(real_client(), ledger, "run")

    selected = args.strategy or list(STRATEGIES)
    if not args.branching:
        for strategy in selected:
            print(f"→ {STRATEGY_LABELS[strategy]}: {args.turns} ходов")
            result = run_scenario(
                args.db, strategy, args.recent, client, args.scenario, args.turns
            )
            path = save(f"{args.scenario}-{strategy}", result)
            usage = result["usage"]["total"]
            print(
                f"  токенов {usage['tokens']}, вызовов {usage['calls']} → {path.name}"
            )

    if args.branching or args.all:
        print("→ ветвление: 8 общих ходов, затем две ветки по два")
        result = run_branching(args.db, "full", args.recent, client, args.scenario)
        path = save(f"{args.scenario}-branching", result)
        print(f"  ветки {', '.join(result['branches'])} → {path.name}")

    if args.dry_run:
        print(
            f"\nбез сети: {client.calls} вызовов подставной модели, денег не потрачено"
        )


if __name__ == "__main__":
    main()
