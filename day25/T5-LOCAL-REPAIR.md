# T5: локальный ремонт после A1 FAIL

04.10.2026. Реальная первая приёмка остаётся FAIL; новых SSH/provider calls0. Никакого ответа из старого run не переписано.

## Изменения

- `app/conversation.py`: зависимые реплики распознают ссылку на мою/нашу новую/текущую цель, явную ссылку на нашу цель/план/выбор и последний/действующий формат/ограничения. Точные public5/all5/all12 используют текущий task state в search_query; anchor остаётся пользовательским, разрешённым для scope и той же версии памяти.
- Явный новый день/дата/период по-прежнему имеет приоритет: search_query остаётся ровно текущим вопросом. Исторические цели/даты, assistant text и чужая история не добавляются.
- ROLE уточняет сохранение явно выбранных решений в task_state.clarifications и различие пользовательского выбора/обязательного требования. Различает формат сдачи и результат инструмента. При сопоставлении условий с обсуждениями не требует same-day без явно заданного периода; запрещает выдумывать участников/позиции.
- Контракт sources содержит точный пример `{"source": "значение source переданного фрагмента", "chunk_id": "chunk_id этого фрагмента"}` и запрещает source_key. Citation validator не менялся; плохой ответ не нормализуется и не переписывается.

## Проверки

macOS/Python3.14, офлайн:

-29 app tests PASS3.705с: прежние27 T1–T4 плюс2 регрессии exact failing scenario questions/state, дополнительные формы task references, explicit day/date/recent override, независимый вопрос без task additions, actual generator messages/envelope с SQLite/state и guidance, строгий rejection source_key.
-8 preparation tests PASS0.005с; compile и git diff --check PASS.
- `validation/replay_context.py --run-dir day25/private/live-run-01 --output day25/private/context-repair-replay-01.json`:24 сохранённых ходов rebuilt offline,4 search_query изменены; exact saved public5/all5/all12 теперь включают текущую цель. Подтверждён private/own history и bytes<=24000. Переданные ранее фрагменты использованы только для реконструкции prompt, нового embedding/retrieval/generation нет. Saved public8 по-прежнему invalid source_not_in_context. Network/subprocess запрещены patches. Raw replay только private.

Новые instructions не доказывают, что модель сохранит SQLite, верно различит сдачу и инструмент или даст корректную атрибуцию обсуждений. Replay показывает исправленный контекст/контракт, а не новый ответ или качество нового поиска. Смысл исправленного поведения NOT PROVEN без отдельно согласованного повторного живого прогона. Точка остановки — независимый Astra gate локального ремонта; T5 не закрыта.

## Исправление после повторного local gate

Убран общий trigger итоговый/окончательный план без ссылки на задачу. PostgreSQL с нуля и переезд в Берлин оставляют search_query ровно новым самостоятельным вопросом даже при старой Day18/SQLite памяти и anchor. Exact public5/all5/all12 и explicit day/date остаются покрыты;24 saved replay повторён офлайн, provider/SSH0.
