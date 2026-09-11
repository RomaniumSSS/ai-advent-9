"""День 10: что именно уезжает в модель. Три стратегии, без суммаризации.

Архив в SQLite остаётся полным всегда. Здесь решается один вопрос: какие из
сохранённых сообщений попадут в следующий запрос. Отбрасывается не переписка,
а её часть в контексте — пользователь свою историю видит целиком.

Ветвление (`branches.py`) сюда не входит намеренно: оно отвечает не на вопрос
«сколько истории отправить», а на вопрос «какая это история». Смешать их в один
переключатель значило бы предложить выбор между литрами и цветом.
"""

from dataclasses import asdict, dataclass, field

STRATEGIES = ("full", "sliding", "facts")

STRATEGY_LABELS = {
    "full": "Полная история",
    "sliding": "Sliding Window",
    "facts": "Sticky Facts",
}

# Модель должна понимать, что перед ней сохранённая память, а не реплика
# собеседника и не распоряжение. Формулировка утвердительная: факты сюда
# попадают только после проверки в facts.py, и сомневаться в них незачем.
FACTS_PREFIX = "Проверенная память диалога в формате «ключ: значение»:\n"


@dataclass(frozen=True)
class FactsState:
    """Память «ключ-значение» и номер её версии.

    `revision` растёт на каждое изменение и нужен панели: без него нельзя
    отличить «факты те же» от «факты не обновились, потому что вызов упал».
    """

    values: dict = field(default_factory=dict)
    revision: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def render(self) -> str:
        return "\n".join(f"- {key}: {value}" for key, value in self.values.items())

    def merge(self, updates: dict) -> "FactsState":
        """Новое состояние: только дополнение и перезапись.

        Удаления нет вовсе, и пустое значение сюда не доходит — его отсекает
        `facts.normalize`. Причина записана там же: извлекатель, которому
        разрешено стирать, рано или поздно «прибирает» нужный факт, и пропажа
        обнаруживается только когда агент перестал помнить, что помнил.
        """
        merged = dict(self.values)
        changed = False
        for key, value in updates.items():
            if merged.get(key) != value:
                merged[key] = value
                changed = True
        if not changed:
            # Тот же объект, а не копия: панель сравнивает revision, и лишний
            # инкремент читался бы как «память обновилась», хотя ничего не произошло.
            return self
        return FactsState(values=merged, revision=self.revision + 1)


@dataclass(frozen=True)
class StrategyConfig:
    name: str = "full"
    recent_messages: int = 6

    def __post_init__(self) -> None:
        if self.name not in STRATEGIES:
            raise ValueError(f"стратегия должна быть одной из: {', '.join(STRATEGIES)}")
        if (
            isinstance(self.recent_messages, bool)
            or type(self.recent_messages) is not int
        ):
            raise TypeError("recent_messages должен быть целым числом")
        if not 1 <= self.recent_messages <= 1000:
            raise ValueError("recent_messages должен быть от 1 до 1000")

    @property
    def label(self) -> str:
        return STRATEGY_LABELS[self.name]


def context_history(
    config: StrategyConfig, history: list[dict], facts: FactsState
) -> list[dict]:
    """Часть архива, которая уедет в модель на этом ходу.

    Отдельная функция, а не метод агента, ровно затем, чтобы её можно было
    проверить без агента, без базы и без сети.
    """
    if config.name == "full":
        return [dict(message) for message in history]
    tail = [dict(message) for message in history[-config.recent_messages :]]
    if config.name == "sliding" or not facts.values:
        return tail
    return [{"role": "assistant", "content": FACTS_PREFIX + facts.render()}] + tail
