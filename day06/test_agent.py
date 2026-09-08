"""День 6: офлайн-проверки агента. Сети не требуют, кредитов не тратят.

Главная проверка здесь — `test_agents_are_isolated`: она и есть тот самый вопрос
«сможешь ли ты заспавнить сто агентов с разными конфигами в одном процессе».
Если состояние утечёт в модуль, упадёт именно она.

Запуск:
    uv run day06/test_agent.py
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig, Reply  # noqa: E402
from models import MODELS, cost, price_of, sampling_args  # noqa: E402


class FakeClient:
    """Подставной клиент: запоминает, что ему прислали, и отвечает заготовкой.

    Именно ради него у Agent есть поле client. Без точки подмены проверить сборку
    запроса можно было бы только живым вызовом, то есть за деньги и с сетью.
    """

    def __init__(self, answer: str = "ответ", usage: object | None = None):
        self.answer = answer
        self.usage = (
            usage
            if usage is not None
            else SimpleNamespace(prompt_tokens=100, completion_tokens=20, cost=0.0001)
        )
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.answer), finish_reason="stop"
                )
            ],
            usage=self.usage,
            provider="deepinfra",
        )


def test_agents_are_isolated() -> list[str]:
    """Два агента в одном процессе не видят переписку друг друга."""
    problems = []
    left = Agent(config=AgentConfig(model="gpt-oss-20b"), client=FakeClient("слева"))
    right = Agent(
        config=AgentConfig(model="deepseek-v4-flash", temperature=0.9),
        client=FakeClient("справа"),
    )

    left.ask("меня зовут Роман")
    left.ask("как меня зовут")
    right.ask("привет")

    if left.turns != 2:
        problems.append(f"у левого агента {left.turns} ходов вместо 2")
    if right.turns != 1:
        problems.append(f"у правого агента {right.turns} ходов вместо 1")

    right_texts = [message["content"] for message in right.history]
    if any("Роман" in text for text in right_texts):
        problems.append("история левого агента протекла в правого")

    # Конфиги тоже раздельные: у правого своя температура и своя модель.
    if left.config.temperature is not None:
        problems.append("температура левого агента изменилась вместе с правым")
    if left.config.model == right.config.model:
        problems.append("модели агентов совпали, конфиг общий")
    return problems


def test_hundred_agents() -> list[str]:
    """Буквальная проверка критерия: сто агентов в одном процессе, у каждого своё."""
    problems = []
    keys = list(MODELS)
    agents = [
        Agent(
            config=AgentConfig(model=keys[index % len(keys)], max_tokens=index + 1),
            name=f"агент-{index}",
            client=FakeClient(f"ответ-{index}"),
        )
        for index in range(100)
    ]
    for index, agent in enumerate(agents):
        agent.ask(f"вопрос-{index}")

    if len({agent.name for agent in agents}) != 100:
        problems.append("имена агентов не уникальны")
    for index, agent in enumerate(agents):
        if agent.turns != 1:
            problems.append(f"у агента {index} накопилось {agent.turns} ходов")
            break
        if agent.history[-1]["content"] != f"ответ-{index}":
            problems.append(f"агент {index} получил чужой ответ")
            break
        if agent.config.max_tokens != index + 1:
            problems.append(f"конфиг агента {index} затёрт")
            break
    return problems


def test_system_prompt_is_first_and_single() -> list[str]:
    """Системный промпт стоит первым и ровно один раз, сколько бы ходов ни было."""
    problems = []
    client = FakeClient()
    agent = Agent(config=AgentConfig(system_prompt="ты бухгалтер"), client=client)
    agent.ask("первый")
    agent.ask("второй")
    agent.ask("третий")

    sent = client.calls[-1]["messages"]
    if sent[0] != {"role": "system", "content": "ты бухгалтер"}:
        problems.append("системный промпт не первый в стеке")
    if sum(1 for message in sent if message["role"] == "system") != 1:
        problems.append("системных промптов в стеке больше одного")
    if sent[-1] != {"role": "user", "content": "третий"}:
        problems.append("новый вопрос не последний в стеке")
    # 1 системный + 2 завершённых хода по 2 сообщения + текущий вопрос.
    if len(sent) != 6:
        problems.append(f"в стеке {len(sent)} сообщений вместо 6")

    # Роль живёт в конфиге, а не в истории: после сброса она обязана остаться.
    agent.reset()
    agent.ask("после сброса")
    if client.calls[-1]["messages"][0]["role"] != "system":
        problems.append("после reset() агент потерял системный промпт")
    if len(client.calls[-1]["messages"]) != 2:
        problems.append("reset() не очистил историю")
    return problems


def test_history_is_not_shared_by_reference() -> list[str]:
    """Свойство history отдаёт копию: снаружи историю не переписать молча."""
    problems = []
    agent = Agent(client=FakeClient())
    agent.ask("вопрос")
    snapshot = agent.history
    snapshot.append({"role": "user", "content": "подделка"})
    snapshot[0]["content"] = "подмена"
    if agent.turns != 1:
        problems.append("в историю агента дописали снаружи")
    if agent.history[0]["content"] != "вопрос":
        problems.append("сообщение в истории подменили снаружи")
    return problems


def test_failed_call_leaves_history_clean() -> list[str]:
    """Сбой не оставляет в стеке вопрос без ответа."""
    problems = []

    class BrokenClient(FakeClient):
        def _create(self, **kwargs):
            raise RuntimeError("сеть недоступна")

    agent = Agent(client=BrokenClient())
    reply = agent.ask("вопрос в пустоту")
    if reply.ok:
        problems.append("сбой вернулся как удачный ответ")
    if reply.text:
        problems.append("при сбое пришёл непустой текст")
    if agent.turns != 0:
        problems.append("неудачный вопрос попал в историю")
    if "сеть недоступна" not in (reply.error or ""):
        problems.append("причина сбоя потерялась по дороге")
    return problems


def test_missing_usage_gives_none_not_zero() -> list[str]:
    """Нет usage — цена None. Ноль соврал бы, что вызов был бесплатным."""
    problems = []
    agent = Agent(client=FakeClient(usage=False))  # usage=False → ответ без usage
    reply = agent.ask("вопрос")
    if reply.cost is not None:
        problems.append(f"цена без usage равна {reply.cost!r} вместо None")
    if reply.prompt_tokens is not None:
        problems.append("токены без usage не None")
    if cost(None, 20, "kimi-k3") is not None or cost(100, None, "kimi-k3") is not None:
        problems.append("cost() вернул число при отсутствующих токенах")
    return problems


def test_temperature_is_omitted_when_none() -> list[str]:
    """Не передали температуру — параметра в теле запроса нет вовсе."""
    problems = []
    client = FakeClient()
    Agent(config=AgentConfig(temperature=None), client=client).ask("вопрос")
    if "temperature" in client.calls[-1]:
        problems.append("температура ушла в запрос, хотя её не задавали")

    client = FakeClient()
    Agent(config=AgentConfig(temperature=0), client=client).ask("вопрос")
    if client.calls[-1].get("temperature") != 0:
        problems.append("температура 0 не дошла до запроса")
    if sampling_args(None) != {} or sampling_args(0) != {"temperature": 0}:
        problems.append("sampling_args() путает «не задано» и ноль")
    return problems


def test_config_rejects_nonsense() -> list[str]:
    """Опечатка в конфиге падает при создании агента, а не на сетевом вызове."""
    problems = []
    for changes in (
        {"model": "gpt-5-turbo-ultra"},
        {"temperature": 3},
        {"max_tokens": 0},
    ):
        try:
            AgentConfig(**changes)
        except ValueError:
            continue
        problems.append(f"конфиг принял мусор: {changes}")
    return problems


def test_reply_reports_truncation() -> list[str]:
    """Обрыв по лимиту виден снаружи и попадает в строку дебага."""
    problems = []
    reply = Reply(
        text="начал и не", model="kimi-k3", elapsed=1.0, finish_reason="length"
    )
    if not reply.truncated:
        problems.append("обрыв по лимиту не распознан")
    if "ОБРЕЗАН" not in reply.debug_line():
        problems.append("строка дебага молчит об обрыве")
    if not Reply(text="", model="kimi-k3", elapsed=0.1, error="сбой").debug_line():
        problems.append("строка дебага пуста при ошибке")
    return problems


def test_price_matches_catalog() -> list[str]:
    """Арифметика цены — та же, что в дне 5, каталог не разъехался."""
    problems = []
    expected = 1_000_000 / 1_000_000 * MODELS["kimi-k3"]["price_in"] + (
        1_000_000 / 1_000_000 * MODELS["kimi-k3"]["price_out"]
    )
    if abs(price_of(1_000_000, 1_000_000, "kimi-k3") - expected) > 1e-12:
        problems.append("price_of() разошёлся с прайсом каталога")
    if price_of(0, 0, "kimi-k3") != 0:
        problems.append("нулевой расход стоит денег")
    return problems


TESTS = (
    test_agents_are_isolated,
    test_hundred_agents,
    test_system_prompt_is_first_and_single,
    test_history_is_not_shared_by_reference,
    test_failed_call_leaves_history_clean,
    test_missing_usage_gives_none_not_zero,
    test_temperature_is_omitted_when_none,
    test_config_rejects_nonsense,
    test_reply_reports_truncation,
    test_price_matches_catalog,
)


def main() -> int:
    failed = 0
    for test in TESTS:
        problems = test()
        if problems:
            failed += 1
            print(f"FAIL {test.__name__}")
            for problem in problems:
                print(f"     {problem}")
        else:
            print(f"ok   {test.__name__}")
    print(f"\n{len(TESTS) - failed} из {len(TESTS)} проверок прошли")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
