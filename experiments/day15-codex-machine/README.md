# Внешняя FSM работы над Днём 15

Эта машина управляет работой Codex, а не состояниями задач учебного ассистента.
Продуктовый код будет жить в отдельной папке `day15/`.

```text
PLAN → IMPLEMENT → VERIFY → DEMO → REVIEW → LIVE_VALIDATION → CI → DONE
           ↑          │       │        │              │           │
           └──────────┴───────┴────────┴──────────────┴───────────┘
                  исправление ошибки
```

`PLAN → IMPLEMENT` требует явного согласования [плана](plan.md) Романом.
Остальные переходы требуют существующего файла с результатом этапа. `VERIFY`,
`DEMO`, `REVIEW`, `LIVE_VALIDATION` и `CI` могут вернуть работу в `IMPLEMENT` с причиной. Пауза сохраняет
этап и артефакты; после продолжения работа идёт с того же места.

`LIVE_VALIDATION` требует минимум 10 реальных вызовов DeepInfra и отчёт
`day15/results/live-run-01/report.json`. `CI` завершается после пуша и проверки успешного GitHub Actions run. Контроллер
сверяет `conclusion: success`, ссылку на run и SHA с текущим `HEAD`. Локальные
тесты в `VERIFY` не подменяют эту проверку. Контроллер не делает пуш сам.

```bash
python3 experiments/day15-codex-machine/machine.py status
python3 experiments/day15-codex-machine/machine.py check
# После явного утверждения плана:
python3 experiments/day15-codex-machine/machine.py approve-plan --evidence 'ссылка или дата сообщения Романа'
python3 experiments/day15-codex-machine/machine.py advance --evidence experiments/day15-codex-machine/plan.md
```

Переходы и значимые остановки сохраняются атомарно в `state.json`. Это короткий
указатель для возобновления; подробные результаты проверок остаются в файлах
этапов и кратко отражаются в `todo.md`. `DONE` здесь означает проверенную работу
и готовые материалы для сдачи, но не автоматическую публикацию.
