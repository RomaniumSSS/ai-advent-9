# Day32 — ревью PR с видимым контекстом

Самостоятельный read-only reviewer. Python stdlib + Git + SQLite FTS5;
для GitHub polling нужен авторизованный `gh`. Старые дни не импортируются.
Код PR, его тесты, hooks и инструкции из файлов не исполняются.

```sh
uv run --no-sync python day32/test_review.py
uv run --no-sync python day32/cli.py fixture --state day32/.runtime/demo
uv run --no-sync python day32/cli.py serve --state day32/.runtime/demo
```

Панель: http://127.0.0.1:8072. Она только читает отчёты и не запускает оплату.
Fixture создаёт из target отдельный локальный Git с baseline и регрессией;
его статический ответ помечен `offline fixture`. Это проверка механики,
не измерение качества Qwen и не проверка настоящего GitHub-trigger.

Для эксперимента выполните fixture с `--mode diff`, `--mode files`, `--mode rag`.
Контексты и отчёты сохраняются раздельно. При повторе того же режима/снимка
нового вызова нет. Улучшение RAG заранее не доказано.

Локальный закреплённый снимок:

```sh
uv run --no-sync python day32/cli.py local --repo /path/to/repo --base FULL_SHA --head FULL_SHA --scope day32/target --mode rag
```

По умолчанию provider — fixture. Его правило знает конкретную учебную регрессию;
для произвольных diff он не является независимым ревьюером.

## Настоящий watcher — пока не запускать без согласованного бюджета

```sh
uv run --no-sync python day32/cli.py watch --repo RomaniumSSS/ai-advent-9 --live --budget APPROVED_USD --state day32/.runtime/live
```

`OPENROUTER_API_KEY` передаётся через окружение. CLI не читает `.env` автоматически.
Нужны одновременно `--live` и положительный бюджет. Нет автоматических retries,
fallback, публикации комментариев, commit/push или merge. Watcher каждые 30 секунд
читает до 20 открытых PR; `--once` выполняет одну проверку. Git fetch хранится в
отдельном bare cache, full SHA и merge-base закрепляются до чтения blobs.
Идентичность: repository + PR + base SHA + head SHA + режим + профиль provider.
Даже незавершённый после падения запуск не оплачивается снова.

Qwen-профиль из проверенного Day31: `qwen/qwen3.8-max-0902`,
`alibaba/us-east-1`, low reasoning, 4096 output, $2/$6 за миллион input/output.
`allow_fallbacks=false`, `require_parameters=true`; urllib делает один запрос.
Резерв до запроса — верхняя оценка UTF-8 bytes входа с запасом schema/framing
и весь output ceiling. SQLite BEGIN IMMEDIATE защищает резерв от двух процессов.
Фактические cost/tokens берутся только из usage; отсутствие — null. Неизвестная
стоимость удерживает резерв, неоднозначный сбой не повторяется.
Блокировку budget нельзя обойти простым перезапуском того же снимка.

## Учебный PR

`target/git_tool.py` — новая небольшая функция по идее Day17; происхождение в
`target/docs/provenance.md`. Контракт: целое limit от 1 до 10 включительно.
`fixtures/regression.patch` применяется в отдельном fixture-repo;
`fixtures/pr-regression.patch` — тот же reviewable diff с путём day32/target/git_tool.py.
Сначала baseline должен присутствовать в целевой base-ветке; затем отдельная
регрессионная ветка меняет <=10 на <10. Здесь ветки/PR не публиковались.
Публикация baseline и regression требует отдельного поручения.

## Артефакты и ограничения

В STATE/state.sqlite3 — dedupe, статусы, резерв и reported actual.
В STATE/TRACE/ — snapshot.json (с bounded corpus), context.json,
messages.json (точные SYSTEM + user), request.json (профиль и schema без ключа), response.json (сырой ответ), report.json.
UI показывает snapshot, diff, версии файлов, docs/code sources, prompt, findings,
время, стоимость и ограничения. Findings требуют существующий changed path,
явную head/merge_base сторону, существующую строку blob и переданные IDs.
Строка также должна присутствовать в фактическом prompt после ограничений:
в полном файле, в hunk diff или в source range соответствующего SHA.
Версия merge_base для удалений/rename — merge-base, как у diff. Эти проверки не доказывают
смысловую правильность замечания; это предмет отдельной оценки.

Лимиты: diff 60KB, файл 24KB, корпус 240KB/100 файлов, prompt 110KB,
response 300KB. Поддерживаемые текстовые расширения перечислены в review.py.
Симлинки и binary blobs исключены; неполнота помечается limited.
При превышении лимитов tree (200KB) / change manifest (100KB) соответствующая
коллекция остаётся пустой с явной причиной неполноты, snapshot сохраняется.
Live corpus ограничен day32/target; изменённые файлы за пределами scope
всё равно читаются в пределах лимитов. GitHub polling ограничен 20 PR;
первый live-trigger и реальные модельные результаты ещё не проверены.
Не удаляйте ledger для повторной оплаты неясного запуска.

## Расширенная проверка и длинное видео

Пользователь разрешил две учебные ветки, PR в baseline и общий бюджет $0.50.
Дополнительные команды:

```sh
uv run --no-sync python -m unittest discover -s day32 -p 'test_*.py'
uv run --no-sync python day32/video/test_run_demo.py
uv run --no-sync python day32/eval_faults.py --state /NEW/OFFLINE/STATE
```

Всего 56 основных тестовых методов и 6 recorder-тестов; отдельно100seeded
проверок(seed320016) и9SIMULATED fault-сценариев. [Доказательства](results/offline-extension-evidence.json).
[Сценарий видео](video/SCENARIO.md), [ревью расширения Astra](results/review-extension-astra.md).
Один реальный Qwen readiness probe нашёл limit=10 ошибку; $0.006884 reported.
Это пока local snapshot, не доказательство GitHub trigger/видео.
