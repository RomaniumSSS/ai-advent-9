"""Офлайн-проверки ветвления. Подставной клиент, сети нет."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig, StrategyConfig  # noqa: E402
from branches import branch_list, checkpoint, fork, switch  # noqa: E402
from store import SqliteStore  # noqa: E402
from test_agent_strategies import FakeClient  # noqa: E402

failures = []


def check(condition, message):
    if condition:
        print(f"ok  {message}")
    else:
        failures.append(message)
        print(f"FAIL {message}")


def make_agent(directory, client=None, strategy=None, session="main"):
    return Agent(
        config=AgentConfig(model="deepseek-v4-flash"),
        client=client or FakeClient(),
        strategy=strategy or StrategyConfig("full"),
        store=SqliteStore(Path(directory) / "history.db", session),
    )


def test_branches_diverge():
    with tempfile.TemporaryDirectory() as directory:
        agent = make_agent(directory)
        agent.ask("общий вопрос")
        point = checkpoint(agent)
        fork(agent, "a", point)
        fork(agent, "b", point)

        switch(agent, "main/a")
        agent.ask("только в A")
        check(agent.turns == 2, "ветка A продолжила общий разговор")

        switch(agent, "main/b")
        contents = [message["content"] for message in agent.history]
        check("только в A" not in contents, "ветка B не видит ход ветки A")
        check(agent.turns == 1, "в ветке B остался только общий ход")

        switch(agent, "main")
        check(agent.turns == 1, "исходная сессия не изменилась")


def test_checkpoint_counts_saved_messages():
    with tempfile.TemporaryDirectory() as directory:
        agent = make_agent(directory)
        agent.ask("вопрос")
        check(checkpoint(agent) == 2, "точка ветвления считается в сообщениях")


def test_fork_copies_facts():
    with tempfile.TemporaryDirectory() as directory:
        client = FakeClient(["ответ модели", '{"цель": "сайт"}'])
        agent = make_agent(directory, client, StrategyConfig("facts"))
        agent.ask("Планируем сайт")
        fork(agent, "a")
        switch(agent, "main/a")
        check(agent.facts.values == {"цель": "сайт"}, "ветка унаследовала память")


def test_switch_rereads_facts_from_disk():
    with tempfile.TemporaryDirectory() as directory:
        agent = make_agent(directory)
        agent.store.save_facts({"цель": "сайт"})
        fork(agent, "a")
        SqliteStore(agent.store.path, "main/a").save_facts({"цель": "другое"})
        switch(agent, "main/a")
        check(
            agent.facts.values == {"цель": "другое"},
            "память ветки перечитана, а не перенесена из процесса",
        )


def test_branch_name_rules():
    with tempfile.TemporaryDirectory() as directory:
        agent = make_agent(directory)
        agent.ask("вопрос")
        for bad, why in ((" ", "пустое имя"), ("a/b", "имя с косой чертой")):
            try:
                fork(agent, bad)
            except ValueError:
                check(True, f"{why} отвергается")
            else:
                check(False, f"{why} отвергается")


def test_duplicate_branch_refused():
    with tempfile.TemporaryDirectory() as directory:
        agent = make_agent(directory)
        agent.ask("вопрос")
        fork(agent, "a")
        try:
            fork(agent, "a")
        except ValueError:
            check(True, "повторное имя ветки отвергается")
        else:
            check(False, "повторное имя ветки отвергается")


def test_fork_keeps_agent_in_place():
    with tempfile.TemporaryDirectory() as directory:
        agent = make_agent(directory)
        agent.ask("вопрос")
        fork(agent, "a")
        check(agent.store.session == "main", "создание ветки не переносит агента в неё")


def test_branch_list_marks_active():
    with tempfile.TemporaryDirectory() as directory:
        agent = make_agent(directory)
        agent.ask("вопрос")
        fork(agent, "a")
        switch(agent, "main/a")
        rows = {row["session"]: row["active"] for row in branch_list(agent)}
        check(rows == {"main": False, "main/a": True}, "активная ветка помечена")


def test_branching_requires_store():
    agent = Agent(config=AgentConfig(model="deepseek-v4-flash"), client=FakeClient())
    try:
        checkpoint(agent)
    except RuntimeError:
        check(True, "агент без базы не умеет ветвиться и говорит об этом")
        return
    check(False, "агент без базы не умеет ветвиться и говорит об этом")


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
