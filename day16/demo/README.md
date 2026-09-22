# Видео Day 16

Сценарий запускает настоящую локальную панель и Everything MCP Server, нажимает
discovery и записывает непустой список tools. Статического списка в ролике нет.

```bash
uv sync --locked
uv run python day16/demo/record.py
```

Результат: `day16-mcp-discovery.mp4`, без аудио. Нужны `npx`, Chrome или браузер
Playwright и `ffmpeg`.

[Готовое видео](day16-mcp-discovery.mp4): 22,12 с, 1440×900, H.264, без аудио.
