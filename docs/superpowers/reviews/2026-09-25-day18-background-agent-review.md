# Независимый review SPEC Day 18 — 25.09.2026

## Объект и источники

- Тип: нормативная **SPEC-кандидат**, проверка готовности к Implementation Plan; реализация, тесты и запуск сервисов в scope review не входят.
- Артефакт: [`../specs/2026-09-25-day18-background-agent.md`](../specs/2026-09-25-day18-background-agent.md), SHA-256 `01850df4f9f2a0d4f910068abca64ce3df948de17655fb83842c6e4eb19eeccd`.
- Авторитетное требование: [`../../day18-requirements.md`](../../day18-requirements.md), SHA-256 `42262250d987d735fe45056bb7c1d696ab7c0a6ad6ad38611477ec58ec3df7e4`; текущий запрос на review; переданные пользователем AGENTS.md instructions; локальные `CLAUDE.md`, `todo.md`, `HANDOFF.md`. Git HEAD `e1ad49df8815db94589327c1deb766346db399ce` (`RomaniumSSS/day18-background-scheduler`). Day 17 SPEC и соответствующие `day17/agent.py`, `tool_calling.py`, `store.py`, `mcp_client.py`, `base_agent.py`, `models.py` просмотрены как свидетельство существующего подхода, не как контракт Day 18.
- `SPEC_REVIEW.md` отсутствует в этом worktree, дереве `main` (`81f3149f32283f25d92283bffecdb4d820e4c69a`) и доступной Git history по этому имени. Его возможные проектные критерии **NOT PROVEN**; подменять их предположениями нельзя. Применён rubric `artifact-review/references/spec-review.md`.
- Внешняя документация подтверждает, что [Хабр предоставляет RSS результатов поиска и параметр `limit=100`](https://habr.com/ru/docs/help/lenta/), а [Telegram `sendMessage` возвращает `Message` и ограничивает текст 4096 символами](https://core.telegram.org/bots/api#sendmessage). Эти страницы не доказывают корректность закреплённого в SPEC search URL, доступ с VPS или реальную доставку.

## Модель отказов для этой SPEC

Правдоподобный happy path может скрыть: (1) потерю подготовленного отчёта между двумя durable операциями; (2) «успешную пустоту» после отбрасывания неполных RSS items; (3) двойную публикацию одних observations при конкуренции старого retry и нового backlog report; (4) неполный feed, ошибочно объявленный полным; (5) смену адресата или политики через RSS/model output; (6) неизвестный исход Telegram, ошибочно приравненный к delivered либо автоматически повторённый. Проверка ниже сопоставляет требования, failure paths и acceptance с этими рисками.

## Findings

### BLOCKER B1 — committed report может застрять до `REPORT_READY`

**Место и evidence:** SPEC §«Coverage, выбор материалов и отчёт», строка 138, требует сохранить report+membership одной транзакцией; §FSM, строки 149–150, допускает переход `REPORT_PENDING → REPORT_READY` только отдельно и разрешает crash-resume из `REPORT_PENDING` лишь пока второй model call не начат. §«Расписание…», строка 31, запрещает третий model call. **Сценарий:** LLM2 уже израсходован, report+membership committed, процесс падает до перехода FSM. После рестарта run остаётся `REPORT_PENDING` с существующим `UNIQUE(run_id)` report, а разрешённого правила «проверить сохранённый валидированный report и завершить переход» нет. A09 проверяет recovery «после обоих» состояний, но не это межоперационное окно. Требование о durable отчёте и восстановимом отказе может не выполниться при прохождении всех названных критериев. **Минимальное исправление:** потребовать атомарный commit report+membership+transition `REPORT_READY` либо явную идемпотентную promotion уже сохранённого report по hash/evidence без повторного model call; добавить crash injection именно между этими шагами.

### BLOCKER B2 — ошибочные RSS items разрешают ложный `success_no_matching_cases`

**Место и evidence:** output enum и семантика в строках 68, 109; eligibility gate в строке 136; A07 в строке 192. SPEC относит к `success_no_matching_cases` новые элементы, не прошедшие gate из-за отсутствия валидного article ID/link или «профильной связи», тогда как semantic case classification происходит только позже у модели (строка 138). **Сценарий:** в RSS есть новый текст о практическом кейсе, но сломан `link`; tool возвращает успешный «нет подходящих», не передав этот материал на классификацию. Это дефект данных/охвата, а не доказательство отсутствия кейсов; `A07` проверяет различимость статусов, но не запрещает этот ложный success. Противоречит требованиям `day18-requirements.md:35–41` честно различать отсутствие кейсов и ошибку/частичность чтения. **Минимальное исправление:** для недостоверных/непригодных items фиксировать partial или source error с отдельным счётчиком и evidence; tool-status не должен утверждать отсутствие matching cases на основании syntactic gate. `no_confirmed_cases` оставлять итогом модельной классификации валидных кандидатов; добавить fixture «релевантный item без link/ID».

### BLOCKER B3 — старый retry и новый backlog report могут доставить одни observations дважды

**Место и evidence:** строка 136 включает ещё не доставленные observations прежних failed/partial slots в кандидаты нового отчёта. Строки 155–156 допускают безопасный retry старого immutable report после `FAILED_BEFORE_SEND`/`DELIVERY_FAILED`. Строки 142 и 159 блокируют новые sends и резервируют membership лишь для `DELIVERY_UNKNOWN`; общего ownership/reservation для иных уже созданных reports нет. **Сценарий:** отправка report D1 получает definitive failure; D2 включает observations D1 и сохраняет новый report; позднее оператор повторяет D1. Даже при одном sender и упорядочивании по slot обе immutable payload могут быть отправлены, поскольку локальные guards каждого report не запрещают пересечение membership. Если D1 отправить первым, D2 уже нельзя безопасно изменить без указанного правила invalidation/rebuild. A02/A10 проверяют concurrency и unknown, но не этот сценарий. **Минимальное исправление:** выбрать один взаимоисключающий путь для observations опубликованного report — retry старого payload или перенос в backlog; определить durable ownership, что делать с уже подготовленным более новым report, порядок release очереди и монотонность checkpoint; проверить последовательности `failed → next report ready → old retry/new send` и restart. Ветка `DELIVERY_UNKNOWN` уже имеет полезную reservation и не должна быть ослаблена.

### SHOULD FIX S1 — контракт модельного draft остаётся неполным

**Место и evidence:** строка 138 перечисляет поля draft и обещает strict schema/grounding, но не задаёт типы, обязательность, пределы и совместимость `outcome` с категориями `confirmed_described_case`/`possible_case`/`no_confirmed_cases`; в отличие от полного tool input/output schema (строки 38–107). A07/A11 могут пройти при разных несовместимых представлениях пустого итога, attribution и full selected membership. **Направление:** добавить нормативный минимальный draft contract или таблицу полей/условных invariants и acceptance на несовместимые combinations; точную библиотеку/SDK оставить Plan.

### SHOULD FIX S2 — счётчики current feed и backlog не разведены

**Место и evidence:** `eligible_candidates` и `omitted_candidates` в output schema имеют максимум 100 (строки 75–84), но кандидаты в строке 136 включают накопленный backlog из предыдущих slots, который может превысить 100. Не ясно, считают ли поля только текущий feed либо полный пул перед лимитом 40, и как report отражает backlog/partial analysis. **Направление:** разделить current-feed и report-pool counts, указать source slot/period для backlog и поведение при превышении 100; проверить длительную серию failed/partial slots.

### SHOULD FIX S3 — выход очереди после operator resolution требует наблюдаемого условия

**Место и evidence:** строка 142 обещает отправку очереди по slot order после решения unknown, но обычный cron для существующего run лишь возвращает статус (строка 30); не сказано, какое событие запускает готовый report и как обрабатывается старший `REPORT_READY` после quarantine/resolution. **Направление:** зафиксировать trigger/lease selection и acceptance на `unknown → operator resolution/quarantine → oldest ready send` без второго model/MCP call. Это не заменяет ownership fix B3.

### NOT PROVEN N1 — недоступен запрошенный проектный rubric

`SPEC_REVIEW.md` не найден в названных источниках. Соответствие его возможным дополнительным правилам не установлено. Если он существует вне checkout, нужен именно этот файл и повторный review; его отсутствие не отменяет доказанные B1–B3.

### NOT PROVEN N2 — закреплённый RSS profile и live integrations

`docs/day18-requirements.md:20–23` оставляет конкретный поиск/coverage на выбор SPEC; SPEC строка 15 фиксирует одну поисковую фразу и признаёт, что это узкая выборка. Официальная документация поддерживает RSS поиска, но точный URL, сортировка, sample coverage для реальных бизнес-кейсов, доступ с VPS, реальная модель и Bot API не проверялись в этом read-only review. SPEC корректно ставит их в launch gates (строка 203). Если профиль окажется непригодным, до Plan/реализации его нужно версионированно пересмотреть, а не незаметно заменить в runtime.

## Traceability

| Upstream требование | Required behavior / failure path в SPEC | Acceptance | Вердикт |
|---|---|---|---|
| R01: cron → агент на VPS, 18:00 Warsaw (`requirements:8–10,19`) | `spec:21–32,140–159`; DST, missed slot, backfill | A01–A02 | OK на уровне SPEC; live A01 ещё не доказан |
| R02: модель выбирает MCP, harness валидирует и возвращает observation (`requirements:11–14,30–32`) | `spec:21–25,34–109`; один call, linked result | A03–A05 | OK на уровне SPEC |
| R03: RSS+SQLite aggregate, durable/repeat-safe (`requirements:13–14,33–34`) | `spec:111–136`; atomic batch, identity, coverage | A06–A07 | BLOCKER B2; SHOULD FIX S2 |
| R04: бизнес-кейс против гайда/рекламы, attribution (`requirements:20–23,35–37`) | `spec:136–138`; semantic classification только моделью | A07, A11 | BLOCKER B2; SHOULD FIX S1; profile NOT PROVEN N2 |
| R05: честные empty/partial/error и восстановление (`requirements:38–41`) | `spec:109,130,134,140–159` | A07, A09–A10 | BLOCKER B1–B2 |
| R06: фиксированный Telegram recipient, unknown не delivered (`requirements:24–26,40–44`) | `spec:142,157–165`; config fingerprint, receipt gate | A08, A10, A12, A14 | BLOCKER B3 на failed/retry; unknown guard OK; live N2 |
| R07: Day 18 отдельно от Day 17 (`requirements:45–47`) | `spec:5,13,17–25` | A13 | OK; Day 17 является примером, runtime reuse не предписан |
| R08: код и видео расписания (`requirements:15`) | `spec:182–203` | A01, A03, A14 | OK как будущий gate; evidence пока нет |

Непокрытые upstream rows: нет полностью пропущенных; B1–B3 показывают, где заявленное покрытие не доказывает нужный инвариант. Материальных orphan requirements вне Day 18 не найдено: SQLite/FSM/лимиты — выбранные механизмы этой SPEC, а не требования Day 17.

## Подтверждённые сильные проверки

- **OK:** model/tool/harness границы, запрет произвольного URL/SQL/recipient, локальная валидация и linked result отражают Day 17 принцип без копирования его Git-only runtime (`spec:17–25,34–58`; `day17/agent.py:269–430`, `day17/tool_calling.py:119–187`).
- **OK:** batch identity, commit-before-success и reconciliation по тому же key явно покрывают MCP timeout после commit (`spec:121–130,173`).
- **OK:** для Telegram `SENDING` предшествует request, unknown не становится delivered и не resend автоматически; `message_id` требуется как receipt, а не как доказательство чтения (`spec:151–163,177–180`).
- **OK:** частичное окно RSS, 100-item cap, 40-candidate analysis и невозможность объявить «ничего нет» при partial coverage названы явно (`spec:109,132–138`).

## Готовность

**3 BLOCKER, 3 SHOULD FIX, 2 NOT PROVEN. SPEC пока не готова к Implementation Plan.** Сначала устранить B1–B3 и обновить acceptance на их failure sequences; затем повторить review точной новой версии. `SPEC_REVIEW.md` остаётся недоступным авторитетным входом для запрошенного quality gate. Код, модель, VPS, RSS endpoint и Telegram не запускались; вывод относится к тексту SPEC и указанным read-only источникам.
