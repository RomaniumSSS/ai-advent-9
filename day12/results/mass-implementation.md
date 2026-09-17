# EXECUTION — mass-live implementation

Реализован утверждённый план для текущего gate. Переход этапа не выполнялся;
state.json не изменялся. Все изменения находятся в day12/. Модель/VPS/SSH,
commit/push/deployment не выполнялись. Прежние live artifacts не изменены.

План: `experiments/day12-mass-live-machine/runs/00-planning-retry1-result.json`.

## Реализация

- `mass_cases.json`: 24 фиксированных cases в порядке P01–P08, M01–M08,
  S01–S04, A01–A04; вопросы, области, транзакционные fixture operations,
  положительные/запрещённые сигналы, rubric, reuse и restart dependency.
- `mass_checkpoint.py`: server-side ledger, manifest с code/policy/fixture/prior
  hashes, atomic replace + fsync, lock на весь SDK boundary, неизменяемый prior
  anchor (3 вызова, $0.00013246), event hash chain, защита от случайного удаления
  ledger через `.created`. Cost counters проверяются при каждом чтении.
- `mass_live.py`: отдельный guard/runner, 24 send максимум, Decimal $0.02 вместе
  с prior, резерв без cache discount; pinned model/open-inference/none/256/0.2,
  SDK retries=0. Loopback owner HTTP client без proxy/redirect/retry.
  Raw response durable до grading; известная cost учитывается даже при ошибке
  provider. Отсутствующая cost оставляет unresolved reserve и cost_complete=false.
  quality_fail/length продолжают кампанию; security/provider/usage/persistence
  ошибки останавливают сеть и делают остальные cases blocked_safety.
- Recovery: pending/prepared безопасно продолжаются; response_recorded локально
  завершается без сети; in_flight без ответа становится indeterminate, повтор запрещён.
  Request ID + response hash и реальный turn фиксируются одной SQLite transaction;
  crash после этой записи не дублирует turn. Повтор terminal ID возвращает ledger.
- `mass_fixture.py`: synthetic history отдельно от live evidence; атомарный seed
  с provenance и idempotency marker; проверка expected state/ownership перед send,
  автоматический profile reuse, парные payload hashes, реальная проверка отказа
  открытия victim session. Reset использует общий SqliteStore.clear_in_transaction;
  сохранность working/long/profile проверяется внутри той же transaction.
- `mass_grade.py`: только deterministic predicates, NFC/strip, точные коды,
  JSON/абзацы/списки/лимиты/roots/эмодзи, severity. Human rubric pending отдельно
  со ссылкой на response hash; Codex/model judge не используется.
- Restart: строго после первых 18 terminal cases и до S03. Durable restart_pending,
  S01 history/notes/profile/DB path, completed hash/cost и actual PID/InvocationID;
  restart_verified требует нового процесса и неизменного snapshot плюс owner raw
  network/integrity evidence. Seed при restart не выполняется.
- `web.py`: private campaign dispatch/evidence/restart routes. ReadHandler отказывает
  публичным POST до body read, evidence GET недоступен. Campaign mode отключает
  legacy mutations. `DAY12_MASS_LEDGER` также блокирует обычный get_client.
- `base_agent.py`: общий request_options и опциональный reasoning_effort; обычные
  defaults сохранены. Campaign использует существующие Agent.build_messages и
  request_options; прежние runtime/prompt/memory semantics сохранены.
- `deploy/mass-live-policy.json`, `deploy/mass-live.conf`, runbook: opt-in rollout,
  обязательный owner preflight, rollback без отката costs. Исторические тарифы
  не выдаются за свежую проверку. Gate JSON — owner attestation с anchored raw
  evidence; внешний VALIDATION должен проверять фактические команды/выводы.
- `demo/record.cjs`: replay новой campaign evidence с показом неудач и restart,
  browser network abort. Видео в этом этапе не создавалось.

Отдельный campaign guard оставлен в mass_live/mass_checkpoint, вместо изменения
legacy LiveBudget enforcement: это сохраняет прежние MAX_CALLS/manual_resume и
не допускает смешения старого stopped ledger с новой кампанией. Его atomic-write
и locking primitives используются повторно. Unit по умолчанию остаётся legacy;
mass mode включается только явным drop-in на разрешённом этапе.

## Фактическая проверка

`mass-implementation-tests.json`: финальный прогон в scratch-копии day12,
локальный macOS, Python существующего .venv, API key удалён из окружения.

Прошли test_memory, test_profile, test_web, test_live_budget, test_verify_live,
test_runtime, test_resume_live; 24 новых unittest; node --check для web/app.js и
 demo/record.cjs. Новые тесты покрывают 24 fixtures, quality-continue, final options,
concurrent dedup, prepared/in_flight/response_recorded/SQLite receipt crash windows,
atomic reservation write failure, telemetry/Decimal boundaries, missing cost,
manifest/evidence tampering, gate anchors, scope, public route denial, restart boundary,
legacy shutdown и запрет нового бюджета после удаления ledger. Все ответы — test doubles.

`test_deploy.py` не завершился: sandbox запретил socket.bind(127.0.0.1, 0),
PermissionError EPERM. Реальный локальный HTTP smoke не заявляется пройденным;
повторить на VALIDATION в среде с разрешённым listener. Это не дефект, выявленный
HTTP-ответом, и не причина fail текущего EXECUTION gate.

Первый scratch запуск случайно разрешил symlink Python вне venv и получил отсутствие
openai; он сохранён в mass-implementation-tests-initial.json. Исправлен путь launcher;
код продукта ради этой ошибки не менялся. Промежуточный результат сохранён отдельно.

`mass-implementation-scope.json`: day01–day11 совпадают с начальным hash inventory и
baseline_ref; все ранее существовавшие results неизменны. Начальное dirty Git состояние
(todo.md, untracked .agents/day12/experiments) сохранено; root todo.md не редактировался.

## Следующее действие внешнего валидатора

Проверить текущий EXECUTION gate и при принятии перевести в VALIDATION. Там выполнить
независимую проверку implementation/offline regression и разрешённый HTTP smoke.
Live/VPS/network rollout, реальные 24 ответа, human rubric, visual/video и independent
review остаются будущими этапами; здесь их прохождение не заявляется.
