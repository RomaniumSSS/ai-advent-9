# Видео Day 17

Сценарий поднимает реальную локальную панель с online provider и собственным
Git MCP server. В ролике показаны discovery schema, естественный chat request,
trace `provider_initial → mcp_execution → provider_final` и grounded response.

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python day17/demo/record.py \
  --env-file /безопасный/путь/.env
```

Результат: `day17-mcp-tool-calling.mp4`, H.264 без аудио. Содержимое `.env` и
ключ провайдера в браузер и видео не передаются.
