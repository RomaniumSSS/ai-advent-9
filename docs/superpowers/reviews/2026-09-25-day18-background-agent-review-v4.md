# Финальный fresh-context review SPEC Day 18 — 25.09.2026

## Объект, область и источники

- Тип: нормативная SPEC-кандидат; проверяется пригодность текста как входа для отдельного Implementation Plan. Это не проверка реализации или готовности к выпуску.
- Объект: [`../specs/2026-09-25-day18-background-agent.md`](../specs/2026-09-25-day18-background-agent.md), 214 строк, SHA-256 `0e537f54a1271c14f237c2d5bed558d176fc0b2cb7c37a9f7515641490acfcaa`. Предыдущие [v1](2026-09-25-day18-background-agent-review.md), [v2](2026-09-25-day18-background-agent-review-v2.md) и [v3](2026-09-25-day18-background-agent-review-v3.md) прочитаны как история замечаний, не как доказательство качества этой версии.
- Авторитетные входы: текущий запрос; [`../../day18-requirements.md`](../../day18-requirements.md), SHA-256 `42262250d987d735fe45056bb7c1d696ab7c0a6ad6ad38611477ec58ec3df7e4`; переданные AGENTS.md instructions; `CLAUDE.md`; текущие `todo.md`/`HANDOFF.md` как контекст, не как доказательство работающего Day 18. Day 17 SPEC, релевантные source/tests сверены только как образец существующего model → MCP → observation loop. Git HEAD `e1ad49df8815db94589327c1deb766346db399ce`, локальный `main` `81f3149f32283f25d92283bffecdb4d820e4c69a`; Day 18 остаётся незакоммиченным артефактом.
- Применены `artifact-review` и его SPEC rubric, а также релевантные правила `agents-best-practices` для tool boundary, budgets, trace и eval. Запрошенный проектный `SPEC_REVIEW.md` отсутствует в worktree и дереве локального `main`; критерии этого файла недоступны. Модель, сеть, VPS, Telegram, тесты и исполняемый код не запускались.

## Модель отказов

Проверены случаи, когда правдоподобный выпуск скрывает потерю committed batch/report при crash, ложный empty/no-cases из повреждённого или недатированного RSS, голодание новых кейсов за старым backlog, повтор одного observation в старом retry и новом report, повтор Telegram после неизвестного исхода, потерю пустой сводки в очереди, превышение входного/выходного бюджета, смешение source coverage с частичным анализом, подмену source/recipient моделью и неявную зависимость от Day 17.

## Findings

**BLOCKER: 0.** В доступном нормативном тексте не обнаружено доказанного разрыва основного flow или противоречия, при котором все acceptance могли бы пройти с неверным продуктом.

### SHOULD FIX S1 — выходной budget ещё не даёт проверяемой гарантии полного draft на предельном допустимом вводе

**Место и evidence:** SPEC:32 ограничивает переданные модели candidates числом 10 и 16 KiB, поля title/excerpt байтами, а output — 4000 tokens; SPEC:140 даёт доли 5+5 и сокращение `model_seen`; SPEC:144 требует entry для *каждого* `model_seen`, допускает `proposed_text` до 3500 символов, summary до 180 и до двух metric claims с `text`/`attribution` по 150 символов; A11 (206) проверяет, что worst-case не даёт *ложного truncated success*. Уже допустимый draft из 10 entries может содержать до 7800 символов в summary/metric fields плюс до 3500 в `proposed_text`, не считая JSON, IDs и ссылок. Из этих максимальных длин и резерва «до 1000 tokens» нельзя вывести, что полный draft поместится в 4000 output tokens. Входные 16 KiB не ограничивают длину новых полей модели. **Влияние:** предельно плотный, но допустимый batch может законно завершиться `FAILED_AFTER_DATA` даже после сокращения candidates; A11 докажет fail-closed, но не работоспособность worst-case выпуска. **Минимальная правка:** определить проверяемое правило выбора `model_seen` и совокупный output budget для обязательного draft (включая `proposed_text`/claims), затем разделить в A11 две проверки: отсутствие ложного success при truncation и достижимый полный draft на максимально допускаемом наборе. Либо прямо назвать такую ёмкость best-effort и зафиксировать ожидаемый failure/backlog path.

### NOT PROVEN N1 — отсутствует проектный `SPEC_REVIEW.md`

В worktree и локальном `main` нет запрошенного rubric. Соответствие его возможным дополнительным правилам не установлено; `artifact-review` не подменяет этот вход. Это материальная неопределённость **полного запрошенного quality gate**, даже при нуле найденных BLOCKER по доступным источникам. Для закрытия gate нужен сам файл либо явное решение, что он неприменим, и повторная сверка точной версии SPEC.

### NOT PROVEN N2 — пригодность RSS profile и реальные интеграции

SPEC:15,192,214 требует отдельно подтвердить точный RSS URL/сортировку/охват, ответ с VPS, реальный выбор MCP моделью, cron и Telegram receipt. В этом read-only review такие факты не получались. Это launch/evidence gate, а не обнаруженный дефект SPEC и не основание объявлять работающий код или доставку. При изменении profile нужен указанный в SPEC version/review, а не скрытая runtime-подмена.

## Traceability

| Входное требование | Нормативный путь в SPEC: поведение → отказ/инвариант | Acceptance | Итог |
|---|---|---|---|
| R01: cron запускает агента на VPS в 18:00 Warsaw (`requirements:8–10,19`) | 21–32: slot/DST/lease/backfill; 146–165: restart dispatcher, queue | A01–A02,A09–A10 | OK текст; live N2 |
| R02: модель выбирает MCP, harness проверяет и возвращает result (`requirements:11–14,30–32`) | 19–25,34–111: `auto`, strict input/output, linked denial/result, отсутствие worker fallback | A03–A05 | OK; ёмкость draft S1 |
| R03: RSS aggregate и SQLite переживают restart/repeat (`requirements:13–14,33–34`) | 111–140: committed batch, key replay, article identity, недатированный item и source coverage | A06–A07,A09 | OK |
| R04: реальный кейс против гайда/рекламы, ссылки и attribution (`requirements:20–23,35–37`) | 127–129,140–144: broad eligibility, durable disposition, evidence refs, bounded payload | A07,A11 | OK контракт; фактический профиль N2, worst-case S1 |
| R05: честные empty/partial/error и восстановление (`requirements:38–41`) | 111,138,144,148–165: разные статусы, source/analysis separation, atomic report, empty dispatcher | A07,A09–A11 | OK |
| R06: фиксированный Telegram recipient, unknown не delivered (`requirements:24–26,40–44`) | 30–32,129–132,148–169: claims, global gate, persisted attempts, receipt/proof, checkpoint | A08,A10,A12,A14–A15 | OK контракт; live N2 |
| R07: самостоятельный Day 18 (`requirements:45–47`) | 5,13,17–25: Day 17 только образец, runtime import запрещён | A13 | OK |
| R08: рабочий код и видео по расписанию (`requirements:15`) | 192–214: раздельные mock/live/VPS/Telegram evidence и launch gates | A01,A03,A14 | Критерий есть; выполнение N2 |

Полностью непокрытых upstream требований и материальных orphan requirements не обнаружено. SQLite, FSM и локальные лимиты служат выбранными средствами для указанного Day 18, без расширения до Day 19/20. `SPEC_REVIEW.md` остаётся внешним непроверенным входом N1.

## Подтверждённые исправления и другие OK

- **OK, прежние BLOCKER v1:** batch фиксируется отдельной атомарной транзакцией, а классификации/report/membership/claims и `REPORT_READY` — следующей атомарной транзакцией (SPEC:134,144,155,183; A06,A09); повреждённые ID/link/date дают минимум partial, недатированный item остаётся в текущем read batch (111,126,138–140; A07); active ownership и retirement исключают два sendable reports с одним observation (129,148,165,185; A15).
- **OK, прежние BLOCKER v2:** `processed_out_of_scope` исключает классифицированные нерелевантные items из backlog, а доли 5+5 защищают новые (127,140,186; A11); единый persisted cap 2 согласован с FSM: automatic retry только после proven pre-send, explicit operator retry только после definitive rejection или авторитетного Telegram-side negative proof (32,161–163,169,187; A12).
- **OK, v3 S2/S3:** dispatcher вызывается при каждом entrypoint и после resolution, выбирает даже пустой ready report; A09/A10 прямо проверяют crash до dispatch и queue release для пустого membership без новых model/MCP calls (148,204–205). Отсутствие receipt или сообщения в UI прямо исключено из proof для retry (32,163,169,207).
- **OK, v3 S1 частично:** candidate cap снижен до 10/16 KiB, title/excerpt ограничены UTF-8 bytes, доли 5+5 и `analysis_omitted` заданы, truncation fail-closed (32,95–105,140,144,206). Остаётся только S1 о доказуемой ёмкости обязательного output.
- **OK:** source coverage отдельно от analysis omission (32,111,138–144), fixed source/recipient, узкий MCP contract, отсутствие секретов в model context и запрет runtime-импорта Day 17 имеют механические guards и acceptance (5,15,25,36–58,169–171,203,208).

## Готовность

**0 BLOCKER, 1 SHOULD FIX, 2 NOT PROVEN.** По доступным требованиям и rubric текст допускает подготовку отдельного Implementation Plan с явным решением S1. Однако полный запрошенный quality gate **не закрыт и статус «готово к handoff как approved SPEC» не подтверждён**: N1 материальна по пользовательскому правилу «любой material NOT PROVEN ⇒ not ready». N2 относится к последующему integration/launch gate; production и сдача здесь не подтверждаются. Вывод ограничен этой SHA-256 и перечисленными read-only источниками.
