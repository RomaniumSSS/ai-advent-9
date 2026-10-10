# Day28 — локальная LLM + RAG

Самостоятельные UI и CLI отвечают по прежнему Structure-индексу через локальные
`qwen3-embedding:0.6b` и `qwen3:8b`. Итоговый E2E: **6/6 валидных ответов/признаний
нехватки данных**, факты подтверждены агентской оценкой; составное сравнение E02
раскрыто частично. Проверены 31 офлайн тест, отдельный dry run и новая живая запись
2:59. [Фактические результаты и ограничения](RESULT.md).

## Запуск

Нужны Python 3.10+ на macOS/Linux, Ollama на **http://127.0.0.1:11434**, обе модели с digest ниже
и подготовленный локальный снимок `day28/private/index-release-v1/`. Корпус не входит
в исходный код или кодовый архив; перенос индекса и установка моделей — подготовка,
runtime не вызывает SSH, registry/pull, облако или API-ключи.

Из корня репозитория:

```sh
python3 day28/app.py --index-root day28/private/index-release-v1 --port 8068
python3 day28/app.py --question "Что требуется сделать в задании дня 18?"
python3 day28/app.py --question "Что требуется сделать в задании дня 21?" --scope all --output day28/private/cli-all
```

UI: **http://127.0.0.1:8068**. Адрес/порт фиксированы; public охватывает только
24 assignment-документа. CLI all требует явный каталог внутри `day28/private/`
и печатает статус/путь receipt без приватного текста. SQLite открывается read-only,
векторы не пересчитываются. Соседние дни и общие зависимости не импортируются.

## Источники и ограничения

В новом E2E модель возвращает `{"answer":"…","source_refs":["S1"]}`. Контекст содержит
короткую ссылку, document_id и **полный исходный text**. Только выбранные моделью
ссылки преобразуются приложением во внешний `{answer,sources,quotes}`; quotes —
неизменённый оригинальный фрагмент, а не цитата, скопированная моделью. Неизвестные,
повторные или неверные ссылки дают error. Unknown требует пустых ссылок и признания
нехватки сведений. Найденный поиском, но не использованный источник подписан отдельно.

В receipts разделены `raw_response`, `raw_model_answer`, `source_reference_map`,
`response_format`, `citation_mode` и материализованный ответ. Проверка точности
источника не доказывает полноту и смысл всех утверждений. Автоматическое
`groundedness_semantic=null`; отдельная агентская рубрика не является человеческой приёмкой.

Public scope применяется до ранжирования. Явный день с assignment-намерением
ограничивает поиск соответствующими заданиями; отсутствующий день оставляет empty.
Общие public-вопросы и all используют векторный путь своего scope. Отбор:
0.8 cosine + 0.2 lexical coverage, threshold 0.35, top-k 5, порядок при равенстве по ID.
Явные assignment-документы обходят только порог; ограничения количества и размера
сохраняются. Не помещающийся фрагмент исключается целиком с причиной в trace.
Пустой поиск не вызывает генерацию. Недоверенные документные команды не исполняются.

| Фиксированная часть | Значение |
| --- | --- |
| Structure generation | `5d5502c69976163325ad6c35`; 724 chunks / 663 docs |
| SQLite SHA256 | `9894d937c4bcbae653459a6fe758f231992571e436622a0cd33fcda7f707f11b` |
| Corpus SHA256 | `90bae6a60fc91b8419a07a5ba445beecf95dd5701f69ea84a423a845d4dcf240` |
| Embedding digest | `ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d` |
| Embedding | 1024 dimensions; num_ctx=2048, num_thread=1, num_batch=128, truncate=false |
| Qwen3:8b digest | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| Generation | Q4_K_M; think=false, temperature=0, num_ctx=8192, num_predict=1024 |
| Limits | question 1–500 chars; Ollama timeout 300 s; no retries/redirects/env proxy |

Окно 8192 закреплено до оценочных запусков для exact replay без изменения messages.
Консервативный предел: bytes(packed(messages)) + 496 байт большой старой schema
+ 512 запаса chat-template + 1024 выхода ≤ 8192. Новая E2E schema занимает 213 байт;
единый предел намеренно выше фактического. E01/E02/E03 input bounds 3844/4814/3898,
replay Q03/Q08/Q07 — 6801/6895/5312. Это байтовая оценка, не токенизатор.
После ответа фиксируются prompt_eval_count, done=true и done_reason=stop;
length, незавершение или overflow дают error. Отсутствующие метрики — null.

## Проверки и воспроизведение

```sh
python3 -m unittest discover -s day28/tests -p 'test_*.py'
uv run --offline --no-project --with playwright python day28/tests/check_browser.py --output /tmp/day28-browser-new
python3 day28/evaluate.py --mode e2e --suite day28/eval-suite.json --repeats 2 --output day28/private/runs/e2e-new
python3 day28/evaluate.py --mode replay --suite day28/private/replay-suite.json --repeats 1 --output day28/private/runs/replay-new
```

Первые две команды — офлайн fixtures; последние две вызывают реальную локальную
модель. Каждая повторная оценка создаёт новые запросы и новый каталог. Глобальный
lock разделяет UI/CLI/replay; чужие Ollama-процессы не останавливаются. Receipts
и replay тексты остаются в игнорируемой private: каталоги 0700, файлы 0600.

[Публичный E2E-набор](eval-suite.json) и рубрика заморожены до ответов.
Replay suite содержит cases с question/messages/selected/expected/hashes и
historical_response/historical_metrics. Query embedding в replay не вызывается,
messages/hash сохраняются, **старая** трёхполевая schema и строгая проверка модельных
цитат остаются прежними (`citation_mode=model_exact_quotes`). Это отдельное сравнение
генераторов при старом retrieval; новое E2E использует `source_references_original_text`.
Исторические cloud времена не являются новым сопоставимым speed benchmark.

Evidence: [31 офлайн тест](tests/offline-green.txt),
[RED → GREEN для source_refs](tests/tdd-references-red.txt), [GREEN](tests/tdd-references-green.txt),
[responsive fixture](results/browser-references-2/results.json),
[два источника](results/browser-references-2/two-sources.png),
[unknown preview сохранённого ответа, без нового вызова](results/ui-unknown-cached-preview-1/results.json).
Кешированные Playwright/Chromium используются отдельно через uv; pyproject/lock не меняются.

## Видео и статус

[Сценарий](video/SCENARIO.md), [скрипт](video/run_demo.py),
[прогоны и проверка записи](video/README.md). Dry run и record делают по три **новых**
public-запроса, ждут конечное состояние конкретного request ID. Запись показывает
настоящий viewport, не слайды старых ответов. Произвольных private-file routes нет;
UI отдаёт фиксированные assets, public результаты и проверенную публичную сводку.

Требования/план: Astra `gpt-6-astra` high; реализация/исправления/документы:
Sol `gpt-6.1-sol` high; первое ревью: Luna `gpt-6-luna` medium;
обязательное второе: Astra `gpt-6-astra` xhigh. [Роли](results/model-routing.json).
Usage/cost разработки не предоставлены; эффективность маршрутизации не измерена.

Код и [живая запись 2:59](video/Day28-live.mp4) проверены локально:
[сверка кадров/запросов](results/video-verification.json). Код и видео [опубликованы на GitHub](https://github.com/RomaniumSSS/ai-advent-9/tree/main/day28);
Day01–28 объединены в main. [Проверка публикации](results/github-publication.json).
[Видео в Drive](https://drive.google.com/file/d/1lFO1qjeAPaiP_fJZbfWccZvht0yfb4uj/view?usp=sharing) доступно всем по ссылке (Viewer).
В `Лист1!AC132` сохранён комментарий с двумя ссылками — видео и код; проверен после reload.
[Подтверждение таблицы](results/table-submission.json). Пользовательская приёмка не заявляется. [SPEC](SPEC.md), [TASKS](TASKS.md),
[release notes](RELEASE_NOTES.md), [финальная проверка SPEC](results/implementation-validation.md).

Архив ZIP сохранён как проверенная локальная сборка до публикации; GitHub содержит
актуальные исходники и последующие записи статуса.
