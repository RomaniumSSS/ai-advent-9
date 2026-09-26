# Day 18 — ежедневный агентный выпуск

`cron` запускает один agent turn в 18:00 `Europe/Warsaw`: модель с
`tool_choice=auto` предлагает единственный MCP tool `collect_habr_agent_cases`,
локальный harness сверяет аргументы с плановым слотом, MCP сохраняет RSS в SQLite,
модель классифицирует сохранённые кандидаты, harness фиксирует отчёт и показывает
в нём максимум две статьи. Telegram получает уже сохранённый payload и не получает
доступ к модели или RSS. Период, batch, классификации, claims, FSM и попытки
доставки сохраняются для восстановления после сбоя.
Отдельные cron-команды для сбора данных и выдачи сводки не нужны: один
запланированный запуск выполняет оба шага последовательно.

На VPS `crm-agent` установлен ежедневный cron в 18:00 `Europe/Warsaw`.
Одноразовый cron-backfill 27.09 в 00:15 по Варшаве реально вызвал агента:
2 model calls, 1 MCP, 12 статей проанализированы, 2 ссылки в отчёте,
Telegram `message_id=6`, состояние `DELIVERED`. Пользователь подтвердил, что
сообщение видно в чате. [Доказательства VPS](results/vps-live-20260927.md),
[видео запуска](demo/day18-scheduled-agent.mp4). Сам ежедневный trigger
в 18:00 после установки ещё не наступил. Одноразовый cron удалён из активных
заданий; ежедневный остался.

Лимит анализа поднят до 20 статей за один выпуск (15 свежих и 5 из старой
очереди с заполнением свободных мест); лимит публикации остаётся 2 ссылки.
Фильтр допускает практическое применение ИИ-агентов в работе и личных задачах;
неподтверждённое применение маркируется как возможное. Проверенный live
выпуск показывает описанный кейс DBA Agent и возможный кейс агентного QA.
Ранний [live trace](results/live-20260926.md) и
[изолированный тест](results/positive-case-test-20260926.md) описывают
предыдущие проверки. Локальные 55 тестов используют fixture RSS, fake provider
и fake Telegram; отдельный тест открывает настоящий stdio MCP protocol. Из
Day 17 нет runtime-импортов.

## Локальные команды

```sh
uv run python -m unittest day18.test_architecture day18.test_offline -q
uv run python -m day18.cli --db /tmp/day18-demo.sqlite3 init-db
uv run python -m day18.cli --db /tmp/day18-demo.sqlite3 status
```

`manual --date YYYY-MM-DD` создаёт диагностический `no-send` run с отдельным ID;
`scheduled` работает только в плановую минуту и не догоняет пропущенные дни;
`backfill --date ... --actor ...` явно адресует плановый slot. Повторное создание
slot возвращает тот же run. Операторские `resume`, `resolve`, `retry-definitive`,
`retire` и `dispatch` работают с durable evidence; `DELIVERY_UNKNOWN` не
пересылается автоматически. Закреплённая модель —
`deepseek/deepseek-v4.1-flash`; для неё проверен
`--verified-visible-budget 20000`. Локально `OPENROUTER_API_KEY` лежит в
корневом `.env` (файл игнорируется Git, права `600`). CLI читает его только с
`--env-file .env`;
переменные, уже заданные в окружении, имеют приоритет. Для реальной отправки
дополнительно нужны `DAY18_TELEGRAM_BOT_TOKEN`
и `DAY18_TELEGRAM_CHAT_ID`; диагностический `manual` ничего не отправляет.
Значения не пишутся в БД или журнал. На VPS защищённый конфиг лежит в
`/etc/day18/day18.env`, cron — в `/etc/cron.d/day18-agent`; пример в
`cron.example`, запускатель в `deploy/run-scheduled.sh`. Перед миграцией
действующей БД сделать `backup TARGET` и
проверить восстановление копии.
Запросы к провайдеру ограничены 80 000 UTF-8 bytes входного payload до
сетевого вызова. Стоимость и точный scope первого live gate —
[G2 preflight](results/p8-g2-preflight.md).

`status` показывает последние состояния, пропущенные даты между первым и
последним сохранёнными слотами, готовую очередь, неопределённые доставки и
частичные RSS batches. Диагностический manual report не захватывает claims
публикаций и не отнимает материалы у следующего scheduled report.

Состояние `DELIVERY_UNKNOWN` разрешается только по подтверждённому Telegram
`message_id`, авторитетному отрицательному подтверждению той же попытки либо
`quarantine` без повтора и продвижения checkpoint. Отсутствие сообщения в UI
не подтверждает недоставку. Максимум две persisted send attempts на отчёт.

Нормативный контракт — [SPEC](../docs/superpowers/specs/2026-09-25-day18-background-agent.md),
порядок этапов — [план](../docs/superpowers/plans/2026-09-26-day18-background-agent.md),
границы локальной проверки — [local-validation](results/local-validation.md).
