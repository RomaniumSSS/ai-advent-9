"""День 7: офлайн-проверки агента и хранилища. Сети не требуют, кредитов не тратят.

Проверки дня 6 остались целиком — они и есть страховка от того, что память
на диске незаметно сломает изоляцию агентов. Добавлены проверки дня 7, главная
из них `test_history_survives_restart`: первый агент выбрасывается целиком,
второй поднимается с нуля и обязан продолжить разговор.

Настоящий перезапуск процесса тесты не изображают и не пытаются: они убивают
объект, а не интерпретатор. Разницу закрывает ручная проверка из README —
два запуска `cli.py` подряд.

База каждый раз новая, во временном каталоге: тест, который пишет в рабочий файл,
однажды сотрёт живой разговор.

Запуск:
    uv run day07/test_agent.py
"""

import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig, Reply  # noqa: E402
from models import MODELS, cost, price_of, sampling_args  # noqa: E402
from store import SqliteStore  # noqa: E402


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


# ---------------------------------------------------------------- день 7


class TempStore:
    """Хранилище в одноразовом каталоге. Каталог живёт, пока живёт объект.

    Не `:memory:`: база в памяти умирает вместе с соединением, а соединение здесь
    открывается на каждую операцию — то есть проверять было бы нечего. Нужен файл,
    потому что весь смысл дня 7 в том, что данные переживают процесс.
    """

    def __init__(self, session: str = "тест"):
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name) / "history.db"
        self.session = session

    def open(self, session: str | None = None) -> SqliteStore:
        """Новое хранилище на тот же файл — то же, что новый запуск программы."""
        return SqliteStore(self.path, session or self.session)


def test_empty_answer_is_not_a_turn() -> list[str]:
    """Пустой ответ не попадает ни в память, ни в базу — и говорит, почему пуст.

    Дефект, найденный глазами в дне 6 и в базе дня 7: потолок токенов уходит
    в скрытые рассуждения, текста не остаётся, а ход засчитывается как обычный.
    Пустая реплика ассистента после этого уезжает в модель на каждом ходу.
    """
    problems = []
    temp = TempStore()

    class SilentClient(FakeClient):
        """Отвечает пустотой, упёршись в потолок, — как настоящий провайдер."""

        def _create(self, **kwargs):
            response = super()._create(**kwargs)
            response.choices[0].message.content = ""
            response.choices[0].finish_reason = "length"
            return response

    agent = Agent(client=SilentClient(), store=temp.open())
    reply = agent.ask("вопрос в пустоту")

    if not reply.ok:
        problems.append("пустой ответ выдан за сбой вызова: деньги-то списаны")
    if not reply.empty:
        problems.append("агент не распознал пустой ответ")
    if agent.turns != 0:
        problems.append("пустой ход попал в память")
    if temp.open().load():
        problems.append("пустой ход попал в базу")
    if "ПУСТОЙ ОТВЕТ" not in reply.debug_line():
        problems.append("строка дебага молчит о пустом ответе")
    if "рассуждения" not in reply.debug_line():
        problems.append("причина пустоты (потолок) не названа")

    # Второй вид пустоты: модель закончила сама, но сказать ей было нечего.
    class MuteClient(FakeClient):
        def _create(self, **kwargs):
            response = super()._create(**kwargs)
            response.choices[0].message.content = "   "  # одни пробелы
            return response

    quiet = Agent(client=MuteClient(), store=temp.open("тихая"))
    mute = quiet.ask("вопрос")
    if not mute.empty:
        problems.append("ответ из одних пробелов сочтён содержательным")
    if mute.truncated:
        problems.append("добровольное молчание выдано за обрыв по лимиту")
    if "промолчала" not in mute.debug_line():
        problems.append("два вида пустоты описаны одинаково")
    if quiet.turns != 0:
        problems.append("ответ из пробелов попал в историю")

    # Непустой ответ по-прежнему обычный ход — правило не съело нормальный случай.
    normal = Agent(client=FakeClient("есть текст"), store=temp.open("обычная"))
    if normal.ask("вопрос").empty or normal.turns != 1:
        problems.append("обычный ответ перестал засчитываться")
    return problems


def test_store_failure_does_not_eat_the_answer() -> list[str]:
    """Сломанный диск не стоит пользователю уже оплаченного ответа."""
    problems = []

    class BrokenStore(SqliteStore):
        def append_turn(self, question, reply):
            raise RuntimeError("database is locked")

    temp = TempStore()
    agent = Agent(client=FakeClient("оплаченный ответ"), store=BrokenStore(temp.path))
    try:
        reply = agent.ask("вопрос")
    except Exception as error:  # noqa: BLE001 — тест на то, что этого не бывает
        return [f"ask() бросил {type(error).__name__} вместо того, чтобы вернуть Reply"]

    if not reply.ok:
        problems.append("сбой записи выдан за неудачный вызов модели")
    if reply.text != "оплаченный ответ":
        problems.append("текст оплаченного ответа потерялся")
    if reply.saved:
        problems.append("агент утверждает, что ход сохранён, хотя запись упала")
    if "database is locked" not in (reply.store_error or ""):
        problems.append("причина, по которой ход не записан, потерялась")
    if "НЕ СОХРАНЁН" not in reply.debug_line():
        problems.append("строка дебага молчит о том, что ход не записан")
    if agent.turns != 1:
        problems.append("разговор оборвался из-за сбоя записи")

    # Агент без хранилища не должен выглядеть так, будто у него что-то не сохранилось.
    if not Agent(client=FakeClient()).ask("вопрос").saved:
        problems.append("агент без хранилища отчитался о несохранённом ходе")
    return problems


def test_history_survives_restart() -> list[str]:
    """Главная проверка дня: агент выброшен, разговор продолжается."""
    problems = []
    temp = TempStore()

    first = Agent(client=FakeClient("помню"), store=temp.open())
    first.ask("меня зовут Роман")
    first.ask("я живу в Минске")
    del first  # объект первого агента больше не существует

    second = Agent(client=FakeClient("и правда помню"), store=temp.open())
    if second.turns != 2:
        problems.append(f"после перезапуска {second.turns} ходов вместо 2")
    if second.restored_turns != 2:
        problems.append("агент не сообщил, что история восстановлена")
    texts = [message["content"] for message in second.history]
    if "меня зовут Роман" not in texts or "я живу в Минске" not in texts:
        problems.append("вопросы прошлого запуска потерялись")
    if texts != ["меня зовут Роман", "помню", "я живу в Минске", "помню"]:
        problems.append(f"порядок реплик после восстановления сбился: {texts}")

    # Восстановленная история обязана уехать в модель, а не просто лежать в объекте:
    # иначе агент «помнит» только на экране.
    client = FakeClient()
    third = Agent(client=client, store=temp.open())
    third.ask("как меня зовут")
    sent = client.calls[-1]["messages"]
    if sent[0]["role"] != "system":
        problems.append("системный промпт перестал быть первым после восстановления")
    if len(sent) != 6:
        problems.append(f"в запрос уехало {len(sent)} сообщений вместо 6")
    if not any("Роман" in message["content"] for message in sent):
        problems.append("восстановленная история не дошла до запроса")
    return problems


def test_sessions_do_not_leak() -> list[str]:
    """Два разговора в одном файле не видят друг друга — и после перезапуска тоже."""
    problems = []
    temp = TempStore()

    Agent(client=FakeClient("слева"), store=temp.open("левая")).ask("меня зовут Роман")
    Agent(client=FakeClient("справа"), store=temp.open("правая")).ask("привет")

    right = Agent(client=FakeClient(), store=temp.open("правая"))
    if any("Роман" in message["content"] for message in right.history):
        problems.append("история левой сессии протекла в правую через базу")
    if right.turns != 1:
        problems.append(f"в правой сессии {right.turns} ходов вместо 1")

    names = {row["session"] for row in temp.open().sessions()}
    if names != {"левая", "правая"}:
        problems.append(f"в базе оказались сессии {names}")
    return problems


def test_failed_call_writes_nothing() -> list[str]:
    """Сбой не оставляет следа и на диске, не только в памяти."""
    problems = []
    temp = TempStore()

    class BrokenClient(FakeClient):
        def _create(self, **kwargs):
            raise RuntimeError("сеть недоступна")

    agent = Agent(client=BrokenClient(), store=temp.open())
    agent.ask("вопрос в пустоту")
    if agent.turns != 0:
        problems.append("неудачный ход попал в память")
    if temp.open().load():
        problems.append("неудачный ход попал в базу")
    if temp.open().stats()["turns"] != 0:
        problems.append("сводка считает неудачный ход")
    return problems


def test_reset_clears_disk_too() -> list[str]:
    """`/reset` забывает насовсем, а не до следующего запуска."""
    problems = []
    temp = TempStore()

    agent = Agent(client=FakeClient(), store=temp.open())
    agent.ask("это надо забыть")
    agent.reset()
    if agent.turns != 0:
        problems.append("reset() не очистил память")
    if temp.open().load():
        problems.append("reset() не очистил базу")

    revived = Agent(client=FakeClient(), store=temp.open())
    if revived.turns != 0:
        problems.append("забытый разговор воскрес после перезапуска")

    # Чистится только своя сессия. Одна база — много разговоров, и «забыть этот»
    # не должно означать «стереть все».
    Agent(client=FakeClient(), store=temp.open("соседняя")).ask("я цела")
    Agent(client=FakeClient(), store=temp.open()).reset()
    if temp.open("соседняя").stats()["turns"] != 1:
        problems.append("reset() снёс чужую сессию")
    return problems


def test_config_change_does_not_resurrect_history() -> list[str]:
    """Смена конфига обещает пустую историю — обещание переживает перезапуск."""
    problems = []
    temp = TempStore()

    agent = Agent(client=FakeClient(), store=temp.open())
    agent.ask("под старой ролью")
    fresh = agent.with_config(system_prompt="ты бухгалтер")
    if fresh.turns != 0:
        problems.append("новый конфиг унёс с собой старую историю")
    if fresh.restored_turns != 0:
        problems.append("новый агент поднял из базы историю прошлого конфига")
    if temp.open().load():
        problems.append("в базе осталась история, которой у агента уже нет")
    return problems


def test_order_survives_same_second() -> list[str]:
    """Сорок ходов в одну секунду не перемешиваются: порядок задаёт id, не время."""
    problems = []
    temp = TempStore()
    store = temp.open()
    agent = Agent(client=FakeClient("ответ"), store=store)
    for number in range(20):
        agent.ask(f"вопрос-{number}")

    loaded = temp.open().load()
    questions = [m["content"] for m in loaded if m["role"] == "user"]
    if questions != [f"вопрос-{number}" for number in range(20)]:
        problems.append("порядок вопросов в базе перепутался")
    if len(loaded) != 40:
        problems.append(f"в базе {len(loaded)} сообщений вместо 40")

    # В базе у каждого сообщения есть время, модель и цена, но наружу load()
    # обязан отдать только две графы: всё остальное уехало бы в модель и было бы
    # оплачено токенами как часть разговора.
    if any(set(message) != {"role", "content"} for message in loaded):
        problems.append("в запрос к модели уехали бы служебные поля")
    return problems


def test_money_is_counted_by_the_base() -> list[str]:
    """Расход считает база, поэтому он не обнуляется при перезапуске."""
    problems = []
    temp = TempStore()

    first = Agent(client=FakeClient(), store=temp.open())
    reply = first.ask("первый")
    first.ask("второй")
    del first

    stats = Agent(client=FakeClient(), store=temp.open()).store.stats()
    if stats["turns"] != 2:
        problems.append(f"база насчитала {stats['turns']} ходов вместо 2")
    if reply.cost is None or stats["cost"] is None:
        problems.append("цена хода не доехала до базы")
    elif abs(stats["cost"] - reply.cost * 2) > 1e-12:
        problems.append("сумма по базе разошлась с ценой ходов")
    if not stats["first_at"] or not stats["last_at"]:
        problems.append("в сводке нет времени первого и последнего хода")
    return problems


def test_restart_notices_changed_role() -> list[str]:
    """Разговор, продолженный под другой ролью, не выдаётся за прежний."""
    problems = []
    temp = TempStore()

    Agent(
        config=AgentConfig(system_prompt="ты бухгалтер"),
        client=FakeClient(),
        store=temp.open(),
    ).ask("вопрос")

    resumed = Agent(
        config=AgentConfig(system_prompt="ты поэт"),
        client=FakeClient(),
        store=temp.open(),
    )
    was = resumed.restored_config or {}
    if was.get("system_prompt") != "ты бухгалтер":
        problems.append("агент не помнит, под какой ролью писалась история")
    if resumed.config.system_prompt != "ты поэт":
        problems.append("восстановление подменило текущую роль")

    # Записанная роль обновляется на текущую: следующий запуск должен сравнивать
    # себя с последним состоянием, а не с самым первым.
    if temp.open().config_of_record()["system_prompt"] != "ты поэт":
        problems.append("в базе осталась устаревшая роль сессии")
    return problems


def test_schema_version_guard() -> list[str]:
    """База от более новой версии кода отвергается, а не читается наполовину."""
    problems = []
    temp = TempStore()
    temp.open().clear()  # файл заведён

    connection = sqlite3.connect(temp.path)
    connection.execute("PRAGMA user_version = 99")
    connection.commit()
    connection.close()

    try:
        temp.open()
    except RuntimeError:
        pass
    else:
        problems.append("база чужой версии открылась молча")

    try:
        SqliteStore(Path(temp.path).parent / "нет-каталога" / "h.db")
    except FileNotFoundError:
        pass
    else:
        problems.append("путь с несуществующим каталогом не вызвал ошибки")
    return problems


def test_agent_without_store_stays_a_day_six_agent() -> list[str]:
    """Без хранилища всё работает как в дне 6 и на диск не лезет."""
    problems = []
    agent = Agent(client=FakeClient())
    agent.ask("вопрос")
    if agent.store is not None:
        problems.append("агент без хранилища завёл его сам")
    if agent.restored_turns != 0 or agent.restored_config is not None:
        problems.append("агент без хранилища что-то восстановил")
    agent.reset()
    if agent.turns != 0:
        problems.append("reset() без хранилища упал или не сработал")
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
    test_empty_answer_is_not_a_turn,
    test_store_failure_does_not_eat_the_answer,
    test_history_survives_restart,
    test_sessions_do_not_leak,
    test_failed_call_writes_nothing,
    test_reset_clears_disk_too,
    test_config_change_does_not_resurrect_history,
    test_order_survives_same_second,
    test_money_is_counted_by_the_base,
    test_restart_notices_changed_role,
    test_schema_version_guard,
    test_agent_without_store_stays_a_day_six_agent,
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
