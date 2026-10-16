# Знакомый Git MCP Day17

## Устройство Git MCP

Day17 — первый собственный MCP-инструмент. `git_mcp_server.py` создаёт MCPServer
с транспортом stdio. Сервер регистрирует read-only `get_recent_commits(limit)`.
`mcp_client.py` делает discovery (`list_tools`) и выполнение (`call_tool`).
`tool_calling.py` проверяет имя инструмента, JSON arguments и JSON Schema.
Его `ToolRuntime.model_tools()` готовит схему инструмента для модели из MCP
discovery: берёт обнаруженные `name`, `description` и `input_schema`, возвращает
список объектов `type="function"`, где `function.name` и `function.description`
переносятся из discovery, а `function.parameters` содержит `input_schema`.
Эту схему создаёт код, не модель. Перед преобразованием `_allowed_tool` проверяет
единственный разрешённый `get_recent_commits`, наличие описания и корректность
JSON Schema. `ensure_snapshot()` получает discovery и сохраняет проверенный
снимок для повторного использования.
В обычном чате Day17 модель выбирает инструмент, а harness исполняет его.
Это описание снимка Day17, а не автономного поведения Day31.

## Данные последних коммитов

`get_recent_commits` принимает целый `limit` от 1 до 10. Возвращает идентификатор
репозитория и непустой список коммитов: id, subject, author, timestamp.
Путь к репозиторию задаётся доверенной конфигурацией при старте; модель не может
его передать или заменить. `git log` выполняется без shell с timeout 10 секунд.

## Запуск stdio-сервера Day17

Из корня репозитория, с установленными зависимостями проекта и Python 3.12+:

```bash
uv run --frozen python day17/git_mcp_server.py --repo /путь/к/repo
```

В `main()` файла `git_mcp_server.py` аргумент `--repo` обязателен (`required=True`)
и разбирается как `Path`. `build_server(args.repo)` разрешает его до Git worktree
root, после чего `.run("stdio")` запускает MCP-сервер с транспортом stdio.
Это запуск отдельного процесса для MCP-клиента; HTTP-адреса у него нет.
Путь — доверенная настройка старта, а не аргумент, который выбирает модель.
Этот пример запускает исходный сервер Day17 с `get_recent_commits`, а не новый
сервер Day31 с `git_context`.

## Границы Day17

Обычный chat допускает максимум 2 вызова модели и 1 выполнение MCP за ход.
Смешанные, множественные, неизвестные или некорректные tool calls не исполняются.
Повторный запрос инструмента во втором ответе получает отказ без третьего вызова.
Workflow FSM в Day17 работает без tools. Ошибки и malformed result не становятся
успешным observation. Discovery не считается выполнением инструмента.

## Отличие нового git_context

Day31 использует отдельный собственный MCPServer `git_context()` без аргументов.
Он возвращает текущую ветку, detached HEAD, полный head SHA и repository_id.
Git-root фиксируется на старте, по умолчанию это worktree приложения Day31.
Ветка читается заново для каждого вопроса; снимок документации Day17 не определяет
текущую ветку и не сообщает состояние Git. Это делает MCP во время запроса.
