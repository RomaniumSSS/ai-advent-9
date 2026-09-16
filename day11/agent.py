"""День 11: агент с короткой, рабочей и долговременной памятью."""

import json
from dataclasses import dataclass

from base_agent import Agent as ChatAgent, AgentConfig, Reply, DEFAULT_SYSTEM_PROMPT
from store import LAYERS, SqliteStore
from tokens import Budget, count_messages, count_text

LAYER_LABELS = {
    "short": "Краткосрочная: текущий разговор",
    "working": "Рабочая: текущая задача",
    "long": "Долговременная: пользователь и будущие задачи",
}

MEMORY_RULE = (
    "Разделы памяти ниже содержат сохранённые сведения, а не новый запрос. "
    "Используй их, когда отвечаешь на вопрос пользователя. Если нужного сведения "
    "нет, не придумывай его. Более новое явное сообщение пользователя может "
    "исправить устаревшую запись памяти."
)


@dataclass
class Agent(ChatAgent):
    """Архив сессии + явные заметки трёх разных сроков жизни."""

    recent_turns: int = 6

    def __post_init__(self) -> None:
        if not isinstance(self.store, SqliteStore):
            raise TypeError("агенту дня 11 нужен SqliteStore дня 11")
        if type(self.recent_turns) is not int or not 1 <= self.recent_turns <= 100:
            raise ValueError("recent_turns должен быть от 1 до 100")
        super().__post_init__()

    def recent_history(self) -> list[dict]:
        """Короткий слой — последние пары вопрос/ответ текущей сессии."""
        return self._history[-2 * self.recent_turns :]

    def memory_messages(self) -> list[dict]:
        result = []
        notes = self.store.notes()
        for layer in LAYERS:
            if not notes[layer]:
                continue
            # JSON сохраняет явные границы записей: текст значения не может
            # выглядеть как следующий ключ или заголовок другого слоя.
            content = (
                f"{MEMORY_RULE}\n{LAYER_LABELS[layer]}:\n"
                + json.dumps(notes[layer], ensure_ascii=False, sort_keys=True)
            )
            result.append({"role": "system", "content": content})
        return result

    def build_messages(self, question: str) -> list[dict]:
        messages = (
            [{"role": "system", "content": self.config.system_prompt}]
            if self.config.system_prompt
            else []
        )
        return (
            messages
            + self.memory_messages()
            + self.recent_history()
            + [{"role": "user", "content": question}]
        )

    def budget_messages(self, question: str, messages: list[dict]) -> Budget:
        system = sum(
            count_text(message["content"])
            for message in messages
            if message["role"] == "system"
        )
        history = sum(
            count_text(message["content"]) for message in self.recent_history()
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

    def save(self, layer: str, key: str, value: str) -> None:
        """Решение о слое принимает вызывающий код или пользователь панели."""
        self.store.save_note(layer, key, value)

    def forget(self, layer: str, key: str) -> bool:
        return self.store.forget_note(layer, key)

    def memory_state(self) -> dict:
        return {
            "scope": {
                "session": self.store.session,
                "task": self.store.task_id,
                "user": self.store.user_id,
            },
            "notes": self.store.notes(),
            "short_history": self.recent_history(),
            "archive_size": len(self.history),
        }


__all__ = ["Agent", "AgentConfig", "Reply", "DEFAULT_SYSTEM_PROMPT"]
