# Review — modular context

**Overall: APPROVED**

Блокирующих дефектов и warnings не обнаружено.

Проверено read-only:

- `AgentCapabilities` валидируется и не изменяется после создания;
- default сохраняет старое поведение и порядок context blocks;
- выбранные memory layers читаются по одному, скрытых `store.notes()` в request
  path нет;
- `profile=False` и `task_state=False` исключают соответствующие store reads;
- capabilities и FSM фиксируются до `ChatAgent.ask()` и очищаются в `finally`;
- pause/done guards сохраняются при включённой FSM, а plain-chat режим является
  явным решением приложения, не модели;
- `recent_turns` CLI панели сохранён как совместимый adapter;
- все внутренние конструкторы Agent переведены на новый API;
- отключение контекста не удаляет данные;
- scope clean, секретов и внешних вызовов нет.

Предел проверки: реальный provider намеренно не запускался; для изменения
детерминированной сборки payload достаточно fake-client evidence.
