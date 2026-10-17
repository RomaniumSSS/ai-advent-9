# Day34 — состав публикации кода

Код опубликован 17.10.2026: [Код на GitHub](https://github.com/RomaniumSSS/ai-advent-9/tree/day34-project-files/day34),
[commit `3f1a8d7`](https://github.com/RomaniumSSS/ai-advent-9/commit/3f1a8d749b7cfdfe97e50533dd60dc921f320c61). Commit/push выполнены; remote SHA проверен координатором.
Пользовательская приёмка результата остаётся отдельно.

Включены runtime/UI, mock, офлайн-тесты, синтетические исходные и robustness fixtures,
сценарий/скрипты демонстрации, SPEC/TASKS и компактные офлайн evidence/reviews.
Корневые зависимости уже определены в pyproject.toml/uv.lock; инструкции — README.md.

Исключены ledger/SQLite, .env/ключи, actions/session logs, скрытые рассуждения,
полные live responses/traces/sandbox runs, raw outputs, MP4/WebM/PNG и остальные
медиа. Локальные evidence в RESULT/RELEASE_NOTES явно помечены и отсутствуют
в свежем клоне. Новые live-запросы при подготовке публикации не выполнялись.
Видео опубликовано отдельно от Git: [Видео Day34, 109,4 с](https://drive.google.com/file/d/18lbaa5uEtTr8i0UGHyS-F6Um3KCVALDO/view?usp=sharing).
Координатор проверил UI-загрузку и доступ «все, у кого есть ссылка — читатель».
Локальный исходник: 3 272 378 байт, SHA256
`314857970899b4e6a9f3e9faccb2f78ce0fda0c030847dd6602c986764e36b6b`.
Это метаданные локального исходника; cloud hash не проверялся.
Таблица, строка 132: заполнение координатором в процессе; пользователь проверит
результат самостоятельно, независимая приёмка таблицы не заявляется.
Root todo/HANDOFF и другие дни не входят в stage.

Проверки 17.10.2026: macOS, uv Python 3.12.12; offline application 13,
robustness 10, recorder 3 PASS. Проверки выполняют реальные временные файловые
операции и loopback HTTP со scripted/mock моделью, а не live-provider.
Тот же экспорт из Git index (без локальных ignored/untracked artifacts):
26 tests PASS, mock runner обеих целей PASS, browser mock dry PASS
(Playwright + локальный Chrome; запись медиа и live не запускались).

Секреты: staged-content scan на private-key blocks/provider keys/AWS keys — 0;
проверка запрещённых путей — 0. Значения секретов не выводились.

Точный allowlist (плюс этот PUBLISH.md):

- `day34/.gitignore`
- `day34/PREP.md`
- `day34/README.md`
- `day34/RELEASE_NOTES.md`
- `day34/RESULT.md`
- `day34/SPEC.md`
- `day34/TASKS.md`
- `day34/budget.py`
- `day34/core.py`
- `day34/fixtures/README.md`
- `day34/fixtures/src/api.py`
- `day34/fixtures/src/cli.py`
- `day34/fixtures/src/service.py`
- `day34/mock_model.py`
- `day34/model.py`
- `day34/results/robustness-astra-fixes.json`
- `day34/results/robustness-offline.json`
- `day34/results/robustness-review-astra.md`
- `day34/results/robustness-review-luna.md`
- `day34/robustness/fixtures/ambiguous/README.md`
- `day34/robustness/fixtures/ambiguous/alpha/api.py`
- `day34/robustness/fixtures/ambiguous/beta/api.py`
- `day34/robustness/fixtures/distributed/README.md`
- `day34/robustness/fixtures/distributed/adapters/delivery.py`
- `day34/robustness/fixtures/distributed/commands/bulk.py`
- `day34/robustness/fixtures/distributed/commands/signup.py`
- `day34/robustness/fixtures/distributed/lib/invitations.py`
- `day34/robustness/fixtures/distributed/notes/example.txt`
- `day34/robustness/live-manifest.json`
- `day34/robustness_runner.py`
- `day34/static/index.html`
- `day34/test_day34.py`
- `day34/test_robustness.py`
- `day34/video/SCENARIO.md`
- `day34/video/run_demo.py`
- `day34/video/runner.py`
- `day34/video/test_run_demo.py`
- `day34/web.py`
