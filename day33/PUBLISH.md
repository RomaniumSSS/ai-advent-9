# Day33 — состав публикации кода

[Видео Day33, 68.2 с](https://drive.google.com/file/d/1CNtHo7ruiEZpUN7VGUeeQiHJGXTPJYLt/view?usp=sharing). Загрузку и доступ «Anyone with the link / Viewer»
координатор проверил через UI. Пользователь ещё должен оценить результат.
Локальный исходник: 2 133 663 байта, SHA256
`36059bf96377f913c5165dde64db934a30303e44d945602567e7d956f1ad2ae2`.
Это hash локального файла, не независимо проверенный hash облачной копии.

Код опубликован в ветке `day33-support`: [код Day33](https://github.com/RomaniumSSS/ai-advent-9/tree/day33-support/day33), [коммит `c6e54e2`](https://github.com/RomaniumSSS/ai-advent-9/commit/c6e54e2ffbb8ed0cab19393c32f3f22563933075).
Координатор подтвердил SHA в remote.
Пользовательская сдача отдельно, user_acceptance=false.

В allowlist включены:
- восемь runtime-модулей: app, budget, domain, mcp_client, mcp_server, model, transport,
  а также операторский live_robustness (сам по себе не запускался при публикации);
- static/index.html, синтетические data/crm.json, knowledge.json и robustness fixtures;
- test_app.py, test_robustness.py, test_transport.py, video/run_demo.py и test_run_demo.py;
- README, SPEC, TASKS, RESULT, RELEASE_NOTES, PUBLISH и сценарий видео;
- компактные исторические отчёты results/robustness-offline.json,
  robustness-review-luna.md, robustness-review-astra.md;
- results/live-dry-04/response-01.json: один компактный сохранённый ответ синтетической
  CRM, необходимый test_saved_successful_dry04. Это historical live evidence,
  а не новый вызов и не доказательство актуальной семантики всех ответов.

Не включены PREP/экспорт чата и персональные локальные пути, actions.jsonl,
planning-day34, ledger/SQLite, .env/credentials, session logs, hidden reasoning,
видео MP4/WebM, PNG, остальные raw responses, runs и budget snapshots.
Локальные пути к таким материалам в RESULT/RELEASE_NOTES обозначены явно;
они не обещают доступность из свежего клона. Исторические review-отчёты могут
упоминать эти локальные материалы и прежние NOT PROVEN статусы.

Приложение и основные offline-тесты используют Python 3.12+ stdlib.
Recorder использует Playwright из корневой dev-группы и Google Chrome;
запись требует ffmpeg/ffprobe. Корневой pyproject.toml не изменён.
Проверка публикации: offline unittest приложения/robustness/transport и recorder;
новые API/live/видео, VPS и Drive не выполняются. Свежая проверка 17.10.2026: 22 app/robustness/transport + 3 recorder tests PASS
в uv Python 3.12.12. Те же 25 тестов PASS в изолированной временной копии
только allowlist (без локальных runs/media/ledger). Проверка credentials и непустых
JSON reasoning/authorization/key полей не дала находок; diff --cached --check чист.
Это офлайн-проверка с loopback/stdio, mock model и fault injection; новый live
провайдер, браузер и запись при подготовке публикации не проверялись.
