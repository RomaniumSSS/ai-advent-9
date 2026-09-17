# LIVE_VALIDATION — fake-client E2E

Реальный provider и сеть не использовались.

Сценарий на чистой временной SQLite DB:

1. `planning`: 1 model turn, остановка `approval_required`.
2. Новый экземпляр агента с той же задачей: proposal найден, 0 новых calls.
3. Один user approve: автоматически выполнены 2 model turns
   (`execution`, затем `validation`), остановка `approval_required`.
4. Финальный user approve: `done`, новых model calls нет.

Итого: 3 fake model calls, из них два подряд без нового user message.
Служебные workflow prompts не попали в chat history (`chat_messages = 0`);
результаты сохранены как FSM artifacts/proposals.

Существующие suites перед этим этапом: workflow 6/6, task-state 10/10,
web 6/6, deterministic campaign regression 68/68, JS syntax pass.
