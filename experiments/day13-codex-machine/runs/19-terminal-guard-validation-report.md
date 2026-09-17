# Валидация локального terminal guard

Проверки выполнены в отдельной временной копии `day13/` с чистыми SQLite-базами.

- Agent на `done` возвращает локальный ответ
  `Задача завершена; ожидаемого действия нет.`, `finish_reason=local_state`;
  model client не вызывается, FSM не меняется.
- Manifest содержит 68 уникальных ситуаций: 60 model paths на planning,
  execution и validation, 4 pause guards и 4 done guards без сети.
- 12 live restart/resume cases сохраняют task state при пустой истории.
- Модель возвращает только `{answer}`. Попытка вернуть `decision` или поля state
  отклоняется строгим parser как quality failure; state-envelope остаётся
  приложению.
- Provider uncertainty останавливает campaign без retry; tamper checkpoint
  обнаруживает изменение ledger.
- Live-05 связан с SHA-256 live-04, собственной стоимостью `$0.00050263` и
  накопительным расходом `$0.00213769`; общий лимит остаётся `$0.02`.
- FSM/web тесты, JavaScript syntax и Python compilation прошли.

Реальная сеть на этом этапе не использовалась.
