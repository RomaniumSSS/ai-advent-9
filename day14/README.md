# День 14 — инварианты и ограничения состояния

Накопительный агент дня 13 теперь работает внутри набора обязательных правил.
Диалог отвечает «что говорили», память — «что известно», FSM — «где находится
задача», а инварианты — «какие решения недопустимы независимо от запроса».

```text
user request
    │
    ▼
request policy check ── conflict ──> локальный отказ + audit (0 model calls)
    │ allow
    ▼
system context: profile + invariant snapshot + FSM + memory + history
    │
    ▼
model response
    │
    ▼
response policy check ── conflict ──> безопасный отказ + audit
    │ allow
    ▼
history / SQLite / user
```

## Что является инвариантом

`Invariant` содержит стабильный ID, категорию (`architecture`, `technical`,
`stack`, `business`), правило, причину и набор проверяемых deny-patterns.
Демонстрация задаёт три правила: сохранить модульный монолит, не заменять SQLite
серверной БД и не выполнять внешнюю публикацию без подтверждения человека.

Правила находятся в таблице `invariants` в области `user_id + task_id`. Это не
сообщения и не заметки памяти: очистка разговора и новый экземпляр агента их не
удаляют. Другая задача их не получает. Таблица `invariant_checks` хранит короткий
audit: фаза `request|response`, решение `allow|deny` и ID сработавших правил —
без скрытой chain-of-thought.

## Два уровня защиты

1. До model call код сверяет запрос с активным снимком. Явный конфликт получает
   локальный отказ, где названы ID, само правило, причина и следующий безопасный
   шаг. Токены не расходуются.
2. Для допустимого запроса тот же снимок входит отдельным system-сообщением в
   фактический context. Ответ провайдера повторно проверяется **до** `append_turn`.
   Если модель всё же предлагает запрещённое, сырой текст не попадает в историю
   и SQLite; workflow не создаёт из него proposal и не меняет FSM.

Policy разделяет вход и выход. На входе action-patterns отличают запрос нарушения
от вопроса или отрицания; безопасное обсуждение обслуживает harness локально.
На выходе защищённые технологии блокируются по термам независимо от глагола, а
business action разрешается только при явной позитивной approval-формуле
(`только после/при наличии подтверждения`); иначе блокируется. Это наблюдаемый механический
контракт, а не заявление об универсальном семантическом понимании языка. Для
production фактические действия дополнительно должны иметь typed-параметры и
проверяться на tool boundary.

## FSM дня 13 сохранена

`planning → execution → validation → done`, pause/resume, optimistic version,
durable proposal, restart и полуавтономный `run_to_boundary()` работают как
раньше. Инварианты добавлены поверх этого контура и также применяются к model
turn внутри workflow.

Отдельная FSM самой работы Codex находится в
[`../experiments/day14-codex-machine/`](../experiments/day14-codex-machine/):

```text
PLANNING → EXECUTION → VALIDATION → LIVE_VALIDATION → REVIEW → DONE
```

## Запуск

Офлайн-панель использует полный production-код пути запроса, но не сеть:

```bash
uv run python day14/web.py --db /tmp/day14-demo.db --port 8044
# http://127.0.0.1:8044
```

В панели кнопка «Проверить отказ» отправляет конфликт
`Перейти с SQLite на PostgreSQL`. Результат должен показать `ОТКАЗ`,
`INV-STACK-001` и audit `request: deny`; внешний клиент не вызывается.

CLI:

```bash
uv run python day14/cli.py --offline --db /tmp/day14-cli.db
```

Дополнительные команды: `/invariants` и `/checks`.

## Проверка

```bash
uv run python day14/test_invariants.py
uv run python day14/test_task_state.py
uv run python day14/test_workflow_loop.py
uv run python day14/test_web.py
node --check day14/web/app.js
uv run python -m compileall -q day14
python3 experiments/day14-codex-machine/test_machine.py
python3 experiments/day14-codex-machine/machine.py check
```

`test_invariants.py` отдельно доказывает двенадцать формулировок конфликта до сети,
шесть безопасных обсуждений без ложного отказа, девять вариантов нарушающего
provider output до persistence, clear/restart, task scope, system context и
остановку workflow без proposal; позитивный approval-case проходит.
