"""День 10: агент, который не знает, как собран его контекст.

Единственная развилка дня — что уедет в модель. Она вынесена в `strategies.py`
целиком, и агент видит только объект стратегии. Так переключатель становится
подменой одного поля, а не набором `if` по всему файлу: третий такой `if`
обязательно разъехался бы с первыми двумя.

Архив при этом не режется ни одной стратегией. Пользователь видит переписку
целиком всегда; урезается только копия, уходящая в запрос.
"""

from dataclasses import dataclass, field, replace

from base_agent import Agent as ChatAgent, AgentConfig, Reply, DEFAULT_SYSTEM_PROMPT
from facts import FACTS_SYSTEM_PROMPT, extraction_input, normalize, parse_facts
from strategies import FactsState, StrategyConfig, context_history
from tokens import Budget, count_messages, count_text

# Потолок служебного ответа. Факты — это несколько строк «ключ: значение»,
# и давать сюда полный MAX_TOKENS значило бы резервировать деньги под ответ,
# которого не бывает.
FACTS_MAX_TOKENS = 600


@dataclass
class Agent(ChatAgent):
    """Агент дня 10. Отличается от базового ровно двумя вещами.

    Первая: контекст собирает стратегия. Вторая: при стратегии `facts` после
    каждого хода делается отдельный служебный вызов, обновляющий память.

    Этот второй вызов — главная цена Sticky Facts, и он намеренно виден в
    журнале отдельным видом (`kind='facts'`). Спрятать его в общий счёт значило
    бы сравнивать стратегии по неполной цене и получить вывод в свою пользу.
    """

    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    facts: FactsState = field(default=FactsState(), init=False)
    facts_event: dict | None = field(default=None, init=False)

    def __post_init__(self):
        super().__post_init__()
        if self.store is not None:
            self.facts = FactsState(values=self.store.load_facts())

    def context_history(self) -> list[dict]:
        return context_history(self.strategy, self._history, self.facts)

    def build_messages(self, question: str) -> list[dict]:
        system = (
            [{"role": "system", "content": self.config.system_prompt}]
            if self.config.system_prompt
            else []
        )
        return system + self.context_history() + [{"role": "user", "content": question}]

    def budget(self, question: str) -> Budget:
        """Вес именно того запроса, который уедет, — а не всего архива.

        Считается по `context_history()`, поэтому у sliding история в бюджете
        маленькая, хотя в базе лежит целиком. Это и есть то, за что платят.
        """
        messages = self.build_messages(question)
        system = count_text(self.config.system_prompt)
        history = sum(
            count_text(message["content"]) for message in self.context_history()
        )
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
        """Ход разговора, а следом — обновление памяти, если стратегия этого просит.

        Порядок именно такой. Факты извлекаются ПОСЛЕ ответа, а не до: в запрос
        они попадут на следующем ходу, и пытаться успеть к текущему значило бы
        задерживать ответ собеседнику ради служебного вызова.

        Неудача обновления фактов не трогает ответ. Он уже получен и оплачен,
        и ронять его из-за того, что память не пополнилась, — плохой обмен.
        """
        self.facts_event = None
        reply = super().ask(question)
        if self.strategy.name == "facts" and reply.ok and not reply.empty:
            self._update_facts(question.strip(), reply.text)
        return reply

    def _update_facts(self, question: str, answer: str) -> None:
        worker = ChatAgent(
            config=replace(
                self.config,
                system_prompt=FACTS_SYSTEM_PROMPT,
                max_tokens=FACTS_MAX_TOKENS,
                temperature=0,
            ),
            client=self.client,
        )
        reply = worker.ask(extraction_input(question, answer, self.facts.values))
        event = {
            "applied": False,
            "revision": self.facts.revision,
            "error": None,
            "prompt_tokens": reply.prompt_tokens,
            "completion_tokens": reply.completion_tokens,
        }
        self.facts_event = event
        if reply.ok and self.store is not None:
            try:
                self.store.append_call(reply, kind="facts")
            except Exception as error:
                event["error"] = (
                    f"не сохранён расход facts: {type(error).__name__}: {error}"
                )
                return
        if not reply.ok or reply.empty:
            event["error"] = reply.error or "извлекатель промолчал; память прежняя"
            return
        updates = normalize(parse_facts(reply.text))
        if not updates:
            event["error"] = "в ответе извлекателя нет известных фактов; память прежняя"
            return
        merged = self.facts.merge(updates)
        if merged is self.facts:
            event["error"] = "новых сведений не оказалось; память прежняя"
            return
        try:
            if self.store is not None:
                self.store.save_facts(merged.values)
        except Exception as error:
            # Память в процессе не меняем: иначе после перезапуска агент забыл
            # бы то, что весь сеанс считал известным, и никто бы не понял почему.
            event["error"] = f"facts не сохранены: {type(error).__name__}: {error}"
            return
        self.facts = merged
        event.update(applied=True, revision=merged.revision, added=updates)

    def switch_strategy(self, name: str, recent_messages: int | None = None) -> None:
        """Сменить стратегию, не трогая ни историю, ни память.

        В этом и смысл переключателя: сравнивать стратегии на одном и том же
        разговоре. Чистка истории при переключении сделала бы сравнение
        невозможным, а не более честным.
        """
        self.strategy = StrategyConfig(
            name=name,
            recent_messages=(
                self.strategy.recent_messages
                if recent_messages is None
                else recent_messages
            ),
        )

    def reset(self) -> None:
        if self.store is not None:
            self.store.clear()
        self._history.clear()
        self.restored_turns = 0
        self.facts = FactsState()
        self.facts_event = None

    def with_config(self, **changes) -> "Agent":
        self.reset()
        return Agent(
            config=replace(self.config, **changes),
            name=self.name,
            client=self.client,
            store=self.store,
            strategy=self.strategy,
        )


__all__ = [
    "Agent",
    "AgentConfig",
    "DEFAULT_SYSTEM_PROMPT",
    "FactsState",
    "Reply",
    "StrategyConfig",
]
