"""Офлайн-проверки агента со стратегиями. Подставной клиент, сети нет."""

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig, StrategyConfig  # noqa: E402
from store import SqliteStore  # noqa: E402

failures = []


def check(condition, message):
    if condition:
        print(f"ok  {message}")
    else:
        failures.append(message)
        print(f"FAIL {message}")


class FakeClient:
    """Записывает каждый запрос и отдаёт заранее заданные ответы по очереди.

    Ответы кончились — отдаётся последний. Так тесту не нужно угадывать точное
    число служебных вызовов, чтобы проверить содержание первого.
    """

    def __init__(self, replies=("ответ модели",)):
        self.replies = list(replies)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        index = min(len(self.requests) - 1, len(self.replies) - 1)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.replies[index]),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, cost=0.000001),
            provider="fake",
            id="fake-1",
        )

    @property
    def calls(self):
        return len(self.requests)

    def sent(self, index=-1):
        return self.requests[index]["messages"]


def make_agent(client, strategy, store=None):
    return Agent(
        config=AgentConfig(model="deepseek-v4-flash"),
        client=client,
        strategy=strategy,
        store=store,
    )


def test_full_sends_whole_history():
    client = FakeClient()
    agent = make_agent(client, StrategyConfig("full"))
    for index in range(3):
        agent.ask(f"вопрос {index}")
    check(len(client.sent()) == 1 + 4 + 1, "full шлёт роль, всю историю и вопрос")


def test_sliding_sends_only_tail():
    client = FakeClient()
    agent = make_agent(client, StrategyConfig("sliding", recent_messages=2))
    for index in range(4):
        agent.ask(f"вопрос {index}")
    check(len(client.sent()) == 1 + 2 + 1, "sliding шлёт роль, хвост и вопрос")
    check(agent.turns == 4, "архив агента при этом полный")


def test_facts_makes_extra_call_and_remembers():
    client = FakeClient(["ответ модели", '{"цель": "сайт записи"}'])
    agent = make_agent(client, StrategyConfig("facts"))
    agent.ask("Планируем сайт записи")
    check(client.calls == 2, "стратегия facts делает второй, служебный вызов")
    check(agent.facts.values == {"цель": "сайт записи"}, "факт извлечён и сохранён")
    check(
        agent.facts_event["applied"] is True, "событие говорит, что память обновилась"
    )


def test_facts_block_reaches_next_request():
    client = FakeClient(["ответ модели", '{"цель": "сайт записи"}'])
    agent = make_agent(client, StrategyConfig("facts"))
    agent.ask("Планируем сайт записи")
    agent.ask("Что дальше?")
    block = client.requests[2]["messages"][1]["content"]
    check("цель: сайт записи" in block, "на следующем ходу факты уехали в запрос")


def test_broken_facts_json_keeps_memory_and_reports():
    client = FakeClient(["ответ модели", "извините, не понял"])
    agent = make_agent(client, StrategyConfig("facts"))
    agent.ask("вопрос")
    check(agent.facts.values == {}, "битый служебный ответ не портит память")
    check(bool(agent.facts_event["error"]), "причина названа, а не проглочена")


def test_unknown_fact_keys_ignored():
    client = FakeClient(["ответ модели", '{"погода": "дождь"}'])
    agent = make_agent(client, StrategyConfig("facts"))
    agent.ask("вопрос")
    check(agent.facts.values == {}, "ключ вне списка в память не попадает")


def test_facts_call_does_not_break_the_answer():
    client = FakeClient(["настоящий ответ", ""])
    agent = make_agent(client, StrategyConfig("facts"))
    reply = agent.ask("вопрос")
    check(reply.text == "настоящий ответ", "пустой служебный ответ не портит ход")
    check(agent.turns == 1, "ход засчитан")


def test_sliding_makes_no_extra_call():
    client = FakeClient()
    agent = make_agent(client, StrategyConfig("sliding"))
    agent.ask("вопрос")
    check(client.calls == 1, "sliding обходится одним вызовом на ход")


def test_switch_strategy_keeps_history_and_facts():
    client = FakeClient(["ответ модели", '{"цель": "сайт"}'])
    agent = make_agent(client, StrategyConfig("facts"))
    agent.ask("вопрос")
    agent.switch_strategy("sliding")
    check(agent.turns == 1, "переключение не трогает историю")
    check(agent.facts.values == {"цель": "сайт"}, "переключение не трогает память")
    check(agent.strategy.name == "sliding", "стратегия сменилась")


def test_switch_to_unknown_strategy_refused():
    agent = make_agent(FakeClient(), StrategyConfig("full"))
    try:
        agent.switch_strategy("magic")
    except ValueError:
        check(True, "переключение на несуществующую стратегию отвергается")
        return
    check(False, "переключение на несуществующую стратегию отвергается")


def test_budget_counts_sent_history_not_archive():
    client = FakeClient()
    agent = make_agent(client, StrategyConfig("sliding", recent_messages=2))
    for index in range(4):
        agent.ask(f"вопрос номер {index} с некоторым текстом")
    short = agent.budget("следующий вопрос").history
    agent.switch_strategy("full")
    full = agent.budget("следующий вопрос").history
    check(short < full, "у sliding в бюджете только отправляемая часть истории")


def test_facts_survive_restart():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "history.db"
        client = FakeClient(["ответ модели", '{"цель": "сайт"}'])
        first = make_agent(client, StrategyConfig("facts"), SqliteStore(path, "main"))
        first.ask("вопрос")
        second = make_agent(
            FakeClient(), StrategyConfig("facts"), SqliteStore(path, "main")
        )
        check(second.facts.values == {"цель": "сайт"}, "память поднялась с диска")


def test_facts_call_logged_separately():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "history.db"
        client = FakeClient(["ответ модели", '{"цель": "сайт"}'])
        agent = make_agent(client, StrategyConfig("facts"), SqliteStore(path, "main"))
        agent.ask("вопрос")
        usage = agent.store.usage_by_kind()
        check(
            usage["chat"]["calls"] == 1 and usage["facts"]["calls"] == 1,
            "служебный вызов виден в журнале отдельной строкой",
        )


def test_reset_clears_facts():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "history.db"
        client = FakeClient(["ответ модели", '{"цель": "сайт"}'])
        agent = make_agent(client, StrategyConfig("facts"), SqliteStore(path, "main"))
        agent.ask("вопрос")
        agent.reset()
        check(agent.facts.values == {}, "сброс уносит память в процессе")
        check(agent.store.load_facts() == {}, "сброс уносит память и в базе")


def main():
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    if failures:
        print(f"\nПРОВАЛЕНО {len(failures)}:")
        for item in failures:
            print(f"  - {item}")
        raise SystemExit(1)
    print("\nвсе проверки прошли")


if __name__ == "__main__":
    main()
