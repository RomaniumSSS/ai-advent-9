# День 17 — первый MCP-инструмент

Обычный chat flow получает schema из MCP discovery. Модель может выбрать
`get_recent_commits`; harness проверяет имя и arguments, выполняет не более одного
`tools/call`, возвращает typed observation во второй model call и сохраняет только
проверенный final response. FSM workflow остаётся tool-disabled.

Собственный stdio MCP server читает только настроенный при старте Git repository.
Tool принимает `limit` от 1 до 10 и возвращает непустой список commit ID, subject,
author и timestamp. Путь repository модель передать или заменить не может.

## Запуск

Нужны Python 3.12+, `uv` и Git:

```bash
uv sync --locked
uv run python day17/web.py --db /tmp/day17-demo.db --port 8047
# http://127.0.0.1:8047
```

Без `--env-file` используется детерминированный offline provider, но настоящий
локальный MCP server. Для реальной модели:

```bash
uv run python day17/web.py \
  --db /tmp/day17-live.db --port 8047 \
  --env-file /безопасный/путь/.env
```

Файл окружения должен содержать `OPENROUTER_API_KEY`; ключ не передаётся браузеру,
MCP server или отчётам. MCP-конфигурация по умолчанию — `mcp-git.json`; приложение
принимает только локальный stdio command и строковый список arguments.

## Границы

- tools доступны только обычному chat; workflow model turns вызываются без schema;
- на logical turn допускаются максимум 2 provider calls и 1 MCP execution;
- mixed/multiple/malformed/unknown calls не исполняются;
- повторный tool request от LLM2 получает denial и не создаёт LLM3;
- discovery не считается execution, успешный snapshot переиспользуется;
- paused/done и любое изменение FSM version инвалидируют применение turn;
- error, timeout, empty/malformed result не становятся successful observation;
- audit provider calls, MCP execution и local policy outcomes хранится раздельно.

## Проверки

Полный offline Day 17 suite:

```bash
for f in day17/test_*.py; do
  PYTHONDONTWRITEBYTECODE=1 uv run --no-dev --no-sync python "$f" || exit 1
done
node --check day17/web/app.js
git diff --check
```

Live provider probe и comparative evaluation запускаются только после offline green:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-dev --no-sync python \
  day17/live_mcp_acceptance.py probe \
  --env-file /безопасный/путь/.env --output /tmp/day17-probe

PYTHONDONTWRITEBYTECODE=1 uv run --no-dev --no-sync python \
  day17/live_mcp_acceptance.py compare \
  --env-file /безопасный/путь/.env \
  --probe-report /tmp/day17-probe/report.json --output /tmp/day17-comparison
```

Фактические результаты и ограничения описаны в [VERIFICATION.md](VERIFICATION.md).
Короткое live-видео: [Day 17 MCP tool calling](demo/day17-mcp-tool-calling.mp4).
