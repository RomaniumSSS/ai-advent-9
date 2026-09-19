# Проверки Дня 15

Среда: локальный macOS, `uv run --no-dev`, Python проекта; сеть провайдера не
вызывалась. Офлайн-клиент возвращал контролируемые ответы.

| Проверка | Результат |
|---|---|
| `test_controlled_transitions.py` | 2/2: запрещённые переходы, audit, чат, пауза/restart/resume, возврат |
| `test_task_state.py` | 10/10: FSM, терминальный `done`, хранение, миграция, область, snapshot |
| `test_workflow_loop.py` | 7/7: предложения, версионность, пауза во время вызова, обрезанный ответ не переводит этап |
| `test_invariants.py` | 8/8: накопительные правила Дня 14 |
| `test_web.py` | 7/7: API, workflow, накопительная панель |
| `node --check`, `compileall`, `machine.py check` | pass |
| YAML CI (`PyYAML BaseLoader`) | pass: push, pull_request, 6 шагов |
| SQLite v5 → v6 в отдельной временной БД | pass: версия 6 и таблица `transition_denials` |

После исправления, найденного живым прогоном, локальный набор повторён: 34/34.
Браузерная демонстрация: [browser-report.json](browser-report.json), три ширины
без горизонтального переполнения и ошибок страницы. Реальный провайдер
проверен отдельно в `live-run-01/`; GitHub Actions ещё не запускался.
