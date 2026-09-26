# Read-only cross-artifact review Implementation Plan Day 18 — 26.09.2026

## Объект, источники и предел проверки

Объект — [Implementation Plan Day 18](../plans/2026-09-26-day18-background-agent.md), SHA-256 `4e3771882773e99382e097e4bdf1bb43ffd7f5d170121704d61feb6c655535b0`, HEAD `e1ad49df8815db94589327c1deb766346db399ce`, ветка `RomaniumSSS/day18-background-scheduler`. Проверена цепочка [требования](../../day18-requirements.md), SHA-256 `42262250d987d735fe45056bb7c1d696ab7c0a6ad6ad38611477ec58ec3df7e4` → [SPEC](../specs/2026-09-25-day18-background-agent.md), SHA-256 `a4cbc925356d6287b548133cd64301919f7b4a82584552ba2f8e4ed49691172c` → план. Сопоставлен [SPEC review v6](2026-09-25-day18-background-agent-review-v6.md), SHA-256 `17cc4b302156376088f6f3a419c13053db1dfcaf9d8ba581efc235d6fbe6c24b`, и `CLAUDE.md`. Метод — `artifact-review`/plan rubric и `agents-best-practices`; fresh-context reviewer выполнил read-only проход без изменения плана. Day 17 использован только как проверенный архитектурный образец. Проектный `SPEC_REVIEW.md` отсутствует в checkout и локальном `main`, заменяющий документ не создавался.

Это аудит качества плана для **отдельного утверждения точного SHA**, не validation кода, не approval к реализации и не проверка работающего Day 18. Ни код, ни платные вызовы, ни RSS/VPS/Telegram/cron не запускались.

## Модель отказов

Проверены способы, которыми полный на вид план мог бы нарушить SPEC: второй provider call до worst-case preflight; потеря статьи без pubDate; collision manual/scheduled identity; неправильное списание многодневного downtime в active wall; batch duplicate после timeout; report или claims без атомарного commit; send после UNKNOWN; RSS prompt injection или смена recipient; платный live-прогон без оценки верхней стоимости; выдача mock evidence за реальное.

## Findings и закрытие v1

**BLOCKER: 0. SHOULD FIX: 0.** Новых доказанных противоречий и материальных пробелов в плане по доступным источникам не найдено.

Первый [read-only review v1](2026-09-26-day18-background-agent-plan-review-v1.md) относился к прежнему SHA плана `f9d711346f201d7b8654e08518b02b708af3851388efd8cbab4f1dc97f47c99e` и выявил 5 SHOULD FIX. После завершения того review сделан отдельный authoring-проход; текущий read-only review проверил их закрытие:

| Finding v1 | Исправление в текущем плане | Проверка |
|---|---|---|
| S1: P4 вызывал модель второй раз до preflight P5 | P4 заканчивается на `DATA_READY`, второй вызов закрыт до P5; P5 тестирует полный loop после preflight | plan P4–P5, A05/A11 |
| S2: missing pubDate лишь назван fixture | item с валидным ID/link сохраняется в текущем read batch с `published_at_utc=null`, partial coverage, candidate доступен модели даже после 18:00; broken ID/link — отдельный source rejection | plan P3, A07 |
| S3: manual identity без schema | `origin=manual`+`manual_invocation_id` отделены от scheduled `slot_id`, no-send guard и same-date collision test | plan P1/P7, A01/A02 |
| S4: незакрытая active phase после crash | reservation до вызова, settlement после; crash списывает bounded phase cap, не календарный downtime; test restart после `>960 s` | plan P1/P4/P6, A05/A10 |
| S5: нет pre-live cost estimate | worst-case расчёт по `MAX_TOKENS` и числу attempts до платного прогона; reported `usage.cost` отдельно от расчёта | plan P8, `CLAUDE.md` |

**NOT PROVEN N1 (не блокирует план):** реальный RSS URL/охват, provider tokenizer и tool choice, cron на VPS, Telegram receipt и видео — будущие G2–G4. План не утверждает их проверенными и не подменяет mock результатом.

**NOT PROVEN N2 (не блокирует по текущему поручению):** недоступный `SPEC_REVIEW.md` мог бы содержать дополнительные project rules; пользователь просил продолжать по доступным источникам. Если файл появится, выполнить отдельную сверку перед изменением уже утверждаемого контракта.

## Traceability требований и SPEC

| Входная группа | SPEC acceptance | Этапы плана и проверяемое evidence | Итог |
|---|---|---|---|
| R1 cron запускает агента, 18:00 Warsaw, VPS/video | A01–A03,A14 | P4/P7/P8; real-model trace, zone/cron logs, human video | OK; live N1 |
| R2 собственный MCP, validated call/aggregate | A03–A06 | P3/P4; protocol, denial, linked result, replay | OK |
| R3 durable data/report, dedup | A02,A06,A09,A15 | P1/P2/P5/P6; UNIQUE/FK, atomic commit, crash/reopen | OK |
| R4 кейсы, ссылки, claims | A07,A11 | P3/P5/P8; RSS fixtures, grounding, classifier eval | OK; live N1 |
| R5 empty/no cases/partial/error/unknown | A07,A09,A10,A12,A15 | P3/P5/P6; outcome and adapter fault matrix | OK |
| R6 fixed recipient, secrets/tool scope | A04,A08,A12 | P0/P3/P4/P6; config boundary, schemas, injection/secret scan | OK |
| R7 Day 18 standalone | A13 | P0/P7; import/path/static diff guard | OK |

Плановая матрица I01–I18 связывает каждый инвариант SPEC с этапом, компонентом, механическим enforcement, тестом и acceptance evidence; все A01–A15 имеют адресный будущий check. Непокрытых applicable SPEC items, material orphan work или неразрешённого расширения scope не обнаружено. Очередность `schema/FSM → repository → RSS MCP → harness → report → delivery → cron/VPS → live/video` соблюдена; P0 лишь создаёт самостоятельный каркас. Telegram не стал MCP-инструментом, Day 17 не импортируется, публичный endpoint и автоматический catch-up не добавлены. FSM guards и crash table сохраняют различие batch/report/send/receipt/UNKNOWN; checkpoint и claims не смешаны с source coverage. Mock/local/live evidence названы раздельно.

## Readiness

**0 BLOCKER, 0 SHOULD FIX, 2 неблокирующих NOT PROVEN. План готов к отдельному утверждению точной версии `4e3771882773e99382e097e4bdf1bb43ffd7f5d170121704d61feb6c655535b0` перед реализацией.** Даже после утверждения будущие live gates потребуют отдельного разрешения и фактических доказательств; текущий review их не закрывает.
