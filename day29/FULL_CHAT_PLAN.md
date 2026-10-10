# Full local chat — план

Контракт: [FULL_CHAT_SPEC](FULL_CHAT_SPEC.md); выполнение: [FULL_CHAT_TASKS](FULL_CHAT_TASKS.md).
Изолированные добавления внутри Day29; штатные docs можно дополнить ссылкой на чат.
Формальная FSM, повторный benchmark sweep и новый pipeline не нужны.

1. **Зафиксировать границы и RED.** Сохранить hashes исходного public-кода/профилей,
   frozen inputs/results, видео/ZIP; проверить текущие index identity и модели без
   генерации. Добавить небольшие synthetic fixtures и RED-тесты для all eligibility,
   discussion без day, исходной атрибуции, follow-up/topic switch/reset, бюджета,
   invalid refs/JSON/length, приватного хранения и HTTP loopback boundary.
2. **Sol: отдельный runtime.** `full_chat_core.py` загружает полный metadata и строит
   свежий retrieval/context; `full_chat.py` обслуживает API; `full_chat_static/` — чат.
   Допустим reuse из `core.py`: Ollama, lock, packed/hash/vector, atomic private save и
   identity constants. Не использовать public Engine/snapshot/evaluate для all.
   Сначала проверить существующим loader identity, затем read-only дочитать metadata
   и сопоставить chunk IDs/hash; либо перенести проверки в отдельный loader без
   изменения core. Сохранять members/source_sections/offsets. Не переносить облачную
   обвязку Day25; conversation.py и temporal.message_parts — только образцы поведения.
3. **Sol: память и UI.** Отдельное приватное хранилище разговоров и receipts, атомарный
   жизненный цикл submitted/running/done/unknown/error/interrupted. API new/list/get/ask/reset;
   reset/new во время pending не позволяют позднему ответу попасть в новый разговор.
   История ограничена только при сборке prompt; сохранённая история не теряется.
   Разрешение follow-up детерминировано и записывает anchor/search query; без отдельного
   LLM rewrite/summarizer. Собственный system для помощи по заданиям, обсуждениям и
   заметкам; отдельная materialization источников учитывает составные чанки.
4. **Проверить в ограниченном объёме.** GREEN новых tests и прежний Day29 offline suite.
   Браузером проверить ввод, pending/error, источники, reload, новый/сброс разговора.
   Один initial smoke из трёх запросов: новый discussion-вопрос, follow-up к нему и
   personal_note. Смешанный assignment+discussion, unknown и injection сначала
   проверяются offline; четвёртый live-кейс нужен только при оставшемся конкретном
   сомнении. Unknown может обойтись без generation. До прогона сверить
   ответы-ожидания с оригиналами и сохранить кейсы private. Реальный prompt-injection
   fixture допустим только отдельно от immutable corpus и помечается synthetic;
   не приписывать его исходному архиву. Все вызовы последовательно под общим lock.
   Проверять факты/авторов/даты/смену темы, не только refs. После конкретного исправления
   повторять только затронутые кейсы; сохранять исходный FAIL, без broad sweeps.
5. **Независимая проверка и поставка.** Luna читает diff/spec/tests/evidence; Sol исправляет;
   Astra самостоятельно проверяет замечания, исправления и пропуски даже при первом PASS.
   Проверить hashes сохранённой public-поставки и immutable DB после работы. README
   объясняет запуск /8070 и отличие от /8069; отдельный краткий full-chat отчёт содержит
   проверенную среду, реальные статусы и ограничения без private текстов. Значимые
   события — существующий actions.jsonl без private payload; подробные evidence private.
   Обновить краткие todo/HANDOFF после результата, оставить готовый локальный чат.
