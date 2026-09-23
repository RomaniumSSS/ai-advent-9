# День 17: первый MCP-инструмент — Implementation Plan

Дата: 23.09.2026
Статус требований: SPEC утверждена и заморожена.
Источник требований: `docs/superpowers/specs/2026-09-23-day17-mcp-tool-calling.md`.

## Цель реализации

Создать самостоятельный `day17/` поверх проверенного `day16/` и добавить только
обычному chat flow один bounded read-only MCP tool `get_recent_commits`. Один
logical turn должен иметь один из двух путей:

```text
user → LLM1 final → response guard → persistence

user → LLM1 tool request → local validation → MCP tools/call
     → typed observation → LLM2 final → response guard → persistence
```

FSM workflow остаётся на прежнем пути без tool schemas, tool observations и MCP
execution. Day 15 и Day 16 не изменяются.

## Проверенный baseline и точки расширения

- `day16/agent.py::Agent.ask()` уже выполняет request invariants, terminal guards,
  снимает один FSM snapshot и проверяет final response до истории/SQLite.
- `day16/agent.py::_workflow_model_turn()` вызывает общий provider boundary напрямую;
  эту ветку нельзя переводить на tool-enabled orchestration.
- `day16/base_agent.py` умеет только текстовый Chat Completions response. Его текущий
  `Reply.empty` ошибочно классифицировал бы корректный ответ с `tool_calls` как пустой.
- `day16/mcp_client.py` уже изолирует MCP session, negotiation, pagination, timeout и
  cleanup, но discovery сохраняет только name/title/description и не реализует
  `call_tool`.
- `day16/store.py` schema v6 хранит conversation, provider usage и audit Day 14/15,
  но не имеет общего logical-turn ID и не различает LLM1, MCP и LLM2.
- `day16/web.py` сериализует один `Reply` и определяет model call эвристикой; для двух
  provider calls источником правды должен стать turn audit.
- endpoint pause намеренно обходит runtime lock. Поэтому повторные проверки FSM
  нужны даже при последовательном orchestration внутри одного HTTP request.

## Целевые компоненты

| Компонент | Изменение в Day 17 | Неизменяемая граница |
| --- | --- | --- |
| `day17/git_mcp_server.py` | собственный stdio MCP server с одним `get_recent_commits` | только чтение одного настроенного repo |
| `day17/mcp_client.py` | schema-aware discovery и один bounded `tools/call` | transport/session не знает о chat/FSM |
| `day17/tool_calling.py` | typed requests/results, schema validation, provider messages, result validation | не выполняет provider/MCP самостоятельно |
| `day17/base_agent.py` | общий низкоуровневый provider response parser | tool-disabled `_call()` для workflow сохраняется |
| `day17/agent.py` | chat-only bounded tool orchestration и FSM rechecks | workflow methods не получают tools |
| `day17/store.py` | schema v7 и durable ordered audit logical turn | старые Day 14/15 audit records сохраняются |
| `day17/web.py`, `day17/cli.py`, `day17/web/*` | подключение собственного MCP и показ проверяемого trace | никаких новых FSM actions |
| tests/live evidence/docs | offline failure matrix, real MCP protocol, real-provider E2E, video | mock и live evidence маркируются отдельно |

## План реализации

### 1. Изолировать Day 17 от опубликованного baseline

Создать `day17/` как самостоятельную копию исходников и regression-проверок
`day16/`, не копируя прежнее видео, generated results и SQLite. Переименовать только
Day 17-facing тексты, порт и default MCP config. `day15/` и `day16/` оставить byte-for-byte
без изменений.

Сразу зафиксировать две разные runtime-зависимости: обычный chat получает новый
tool gateway, а `_workflow_model_turn()` продолжает использовать tool-disabled
provider call. Не добавлять tools в `AgentCapabilities`: это контекстные возможности
агента Day 13, а не разрешение workflow на execution.

**Покрытие SPEC:** Scope 1; Out of Scope 1, 8; Invariants 4–5, 13; AC19, AC21.
**Validation/evidence:** сравнение `git diff --no-index day16 day17` с allowlist
ожидаемых Day 17-файлов; полный исходный набор Day 15 и Day 16; отдельный regression,
что workflow provider payload не содержит `tools`, `tool_choice` или tool messages,
а `model_turns` и FSM transitions совпадают с baseline.

### 2. Реализовать собственный read-only Git MCP server

Зарегистрировать ровно один MCP tool `get_recent_commits`. Repository path задаётся
доверенной конфигурацией процесса при старте сервера и не входит в arguments модели.
Перед запуском сервер разрешает и валидирует фиксированный repo root; tool принимает
только обязательный integer `limit` с узким minimum/maximum и без дополнительных
properties.

Чтение выполнять отдельным `git -C <configured-root> log` без shell, с фиксированным
format, timeout и output cap. Разделители должны позволять безопасно разобрать subject
и author как данные, включая переводы строк и похожий на инструкции текст. Никаких
Git-команд записи, изменения файлов или выбора пути из tool arguments.

Structured result содержит идентификатор настроенного repository и непустой массив
`commits`, отсортированный Git от нового к старому. Каждый элемент содержит непустые
`id`, `subject`, `author`, `timestamp`. Пустая история и ошибки Git возвращаются как
MCP error, а не как успешный result.

Repository identity определить одинаково на обеих сторонах как opaque SHA-256 от
canonical resolved Git worktree root, полученного из доверенной process config; путь
модели не показывать. `Newest-first` означает не сортировку timestamp, а точное
совпадение последовательности commit IDs с отдельным bounded `git log` того же
resolved repo и limit. Так одинаковые timestamp и clock skew не меняют oracle.

Добавить default stdio config Day 17, запускающий именно этот server для корня
проекта. Existing Everything config остаётся только артефактом Day 16.

**Покрытие SPEC:** Scope 2–5; RB1, RB6; Invariants 3, 9–10; Failure Behavior 5;
AC1, AC5–7, AC12, AC16–17.
**Validation/evidence:** protocol test настоящего MCP SDK проверяет регистрацию,
description и generated input schema; integration test на временном Git repo сверяет
результат с независимым `git log`; negative cases покрывают limit ниже/выше границы,
unknown property, empty repo, timeout и malformed metadata. До/после execution
сравниваются полный refs snapshot, digest index и content manifest worktree, включая
ignored/untracked files. Stdio server запускается с отключённой записью bytecode;
subprocess spy подтверждает фиксированный repo, allowlisted argv и `shell=False`.

### 3. Расширить MCP boundary: discovery snapshot и execution

Расширить `DiscoveredTool` сохранением полного `inputSchema`; snapshot считать
допустимым только если в discovery ровно один разрешённый по имени
`get_recent_commits` имеет непустое description и валидный object schema. Прочие MCP
capabilities не считать ошибкой, но не делать model-visible. Provider schema строить
прямым преобразованием этого snapshot; отдельную ручную копию schema не заводить.

Успешный snapshot держать в памяти runtime и повторно использовать между chat turns.
Ручной discovery endpoint обновляет тот же snapshot. Перед первым eligible chat turn
без snapshot выполнить discovery; его failure не считать MCP execution и не кэшировать
как success. Только на этом failure path узкое deterministic правило по явным маркерам
`git`/`commit`/`коммит` маршрутизирует запрос к canonical local сообщению о
недоступности. Это не общий intent classifier. Сообщение проходит применимые response
guards и получает audit текущего turn. Остальные вопросы отправляются модели без tools
с trusted notice, что Git tool недоступен и факты о текущем repo нельзя выдумывать.

Добавить отдельную `call_tool` boundary с собственным timeout и без automatic retry.
Она получает только уже validated name/arguments и возвращает raw MCP result вместе с
transport/protocol status. Любое исключение переводится в typed error observation;
наружу не уходит stderr, command или секреты конфигурации.

**Покрытие SPEC:** Scope 6–7; RB1, RB3–6; Failure Behavior 1, 3, 5;
AC1–4, AC6, AC9, AC12.
**Validation/evidence:** tests доказывают byte-equivalent provenance name/description/
schema от discovery snapshot до provider payload, reuse snapshot без нового discovery,
zero `tools/call` при discovery и его failure, filter дополнительных capabilities,
отдельные timeout/transport/protocol/cleanup outcomes и отсутствие retry. Fixtures
проверяют обе discovery-failure ветки, canonical local response, response guard,
provider/MCP counts и отсутствие выдуманной Git history.

### 4. Ввести typed provider step без утечки tools в workflow

Низкоуровневый provider boundary должен разбирать один response в typed step с
отдельными полями final text и списка tool requests, provider call IDs, finish reason,
usage/cost и safe error status. Классификация взаимоисключающая: отсутствие requests
разрешает direct-final path; наличие хотя бы одного request всегда выбирает tool path,
а сопутствующий непустой text делает batch protocol-invalid: MCP не выполняется,
каждый request получает linked error result, text не может быть сохранён как final.
Он принимает tools как явный
optional argument. Существующий
`_call()` вызывает его без tools и преобразует только final text в прежний `Reply`;
любой неожиданный tool request на tool-disabled пути становится provider error и не
может стать workflow artifact/proposal.

Каждому request назначить уникальный harness correlation ID. Валидный непустой
provider call ID сохраняется как protocol ID; missing или duplicate ID получает
детерминированный synthetic ID с mapping на raw position. Реконструированные assistant
tool-call и tool-result messages для LLM2 используют эти уникальные IDs, поэтому даже
malformed batch не оставляет request без связанного result. Missing/duplicate ID также
делают batch protocol-invalid и запрещают MCP execution.

Chat orchestration вызывает тот же parser с discovered schema только для LLM1.
LLM1 запускается с automatic model choice, без forced concrete tool. LLM2 получает
исходный user message, provider-native assistant tool request и соответствующие
`role=tool` observations. Tool content сериализуется как bounded JSON data с явной
инструкционной границей. LLM2 не получает право execution; даже если provider вернёт
новый tool request или mixed text + requests, parser должен увидеть каждый request для
локального denial; text такого response не становится final.

Token preflight учитывать не только обычные messages, но и model-visible tool schema,
assistant tool-call envelope и serialized observations. Existing provider timeout,
empty/truncated/error distinctions сохраняются для обоих calls.

**Покрытие SPEC:** RB2–3, RB7–8; Invariants 1–2, 4, 6, 9–11;
Failure Behavior 2, 6; AC3–4, AC8, AC11, AC13, AC17, AC19.
**Validation/evidence:** fake-provider tests проверяют exact payload LLM1/LLM2,
automatic selection, tool-disabled workflow payload, parser для final/tool/multiple/
mixed text+tool/missing-ID/duplicate-ID/empty/truncated responses, result на каждый
нормализованный request и строгий максимум двух фактических calls.

### 5. Добавить локальную validation и observation normalization

До `tools/call` обработать все requests LLM1 как одну batch-проверку:

1. сохранить raw provider ID/position и уникальный harness correlation ID каждого
   request;
2. отклонить zero/multiple requests как protocol/limit outcome;
3. проверить exact allowlisted name;
4. разобрать arguments только как JSON object;
5. проверить их непосредственно против discovered schema и дополнительного локального
   limit ceiling;
6. проверить оставшийся budget одного MCP execution.

Непустой mixed text+requests, missing/duplicate protocol IDs и multiple requests
отклоняются batch-целиком до проверки исполнимости отдельного request.

При нескольких requests не исполнять ни один и создать отдельный linked denial result
для каждого. Unknown name, malformed JSON и schema violation также получают linked
local error observation и затем один LLM2. Ни один такой path не вызывает MCP.

После реального `tools/call` successful observation создаётся только когда одновременно
выполнены `is_error=false`, repository identity match, непустой bounded список, полный
набор полей и exact commit-ID order относительно отдельного Git oracle. Empty,
malformed, oversized, wrong-repository,
unordered, `is_error`, timeout и protocol failure становятся linked error observation.
Raw MCP content не добавляется в обычную history и не интерпретируется как instruction.

**Покрытие SPEC:** RB4, RB6–8; Invariants 1–2, 9–12;
Failure Behavior 3–6; AC6–7, AC9–12, AC17.
**Validation/evidence:** table-driven unit suite на каждую validation/result ветку;
execution spy подтверждает 0/1 MCP calls; assertions связывают каждый request ID ровно
с одним result; adversarial commit subject остаётся JSON data, не создаёт новый call и
не обходит final response guard.

### 6. Реализовать chat-only bounded orchestration и FSM race guards

После существующих request invariants снять immutable FSM identity: отсутствие state
либо `(stage, status, version)`. Проверить `paused`/`done` до discovery. Если discovery
выполнялся, повторно сравнить identity и terminal status непосредственно после него,
до сборки provider payload и передачи schema LLM1. Snapshot reuse также проходит guard
непосредственно перед LLM1.
Для каждого дальнейшего checkpoint заново прочитать state и сравнить identity:

- после LLM1 audit и непосредственно перед MCP execution;
- после MCP audit и непосредственно перед LLM2;
- после LLM1 direct-final либо LLM2 перед подготовкой final persistence; решающая
  compare-and-commit проверка повторяется внутри самой SQLite transaction.

Любое изменение state/version или terminal state инвалидирует остаток turn. Уже
завершённый read-only MCP result остаётся только audit event: его не отправлять LLM2,
не добавлять в conversation и не применять к FSM.

После valid/error observation выполнить ровно один LLM2. Повторный tool request LLM2
не исполнять; каждый повторный request, включая mixed/multiple batch, получает linked
local denial только в audit. Не выполнять LLM3 и вернуть
application error без conversational turn. Final text пропустить через существующий
response invariant guard и observation-aware grounding guard. Для successful
observation final обязан содержать хотя бы один точный observed commit ID или subject,
а неизвестные commit-like IDs запрещены. Для error/local-denial observation LLM2 всё
равно выполняется и аудируется, но его текст никогда не считается доказательством и не
показывается/сохраняется: приложение использует canonical safe failure response,
построенный только из trusted error category. Только прошедший fail-closed policy ответ
можно вернуть и сохранить; сырой blocked/discarded output нигде не становится task
result или proposal.

**Покрытие SPEC:** RB2–3, RB5, RB7–11; Invariants 2, 4–8, 12–13;
Failure Behavior 2–4, 6–8; AC3–4, AC7, AC9–15, AC17, AC19–20.
**Validation/evidence:** deterministic hook tests меняют FSM во время discovery, перед
каждым внешним checkpoint и между последним re-read и transactional final commit;
assertions проверяют remaining-call counts, conversation и FSM. Отдельно проверяются
initial paused/done, direct final, successful tool turn, error observation, mixed/
multiple requests, repeated LLM2 request и blocked final. Adversarial provider после
error observation заявляет выдуманный Git success: raw text получает discarded status,
не показывается и не сохраняется, а пользователь получает canonical failure.

### 7. Сделать ordered fail-closed audit и атомарный final commit

Поднять Day 17 SQLite schema до v7 с миграцией v6. Добавить logical chat turns и
ordered events. Event хранит turn ID, sequence, kind (`provider_initial`,
`mcp_execution`, `provider_final`, `local_result`), status, provider/tool role,
tool call ID, validated arguments, safe result summary/error category и timestamp.
Provider events отдельно содержат usage/cost; MCP execution не маскируется под
provider call. Safe MCP summary ограничить repository identity, count и commit IDs —
не сохранять raw untrusted subject как управляющий текст.

Зафиксировать write groups явно:

1. До LLM1 отдельная transaction создаёт logical turn; её failure даёт ноль provider
   calls и явную application error без подстановки предыдущего audit.
2. Сразу после каждого состоявшегося provider call одна transaction сохраняет provider
   event и, если usage известен, соответствующую строку legacy ledger `calls`. Она
   завершается до validation/MCP/следующего provider call.
3. Local validation results или MCP result одной transaction сохраняются как linked
   events до LLM2. Для MCP event это происходит до проверки, разрешено ли применять
   observation дальше.
4. После LLM2 provider event и ledger уже durable. Затем finalization transaction под
   write lock повторно читает FSM, сравнивает исходную identity и только при совпадении
   атомарно пишет terminal turn status и единственную user/assistant пару. При mismatch
   та же transaction пишет `invalidated` без conversation. Direct-final LLM1 использует
   тот же finalization boundary.
5. Repeat LLM2 requests получают все linked denial events и terminal limit error одной
   transaction, без conversation.

In-memory history обновлять только после successful finalization commit. Ошибка любой
mandatory transaction немедленно возвращает application error и запрещает следующий
шаг/показ final. Failure оставляет только фактически подтверждённые ранние events;
незавершённый turn не интерпретируется как success после restart.

**Покрытие SPEC:** Scope 10; RB11–12; Invariants 2, 7, 9–10, 13;
Failure Behavior 2, 6–9; AC8, AC11–15, AC18, AC20.
**Validation/evidence:** schema migration test v6→v7; exact ordered-event assertions
для success/direct/failure paths; injected failure при создании turn audit и после
LLM1, MCP, LLM2; race между external re-read и finalization transaction; restart test;
SQL assertions, что successful tool turn имеет только два chat messages, два separately
metered provider events и один MCP execution.

### 8. Подключить flow к приложению и сделать evidence видимым

Runtime собирает Agent с одним Git MCP gateway и общим in-memory discovery snapshot.
`/api/chat` возвращает final/application error и безопасную сводку только по turn ID
текущего request; после audit-create failure previous successful turn не подставляется.
`model_called` и call counts берутся из audit текущего turn, а не из эвристики по одному
`Reply`. `/api/mcp/discover` использует и обновляет тот же snapshot.

В панели сохранить отдельный discovery action и добавить компактный trace последнего
turn: LLM1 → validation/result → MCP при наличии → LLM2, с status и счётчиками. Не
показывать raw provider payload, stderr или скрытые инструкции. CLI использует тот же
`Agent.ask()` и печатает application error отдельно от final answer.

**Покрытие SPEC:** Goal; Scope 1, 6–10; RB1–12; AC1–4, AC8, AC14–15, AC19.
**Validation/evidence:** HTTP integration tests для direct/tool/error/paused paths;
browser test подтверждает trace и только проверенный final text; CLI smoke использует
тот же execution boundary; web/CLI не имеют обходного прямого `call_tool`.

### 9. Выполнить offline verification и regressions

Offline набор должен разделять уровни доказательств:

- unit: schema/argument/result validation, provider parsing, FSM identity, audit;
- protocol integration: настоящий in-process MCP Client/Server и реальный `tools/call`;
- application integration: fake provider + настоящий собственный MCP server на
  временном Git repo;
- regression: все Day 17 copies релевантных Day 15/16 checks плюс неизменённые suites
  непосредственно из `day15/` и `day16/`;
- static/smoke: `compileall`, JS syntax, secret scan и `git diff --check`.

**Покрытие SPEC:** все invariants; AC1–4, AC6, AC8–21.
**Validation/evidence:** `day17/VERIFICATION.md` фиксирует команды, среду, counts и
раздельно mock/in-process/real-provider результаты. Ни один mock test не используется
как доказательство AC5.

### 10. Выполнить настоящий E2E acceptance и подготовить сдачу

Создать reproducible live runner, который поднимает собственный stdio Git MCP server,
запускает application boundary с реальным provider и задаёт естественный вопрос о
последних коммитах. Не передавать forced tool choice и не подменять MCP/final response.

Runner до вызова независимо читает `git log` того же repository/limit и снимает refs,
index и полный content manifest worktree, включая ignored/untracked files. После turn
он проверяет audit sequence, model-selected tool
name/arguments, один `tools/call`, совпадение normalized MCP result с независимой Git
history по exact commit-ID sequence, совпадение opaque repository identity,
использование хотя бы одного фактического commit ID или subject в LLM2 final,
два provider calls и неизменность Git. Сохранить redacted machine-readable report и
короткий human report с model/provider, usage, cost, elapsed и commit hashes evidence.
До after-snapshot временные отчёты держать вне проверяемого repo, чтобы сама система
evidence не создавала ложное изменение worktree.

После зелёного E2E снять короткое видео из реального приложения: естественный запрос,
видимый trace LLM1 → MCP → LLM2, финальный ответ с фактическими commits и код
регистрации/schema/result. Видео не заменяет machine checks; credentials и `.env` в
кадр и artifacts не попадают.

**Покрытие SPEC:** Goal; RB1–12; Invariants 1–3, 8–12;
AC1, AC4–8, AC14, AC16–17, AC21; исходный формат «Видео + Код».
**Validation/evidence:** отдельный live report с independently computed expected Git
history, audit export и before/after Git snapshot; `day17/README.md`,
`day17/VERIFICATION.md`, demo README и видео metadata/frame inspection.

## Failure-path contract реализации

| Сбой | Provider calls | MCP executions | LLM2 | Conversation | Обязательный audit outcome |
| --- | ---: | ---: | --- | --- | --- |
| initial `paused`/`done` | 0 | 0 | нет | нет | local terminal outcome |
| discovery failed, explicit Git request | 0 | 0 | нет | canonical guarded local response | current turn: discovery unavailable, не execution |
| discovery failed, ordinary request | 1 | 0 | нет | только checked final | provider initial + tool-disabled reason |
| LLM1 error/timeout/empty/truncated | 1 | 0 | нет | нет | provider initial failure |
| LLM1 direct final | 1 | 0 | нет | одна пара | provider initial final |
| unknown/invalid single request | 2 | 0 | да, с error result | canonical safe failure | provider1 + linked local result + provider2 |
| mixed/multiple LLM1 requests | не более 2 | 0 | не более одного | canonical safe failure | linked denial на каждый normalized request; text не final |
| MCP success | 2 | 1 | да | одна пара | provider1 + MCP success + provider2 |
| MCP error/timeout/malformed/empty | 2 | 1 | да, с error result | canonical safe failure; raw LLM2 discarded | MCP failure, не success |
| FSM changed before MCP | 1 | 0 | нет | нет | invalidated before execution |
| FSM changed after MCP | 1 | 1 | нет | нет | result audit-only + invalidated |
| FSM changed during LLM2 | 2 | ≤1 | завершён, но не применён | нет | provider2 + invalidated |
| LLM2 requests tool again, включая mixed batch | 2 | ≤1 | уже выполнен | нет | linked denial на каждый request + limit error |
| LLM2 error/timeout/empty/truncated | 2 | ≤1 | failure | нет | provider2 failure |
| blocked final response | 1 или 2 | ≤1 | по пути | raw output не сохраняется | response denial; optional safe local refusal |
| audit-create failed | 0 | 0 | нет | нет | application error без previous-turn substitution |
| mandatory later audit write failed | только уже вызванные | только уже вызванные | следующий шаг запрещён | нет | application error; unconfirmed success absent |

`MCP executions` в таблице означает только фактический `tools/call`; discovery в этот
счётчик не входит.

## Матрица SPEC → implementation evidence

| SPEC | Реализация | Объективное доказательство |
| --- | --- | --- |
| RB1 / AC1–2 | schema-aware cached discovery snapshot, allowlist одного tool | provenance/reuse/failure tests, provider payload capture |
| RB2–3 / AC3 | любой request выбирает tool path; только request-free text является direct final | final/tool/mixed provider traces и audit counts |
| RB4 / AC9–10 | batch validation до execution, unique correlation IDs, linked local results | invalid-name/arguments/mixed/multiple/missing/duplicate-ID tests, execution spy = 0 |
| RB5 / AC15 | guard после discovery и transactional FSM compare-and-commit | discovery/final TOCTOU hooks и SQL/history assertions |
| RB6 / AC6, AC12 | strict normalized result contract и canonical failure final | result matrix + false-success adversarial provider test |
| RB7 / AC4, AC7 | provider-native request/result messages в единственный LLM2 | captured LLM2 payload, grounded final assertion |
| RB8 / AC11 | repeated LLM2 request получает audit-only denial | 2 provider/≤1 MCP/no conversation assertion |
| RB9–10 / AC15, AC20 | transactional state check, response + observation-aware guards | stale/blocked/error-hallucination final tests |
| RB11 / AC14 | intermediate protocol data не входит в messages | exact two-row conversation SQL assertion |
| RB12 / AC8, AC13, AC18 | explicit audit write groups, current turn ID и atomic compare-and-commit | audit-create/later fault injection, sequence/usage/restart tests |
| Read-only / AC16 | fixed repo + allowlisted `git log`, bytecode off | refs/index/full worktree manifest before/after |
| Untrusted observation / AC17 | structured data boundary + no second execution + final guard | injection fixture and forbidden-output test |
| Workflow isolation / AC19 | old `_workflow_model_turn()` remains tool-disabled | payload capture + Day 15/16 workflow regressions |
| Full real flow / AC5 | real model + own stdio MCP + independent Git oracle | live report with trace, comparison and final grounding |
| Regression / AC21 | additive `day17/`, unchanged earlier days | Day 15 and Day 16 suites from original directories |

## Порядок проверок

1. Targeted unit tests после каждого component boundary.
2. Полный offline Day 17 suite и schema migration/restart.
3. Оригинальные Day 15 и Day 16 regression suites.
4. Compile/JS/diff/secret checks.
5. Один настоящий E2E после полного offline green; повтор только при зафиксированной
   технической или quality-причине.
6. Browser responsive/console check и затем запись видео на уже проверенном flow.

## Явно не реализуется

- tool loop внутри planning/execution/validation workflow;
- второй MCP execution, parallel calls, sequential multi-tool loop или retries;
- side-effect tools, approval state или permission UI;
- выбор repository/model-visible path, несколько MCP servers или dynamic install;
- превращение tool observations в durable chat messages, memory или FSM artifacts;
- изменение смысла workflow `model_turns` либо ослабление Day 14/15 guards.

## Definition of Done

Реализация готова только когда все offline и regression checks зелёные, настоящий E2E
доказывает model-selected `get_recent_commits` и независимо совпавшую Git history,
audit показывает максимум два provider calls и один `tools/call`, Git до/после не
изменён, workflow остаётся tool-disabled, а пользователю и durable conversation
достаётся только прошедший guards final response. Видео и код оформлены как отдельные
артефакты сдачи; commit, push, deploy и внешняя отправка выполняются только по отдельной
команде Романа.
