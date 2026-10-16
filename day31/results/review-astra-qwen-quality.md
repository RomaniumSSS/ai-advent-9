# Второе независимое ревью Qwen 10-case runner

2026-10-16. Фактическая модель reviewer: **gpt-6-astra**. Worktree/branch: `day31-qwen-eval`, HEAD `1a9d91a0e897dfe4ed5f6a01e5831e1ffbe76431`.

**NEEDS_CHANGES для текущего комплекта критериев оценки. Код runner и offline budget/integrity механика APPROVED.** Реальные десять ответов **NOT RUN / NOT PROVEN**: прежний лимит $0.50 недостаточен; его увеличение пользователь отклонил. Ревью не разрешает платный запуск или обход ledger.

## Findings

**P2 — `eval/qwen-quality-cases-20261016.json:117`: неверное имя поля Day17 в D1 rubric.** Требуется `repository_id`, но `day17/git_mcp_server.py:31` объявляет `repository`, и строка 92 возвращает `RecentCommits(repository=...)`. `repository_id` принадлежит новому Day31. Такой gold способен поощрить смешение интерфейсов и наказать правильный ответ. Минимальный fix: «идентификатор репозитория (в исходном Day17 поле repository)»; вопрос и опубликованный корпус не менять.

**P2 — `eval/qwen-quality-cases-20261016.json`, rubric T3:** требуется `limit integer 1–10`, но фактический frozen `T3-input.json` не содержит `docs/git-mcp.md:20–26` или другой фрагмент с этим ограничением. В нём есть только `get_recent_commits(limit)` и общий перенос input_schema. Нужно явно указать в rubric: полноту конкретных ограничений оценивать относительно actual sources; их отсутствие в выдаче — retrieval limitation, не автоматически ошибка модели. Синтаксический псевдо-JSON остаётся FAIL независимо от этой оговорки. Не подмешивать ручные chunks и не менять опубликованный корпус.

Оба замечания относятся к будущей достоверности смысловой оценки, не к возможности потратить деньги. Исправленные cases должны получить новый cases fingerprint в plan; фактические questions/requests не требуют изменения.

## Закрытие исходного замечания Luna

Luna зафиксировала отсутствие self-hash untracked runner. Теперь `runner_fingerprint()` хэширует фактический файл, prepare сохраняет `runner_sha256`, execute сравнивает его до создания индекса, provider или ledger. Проверенный SHA256: `fd16528836a10d808f7f4edba887a441eefd3b32d6fd17cc0a4417ee1fb81b5b`; final plan совпадает. Исходное finding закрыто собственным чтением и тестом, а не ссылкой на заключение автора.

## Самостоятельно проверено

- Прочитан весь `qwen_quality.py`, cases, report Luna, helper suite, frozen inputs D1/T3 и связанные budget/provider/ContextSnapshot контракты. Published app/corpus не изменялись этой работой.
- Plan использует настоящий обычный retrieval top5 и MCP; temporary index не подменяет выдачу. Empty retrieval делает кейс не eligible; execute запрещает такую серию, ручных источников нет.
- В model request идут только question/sources/git_context и исходный SYSTEM; rubric/reference остаются вне prompt. Q1–Q6 совпадают с исходными, Q6/T3 с paired; всего десять разных вопросов.
- Plan читает существующую SQLite через `mode=ro`, не создаёт BudgetLedger/Provider, не читает ключ и не выполняет генерацию. Бесплатный metadata preflight есть в prepare; при моих тестах сетевого preflight не было.
- Execute проверяет runner/cases/profile/runtime/SYSTEM/schema/corpus/fresh top5/MCP/Git, затем совокупный потолок всех десяти запросов до создания provider/ledger. Абсолютный путь ведёт к прежнему ledger в day31-dev-assistant. Явный бюджет должен совпадать с существующим лимитом.
- Каждый разрешённый вызов всё равно проходит атомарный reserve прежнего provider; unknown usage сохраняет hold. При конкурирующем расходе per-call guard останавливает серию, не обходя лимит. Retry/fallback не добавлены; raw final, guards и semantic status разделены.
- Проверка внутреннего JSON T3 устанавливает синтаксис/минимальную форму, а не смысловую корректность: она честно остаётся PENDING_REVIEW.

Свежая собственная команда:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day31-dev-assistant/.venv/bin/python day31/results/qwen-quality-plan-20261016/test_runner.py
```

**10/10 PASS, 0.131 s.** Fake transport проверил десять точных отдельных requests/reserves и порядок; это не десять ответов Qwen. Проверены отказ до provider/ledger при нехватке бюджета, changed runner/context, отсутствие создания отсутствующей ledger DB и неизменность существующей при read-only чтении. Paid/API inference calls reviewer: **0**. Ключи не читались; постоянные файлы, кроме этого отчёта, reviewer не менял.

## Финансовая и фактическая готовность

Final plan: `blocked_budget`, model_calls_sent=0, eligible=10/10. Потолок серии **$0.517374**; существующий лимит **$0.50**, remaining **$0.0265093576**, known cost **$0.0163579524**, unknown holds **$0.45713269**. Рассчитанный minimum total limit **$0.9908646424** — расчёт, не авторизация на повышение. Unknown holds не объявляются нулём или подтверждённым списанием.

После исправления двух rubric finding код можно считать offline готовым. При неизменном бюджете реальные десять запросов остаются **NOT RUN**, качество Qwen — **NOT PROVEN**. Бюджетная блокировка не является дефектом runner.

## Повторная проверка исправлений D1/T3 — итоговый вердикт

2026-10-16, тот же reviewer **gpt-6-astra**. **APPROVED — только offline runner/план/критерии.** Оба P2 finding закрыты; исходное NEEDS_CHANGES и основания выше сохранены как история.

D1 теперь правильно называет идентификатор репозитория и исходное поле `repository`, разрешая ответ обычными словами без выдуманного требования `repository_id` для Day17. T3 явно отмечает отсутствие limit integer 1–10 в actual top5 как ограничение retrieval, не обязательный факт для PASS; синтаксический псевдо-JSON по-прежнему FAIL. Вопросы и model context не менялись.

Самостоятельное сравнение `final/` и `final-reviewed/` показало: все десять `*-input.json` побайтно одинаковы. В plan изменены **только** cases_sha256 и rubric_review_note; прежние request_inputs_sha256, corpus/system/schema/runtime/Git/preflight/budget сохранены. Новый cases fingerprint `e5488bb51e2d5faf9b43a39688ddf17ed57668b232c150b76d98333d60303374` совпал с текущими cases; runtime и runner fingerprints совпали с файлами. Новый план является явно обозначенной offline-копией, не новым измерением.

Свежие четыре targeted проверки с `PLAN_DIR=final-reviewed` через тот же Python старого worktree и `PYTHONPATH=.`: **4/4 PASS, 0.044 s**. Проверены неизменные десять вопросов, отсутствие rubric в actual input, ранний отказ при изменённом runner и бюджетный отказ до создания provider/ledger/preflight. Сетевых и inference API calls: **0**.

Итоговая готовность: **offline APPROVED; 10 real Qwen answers NOT RUN; semantic quality NOT PROVEN.** Лимит остаётся $0.50, aggregate ceiling не помещается, unknown holds не освобождены. По сообщению координатора дополнительные GET receipt вернули 404 без сумм; это не основание считать неизвестные расходы нулевыми. Платный execute этим заключением не разрешается, новый рейтинг качества Qwen отсутствует.
