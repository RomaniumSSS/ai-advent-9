# Day33 — состав публикации кода

Код публикуется в ветке `day33-support`. На момент подготовки этого документа
commit/push ещё не выполнены; SHA и внешняя ссылка на видео не заявлены.
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
