"""День 6: агент как отдельная сущность.

Снаружи у агента одна дверь: `ask(текст) -> Reply`. Всё остальное — сборка запроса,
системный промпт, стек сообщений, вызов, разбор ответа, учёт токенов и денег —
его внутреннее дело.

Проверка, ради которой это написано именно так: сто агентов с разными конфигами
должны подниматься внутри ОДНОГО процесса и не видеть переписку друг друга.
Отсюда два решения, которые легко принять наоборот и потом долго чинить:

- состояние (конфиг и история) живёт в полях объекта, а не в модуле. Модульная
  переменная сделала бы второго агента невидимым разрушителем первого;
- HTTP-клиент, наоборот, один на процесс. Он разговора не помнит, это просто труба,
  и сто клиентов означали бы сто пулов соединений на ровном месте.

Системный промпт в историю не кладётся: он подставляется при каждой сборке запроса.
Иначе после `reset()` агент терял бы роль, а при будущей обрезке контекста роль
вылетала бы первой — она же самая старая запись.

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

    def __post_init__(self) -> None:
        # Падать здесь, а не на сетевом вызове: опечатка в имени модели иначе
        # обнаружится только после того, как пользователь напишет первое сообщение.
        if self.model not in MODELS:
            raise ValueError(f"неизвестная модель {self.model!r}")
        if self.max_tokens < 1:
            raise ValueError("max_tokens должен быть положительным")
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("температура вне диапазона 0..2")

    @property
    def model_id(self) -> str:
        return MODELS[self.model]["id"]


@dataclass(frozen=True)
class Reply:
    """Что агент отдаёт наружу. Сырой ответ API за дверью не показывается.

    При сбое `error` заполнен, а `text` пуст — вызывающий код обязан различать
    «модель промолчала» и «до модели не дошло».
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

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def truncated(self) -> bool:
        """Ответ оборвался по потолку токенов, а не закончился сам."""
        return self.finish_reason == "length"

    def debug_line(self) -> str:
        """Одна строка для терминала и панели: доказательство, что коробка работает."""
        if self.error:
            return f"[{self.model}] ошибка за {self.elapsed:.1f} с: {self.error}"
        tokens = f"{self.prompt_tokens or '?'}→{self.completion_tokens or '?'}"
        spent = f"${self.cost:.6f}" if self.cost is not None else "цена неизвестна"
        tail = "  ОБРЕЗАН ПО ЛИМИТУ" if self.truncated else ""
        return (
            f"[{self.model}] {self.elapsed:.1f} с  токены {tokens}  {spent}"
            f"  finish={self.finish_reason}{tail}"
        )


@dataclass
class Agent:
    """Коробка. Снаружи видно только `ask` и `history`.

    `client` — точка подмены для тестов: офлайн-проверки подставляют сюда объект
    с тем же методом и сети не касаются.
    """

    config: AgentConfig = field(default_factory=AgentConfig)
    name: str = "агент"
    client: object | None = None
    _history: list[dict] = field(default_factory=list, repr=False)

    @property
    def history(self) -> list[dict]:
        """Копия, а не сам список: снаружи историю правят только через методы."""
        return [dict(message) for message in self._history]

    @property
    def turns(self) -> int:
        return sum(1 for message in self._history if message["role"] == "user")

    def reset(self) -> None:
        self._history.clear()

    def with_config(self, **changes) -> "Agent":
        """Новый агент с изменённым конфигом и ПУСТОЙ историей.

        Историю не переносим: она снята на другой роли и другой модели, и молча
        приписать её новому конфигу значило бы соврать в замерах.
        """
        return Agent(config=replace(self.config, **changes), name=self.name)

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

    def ask(self, question: str) -> Reply:
        """Один ход разговора. При сбое возвращает Reply с error, а не бросает.

        История пополняется только после удачного ответа. Иначе оборванный вызов
        оставил бы в стеке вопрос без ответа, и следующий запрос ушёл бы с дырой,
        которую модель истолковала бы как реплику, оставшуюся без реакции.
        """
        question = question.strip()
        if not question:
            raise ValueError("пустой вопрос")

        messages = self.build_messages(question)
        reply = self._call(messages)
        if reply.ok:
            self._history.append({"role": "user", "content": question})
            self._history.append({"role": "assistant", "content": reply.text})
        return reply

    def _call(self, messages: list[dict]) -> Reply:
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
                error=f"{type(error).__name__}: {error}",
            )
        return self._record(response, round(time.monotonic() - started, 3))

    def _record(self, response, elapsed: float) -> Reply:
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
        )
