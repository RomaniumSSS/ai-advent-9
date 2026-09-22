# День 16 — MCP discovery

Приложение дня 15 дополнено отдельным MCP-клиентом. По кнопке панель запускает
официальный Everything MCP Server через stdio, согласует версию протокола,
получает полный список `tools/list`, показывает его и закрывает соединение.

Это ещё не tool calling: найденные tools не передаются модели, не исполняются и
не сохраняются в истории, памяти или SQLite. Поэтому прежняя гарантия workflow
«нет инструментов и наблюдений внешнего мира» остаётся истинной.

## Запуск

Нужны Python 3.12+, `uv`, Node.js и `npx`. Первый discovery может скачать
зафиксированный пакет `@modelcontextprotocol/server-everything@2026.8.31`.

```bash
uv sync
uv run python day16/web.py --db /tmp/day16-demo.db --port 8046
# http://127.0.0.1:8046
```

Ключ OpenRouter для MCP discovery не нужен. Без `--env-file` сам агент работает
на офлайн-клиенте.

Другой локальный MCP-сервер подключается заменой JSON-конфигурации:

```bash
uv run python day16/web.py \
  --mcp-config /путь/к/server.json \
  --db /tmp/day16-custom.db --port 8046
```

Формат конфигурации ограничен Day 16: `name`, `transport: "stdio"`, `command`
и строковый список `args`. Браузер не может передать произвольную команду.

## Граница Day 16

`mcp_client.py` владеет короткой session: connect/negotiation, одна или
несколько страниц `tools/list`, close. Современный сервер может согласовать
протокол через `server/discover`, старый — через legacy `initialize`; это решает
SDK. В Day 17 к той же session boundary можно добавить выполнение, не меняя
discovery lifecycle. В Day 16 метода `call_tool` нет.

## Проверки

Офлайн, без `npx` и OpenRouter:

```bash
uv run --no-dev --no-sync python day16/test_mcp_client.py
uv run --no-dev --no-sync python day16/test_mcp_protocol.py
uv run --no-dev --no-sync python day16/test_mcp_web.py
uv run --no-dev --no-sync python day16/test_controlled_transitions.py
uv run --no-dev --no-sync python day16/test_task_state.py
uv run --no-dev --no-sync python day16/test_workflow_loop.py
uv run --no-dev --no-sync python day16/test_invariants.py
uv run --no-dev --no-sync python day16/test_web.py
node --check day16/web/app.js
uv run --no-dev --no-sync python -m compileall -q day16
```

Живая приёмка запускает приложение с Everything Server и требует хотя бы один
tool:

```bash
uv run --no-dev --no-sync python day16/live_mcp_acceptance.py
```

На проверенном прогоне согласован протокол `2025-11-25` и получено 13 tools.
Количество принадлежит версии сервера и не зашито в критерий: требуется `>= 1`.

CI — [`.github/workflows/day16.yml`](../.github/workflows/day16.yml). Он запускает
только воспроизводимые offline-проверки; сетевой Everything acceptance остаётся
отдельным явным шагом.

Короткое live-видео: [соединение, negotiation и 13 обнаруженных tools](demo/day16-mcp-discovery.mp4).
Полная трассировка acceptance — в [VERIFICATION.md](VERIFICATION.md).
