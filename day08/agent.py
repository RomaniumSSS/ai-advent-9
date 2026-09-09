"""День 8: агент дня 7 плюс счёт токенов до вызова и отказ вместо переполнения.

Коробка дня 7 с локальной оценкой запроса до отправки и журналом расхода.
Пустой ответ не добавляет сообщений, но его usage сохраняется отдельно.

Раньше учёт был только постфактум: `usage.prompt_tokens` приезжал вместе с
ответом, то есть сообщал цену уже потраченного. Одним числом на весь запрос.
День 8 добавляет второй счётчик — локальный, до вызова, разложенный на роль,
историю и новый вопрос (см. `tokens.py`), — и оба живут рядом, потому что
единственный способ узнать, что оценка врёт, это сверить её с фактом.

Снаружи у агента по-прежнему одна дверь: `ask(текст) -> Reply`. Появилась вторая,
только на чтение: `budget(текст) -> Budget` — что уедет, если спросить вот это.

Три решения дня 8, которые легко принять наоборот:

- **при переполнении окна вызов не делается вовсе.** Отправить заведомо не
  влезающий запрос значит дождаться отказа провайдера — то есть заплатить
  временем и получить чужую формулировку вместо своей. Отказ приходит локально,
  мгновенно и с разбором, что именно распухло;
- **`context_limit` по умолчанию `None`, то есть проверки нет.** Настоящие окна
  моделей каталога не сверены, а поставить туда правдоподобное число значило бы
  завести в коде факт, которого никто не проверял. Неизвестное окно называется
  неизвестным; ограничитель ставится руками флагом `--context-limit`;
- **потолок ответа входит в бюджет.** Окно общее на вход и выход, и запрос,
  который «влезает», но не оставляет места под ответ, всё равно получит отказ.

Три решения дня 7, которые легко принять наоборот:

- **историю грузит `__post_init__`, а не отдельный метод `resume()`.**
  Восстановление — не действие пользователя, а часть создания агента с памятью.
  Отдельный вызов можно забыть ровно один раз, и агент молча начнёт с чистого
  листа: ошибка, которая ничем себя не проявляет, кроме недоумения собеседника;
- **пишем после каждого удачного хода, а не при выходе.** Сохранение на выходе
  теряет весь разговор при Ctrl+C, обрыве терминала и падении — то есть ровно
  в тех случаях, ради которых память и заводят;
- **`reset()` чистит и базу тоже.** Иначе «забыл» означало бы «забыл до
  следующего запуска», и агент воскрешал бы стёртое.

Системный промпт в историю по-прежнему не кладётся: он подставляется при каждой
сборке запроса. Иначе после `reset()` агент терял бы роль, а при будущей обрезке
контекста роль вылетала бы первой — она же самая старая запись. В базе роль
лежит отдельной строкой в таблице `sessions`, см. `store.py`.

Запуск: этот модуль сам ничего не делает, см. `cli.py` и `web.py`.
"""

import os
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

sys.path.insert(0, str(Path(__file__).parent))

from models import (  # noqa: E402
    DEFAULT_MODEL,
    MAX_TOKENS,
    MODELS,
    PROVIDER,
    cost,
    sampling_args,
)
from tokens import Budget, count_messages, count_text, drift  # noqa: E402

load_dotenv()

# Та же граница, что в дне 5, и по той же причине: самый долгий зафиксированный
# ответ — 243.7 секунды у Kimi K3. Двойной запас нужен, чтобы таймаут не обрывал
# законные ответы, записывая это как ошибку модели.
REQUEST_TIMEOUT_SECONDS = 600.0

DEFAULT_SYSTEM_PROMPT = (
    "Ты — полезный собеседник. Отвечай по-русски, по существу и без воды. "
    "Если вопрос неполон, задай один уточняющий вопрос вместо догадки."
)

_client = None


def get_client() -> OpenAI:
    """Общий клиент процесса. Создаётся при первом вызове, а не при импорте.

    Иначе модуль нельзя было бы импортировать без ключа, и офлайн-тесты падали бы
    на строке импорта, ещё ничего не проверив.
    """
    global _client
    if _client is None:
        token = os.environ.get("OPENROUTER_API_KEY")
        if not token:
            raise RuntimeError("не задан OPENROUTER_API_KEY")
        _client = OpenAI(
            api_key=token,
            base_url="https://openrouter.ai/api/v1",
            timeout=REQUEST_TIMEOUT_SECONDS,
            # Один ход агента — один сетевой вызов. Повторы SDK смешали бы время
            # нескольких попыток в одном elapsed, никак себя не обозначив.
            max_retries=0,
        )
    return _client


@dataclass(frozen=True)
class AgentConfig:
    """Всё, чем один агент отличается от другого. Ничего из этого не глобально."""

    model: str = DEFAULT_MODEL
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    temperature: float | None = None
    max_tokens: int = MAX_TOKENS
    # Окно модели: вход и ответ вместе. None — окно неизвестно, и проверять
    # нечем. Число берётся не из каталога, а от человека, потому что в каталоге
    # его нет: см. шапку модуля про неcверенные окна.
    context_limit: int | None = None

    def __post_init__(self) -> None:
        # Падать здесь, а не на сетевом вызове: опечатка в имени модели иначе
        # обнаружится только после того, как пользователь напишет первое сообщение.
        if self.model not in MODELS:
            raise ValueError(f"неизвестная модель {self.model!r}")
        if self.max_tokens < 1:
            raise ValueError("max_tokens должен быть положительным")
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("температура вне диапазона 0..2")
        # Окно, в которое не влезает даже пустой запрос с потолком ответа, —
        # это не строгая настройка, а опечатка: агент отказал бы на первом же
        # вопросе, и причину пришлось бы искать в разговоре, а не в аргументах.
        if self.context_limit is not None:
            if self.context_limit < 1:
                raise ValueError("context_limit должен быть положительным")
            if self.context_limit <= self.max_tokens:
                raise ValueError(
                    f"окно {self.context_limit} не больше потолка ответа "
                    f"{self.max_tokens}: на вход не остаётся ничего"
                )

    @property
    def model_id(self) -> str:
        return MODELS[self.model]["id"]


@dataclass(frozen=True)
class Reply:
    """Что агент отдаёт наружу. Сырой ответ API за дверью не показывается.

    При сбое `error` заполнен, а `text` пуст — вызывающий код обязан различать
    «модель промолчала» и «до модели не дошло».

    `store_error` — третий, отдельный вид беды: ответ есть, он получен и оплачен,
    но на диск не лёг. Смешивать его с `error` нельзя ни в какую сторону. Назвать
    ход неудачным значило бы выбросить оплаченный текст; промолчать — соврать, что
    разговор сохранён, и обнаружилось бы это только после перезапуска, когда
    восстанавливать уже нечего.

    `budget` — что мы насчитали ПЕРЕД вызовом. Лежит в ответе, а не выбрасывается
    сразу после проверки, ровно затем, чтобы оценку было с чем сверить: рядом уже
    приехал фактический `prompt_tokens`, и разница между ними — единственное, что
    говорит, можно ли этому счётчику верить.

    `overflow` — четвёртый вид «ничего», и он единственный бесплатный. Вызова не
    было: запрос не влез в окно, и агент отказал сам. Смешивать с `error` нельзя —
    сетевой сбой лечится повтором, переполнение от повтора только растёт.
    """

    text: str
    model: str
    elapsed: float
    finish_reason: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost: float | None = None
    cost_reported: float | None = None
    served_by: str | None = None
    error: str | None = None
    store_error: str | None = None
    budget: Budget | None = None
    overflow: bool = False

    @property
    def ok(self) -> bool:
        """Ответ получен. Записался он или нет — отдельный вопрос, см. `saved`."""
        return self.error is None

    @property
    def saved(self) -> bool:
        """Ход дожил до диска. У агента без хранилища всегда True: там нечему
        было не сохраниться, и требовать от него False значило бы придумать беду."""
        return self.store_error is None

    @property
    def truncated(self) -> bool:
        """Ответ оборвался по потолку токенов, а не закончился сам."""
        return self.finish_reason == "length"

    @property
    def empty(self) -> bool:
        """Вызов удался и оплачен, а видимого текста нет.

        Третий вид беды, не сводимый к первым двум. `error` означает, что до
        модели не дошло; `store_error` — что не записалось. Здесь дошло, ответило
        и записалось бы — но говорить нечего. Чаще всего потолок токенов целиком
        съеден скрытыми рассуждениями: замерено в дне 6 на `max_tokens=100`,
        повторено в дне 7 на 60.
        """
        return self.ok and not self.text.strip()

    @property
    def drift(self) -> float | None:
        """Расхождение нашей оценки входа с фактом провайдера, в процентах.

        Плюс — переоценили, минус — недооценили. Недооценка опаснее: на ней
        проверка окна пропускает запрос, который в окно не влезет.
        """
        if self.budget is None:
            return None
        return drift(self.budget.prompt, self.prompt_tokens)

    def debug_line(self) -> str:
        """Одна строка для терминала и панели: доказательство, что коробка работает."""
        if self.overflow:
            # Времени нет и денег нет — печатать их было бы враньём про «0.0 с»
            # как про быстрый ответ. Здесь ответа не было вовсе.
            return f"[{self.model}] {self.error}"
        if self.error:
            return f"[{self.model}] ошибка за {self.elapsed:.1f} с: {self.error}"
        prompt = self.prompt_tokens if self.prompt_tokens is not None else '?'
        completion = self.completion_tokens if self.completion_tokens is not None else '?'
        tokens = f"{prompt}→{completion}"
        spent = f"по прайсу ${self.cost:.6f}" if self.cost is not None else "прайс неизвестен"
        if self.cost_reported is not None:
            spent += f", списано API ${self.cost_reported:.6f}"
        # Три «ничего» различаются словами, а не одним общим «пусто»: причина
        # решает, что делать дальше. Потолок — поднять `--max-tokens`; молчание
        # модели — переспросить иначе.
        if self.empty:
            why = (
                "весь потолок ушёл в рассуждения"
                if self.truncated
                else "модель промолчала"
            )
            tail = f"  ПУСТОЙ ОТВЕТ ({why}), ход не засчитан"
        elif self.truncated:
            tail = "  ОБРЕЗАН ПО ЛИМИТУ"
        else:
            tail = ""
        if self.store_error:
            tail += f"  НЕ СОХРАНЁН: {self.store_error}"
        # Оценка печатается рядом с фактом, а не вместо него, и всегда со знаком
        # расхождения. Счётчик, который показывают в одиночку, невозможно уличить.
        if self.budget is not None and self.drift is not None:
            tail += f"  оценка входа {self.budget.prompt} ({self.drift:+.1f}%)"
        return (
            f"[{self.model}] {self.elapsed:.1f} с  токены {tokens}  {spent}"
            f"  finish={self.finish_reason}{tail}"
        )


@dataclass
class Agent:
    """Коробка. Снаружи видно только `ask` и `history`.

    `client` — точка подмены для тестов: офлайн-проверки подставляют сюда объект
    с тем же методом и сети не касаются.

    `store` — память между запусками. `None` означает агента-однодневку: он
    работает как в дне 6 и после выхода забывает всё. Это не заглушка на время,
    а рабочий режим — панель поднимает по агенту на вкладку, и не каждому из них
    нужна папка на диске.
    """

    config: AgentConfig = field(default_factory=AgentConfig)
    name: str = "агент"
    client: object | None = None
    store: object | None = None
    _history: list[dict] = field(default_factory=list, repr=False)
    restored_turns: int = field(default=0, init=False)
    restored_config: dict | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Поднялся с хранилищем — сразу считал прошлый разговор.

        `restored_turns` запоминается отдельно, чтобы интерфейс мог сказать
        «продолжаю прошлый разговор» вместо того, чтобы молча показать чужие
        реплики: восстановленный контекст должен быть виден, а не подразумеваться.

        `restored_config` снимается ДО того, как в базу уйдёт текущий конфиг.
        Порядок здесь не косметика: сначала перезаписать, потом сравнить — значит
        всегда сравнивать значение с самим собой и никогда не заметить, что
        разговор продолжают под другой ролью или на другой модели.
        """
        if self.store is None:
            return
        self.restored_config = self.store.config_of_record()
        self._history = self.store.load()
        self.restored_turns = self.turns
        self.store.remember_config(self.config.model, self.config.system_prompt)

    @property
    def history(self) -> list[dict]:
        """Копия, а не сам список: снаружи историю правят только через методы."""
        return [dict(message) for message in self._history]

    @property
    def turns(self) -> int:
        return sum(1 for message in self._history if message["role"] == "user")

    def reset(self) -> None:
        """Забыть разговор. Роль остаётся, она в конфиге.

        Чистятся оба хранилища сразу — и список в памяти, и база. Порознь они
        разъезжаются: «очистил» в терминале и полный разговор после перезапуска.
        """
        self._history.clear()
        self.restored_turns = 0
        if self.store is not None:
            self.store.clear()

    def with_config(self, **changes) -> "Agent":
        """Новый агент с изменённым конфигом и ПУСТОЙ историей.

        Историю не переносим: она снята на другой роли и другой модели, и молча
        приписать её новому конфигу значило бы соврать в замерах.

        База при этом тоже чистится, и это сознательная плата. Оставить её — значит
        пообещать пустую историю и вернуть полную при следующем запуске: новый агент
        поднялся бы на том же хранилище и прочитал бы всё обратно. Из двух зол
        потеря переписки громче: она видна сразу, а не через день.
        """
        if self.store is not None:
            self.store.clear()
        return Agent(
            config=replace(self.config, **changes),
            name=self.name,
            store=self.store,
        )

    def build_messages(self, question: str) -> list[dict]:
        """Input policy: системный промпт, затем вся история, затем новый вопрос.

        Отдельный метод затем, чтобы порядок можно было проверить тестом без сети.
        Порядок не косметический: системный промпт стоит первым и ровно один раз,
        сколько бы ходов ни накопилось.
        """
        messages = []
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})
        messages.extend(self._history)
        messages.append({"role": "user", "content": question})
        return messages

    def budget(self, question: str) -> Budget:
        """Во что обойдётся этот вопрос, если его задать. Без сети и без трат.

        Считается ровно то, что соберёт `build_messages`, и разбирается на части
        по той же границе: роль, вся история, новый вопрос. Отдельный метод, а не
        расчёт внутри `ask`, затем, что спросить «сколько это будет стоить» нужно
        и не задавая вопроса — панель показывает вес истории до отправки.

        Накладные считаются вычитанием, а не сложением по формуле. Так `prompt`
        по построению совпадает с `count_messages(messages)`, что бы ни менялось
        в разметке: разъехаться сумма частей и общий счёт не могут в принципе.
        """
        messages = self.build_messages(question)
        system = count_text(self.config.system_prompt)
        history = sum(count_text(message["content"]) for message in self._history)
        asked = count_text(question)
        return Budget(
            system=system,
            history=history,
            question=asked,
            overhead=count_messages(messages) - system - history - asked,
            reserved=self.config.max_tokens,
            limit=self.config.context_limit,
        )

    def ask(self, question: str) -> Reply:
        """Один ход разговора. При сбое возвращает Reply с error, а не бросает.

        История пополняется только после удачного ответа. Иначе оборванный вызов
        оставил бы в стеке вопрос без ответа, и следующий запрос ушёл бы с дырой,
        которую модель истолковала бы как реплику, оставшуюся без реакции.

        Переполнение окна проверяется ДО вызова и до всего остального: это
        единственный вид отказа, который ничего не стоит, и только потому, что
        сети он не касается. Отправить и подождать чужого «context length
        exceeded» означало бы заплатить временем за то, что было известно заранее.

        Пустой ответ засчитывается так же, как оборванный вызов: ход не состоялся.
        Формально он удачный — вызов дошёл, деньги списаны, — но класть в историю
        нечего, а пустая реплика ассистента уезжала бы в модель на каждом
        следующем ходу и стоила бы токенов, ничего не значив. В дне 6 это видели
        на экране, в дне 7 стало видно в базе: такой мусор ещё и консервируется.

        Запись на диск идёт здесь же, а не в вызывающем коде. Терминал и панель
        обе умеют звать `ask`, и если бы сохранять историю полагалось им, забыть
        это можно было бы независимо в двух местах — и разойтись они успели бы
        задолго до того, как кто-нибудь заметил.
        """
        question = question.strip()
        if not question:
            raise ValueError("пустой вопрос")

        # Счёт до вызова. Дальше он поедет в `_call` и вернётся в `Reply` —
        # не ради красоты, а чтобы было с чем сверить фактический prompt_tokens.
        #
        # AICODE-NOTE: оценка почти всегда ЗАНИЖЕНА — замерено 09.09.2026 на
        # deepseek-v4-flash, три прогона по пять ходов: факт больше оценки в 14
        # случаях из 15, разрыв от 39 до 163 токенов (таблица в README). Отсюда
        # следует, что проверка ниже пропустит запрос, который в окно не влезет,
        # если `context_limit` поставлен вплотную к настоящему окну модели.
        #
        # Запас в код не зашит намеренно, и процентный коэффициент вроде `* 1.15`
        # был бы здесь прямо неверен: разрыв в основном ПОСТОЯННЫЙ (служебный
        # шаблон провайдера), процент от него только выглядит убывающим. Хуже
        # того, шаблон разный у разных провайдеров, а провайдер здесь не закреплён
        # с дня 6 — то есть подогнать константу не под что. Правильное лечение —
        # родной токенизатор модели; до тех пор запас держит человек, ставя
        # `--context-limit` ниже настоящего окна примерно на 200 токенов.
        budget = self.budget(question)
        if not budget.fits:
            return self._refuse(budget)

        messages = self.build_messages(question)
        reply = self._call(messages, budget)
        if reply.ok and self.store is not None:
            try:
                self.store.append_call(reply)
            except Exception as error:
                reply = replace(
                    reply, store_error=f"учёт расхода: {type(error).__name__}: {error}"
                )
        if reply.ok and not reply.empty:
            self._history.append({"role": "user", "content": question})
            self._history.append({"role": "assistant", "content": reply.text})
            if self.store is not None:
                reply = self._save(question, reply)
        return reply

    def _refuse(self, budget: Budget) -> Reply:
        """Отказ вместо вызова: запрос не влезает в окно.

        Это и есть ответ дня 8 на «что ломается при переполнении». Ломается ход:
        разговор не может продолжаться, не потеряв часть себя. Дальше выбор из
        трёх — новая сессия, обрезка старых ходов, сжатие в конспект, — и делать
        этот выбор молча за человека агент не должен: любой из вариантов теряет
        то, что модель до сих пор помнила.

        Ни история, ни база не трогаются: локального вызова API не было.
        Пустой ответ API, напротив, сохраняет расход в отдельном журнале.
        """
        over = -budget.free
        return Reply(
            text="",
            model=self.config.model,
            elapsed=0.0,
            budget=budget,
            overflow=True,
            error=(
                f"не влезает в окно: {budget.total} из {budget.limit} "
                f"(лишних {over}). {budget.line()}"
            ),
        )

    def _save(self, question: str, reply: Reply) -> Reply:
        """Записать ход и НЕ уронить разговор, если запись не удалась.

        Исключение отсюда наружу означало бы, что занятая база, полный диск или
        отвалившийся внешний том стирают уже полученный и уже оплаченный ответ:
        вызывающий код получил бы трассировку вместо текста, а в панели — 500 без
        тела. Ловится всё подряд именно поэтому — здесь важен не разбор причины,
        а то, что причина не должна стоить пользователю ответа.

        В памяти ход при этом уже лежит, и разговор продолжается как ни в чём не
        бывало. Расплата приходит при следующем запуске, и чтобы она не оказалась
        сюрпризом, беда едет наружу в `store_error` и печатается в строке дебага.
        """
        try:
            self.store.append_turn(question, reply)
        except Exception as error:
            previous = f"{reply.store_error}; " if reply.store_error else ""
            return replace(reply, store_error=f"{previous}{type(error).__name__}: {error}")
        return reply

    def _call(self, messages: list[dict], budget: Budget) -> Reply:
        client = self.client or get_client()
        started = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=self.config.model_id,
                max_tokens=self.config.max_tokens,
                messages=messages,
                extra_body={"provider": PROVIDER, "usage": {"include": True}},
                **sampling_args(self.config.temperature),
            )
        except (OpenAIError, RuntimeError) as error:
            return Reply(
                text="",
                model=self.config.model,
                elapsed=round(time.monotonic() - started, 3),
                budget=budget,
                error=f"{type(error).__name__}: {error}",
            )
        return self._record(response, round(time.monotonic() - started, 3), budget)

    def _record(self, response, elapsed: float, budget: Budget) -> Reply:
        """Output policy: из сырого ответа API — только то, что нужно наружу.

        Фактически списанное (`usage.cost`) и имя провайдера сохраняются рядом
        с нашим расчётом по прайсу, не подменяя его: расхождение между двумя
        числами — единственный способ заметить, что каталог цен устарел.
        """
        usage = getattr(response, "usage", None)
        prompt_tokens = usage.prompt_tokens if usage else None
        completion_tokens = usage.completion_tokens if usage else None
        choice = response.choices[0]
        return Reply(
            text=choice.message.content or "",
            model=self.config.model,
            elapsed=elapsed,
            finish_reason=choice.finish_reason or "",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost(prompt_tokens, completion_tokens, self.config.model),
            cost_reported=getattr(usage, "cost", None) if usage else None,
            served_by=getattr(response, "provider", None),
            budget=budget,
        )
