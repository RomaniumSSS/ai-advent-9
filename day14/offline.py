"""Локальная демонстрация фактического пути запроса, без генеративной модели."""
from types import SimpleNamespace


class OfflineClient:
    def __init__(self):
        self.requests = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.requests.append(kwargs)
        messages = kwargs["messages"]
        profile = next(m["content"] for m in messages if m["content"].startswith("ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ"))
        question = messages[-1]["content"]
        text = "ОФЛАЙН · запрос получен. Фактический контекст показан отдельно. Это не ответ модели."
        if question == "/empty":
            text = ""
        if question == "/error":
            raise RuntimeError("Демонстрационная ошибка провайдера (без сети)")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason="stop")],
            usage=None,
        )
