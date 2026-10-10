# Full chat delivery recorder — первое независимое ревью

**Вердикт: NEEDS CHANGES.** Изоляция browser context, privacy gate до передачи terminal response в UI, guards собственного CID/RID, создание отдельного каталога, `finally`-закрытие контекста и `ffmpeg -n` реализованы последовательно. До dry/record стоит усилить два gate: квалификацию dry-run и проверку фактической модели/профиля/index в receipt.

## Замечания

🔴 **[BLOCKER]** `day29/video/run_full_demo.py:38-67` — `validate_benchmark` и `validate_full` проверяют request/question/status/scope/citations и части source scope, но не сравнивают receipt/state с ожидаемой моделью, digest, profile options, index generation и DB SHA. Для full receipt доступны `model`, `digest`, `options`, `index`; для benchmark receipt доступны `profile`, `profile_sha256`, `model`, `digest`, `generation_options`, `index`, `resources`. Сейчас synthetic receipts с `wrong-model`, `wrong-digest`, изменёнными options и чужими index values проходят обе функции (`True`, воспроизведено локально). Следовательно, stale/misconfigured `/8069` или `/8070` может дать completed take, хотя видео показывает Qwen3:8b, заданные параметры и frozen index. Сверять full state и обоих benchmark state/receipts с `core` constants и соответствующим frozen profile, включая SHA профиля; отдельно проверять index generation/DB SHA до и после запросов. Добавить тесты, которые отвергают каждое несовпадение. Ресурсы проверять только для тех метрик, которые сценарий действительно показывает, и фиксировать отсутствующие значения как unavailable.

🟡 **[WARNING]** `day29/video/run_full_demo.py:132-137` — `qualify()` трактует `mode=dry-run`, `status=completed`, совпадающие actions/script SHA и длину `requests==3` как доказательство успешного dry. Она не проверяет, что все три entries относятся к ожидаемым приложениям/actions, имеют `status=done` и реальные IDs/receipts; также не проверяет privacy/page-error gates. Синтетическое воспроизведение dry-файла с `requests=[{}, {}, {}]` проходит `qualify`. Это ослабляет обязательный gate «сначала полностью успешный matching dry, затем record». Проверять по каждому действию app/profile/question, terminal `done`, неповторяющиеся request IDs и необходимые receipt/source qualification; требовать успешные privacy/UI checks. Исправить текущий позитивный unit fixture, добавив отрицательные пустой/неполный/ошибочный dry cases.

## Проверки и границы

`python3 -m unittest discover -s day29/tests -p 'test_full_demo.py' -v`: **10/10 synthetic offline tests PASS**. Дополнительные repro вызывали только `qualify`, `validate_benchmark` и `validate_full` с выдуманными объектами; ни local app API, ни Ollama, ни embedding/service endpoints не вызывались. Synthetic browser evidence прочитано, но browser helper повторно не запускал, чтобы не конкурировать за ресурсы с выполняющимся quality run.

Код и сценарий подготовлены, но actual dry/record, просмотр кадров, видео decode и source/answer assessment этим ревью не подтверждены. Review не даёт разрешения на запуск нового take; после фиксов нужны Sol changes и обязательное независимое Astra review, затем root выполняет отдельный dry и проверяет claims/кадры до record.

## Снимки прочитанных файлов

SHA-256 кода и проверочных материалов сверены после тестов и reproductions.

```text
day29/video/run_full_demo.py  57022e229e327c13069fcde7b8e453779d65b426d29ea9822a40f7a68f1f16ff
day29/video/SCENARIO-full-chat.md  35a9d9a52d309b93b4460a1459a732d5fc7a8fc9fec886512d02acdcb16cdc60
day29/tests/test_full_demo.py  2e52e4db42fc67ed019d9c592ec93602d99d5e17cf558e88dea1369da5507fe8
day29/tests/full_demo_browser.py  70bc7115b9d4a30c8bd87c24ae485d5ea1bbf89734017df1777e59f0042a380b
day29/tests/full-demo-evidence.json  b0b0c0779d82ff5580dc587a17268c4a81dcc4c7b5856c336d19e5de06eea70a
.agents/skills/ai-advent-deliver/SKILL.md  f1d3dd146c355b5ddd5547e7416e6f8614b8d77aaed6ce5f1e661af13fa76b11
.agents/skills/ai-advent-deliver/references/recording.md  1c7ebf06108bbcb0285dd81fdab83430b9d525ffd28bc957dc60485e27e1e672
```
