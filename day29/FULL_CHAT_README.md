# Полный локальный чат Day29

Обычные вопросы по всему доступному снимку архива, продолжения разговора и
сохранённая локальная история. Новый экран: **http://127.0.0.1:8070**.
Исходный public benchmark на 8069 и его результаты остаются отдельной поставкой.
Контракт — [FULL_CHAT_SPEC](FULL_CHAT_SPEC.md), этапы — [FULL_CHAT_TASKS](FULL_CHAT_TASKS.md).

Из корня worktree `day29-full-chat`, ветка `day29-full-index-chat`:

```sh
python3 day29/full_chat.py --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1
```

Вход — неизменный read-only индекс: **724 чанка / 663 документа**, включая
24 assignment, 694 discussion и 6 personal_note. Это доступный снимок,
обновления Telegram автоматически не загружаются. Упоминание дня не исключает
обсуждения или заметки без day; семантический и лексический поиск выполняются
заново при каждом вопросе. Для ответов передаётся до пяти релевантных целых чанков.

Модели — установленные `qwen3:8b` Q4_K_M и `qwen3-embedding:0.6b`, только
Ollama `127.0.0.1:11434`. Отдельный начальный chat-профиль: temperature=0,
num_ctx=8192, num_predict=1024, think=false; embedding options/digest прежние.
Это настройки нового чата, а не повторная оценка benchmark-профилей.
Общий lock сохраняет совместимость Day28/29; параллельный запуск показывает busy.

История хранится в `day29/private/full-chat/`: conversations и полные receipts,
включая фактический payload, источники, raw response, индекс/model/digest и timings.
Каталоги 0700, файлы 0600, записи атомарные, папка игнорируется Git.
В prompt входят максимум три последние завершённые пары реплик. При нехватке
бюджета сначала удаляются старые пары из активного контекста, затем целые менее
релевантные источники. Сохранённая история остаётся на диске; текущий вопрос
не обрезается. Автоматических сводок и поиска по старым разговорам нет.

Короткое продолжение использует тему предыдущего пользовательского вопроса
для нового поиска по архиву. Самостоятельный вопрос о новом предмете и явная
«Новая тема: …» имеют приоритет. При неясном участнике/отсутствующем anchor чат
просит уточнение. Это детерминированный resolver с ограниченными языковыми
правилами; предыдущий ответ ассистента помогает понять диалог, но не подтверждает
факты архива. Наиболее надёжная смена темы — самостоятельный вопрос или явный маркер.

«Новый разговор» создаёт другой ID. «Сбросить текущий» очищает историю этого
разговора и меняет epoch. Уже отправленный локальный inference завершается
самостоятельно; поздний результат остаётся в приватном receipt, а в сброшенный
разговор не возвращается. Неоконченный ход после перезапуска становится
interrupted и автоматически не отправляется повторно. Timeout, length,
некорректный JSON или refs показываются ошибкой; скрытых retries нет.

Источники каждого ответа привязаны к его request ID. Раскрываемый блок показывает
оригинальный текст, тип, document/chunk ID и части с автором/датой по исходным
members/source_sections и пересечению offsets. Автор/дата не генерируются моделью;
непокрытые и неоднозначные участки обозначаются неизвестными. Валидные ссылки
подтверждают техническую связь с переданным контекстом. Смысловую поддержку
фактов код автоматически не оценивает — UI показывает это отдельно.

HTTP bind фиксирован на 127.0.0.1:8070, Host/Origin проверяются. API принимает
свободный вопрос до 500 символов и conversation ID, параметры/пути/файлы через
HTTP не передаются. Источники и история рендерятся через textContent; инструкции
в архиве передаются как недоверенные данные. Все runtime запросы — loopback,
без proxy/redirect/cloud fallback, новых весов или переиндексации.

Для программного клиента:

| Метод / маршрут | Payload / результат |
| --- | --- |
| GET `/api/state` | all scope, индекс/настройки, active request |
| GET `/api/conversations` | ID, дата обновления, число ходов |
| POST `/api/conversations` | `{}` → новый разговор |
| GET `/api/conversations/{id}` | сохранённые ходы и ответы |
| POST `/api/ask` | `{"conversation_id":"…","question":"…"}` → 202, новый request ID |
| POST `/api/reset` | `{"conversation_id":"…"}` → очищенный разговор |
| GET `/api/requests/{request_id}` | состояние/ответ текущего сохранённого хода |

Raw responses и provider payload не выдаются HTTP; приватные оригинальные
источники доступны в локальном source panel. Reset убирает ссылки на старые
receipts из API истории, сами receipts остаются для диагностики.

Проверки:

```sh
python3 -m unittest discover -s day29/tests -p 'test_full_chat*.py' -v
uv run --offline --no-project --with playwright python day29/tests/full_chat_browser.py
```

Первое — **28 synthetic/offline tests**: все source types, offsets/ambiguity,
follow-up/topic switch/ellipses, context budget, refs/JSON/length/timeout/busy,
private permissions/atomic failures/restart/reset/new и HTTP boundaries.
Браузерный helper использует временный loopback сервер с синтетическим Engine:
desktop/tablet/mobile, reload, pending/error/unknown, new/reset, text-only XSS и
контролируемые задержанные conversation/bootstrap ответы. Ollama и настоящий
корпус в helper не используются. Evidence/screenshot сохраняются private.

Значимые RED→GREEN: [первый RED](tests/full-chat-tdd-contract-red.txt),
[HTTP RED](tests/full-chat-tdd-http-red.txt), [storage RED](tests/full-chat-tdd-storage-red.txt),
[смена темы RED](tests/full-chat-tdd-topic-switch-red.txt),
[ellipses RED](tests/full-chat-tdd-ellipses-red.txt),
[UI race RED](tests/full-chat-tdd-ui-race-red.txt),
[bootstrap RED](tests/full-chat-tdd-bootstrap-red.txt),
[focused GREEN](tests/full-chat-offline-green.txt),
[доказательства и source hashes](tests/full-chat-offline-evidence.json).

Root отдельно проверил loader на исходном immutable индексе и совместимость
прежних 45 тестов. Три новых реальных запроса дали завершённый JSON, валидные refs
и поддержку фактов исходными источниками: discussion, его follow-up и personal_note.
Первый ответ раскрыл 2 из 3 ожидаемых деталей; follow-up и заметка были полными
в рамках выбранных случаев. Это ограниченная агентская проверка, без оценки
общей точности модели и без человеческой приёмки. См.
[безопасный live summary](full-chat-results/live-summary.json) и
[итоговый full-chat отчёт](FULL_CHAT_RESULT.md).
Обязательное независимое Astra ревью и итоговые статусы фиксируются отдельными
артефактами; успешные offline тесты сами по себе их не заменяют.
