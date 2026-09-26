# Третий независимый review SPEC Day 18 — 25.09.2026

## Объект и границы проверки

- Тип: нормативная SPEC-кандидат; проверяется готовность текста к отдельному Implementation Plan, а не соответствие ещё не написанной реализации.
- Объект: [`../specs/2026-09-25-day18-background-agent.md`](../specs/2026-09-25-day18-background-agent.md), SHA-256 `df1b53c1a684cbee17c15cb424f6e9529e14d53eabed0fe635f36584f6a5875a` (214 строк). Предыдущие reviews относятся к другим версиям: [v1](2026-09-25-day18-background-agent-review.md) — `01850df4…`; [v2](2026-09-25-day18-background-agent-review-v2.md) — `faac2975…`.
- Авторитетные входы: [`../../day18-requirements.md`](../../day18-requirements.md), SHA-256 `42262250d987d735fe45056bb7c1d696ab7c0a6ad6ad38611477ec58ec3df7e4`; переданные AGENTS.md instructions; `CLAUDE.md`; текущие `todo.md` и `HANDOFF.md` как контекст, а не доказательство работы; Day 17 SPEC и релевантные `day17/agent.py`, `tool_calling.py`, `mcp_client.py`, `store.py`, `test_tool_calling.py`, `test_mcp_protocol.py` как свидетельство существующего loop. Git HEAD `e1ad49df8815db94589327c1deb766346db399ce`; Day 18 ещё не реализован.
- Запрошенный `SPEC_REVIEW.md` отсутствует в worktree и локальном `main` (`81f3149f32283f25d92283bffecdb4d820e4c69a`): его возможные дополнительные критерии **NOT PROVEN**. Применён полный `artifact-review/references/spec-review.md`. В этом review не выполнялись модельные, сетевые, VPS или Telegram-вызовы; код и старые артефакты не менялись.

## Модель отказов

Проверены окна crash между batch/report/dispatch, ложные empty/no-cases при битых или недатированных RSS items, застревание 40 нерелевантных статей, двойное владение статьёй у старого retry и нового отчёта, потеря пустого ready report, повтор Telegram после неизвестного исхода, расхождение лимитов с обязательным draft, смена источника/адресата через модель и незаметный перенос Day 17 runtime.

## Findings

**BLOCKER: 0.** В проверенном тексте нет продемонстрированного противоречия или непокрытого основного требования, которое запрещало бы перейти к планированию.

### SHOULD FIX S1 — ёмкость полного draft при крайних допустимых входах не определена

**Место:** SPEC:32,95–105,140,144; A05/A11 (200–206). Tool result ограничен 32 KiB, модель получает до 40 кандидатов с excerpt до 1000 символов, а draft обязан вернуть запись для *каждого* переданного кандидата в пределах 2000 output tokens. Сорок записей с обязательными UUID, category, evidence refs, summary и metric claims могут не поместиться в output budget; сорок длинных RSS excerpts не поместятся в tool-result budget. SPEC требует помечать обрезанный result `partial_coverage`, но не определяет, как выбрать уменьшенный `model_seen`, чтобы полный обязательный draft оставался возможным и старый backlog продвигался. **Риск:** валидный плотный feed может систематически завершаться `FAILED_AFTER_DATA`, а fixture с короткими guide-записями этого не обнаружит. **Минимальное уточнение:** задать допустимое сокращение candidate set с сохранением приоритета и `analysis_omitted`, либо согласовать лимиты; добавить максимальные по длине fixtures и проверку серии до появления нового кейса. Это вопрос работоспособности на границе, а не доказанная невозможность всех выпусков.

### SHOULD FIX S2 — acceptance не совмещает пустой ready report с восстановлением dispatcher

**Место:** SPEC:148 явно предписывает отправлять oldest sendable report даже при пустом membership и запускать dispatcher при каждом старте entrypoint; A07, A09, A10 (202–205) проверяют empty outcome, crash recovery и очередь по отдельности. **Риск:** реализация может пройти перечисленные проверки и пропускать нулевую сводку после crash или снятия старшего gate. **Минимальное уточнение:** одна integration fixture `success_empty/все out_of_profile → REPORT_READY с пустым membership → crash до dispatch → следующий entrypoint → один send без model/MCP`, затем аналогичный queue release после operator resolution.

### SHOULD FIX S3 — класс доказательства для retry после неизвестной отправки стоит назвать однозначно

**Место:** SPEC:32,162–163,169; A12 (207). Основное правило безопасно: 5xx, timeout, UI absence и отсутствие receipt не разрешают повтор; общий cap — два persisted attempts. Однако выражение `Telegram-side proof of non-delivery/no receipt` в строке 162 можно прочитать как «нет receipt» при том, что строка 169 это прямо исключает. **Риск:** операторский интерфейс или тест могут по-разному трактовать admissible evidence для перехода `DELIVERY_UNKNOWN → DELIVERY_FAILED`. **Минимальное уточнение:** убрать `/no receipt`, перечислить допустимый внешний proof или оставить unknown в quarantine при отсутствии такого proof; в A12 явно отказать retry при одном лишь отсутствии receipt.

### NOT PROVEN N1 — дополнительный проектный rubric недоступен

Соответствие возможным правилам `SPEC_REVIEW.md` не установлено: файл не найден ни в worktree, ни в локальном `main`. Это ограничение полноты запрошенного quality gate, а не дефект обнаруженного текста.

### NOT PROVEN N2 — интеграции и пригодность RSS profile

Точный RSS URL, сортировка/охват, ответ с VPS, реальный выбор MCP моделью, расписание и Bot API receipt не проверялись в read-only review. SPEC:15,192,214 относит эти проверки к будущим integration/launch gates и не утверждает, что они выполнены. Отсутствие live evidence до реализации само по себе не блокирует написание Implementation Plan.

## Traceability

| Входное требование | Поведение / отказ в SPEC | Acceptance | Итог |
|---|---|---|---|
| R01: cron, VPS, 18:00 Warsaw (`requirements:8–10,19`) | 21–32,146–165: slot, DST, lease, backfill, restart dispatcher | A01–A02,A09 | OK текст; live N2 |
| R02: модель выбирает MCP, harness исполняет и возвращает result (`requirements:11–14,30–32`) | 19–25,34–111: auto, strict schema, linked result, no worker fallback | A03–A05 | OK; крайние бюджеты S1 |
| R03: RSS aggregate, SQLite, repeat-safe (`requirements:13–14,33–34`) | 111–140: batch, canonical article, idempotency, undated batch, coverage | A06–A07 | OK; S1 на большой выборке |
| R04: кейс против гайда/рекламы, ссылки и attribution (`requirements:20–23,35–37`) | 127–129,140–144: все model-seen классифицированы, out-of-profile отдельно, dispositions durable | A07,A11 | OK; профиль N2 |
| R05: честные empty/partial/error и recovery (`requirements:38–41`) | 111,138,144,148–165: no false success, atomic report, empty dispatch | A07,A09–A11 | OK контракт; объединённый тест S2 |
| R06: фиксированный Telegram, unknown не delivered (`requirements:24–26,40–44`) | 30–32,129–132,148,157–169: ownership, global gate, ≤2 attempts, proof, receipt | A08,A10,A12,A14–A15 | OK контракт; формулировка S3; live N2 |
| R07: самостоятельный Day 18 (`requirements:45–47`) | 5,13,17–25: только принцип Day 17, без runtime import | A13 | OK |
| R08: рабочий код и видео по расписанию (`requirements:15`) | 192–214: mock/live/VPS/Telegram evidence раздельно | A01,A03,A14 | OK как будущий критерий; N2 |

Полностью непокрытых upstream требований и материальных orphan requirements не обнаружено. SQLite/FSM/лимиты являются явно выбранным способом выполнить Day 18; Day 17 не становится скрытой зависимостью.

## Подтверждённые исправления и другие OK

- **OK, v1 B1:** report, membership, dispositions, claims и `REPORT_READY` фиксируются одной транзакцией; crash до/после commit различим (SPEC:144,155,183; A09).
- **OK, v1 B2 и v2 S2:** битый ID/link и неизвестная дата не превращаются в `success_no_matching_cases`; undated item закреплён за текущим read batch, `partial_coverage` и model candidate сохраняются (SPEC:111,126,138–140; A07).
- **OK, v1 B3:** active claim, immutable reports, retirement и global gate не дают старому retry и новому ready report владеть одной observation (SPEC:129,148,165,185; A15).
- **OK, v2 B1:** disposition каждого model-seen item durable; guide/opinion/advertisement/tool_news/not_relevant после `REPORT_READY` исключены из backlog, а relevant/omitted остаются управляемыми (SPEC:127,140,186; A11).
- **OK, v2 B2:** единый persisted cap ≤2, автоматический retry только при proven pre-send, explicit retry только после definitive rejection или доказанной недоставки; unknown не пересылается и не считается delivered (SPEC:32,130,161–163,169,187; A12).
- **OK, v2 S1:** dispatcher вызывается при каждом старте entrypoint и восстанавливает ready report после post-commit crash без новой модели/MCP (SPEC:148; A09). Пустой report тоже назван sendable, с уточнением теста S2.
- **OK:** фиксированный recipient/source, запрет произвольных URL/SQL/секретов, strict result validation и Day 17 independence согласованы с upstream и проверяемы указанными acceptance (SPEC:5,15,25,36–58,169–171,208).

## Готовность

**0 BLOCKER, 3 SHOULD FIX, 2 NOT PROVEN.** Текстовая SPEC готова быть входом для отдельного Implementation Plan по доступным требованиям и rubric; S1–S3 следует решить до реализации соответствующих веток и внести в план/acceptance. Полный запрошенный quality gate по отсутствующему `SPEC_REVIEW.md` остаётся **NOT PROVEN**. Production/сдача также не доказаны: для них нужны отдельные real-model, VPS, RSS, Telegram и human video evidence, предусмотренные SPEC.
