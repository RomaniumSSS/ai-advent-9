# День 13 — состояние задачи (Task State Machine)

Накопительный агент дня 12 получил отдельное формализованное состояние работы.
История отвечает «что говорили», память — «что известно», профиль — «как
отвечать», а FSM — «где находится задача и что должно произойти дальше».

Источники запроса теперь подключаются явно через неизменяемый
`AgentCapabilities`:

```python
AgentCapabilities(
    profile=True,
    memory_layers=("working", "long"),
    task_state=True,
    recent_history_turns=3,
)
```

По умолчанию поведение осталось прежним: профиль, FSM, все непустые слои
памяти и последние шесть ходов. Отключённый источник не читается из SQLite и
не попадает в запрос; сохранённые данные при этом не удаляются.

```text
planning → execution → validation → done
                 ↑          |
                 └──────────┘ request_changes
```

## Состояние

```json
{
  "objective": "Подготовить безопасный релиз",
  "stage": "execution",
  "status": "paused",
  "current_step": "Выполнить согласованный план",
  "expected_action": "submit_result",
  "version": 3,
  "artifacts": {"planning": "Canary, метрики, rollback"}
}
```

`stage` и `status` независимы. Пауза меняет только `status` и `version`; этап,
шаг, ожидаемое действие, цель и результаты остаются прежними. Пауза проверяется
на всех четырёх этапах. Для `done` это фиксация просмотра завершённого результата,
а не разрешение новых переходов.

Допустимые события задаёт таблица `TRANSITIONS` в `task_state.py`:

| Этап | Событие | Следующий этап |
| --- | --- | --- |
| planning | `submit_plan` | execution |
| execution | `submit_result` | validation |
| validation | `approve` | done |
| validation | `request_changes` | execution |

Модель не может изменить этап текстом ответа. Сначала приложение проверяет
событие, затем одной SQLite-транзакцией записывает новый снимок и событие аудита.
Optimistic `version` отклоняет запись поверх более свежего состояния.

## Полуавтономный цикл

Поверх той же FSM добавлен ограниченный `run_to_boundary()`:

```text
model: planning ──proposal──> user: approve/revise
                                  │ approve
                                  ▼
model: execution ──авто──> model: validation ──proposal──> user: approve/revise
                                                               │ approve
                                                               ▼
                                                              done
```

Модель генерирует содержание плана, результата и проверки, но не выбирает
переходы. Приложение выводит текущего исполнителя (`actor`) из FSM и наличия
сохранённого `proposal`. План и финал всегда останавливают цикл у пользователя;
между ними `execution → validation` выполняется без нового сообщения.

Каждый proposal записывается в SQLite вместе с `based_on_version`. Поэтому он
переживает restart, не вызывает модель повторно и применяется только к той
версии FSM, для которой создан. Пауза во время запроса меняет version: расход
вызова остаётся в журнале, но поздний ответ не попадает в историю, не меняет FSM
и не создаёт proposal.
Жёсткий `max_model_turns` останавливает цикл с `turn_limit`, исключая бесконечное
самопродолжение.

### Что считается live для полуавтономного loop

`LIVE_VALIDATION` — только прогон через настоящий внешний provider. Fake-client
проверяет интеграцию, но не является live-доказательством. Отдельный evaluator
делает ровно три вызова — planning, execution и validation — без SDK retries,
проверяет restart, обе пользовательские границы, provider metadata, фактические
tokens/cost, отсутствие truncation и неподтверждённых внешних действий, а также
общий лимит `$0.005`, включая неудачные precursor-runs:

```bash
uv run python day13/live_workflow_eval.py \
  --env-file /безопасный/путь/.env \
  --output day13/results/live-workflow/run-01
```

Credential и путь к нему в evidence не записываются. Повторный запуск требует
нового output-каталога: существующее доказательство evaluator не перезаписывает.

## Продолжение без повторных объяснений

FSM хранится в области `user_id + task_id`, отдельно от сообщений. Команда
очистки разговора удаляет только короткую историю. Новый экземпляр `Agent` с
другим `session`, но той же задачей, читает цель, план, этап, шаг и ожидаемое
действие из SQLite.

Перед фактическим model call агент добавляет один JSON-снимок FSM в system
context. На паузе вызов блокируется Python-кодом до клиента. Поэтому фраза
«Продолжай» после `resume` не требует повторной постановки задачи, а до `resume`
не расходует токены.

## Запуск

Единая офлайн-панель сохраняет весь интерфейс накопительного агента дня 12 —
чат, профиль, три слоя памяти и переключение областей — и добавляет FSM, журнал
переходов, pause/resume, полуавтономный цикл и перезапуск экземпляра. Кнопка
`Запустить цикл` работает до ближайшей пользовательской границы; `Принять` и
`Вернуть на доработку` управляют сохранённым proposal. Все части используют
один `Agent` и один SQLite store; model request собирается настоящим кодовым путём:

```bash
uv run python day13/web.py --db /tmp/day13-demo.db
# http://127.0.0.1:8043
```

Для ручного диалога с реальной моделью путь к credential-файлу передаётся явно;
значение ключа панель не выводит и в SQLite не сохраняет:

```bash
uv run python day13/web.py --db /tmp/day13-online.db \
  --env-file /безопасный/путь/.env --max-tokens 8000
```

Панель по умолчанию резервирует до 8000 токенов на ответ; значение можно менять
через `--max-tokens`. Это отдельная настройка панели и не расширяет лимиты
provider-вызовов в live-evaluator.

CLI:

```bash
uv run python day13/cli.py --offline --db /tmp/day13-cli.db
```

Основные команды CLI:

```text
/start ЦЕЛЬ
/act submit_plan РЕЗУЛЬТАТ
/act submit_result РЕЗУЛЬТАТ
/act approve РЕЗУЛЬТАТ
/act request_changes ЗАМЕЧАНИЯ
/pause
/resume
/state
/events
/clear
```

Офлайн-проверки:

```bash
uv run python day13/test_task_state.py
uv run python day13/test_workflow_loop.py
uv run python day13/test_live_workflow_eval.py
uv run python day13/test_web.py
node --check day13/web/app.js
```

## Видео

[Немой live-ролик на Google Drive](https://drive.google.com/file/d/15xgtpOf5CTi4Qeyk7IVt0Tx5zs6SRAKb/view?usp=sharing)
за 49,68 с показывает настоящий planning-вызов через OpenRouter, сохранение
proposal после pause/restart и кодовые переходы до `done`. Сценарий и проверка
контейнера находятся в [`demo/README.md`](demo/README.md) и
[`results/video-report.md`](results/video-report.md).

## Обязательный массовый live-eval

После офлайн-валидации внешняя Codex-машина требует отдельный этап
`LIVE_VALIDATION`. Его manifest содержит 68 разных ситуаций:

- 60 реальных запросов на незавершённых stage, включая 12 restart/resume и
  adversarial cases;
- 4 paused-ситуации — по одной на stage, где сетевой вызов обязан отсутствовать.
- 4 terminal `done`-ситуации, где приложение отвечает без сетевого вызова.

Кампания использует DeepSeek V4 Flash через закреплённый OpenInference, SDK retry
отключён. Перед каждым send durable ledger резервирует вызов; `in_flight` с
неизвестным исходом никогда не отправляется повторно. Общий лимит — 60 вызовов и
$0.02. Для прохождения gate нужны 68 terminal cases, неизменность FSM, все
restart/pause проверки и не менее 90% строгих непустых рабочих ответов.
Канонические `stage/current_step/expected_action/objective` приложение берёт из
одного снимка FSM. На рабочих этапах модель возвращает только короткий `answer`;
решение `continue` формирует приложение. На `done` приложение возвращает
terminal response без модели. Так LLM не становится источником state или этапа.

```bash
uv run python day13/test_live_eval.py
uv run python day13/live_eval.py \
  --env-file /безопасный/путь/.env \
  --output day13/results/live/day13-live-05 \
  --db day13/results/live/day13-live-05/campaign.db
```

Путь к credential-файлу и значение ключа в evidence не сохраняются.

## Что проверено кодом

- полный прямой цикл и возврат `validation → execution`;
- запрет прыжков, переходов из `done` и действий на паузе;
- pause/resume на `planning`, `execution`, `validation`, `done`;
- новый Agent после очистки чата продолжает с сохранённого шага;
- на паузе fake model client не получает вызов;
- один model call использует один снимок FSM;
- state изолирован по пользователю и задаче;
- stale version не перезаписывает более новое состояние;
- web API проходит `pause → clear → restart → resume → continue`.
- plan/final approval нельзя обойти текстом модели;
- `execution → validation` проходит за несколько model turns без нового сообщения;
- proposal переживает restart и pause/resume без повторного model call;
- in-flight pause, пустой ответ, stale proposal и `max_model_turns` безопасно
  останавливают цикл.

Офлайн-проверки доказывают механику независимо от провайдера. Массовый live-report
отдельно доказывает поведение конкретной модели и не подменяет эти проверки.

## Контекст канала и сдачи участников

В экспорте Telegram задание — `message2977`. Релевантное обсуждение добавило
три полезные границы: задача является отдельным объектом, state может жить в БД
или на доске, а маршрутизация моделей по стадиям — возможное расширение, не
требование дня 13. Поэтому MVP остаётся одним агентом и одной моделью.

В таблице ячейки дня 13 у перечисленных участников были пусты, но в актуальных
репозиториях на 17.09.2026 код найден у девяти:

- Артём Томилов, Виталий Гуков, Илья, Petr, Роман, Игорь Седой,
  Иван Щитов, Roman Sokk и Xenia;
- у Юли и Vladimir Stroganov публичного day13 в проверенных ветках не было.

Повторяющиеся удачные решения: отделять stage от pause/status, хранить state
вне диалога, запрещать переходы кодом и проверять новый процесс/сессию. В нашей
версии дополнительно есть optimistic version, атомарный event log, один снимок
FSM на model call и явная проверка отсутствия вызова модели на паузе.

Внешняя машина, управляющая работой Codex над этим заданием, находится отдельно
в `experiments/day13-codex-machine/`. Она не является частью учебного агента.
