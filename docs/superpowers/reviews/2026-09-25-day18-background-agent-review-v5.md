# Read-only review SPEC Day 18 — 25.09.2026

## Объект, источники и граница

- Объект — нормативная [SPEC Day 18](../specs/2026-09-25-day18-background-agent.md), SHA-256 `0e537f54a1271c14f237c2d5bed558d176fc0b2cb7c37a9f7515641490acfcaa`, HEAD `e1ad49df8815db94589327c1deb766346db399ce` в `RomaniumSSS/day18-background-scheduler`. Проверяется готовность текста к **отдельному implementation plan**, не работающий код.
- Приоритет сравнения: текущий запрос «провести ревью сейчас»; [требования](../../day18-requirements.md), SHA-256 `42262250d987d735fe45056bb7c1d696ab7c0a6ad6ad38611477ec58ec3df7e4`; подтверждённые ответы автора в `HANDOFF.md`; переданные AGENTS instructions и `CLAUDE.md`; Day 17 SPEC/source/tests только как существующий образец MCP loop. Применены `artifact-review`/SPEC rubric и `agents-best-practices` для tool boundary, FSM, безопасности и evals. Текущие `todo.md`/`HANDOFF.md` — контекст, не доказательство реализации.
- `SPEC_REVIEW.md` не обнаружен в worktree и локальном `main`; по прямому уточнению пользователя ревью проводится **сейчас** по доступным требованиям и rubric. Отсутствующий файл не считается доказанным Day 18 requirement и не ставится искусственным blocker. Если он существует вне checkout, его дополнительные правила здесь не проверены. Модель, RSS endpoint, VPS, cron, Telegram и код Day 18 не запускались.

## Модель отказов

Проверены сценарии, в которых happy path скрывает: cron-worker вместо решения модели вызвать MCP; tool без linked result; второй batch после timeout; потерю report между commit и FSM; смешение пустого RSS, отсутствия кейсов и partial coverage; повтор статьи при старом retry/новом отчёте; изменение recipient через RSS; повтор неизвестно доставленного Telegram payload; голодание new/backlog из-за лимитов; успех после обрезанного structured draft.

## Findings

**BLOCKER: 0.** При фиксированном profile `habr_ai_agents_ru_v1` не найдено доказанного противоречия с основным Day 18 flow, которое делало бы отдельный plan неверным уже сейчас.

### SHOULD FIX S1 — ёмкость полного structured draft на верхних границах

SPEC:32 ограничивает второй model call 4000 output tokens и `model_seen` десятью; SPEC:144 одновременно допускает для каждой записи `summary` до 180 символов, две пары metric fields по 150 символов и отдельный `proposed_text` до 3500 символов, требуя запись для каждого `model_seen`. В сумме допустимый по полям JSON может превысить 4000 tokens; reserve «до 1000» не является проверяемым расчётом. A11 доказывает fail-closed при truncation, но не достижимость успешного dense-feed отчёта. Это риск доступности, а не ложного успеха. Перед реализацией зафиксировать совокупный output-size budget или адаптивное правило снижения `model_seen` с тестом полного worst-case draft; либо явно принять ожидаемый `FAILED_AFTER_DATA`/backlog для плотного выпуска.

### SHOULD FIX S2 — wall-time budget при долгой очереди

SPEC:32 задаёт `≤960 s суммарно на run`, а SPEC:147–165 допускает `REPORT_READY` ждать решения `DELIVERY_UNKNOWN` дни и затем отправляться dispatcher без нового model/MCP. Не сказано, включает ли «суммарный wall time» календарное время паузы. Если включает, разрешённая очередь никогда не сможет возобновиться после 960 секунд; A10 требует обратного. Следует считать и хранить только активное execution time попыток, а возраст ожидающего report учитывать отдельно; добавить тест resolution после паузы >960 секунд. Это неоднозначность контракта, которую можно закрыть в plan до кода.

### NOT PROVEN N1 — live-источник и интеграции, не gate для текста SPEC

Точный RSS URL/сортировка/охват, выбор tool реальной моделью, cron на VPS и Telegram receipt пока не проверены. SPEC:15,212–214 относит их к integration/launch gates и не утверждает, что они уже достигнуты. Это не препятствует написанию plan, но запрещает объявлять Day 18 реализованным или готовым к сдаче.

## Traceability

| Входное требование | Контракт / отказ | Evidence | Итог |
|---|---|---|---|
| cron запускает агента в 18:00 Warsaw, не worker | SPEC:21–32,147–165; slot, DST, overlap, backfill | A01–A03,A09 | OK; live N1 |
| модель выбирает MCP, harness исполняет либо отказывает | SPEC:19–25,34–111; strict schema, linked result, budgets | A03–A05 | OK; draft capacity S1 |
| RSS/SQLite, durable idempotent aggregate | SPEC:113–140; batch commit, key replay, article identity | A06–A07,A09 | OK |
| кейсы по RSS evidence, не гайды/реклама; честная partial/empty | SPEC:111,136–144; disposition, claims, coverage | A07,A11 | OK; S1 на пределе |
| фиксированный Telegram, unknown не delivered/не resend | SPEC:128–132,147–169; receipt, claims, global gate, checkpoint | A08,A10,A12,A15 | OK; очередь S2 |
| самостоятельный Day 18, без Day 17 runtime | SPEC:5,13,17–25 | A13 | OK; `git diff --name-only -- day17` пуст |
| код, реальный запуск и видео для сдачи | SPEC:192–214 | A01,A03,A14 | критерии есть, выполнение N1 |

Полностью непокрытых upstream требований и материальных orphan requirements не найдено. Day 17 подтверждает принцип model→MCP→observation и локальные checks, но его Git tool, chat FSM и read-only ограничения не становятся контрактом Day 18.

## OK и verdict

**OK:** linked structured result предусмотрен и для отказов; tool write атомарен и replay по тому же key; `DATA_READY`/`REPORT_READY`/`DELIVERED` имеют durable guards; report claims и quarantine исключают двойную/неопределённую публикацию; RSS и модель не выбирают recipient; prompt-only правило не выдаётся за механическую защиту; mock, real-model, VPS и receipt evidence разделены.

**Итог: 0 BLOCKER, 2 SHOULD FIX, 1 NOT PROVEN (не блокирует plan). SPEC готова как вход для отдельного implementation plan по доступным источникам.** S1–S2 должны быть явно решены до реализации соответствующих веток. Это не approval к коду, deploy или Telegram: работающий Day 18 и live evidence пока отсутствуют. Отсутствие `SPEC_REVIEW.md` зафиксировано как ограничение входов, а не как причина откладывать запрошенное сейчас ревью.
