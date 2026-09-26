# Повторный независимый review SPEC Day 18 — 25.09.2026

## Объект, область и источники

- Тип: нормативная **SPEC-кандидат**; проверка готовности к Implementation Plan после исправлений первого review. Код, тесты, модель, VPS и внешние сервисы не запускались.
- Объект: [`../specs/2026-09-25-day18-background-agent.md`](../specs/2026-09-25-day18-background-agent.md), SHA-256 `faac2975640e06f35536581b142815f9f9f54aa2e03bcce69c6e4169d41840b5`. Сравнение с [`первым review`](2026-09-25-day18-background-agent-review.md), который проверял SHA-256 `01850df4f9f2a0d4f910068abca64ce3df948de17655fb83842c6e4eb19eeccd`.
- Авторитетное требование: [`../../day18-requirements.md`](../../day18-requirements.md), SHA-256 `42262250d987d735fe45056bb7c1d696ab7c0a6ad6ad38611477ec58ec3df7e4`; текущий запрос пользователя; переданные AGENTS.md instructions; `CLAUDE.md`, `todo.md`, `HANDOFF.md`. Git HEAD `e1ad49df8815db94589327c1deb766346db399ce`; Day 18 находится в незакоммиченных документах. Day 17 SPEC, `day17/agent.py`, `tool_calling.py`, `store.py` и tests просмотрены как образец текущего agent/tool loop, без переноса его контракта на Day 18.
- Запрошенный проектный `SPEC_REVIEW.md` отсутствует в worktree и локальном `main` (`81f3149f32283f25d92283bffecdb4d820e4c69a`); его возможные дополнительные требования **NOT PROVEN**. Применён rubric `artifact-review/references/spec-review.md`.

## Модель отказов

Проверены сбой между report commit и отправкой, ложная «пустота» на испорченном RSS, конкуренция старого retry и нового отчёта, повторная публикация или бесконечный повтор уже разобранных материалов, несовместимые retry rules, потеря элемента без даты, неизвестная доставка, смена источника/адресата через модель и достаточность acceptance для этих путей.

## Findings

### BLOCKER B1 — нерелевантные observations могут навсегда занять backlog и скрыть новые кейсы

**Место и evidence:** SPEC:124,126–128 задаёт `UNIQUE(article_id)` для observation, per-run classification и report membership **только релевантных** observations. SPEC:139 включает в pool непоказанные в доставленных отчётах unclaimed/undelivered observations, приоритет — `oldest eligible backlog first`, лимит модели — 40. SPEC:164 освобождает после delivery только непоказанных members; нерелевантные классификации вообще не получают membership/claim. **Сценарий:** первый успешно доставленный выпуск классифицирует 40 статей как `guide`/`opinion`. Они остаются unclaimed, undelivered и не показаны в payload. Каждый следующий выпуск снова выбирает те же 40 как старший backlog. Новые релевантные статьи остаются за лимитом 40 сколь угодно долго; `A11` может показать корректные omitted counts, а все перечисленные acceptance всё же пройдут. Это нарушает цель периодически находить новые реальные кейсы (`requirements:20–23,30–37`). **Минимальная правка:** задать durable disposition для *каждой* валидно классифицированной observation: какие категории после успешного выпуска закрыты для backlog, какие остаются для доставки и когда их можно пересмотреть; исключить уже разобранные нерелевантные статьи из приоритетного backlog. Проверить последовательность `40 нерелевантных → доставленный no_confirmed_cases → новые кейсы` с restart.

### BLOCKER B2 — правила повторной отправки Telegram противоречат FSM

**Место и evidence:** SPEC:32 ограничивает Telegram одним send attempt без доказанного `pre-send failure`, SPEC:168 говорит, что только `pre-send failure` допускает bounded retry. Но SPEC:161 разрешает explicit safe retry из `DELIVERY_FAILED` после definitive API failure; SPEC:162 разрешает перевести `DELIVERY_UNKNOWN` в `DELIVERY_FAILED` по внешнему доказательству недоставки и затем тот же retry; `A15` требует сценарий failed old report retry. В обоих последних случаях request уже мог покинуть процесс, то есть `pre-send failure` нет. **Последствие:** Plan может реализовать как запрет retry, так и повтор после доказанной недоставки; оба будут ссылаться на нормативный текст, но границы безопасности и восстановления различны. **Минимальная правка:** различить автоматический retry и явный операторский retry, определить допустимое доказательство недоставки для каждого, persisted максимум send attempts на report и поведение после исчерпания. Согласовать SPEC:32,160–162,168 и `A12/A15` одной таблицей переходов.

### SHOULD FIX S1 — нет явного trigger восстановления dispatcher после post-commit crash

**Место и evidence:** SPEC:143 и :154 атомарно фиксируют report и `REPORT_READY`, но SPEC:147 запускает dispatcher «после нового `REPORT_READY`» или operator resolution; обычный cron для уже существующего run только возвращает status (SPEC:30,147). Crash сразу после commit и до запуска dispatcher оставляет готовый report без описанного немедленного trigger. Фраза «restart checks global gate» (SPEC:155) не задаёт, какой entrypoint вызывает dispatcher; `A09` проверяет durable state, но не отправку после такого crash. **Правка:** явно запускать/восстанавливать dispatcher при process start или каждом scheduled entrypoint, сохраняя single sender guard; добавить fault injection после commit до dispatch и проверить eventual send без нового model/MCP call.

### SHOULD FIX S2 — неопределённая дата публикации требует однозначного назначения в batch/pool

**Место и evidence:** SPEC:111 требует partial для повреждённой даты *in-period* элемента, а SPEC:137 сохраняет отсутствующий/невалидный `pubDate` с `published_at_utc=null` и оценивает `seen_at` как possible case. Но плановый fetch происходит после закрытия периода в 18:00 (SPEC:29–30), так что `seen_at` уже вне проверяемого интервала. Не сказано, входит ли такой элемент в текущий batch, следующий slot или отдельную очередь; возможны пропуск candidate и ложное `success_empty`. `A07` проверяет повреждённый link/ID, не эту границу. **Правка:** назначить undated item конкретному read batch независимо от ложной даты публикации, указать его допустимость для модели и точную маркировку partial/unknown; проверить fixture с отсутствующим `pubDate` на границе 18:00.

### NOT PROVEN N1 — проектный rubric недоступен

Соответствие дополнительным правилам `SPEC_REVIEW.md` проверить нельзя; наличие файла вне checkout не подтверждено. Этот review не заменяет его возможные требования.

### NOT PROVEN N2 — реальная пригодность профиля и интеграций

SPEC:15,211 сама относит сверку точного RSS URL, coverage, доступ с VPS, реальную модель и Telegram receipt к launch gates. Read-only review не доказывает их. Это не новый дефект текстовой SPEC, но вывод о production готовности пока невозможен.

## Traceability

| Upstream требование | SPEC: требование / failure path | Acceptance | Вывод |
|---|---|---|---|
| R01 — cron/VPS/18:00 Warsaw (`requirements:8–10,19`) | `spec:21–32,145–164` | A01–A02 | OK как контракт; live N2; recovery trigger S1 |
| R02 — модель сама выбирает MCP, harness валидирует (`requirements:11–14,30–32`) | `spec:21–25,34–111` | A03–A05 | OK |
| R03 — RSS+SQLite, durability/idempotency (`requirements:13–14,33–34`) | `spec:113–139` | A06–A07,A09 | B1 для долговременного отбора; S2 для undated item |
| R04 — кейс/гайд/реклама и attribution (`requirements:20–23,35–37`) | `spec:139–143,166–170` | A07,A11 | B1; profile N2 |
| R05 — честные empty/partial/error и восстановление (`requirements:38–41`) | `spec:111,137,143–164` | A07,A09–A10,A15 | S1–S2; прежние B1/B2 исправлены |
| R06 — фиксированный Telegram и unknown gate (`requirements:24–26,40–44`) | `spec:147,160–170` | A08,A10,A12,A14–A15 | B2; live N2 |
| R07 — самостоятельный Day 18 (`requirements:45–47`) | `spec:5,13,17–25` | A13 | OK |
| R08 — работающий код и видео расписания (`requirements:15`) | `spec:189–211` | A01,A03,A14 | OK как будущий gate; evidence ещё нет |

Полностью пропущенных upstream rows не найдено. B1/B2 — случаи, когда формальное покрытие не обеспечивает требуемое поведение. Orphan requirements не выявлены: SQLite/FSM/budgets — выбранные внутри Day 18 механизмы, не скрытый перенос Day 17.

## Исправления первого review и подтверждённые проверки

- **OK, прежний B1:** report, membership, claims и переход `REPORT_PENDING → REPORT_READY` теперь атомарны (SPEC:143,154,182; A09).
- **OK, прежний B2:** повреждённый in-period ID/link/date ведёт минимум к `partial_coverage`; `success_no_matching_cases` ограничен валидными элементами, семантический `no_confirmed_cases` принадлежит модели (SPEC:111,139–141; A07). Неопределённая дата остаётся отдельным S2.
- **OK, прежний B3:** active claim, retirement и global send gate не позволяют одному observation одновременно принадлежать двум sendable reports (SPEC:127–130,139,147,164,184; A15).
- **OK, прежние S1–S3:** draft contract задан в SPEC:143; current feed и report-pool counts разведены в SPEC:139; dispatcher и очередь после operator resolution заданы в SPEC:147,202.
- **OK:** строгий model-visible MCP contract, локальный guard, linked result и запрет модельного URL/recipient согласованы с Day 17 как принципом (SPEC:19–25,34–58). Unknown Telegram не считается `DELIVERED` и не пересылается автоматически (SPEC:162–168; A10,A12).

## Готовность

**2 BLOCKER, 2 SHOULD FIX, 2 NOT PROVEN. SPEC пока не готова к Implementation Plan.** Нужно устранить B1–B2 и обновить acceptance на эти последовательности; затем повторить проверку точной версии. `SPEC_REVIEW.md` остаётся недоступным дополнительным входом. Вывод относится к тексту и указанным read-only источникам, не к работающей интеграции.
