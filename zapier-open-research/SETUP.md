# Setup

## 1. Развернуть API на VPS

1. Используйте Docker Compose и Caddy по инструкции [DEPLOY_VPS.md](DEPLOY_VPS.md).
2. Создайте отдельные ключи: `openssl rand -hex 32` для `API_KEY` и ещё раз для
   `POSTGRES_PASSWORD`; не коммитьте и не вставляйте их в README или скриншоты.
3. После deploy откройте корневой URL и `/health`. На корневой странице должен быть
   synthetic-demo banner, а `/health` должен вернуть `{"ok":true}`.
4. Проверьте auth: `curl -H "x-api-key: $API_KEY" https://YOUR_HOST/v1/me`.

`render.yaml` оставлен только как воспроизводимый запасной Blueprint. Основной demo
работает на VPS и не зависит от сна сервиса или срока жизни бесплатной Render DB.

Опционально добавьте в web service `OPENALEX_API_KEY` и `OPENALEX_MAILTO`. Для casual
запросов OpenAlex допускает работу без ключа, но ключ подходит для стабильного demo.

## 2. Загрузить private integration в Zapier

```bash
npm install -g zapier-platform-cli@19.1.0
cd zapier-open-research/zapier
zapier-platform login --sso
zapier-platform register "Open Research Watch"
npm test
zapier-platform validate
zapier-platform push
zapier-platform env:set 1.0.0 OPEN_RESEARCH_API_BASE_URL=https://YOUR_HOST
```

При SSO официальный CLI использует deploy key из настроек Zapier Developer Platform;
не передавайте его в чат и не коммитьте `~/.zapierrc`. После `push` и `env:set`
откройте Zapier editor, выберите
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
