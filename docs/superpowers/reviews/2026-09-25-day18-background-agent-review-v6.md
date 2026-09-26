# Read-only review SPEC Day 18 — 25.09.2026, v6

## Объект и источники

- Объект — нормативная [SPEC Day 18](../specs/2026-09-25-day18-background-agent.md), SHA-256 `a4cbc925356d6287b548133cd64301919f7b4a82584552ba2f8e4ed49691172c`, HEAD `e1ad49df8815db94589327c1deb766346db399ce`, ветка `RomaniumSSS/day18-background-scheduler`. Проверена готовность текста к отдельному implementation plan, не реализация.
- Авторитетные входы: текущий запрос исправить SHOULD FIX; [Day 18 requirements](../../day18-requirements.md), SHA-256 `42262250d987d735fe45056bb7c1d696ab7c0a6ad6ad38611477ec58ec3df7e4`; подтверждённые ответы автора в `HANDOFF.md`; проектные инструкции `AGENTS.md`/`CLAUDE.md`; Day 17 SPEC/source/tests как образец, не контракт. Метод — `artifact-review` с SPEC rubric и `agents-best-practices` для agent/MCP/evals.
- Проектный `SPEC_REVIEW.md` не обнаружен в worktree и локальном `main`; пользователь отдельно потребовал провести ревью сейчас. Возможные дополнительные правила недоступного файла не проверены. Код Day 18, модель, RSS с VPS, cron и Telegram не запускались. Reviewer не редактировал SPEC.

## Модель отказов

Проверены риски: успешный видимостью draft при фактической нехватке output capacity; запрет отправки после многодневной очереди из-за ошибочного wall budget; потеря/дублирование состояния после crash; повтор неизвестно доставленного payload; обход tool/recipient boundary; смешение пустого RSS с partial/error; acceptance, которое проверяет только mock и не доказывает обязательный живой agent loop.

## Findings

**BLOCKER: 0. SHOULD FIX: 0.** Новых доказанных противоречий и материальных рисков текста по доступным источникам не обнаружено.

### Закрыто S1 предыдущего review — ёмкость draft

SPEC:32,142,146 теперь ограничивает **целый** serialized draft `≤6144` UTF-8 bytes, каждое поле в JSON-escaped bytes и второй model call `≤8192` visible output tokens. Harness до второго вызова выбирает максимальный допустимый `model_seen` по worst-case JSON и tokenizer закреплённого provider; fallback `1 token/byte + 1024` оставляет `6144 + 1024 = 7168 < 8192` visible tokens. При недостатке ёмкости число кандидатов уменьшается, лишние остаются backlog; усечённый ответ отклоняется. A11 требует конструктивный max-field fixture и provider-tokenizer check, отдельно от live trace. Верхняя граница 10 кандидатов больше не обещает, что все десять всегда войдут в draft. Выбор конкретного provider и фактический tokenizer — будущий integration gate, не утверждение об уже проверенной работе.

### Закрыто S2 предыдущего review — длительное ожидание

SPEC:32 разделяет `≤480 s` на generation attempt / `≤960 s` за два активных generation attempts и отдельный dispatch budget `≤60 s` на report. Persisted ожидание в `REPORT_READY`, paused/unknown и между process starts не расходует active time; counters не сбрасываются crash. SPEC:150 допускает dispatcher после resolution, A05/A10 требуют fault injection с паузой `>960 s` и отправку старшего ready report без нового model/MCP call. Многодневный backlog больше не конфликтует с budget.

### NOT PROVEN N1 — будущие live gates, не gate для plan

Точный RSS URL/охват и сортировка, выбор MCP реальной моделью, работа cron на VPS и Telegram receipt пока не проверены. SPEC:15,194–216 явно относит это к integration/launch gates; mock evidence не объявлено live evidence. Это запрещает считать Day 18 реализованным или готовым к сдаче, но не мешает планировать реализацию по доступной SPEC.

## Traceability

| Входное требование | Контракт и отказ | Acceptance evidence | Итог |
|---|---|---|---|
| cron запускает агента в 18:00 Warsaw, DST/overlap/backfill | SPEC:21–32,148–165; один slot/run, durable dispatcher | A01–A03,A09 | OK; live N1 |
| модель выбирает MCP; harness допускает/отклоняет каждый call | SPEC:19–25,34–111; strict schema, linked result и бюджеты | A03–A05 | OK; capacity S1 закрыта |
| идемпотентный RSS/SQLite, наблюдения переживают сбой | SPEC:113–142; batch commit, replay, article identity, backlog | A06–A07,A09,A15 | OK |
| честная классификация, source evidence и ограниченная сводка | SPEC:140–146; partial/empty/error, global draft cap, preflight | A07,A08,A11 | OK; provider live N1 |
| фиксированный Telegram и unknown без автоповтора | SPEC:128–132,150–169; claims, gate, checkpoint, receipt | A08,A10,A12,A15 | OK; queue S2 закрыта |
| самостоятельный Day 18 без runtime Day 17 | SPEC:5,17–25 | A13 | OK; `day17/` не менялся |
| работающий код и видео для сдачи | SPEC:194–216; launch gates | A01,A03,A14 | пока N1, не заявлено выполненным |

Непокрытых upstream требований и материальных orphan requirements не найдено. SPEC не превращена в implementation plan: она задаёт контракт, guards и evidence, но не предписывает файлы, классы или последовательность разработки.

## OK и готовность

Linked result предусмотрен также для отклонённого tool call; committed batch и report являются guards переходов; unknown не становится delivered и блокирует sends; recipient не выбирается данными; output preflight и active-time budget теперь проверяемы; критерии mock/live разделены. Статические проверки: обе JSON Schema parse через `jq`, Markdown/diff whitespace check, SHA-256 SPEC зафиксирован; code/test/live проверки не запускались.

**Verdict: 0 BLOCKER, 0 SHOULD FIX, 1 NOT PROVEN (не блокирует план). SPEC готова к отдельному implementation plan по доступным источникам.** Это не разрешение писать код, делать платные вызовы или deploy в рамках текущего запроса. Если `SPEC_REVIEW.md` будет предоставлен, нужен дополнительный cross-check перед принятием новых требований.
