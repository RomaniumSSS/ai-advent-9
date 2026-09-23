"""Локальная демонстрация фактического пути запроса, без генеративной модели."""
import json
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
        tool_calls = []
        if kwargs.get("tools") and any(
            marker in question.casefold() for marker in ("git", "commit", "коммит")
        ):
            text = ""
            tool_calls = [SimpleNamespace(
                id="offline-get-recent-commits",
                function=SimpleNamespace(
                    name="get_recent_commits",
                    arguments='{"limit": 3}',
                ),
            )]
        elif messages[-1]["role"] == "tool":
            observation = json.loads(messages[-1]["content"])
            commits = observation.get("result", {}).get("commits", [])
            if commits:
                first = commits[0]
                text = f"Последний коммит {first['id']}: {first['subject']}"
            else:
                text = "Не удалось получить проверенные данные Git."
        if question == "/empty":
            text = ""
        if question == "/error":
            raise RuntimeError("Демонстрационная ошибка провайдера (без сети)")
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=text, tool_calls=tool_calls),
                finish_reason="tool_calls" if tool_calls else "stop",
            )],
            usage=None,
        )
