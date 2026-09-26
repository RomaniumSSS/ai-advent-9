# Day 18 G2 — один разрешённый повторный run

Дата: 26.09.2026. Пользователь разрешил ровно один повторный диагностический
`manual no-send` для слота 25.09.2026. Run ID:
`47045b6d-feaf-4e28-ad65-e981a9ce6c2e`.
БД: `/private/tmp/day18-g2-v41-repeat-20260926.sqlite3`; новая БД отделена от
[первого run](g2-v41-first-run.md). Telegram не вызывался.

| Фаза | Сохранённый результат |
| --- | --- |
| Model call 1 (`tool_choice=auto`) | OK: 715 input, 258 output, reasoning 0; `usage.cost=$0.00020846` |
| MCP | 1 accepted execution; feed_seen 100, in_period/eligible 29, invalid_entries 20, omitted_candidates 19; coverage `partial`, feed_limit_hit |
| Draft preflight | model_seen 6, worst-case 5687 bytes |
| Model call 2 | API OK: 4133 input, 1187 output, reasoning 0; `usage.cost=$0.00107716` |
| Validation | `FAILED_AFTER_DATA`, `draft_invalid_json`; 0 reports, 0 classifications, 0 Telegram sends |

Фактическая стоимость по provider `usage.cost`: **$0.00128562**. Вместе с
первым G2 run: **$0.00266840**. Сырой ответ модели не сохранялся; код
`draft_invalid_json` доказывает синтаксическую ошибку JSON, но не показывает
её конкретный фрагмент. RSS мог измениться между двумя запусками; разницу
счётчиков нельзя целиком приписать исправленному парсеру.

После run для второго provider call включён `response_format=json_schema`
со `strict=true`; локальный валидатор по-прежнему проверяет полный контракт,
grounding и охват. Публичный [список параметров endpoint DeepInfra](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints)
содержал `response_format` и `structured_outputs` на момент проверки.
Локальный тест подтверждает форму запроса и отсутствие этого параметра в
первом tool call; фактический результат нового режима пока не проверен.
Разрешение на один повторный run исчерпано: следующие платные model calls и
Telegram требуют отдельного решения пользователя.
