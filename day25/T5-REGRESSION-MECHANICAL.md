# T5: повторный regression — механический результат

04.10.2026. Пользователь отдельно разрешил два новых cap$0.06, максимум24 provider calls, retries0. Это regression на прежних2×12 разнообразных сценариях, не независимый holdout. Первый live-run-01 и A1 FAIL не изменены. T5 PASS здесь не утверждается.

## Preflight и выполнение

До включения новой authorization read-only recompute подтвердил runtime codeSHA `46e75e9f89df35a2f8fd6c3f97c762e7def338e6e0ab560532065350ce589415`, scenarioSHA `2438f66008ce72ccb2f2e3c27b5e33ff86eacfbd5c049b04cf5a1a84ae650430`, frozenSHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`, отдельные scope/пустые новые ledgers/no chat-results и cap$0.06. Только после explicit user grant approved=true/USER_GRANTED. Runner GET-preflight обоих dedicated servers доPOST проверил exactSHA/scope/budget.

UI run: public12 +all12; послеpublic6 checkpoint exit2, настоящий SIGINT/restart8054 с тем же private data-dir, PID25874→26584; шестьIDs/task-state проверены, resume exit0 MECHANICAL_RUN_COMPLETE. Refresh не отправлялPOST. Никаких ambiguous/mismatch/error исходов и retries. Day24 не трогали.

| Scope | Ходы/поиски | Provider calls | Статусы | Actual cost | Tokens prompt /completion /total |
| --- | --- | --- | --- | --- | --- |
| public assignment:18 |12 /12|12|11 verified,1 model_refusal|$0.0037041368|20615 /4762 /25377|
| all frozen corpus |12 /12|12|11 verified,1 model_refusal|$0.0096072872|40012 /12517 /52529|
| всего |24 /24|24|22 verified,2 model_refusal|$0.013311424|60627 /17279 /77906|

Provider DeepInfra/model deepseek/deepseek-v4.1-flash. Cost из actual usage совпал с ledger charged; unknown0. Отказы public11/all11 касаются вопросов о timezone/SLA; semantic correctness отказов ещё оценивается. Валидатор не ослаблялся, ответы не переписывались. Остаток cap не является разрешением на дополнительные эксперименты.

## Данные, видео, оценка

Raw all только private/live-run-02; USAGE-SUMMARY.json, CODE-SNAPSHOT.json и semantic-review.csv (все критерии NOT_REVIEWED) готовы для независимого root/Astra review. Предыдущие private данные не переиспользованы. Ключ сервер читает из существующего env-file, значения не выводились/копировались.

private/live-video-02/saved-public.webm +2PNG/RECORDING.json: exit0, saved-public playback толькоGET, новыхsearches/provider0, public ledger$0.0037041368 до=после, DOM guardPASS. Publication NOT_APPROVED, fresh_search_demonstrated=false; all не входит в запись.

Остановка: согласованные24 вызова выполнены, новых provider calls не планируется. Нужен independent semantic gate всех24 ответов: goal/SQLite/формат/атрибуция, источники и отказы. Verified означает проверенную provenance, не автоматически правильный смысл. Первый FAIL остаётся историческим свидетельством; новый regression сам по себе не независимый holdout. Commit/push/deploy/publication не выполнялись.
