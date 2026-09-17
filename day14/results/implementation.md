# Implementation report — день 14

- Создан самостоятельный `day14/` поверх кода дня 13; `day01`–`day13` не менялись.
- Добавлены typed-инварианты четырёх категорий, отдельные таблицы `invariants` и
  `invariant_checks`, task-scope и миграция SQLite schema v5.
- Request preflight даёт локальный объяснимый отказ без model call.
- Один snapshot правил включается в system context допустимого запроса.
- Response guard работает до истории и SQLite; workflow останавливается без
  proposal и перехода FSM при нарушении.
- Панель показывает активные правила, последние allow/deny checks и кнопку
  воспроизводимого конфликтного сценария.
- Добавлены пять целевых offline-тестов и сохранены регрессии FSM/workflow/web.

## Repair после adversarial review

- Request и response policies разделены: action-intent больше не является
  единственным output guard.
- Защищённые технологии блокируются в provider-output по термам независимо от
  формулировки; business invariant имеет отдельные output-patterns.
- Вопросы, сравнения и отрицания получают локальное объяснение инварианта вместо
  ложного отказа и без model call.
- Business enforcement больше не ищет только отрицательную фразу «без
  подтверждения»: любое внешнее действие требует явной позитивной approval-
  формулы, иначе request/output блокируется.
- Regression matrix: 12 конфликтных запросов, 6 безопасных обсуждений, 9
  различных запрещённых outputs и один разрешённый explicit-approval path.
