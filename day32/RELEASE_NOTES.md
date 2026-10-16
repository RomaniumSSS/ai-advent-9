# Day32 — локальная реализация

Добавлены read-only GitHub polling, закреплённый merge-base snapshot,
FTS5 retrieval по docs/code, режимы diff/files/rag и отдельные точные артефакты.
SQLite сохраняет dedupe и резерв до единственного вызова Qwen без retry/fallback.
Локальная панель 8072 показывает контекст, результат и известные затраты.

Офлайн-проверки проходят. Live-trigger, Qwen и видео ещё не приняты;
fixture явно отделён от доказательства качества модели.
