# Setup

## 1. Развернуть API из GitHub

1. Опубликуйте текущую ветку в GitHub. Автоматический push этим проектом не выполняется.
2. В Render откройте **New → Blueprint**, выберите репозиторий и укажите путь
   `zapier-open-research/render.yaml`, если это не корень отдельного репозитория.
3. Создайте ключ: `openssl rand -hex 32`. Передайте его в запрошенную переменную
   `API_KEY`; не коммитьте и не вставляйте ключ в README или скриншоты.
4. После deploy откройте корневой URL и `/health`. На корневой странице должен быть
   synthetic-demo banner, а `/health` должен вернуть `{"ok":true}`.
5. Проверьте auth: `curl -H "x-api-key: $API_KEY" https://YOUR_HOST/v1/me`.

`render.yaml` создаёт free web service и free PostgreSQL во Frankfurt. Миграция
выполняется идемпотентно в start command: Render не поддерживает отдельный pre-deploy
command на free web service. Free database
на Render имеет срок жизни 30 дней, поэтому это demo, а не долговременное production
хранилище. Для постоянной демонстрации выберите платный Postgres или другой совместимый
PostgreSQL.

Опционально добавьте в web service `OPENALEX_API_KEY` и `OPENALEX_MAILTO`. Для casual
запросов OpenAlex допускает работу без ключа, но ключ подходит для стабильного demo.

## 2. Загрузить private integration в Zapier

```bash
npm install -g zapier-platform-cli@19.1.0
cd zapier-open-research/zapier
zapier-platform login
zapier-platform register "Open Research Watch"
zapier-platform env:set OPEN_RESEARCH_API_BASE_URL https://YOUR_HOST
npm test
zapier-platform validate
zapier-platform push
```

`register`, `env:set` и `push` изменяют внешний аккаунт Zapier и потому здесь
автоматически не выполнялись. После `push` откройте Zapier editor, выберите
**Open Research Watch (Private)** и создайте connection с тем же `API_KEY`.

## 3. Двухшаговые demo Zap

### Zap A: polling → сохранить

1. Trigger: **New Research Work**; query — `retrieval augmented generation`.
2. Action: **Create or Update Saved Work**; сопоставьте OpenAlex ID, title, DOI,
   publication date, source и OA URL из trigger.

При сохранении сопоставьте также automatic score и score explanation. Это действие
порождает событие для следующих двух Zap.

### Zap B: REST Hook → уведомление

1. Trigger: **Saved Research Work Changed**.
2. Action: **Email by Zapier** (или уже подключённый Slack). В текст передайте title,
   Best Article URL, Automatic Score и Score Explanation.

### Zap C: REST Hook → проверить replay-safe action

1. Trigger: **Saved Research Work Changed**.
2. Action: **Record Review Score**; `openalex_id` берётся из work, score задайте `10`,
   а `source_event_id` сопоставьте с верхнеуровневым Event ID.

Чтобы вызвать hook после включения второго Zap, сохраните или измените работу первым
Zap либо выполните авторизованный `PUT /v1/saved-works/:openalexId`.

## 4. Ручные доказательства

После фактического прогона сохраните без секретов:

- `screenshots/polling-zap.png` — trigger + action;
- `screenshots/hook-notification-zap.png` — hook trigger + Email/Slack;
- `screenshots/idempotent-review-zap.png` — hook trigger + ledger action;
- `screenshots/successful-run.png` — успешная запись Zap history;
- `screenshots/retry-no-duplicate.png` — две попытки с одним Event ID и одна строка ledger.

Последний пункт важнее зелёного unit-теста: только он подтверждает idempotency через
реальный Zapier retry и deployed API.
