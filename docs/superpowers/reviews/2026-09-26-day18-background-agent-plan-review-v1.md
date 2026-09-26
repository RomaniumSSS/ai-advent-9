# Read-only review Implementation Plan Day 18 — v1, 26.09.2026

## Объект, scope и источники

Объект — [Implementation Plan Day 18](../plans/2026-09-26-day18-background-agent.md), SHA-256 `f9d711346f201d7b8654e08518b02b708af3851388efd8cbab4f1dc97f47c99e`; HEAD `e1ad49df8815db94589327c1deb766346db399ce`. Это независимый read-only audit **плана**, не проверка реализации. Сравнение: [требования](../../day18-requirements.md) SHA-256 `42262250d987d735fe45056bb7c1d696ab7c0a6ad6ad38611477ec58ec3df7e4` → [SPEC](../specs/2026-09-25-day18-background-agent.md) SHA-256 `a4cbc925356d6287b548133cd64301919f7b4a82584552ba2f8e4ed49691172c` → план; [SPEC review v6](2026-09-25-day18-background-agent-review-v6.md) SHA-256 `17cc4b302156376088f6f3a419c13053db1dfcaf9d8ba581efc235d6fbe6c24b`; проектный `CLAUDE.md`, текущие `todo.md`/`HANDOFF.md`, Day 17 только как архитектурный образец. Применены `artifact-review`/plan rubric и `agents-best-practices`. `SPEC_REVIEW.md` отсутствует в checkout и локальном `main`; его неизвестные правила не подменялись. Reviewer не редактировал план и не запускал код/live-интеграции.

## Модель отказов

Полный на вид план может вызвать модель второй раз до проверки ёмкости draft; потерять валидную статью из-за отсутствующей даты; столкнуть ручной и плановый run на одной дате; списать многодневный простой после crash в active wall budget; начать платные прогоны без предварительной оценки по верхней границе output tokens. Дополнительно проверены duplicate batch, unknown delivery, двойная публикация, source/recipient injection и подмена mock evidence live evidence.

## Findings

**BLOCKER: 0. SHOULD FIX: 5.**

1. **S1, порядок preflight:** plan P4 уже доводит loop до второго model call/draft и тестирует этот путь, а worst-case draft preflight и strict draft schema вводятся только в P5. При реализации поэтапно P4 может вызвать модель без обязательного guard SPEC:32,146. Закончить P4 на валидированном `DATA_READY`/typed result; второй вызов разрешить только в P5 после preflight, сохранив порядок зависимостей.
2. **S2, pubDate:** plan P3 перечисляет fixture `missing pubDate`, но не утверждает проверяемое поведение SPEC:138,A07: item с валидными ID/link и отсутствующим/невалидным pubDate после 18:00 сохраняется в текущем read batch как observation с `published_at_utc=null`, доходит до модели, coverage минимум partial, не превращается в false empty/no cases. Добавить точные assertions; broken ID/link — отдельный source rejection.
3. **S3, manual identity:** plan P1 устанавливает только `UNIQUE` scheduled slot/run, тогда как P7 обещает самостоятельный manual `no-send` без schema changes. SPEC:30 требует отдельную identity; определить её и constraint в P1, проверить manual и scheduled same date без коллизии.
4. **S4, crash accounting:** plan P4 обещает не тратить active wall budget во время persisted ожидания и не сбрасывать расход crash, но правило для незакрытой активной фазы после долгого downtime не задано. Установить консервативное **bounded** списание и fault test crash во время provider/MCP, restart через `>960 s`; иначе восстановление может ошибочно исчерпать budget.
5. **S5, платный gate:** plan P8 не закладывает требуемую `CLAUDE.md` pre-live оценку крупного прогона по потолку `MAX_TOKENS` и сверку сообщённого `usage.cost` с расчётом по прайсу. Добавить evidence и stop при превышении разрешённого бюджета; не выполнять вызов сейчас.

**NOT PROVEN: 2, не блокируют план как текст.** N1: реальный RSS URL/coverage, tokenizer/model choice, VPS cron и Telegram receipt — будущие gates P8, не mock evidence. N2: недоступный `SPEC_REVIEW.md` мог бы добавить правила; по прямому запросу работа идёт без вымышленной замены, а файл при появлении требует отдельного cross-check.

## Traceability

| Входная группа | SPEC acceptance | План/доказательство | Итог |
|---|---|---|---|
| R1 scheduled agent, 18:00 Warsaw/VPS/video | A01–A03,A14 | P4/P7/P8, live trace/cron/video | OK; N1 |
| R2 MCP и harness validation/aggregate | A03–A06 | P3/P4, protocol+denial/replay | частично S1 |
| R3 durable observations/report/dedup | A02,A06,A09,A15 | P1/P2/P5/P6, SQLite/crash | OK; manual S3 |
| R4 RSS cases/claims | A07,A11 | P3/P5/P8, fixtures/grounding/live eval | частично S2 |
| R5 empty/partial/error/unknown | A07,A09,A10,A12,A15 | P3/P5/P6, fault matrix | OK; active time S4 |
| R6 recipient/secrets/tool scope | A04,A08,A12 | P0/P3/P4/P6, config/schema/injection | OK |
| R7 independent Day 18 | A13 | P0/P7, import/path check | OK |
| project paid-run guidance | `CLAUDE.md` | P8 budget gate | частично S5 |

Все SPEC A01–A15 названы; material uncovered requirements и необоснованной новой продуктовой функции не найдено. В матрице I01–I18 плана I15/I16 требуют уточнения S1/S4. FSM states, guards, crash boundaries, global send gate, claim/checkpoint separation, idempotent MCP write, `DELIVERY_UNKNOWN` и mock/live разделение присутствуют; отсутствие кода и внешнего deployment соблюдено.

## Verdict

**0 BLOCKER, 5 SHOULD FIX, 2 NOT PROVEN.** По доступным источникам нет основания останавливать планирование как неверный продукт, но S1–S5 следует исправить до утверждения версии для реализации. Текущий review относится **только** к указанному SHA плана; после authoring нужен новый SHA и отдельный read-only review.
