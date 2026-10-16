# Первое независимое ревью corpus fix — Day31

**Reviewer:** gpt-6-luna
**Вердикт:** NEEDS CHANGES — одно небольшое замечание к воспроизводимости команды запуска.

## Проверка содержания

Описание `ToolRuntime.model_tools()` совпадает с Day17 `tool_calling.py`: из discovery берутся `name`, `description`, `input_schema`; формируется function tool, где `parameters` равен `input_schema` (строки 171–180). `_allowed_tool()` ограничивает discovery единственным `get_recent_commits`, требует description/dict schema и проверяет корректность схемы. `parse_arguments()` отдельно разбирает JSON, проверяет аргументы по схеме и затем ограничивает разрешённый набор одним целым `limit` от 1 до 10. `ensure_snapshot()` сохраняет прошедший эту проверку discovery.

Описание запуска также совпадает с `day17/git_mcp_server.py:129–133`: `--repo` обязателен, преобразуется в `Path`, передаётся в `build_server()`, а сервер запускается с `stdio`. Уточнение, что это отдельный процесс Day17, а не Day31 `git_context`, явно проведено. Факты не смешивают снимок исходников Day17 и runtime Day31. README, provenance и retrieval совпадают с source manifest GLM; структура корпуса по-прежнему состоит из README и трёх документов docs.

## Finding

🟡 **[WARNING] `day31/docs/git-mcp.md:32`** — команда `python day17/git_mcp_server.py ...` не выбирает uv-окружение, установленное проектом. В текущем worktree `python day17/git_mcp_server.py --help` завершился с `ModuleNotFoundError: No module named 'mcp'`; этот вызов только показал help и не запускал сервер. После обычного `uv sync --frozen` зависимости установлены в проектном окружении, а пример не активирует его. Рекомендация: указать `uv run --frozen python day17/git_mcp_server.py --repo /путь/к/repo` либо явно документировать активацию `.venv`.

Платных API-вызовов и генерации новых модельных ответов не было; полный suite не запускался.
