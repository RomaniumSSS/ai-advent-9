# Validation report

Проверено 17.09.2026 в независимой копии `day14/` и чистых временных SQLite DB.

- `test_invariants.py`: 8/8 групп — 12 request deny до сети,
  6 безопасных explanations, 9 разных provider-output, explicit approval,
  persistence/scope,
  legacy payload, system snapshot и workflow stop без proposal.
- `test_task_state.py`: 10/10 — полный FSM дня 13, pause/restart/version/scope.
- `test_workflow_loop.py`: 6/6 — approvals, revise, turn limit и гонки commit.
- `test_web.py`: 7/7 — накопительная панель, FSM, workflow, online boundary и
  локальный invariant refusal.
- `node --check day14/web/app.js`: pass.
- `python -m compileall -q day14`: pass.
- внешняя Codex FSM: 19/19; scope check не нашёл изменений day01–day13.

Повторный adversarial review закрыл обходы `Используй/Рекомендую/Лучший вариант`,
английскую формулировку, микросервисы и варианты публикации/деплоя/выкладки.
Business action теперь требует позитивный approval, а вопросы и отрицания по
stack и business не получают ложный refusal.

Платный provider не вызывался: поведение модели покрыто fake-client, а локальный
конфликт и фактический web path проверены офлайн. Это не real-provider eval.
