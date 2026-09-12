# Развёртывание на VPS

Целевая схема для portfolio-demo:

```text
Zapier → HTTPS/Caddy → 127.0.0.1:8050/API → private Docker network → PostgreSQL
```

Публичны только порты 80/443. API-контейнер слушает loopback VPS, PostgreSQL наружу
не публикуется. Секреты лежат только в `/opt/open-research-watch/.env` с правами `600`.

## Первый запуск

На Ubuntu VPS с Docker Compose:

```bash
sudo install -d -m 755 /opt/open-research-watch
sudo git clone --branch RomaniumSSS/zapier-integration-scaffold \
  https://github.com/RomaniumSSS/ai-advent-9.git /opt/open-research-watch/repository
cd /opt/open-research-watch/repository/zapier-open-research
sudo cp .env.example /opt/open-research-watch/.env
sudo chmod 600 /opt/open-research-watch/.env
```

Заполните два разных случайных значения `API_KEY` и `POSTGRES_PASSWORD`, не помещая
их в shell history. Затем:

```bash
sudo docker compose --env-file /opt/open-research-watch/.env \
  -f compose.vps.yml up -d --build
curl http://127.0.0.1:8050/health
```

Для текущего VPS Caddy проксирует отдельный hostname на `127.0.0.1:8050`:

```caddyfile
research.89.167.40.172.sslip.io {
    encode gzip
    request_body {
        max_size 100KB
    }
    reverse_proxy 127.0.0.1:8050
}
```

После `caddy validate` конфигурация применяется через `systemctl reload caddy`.

## Обновление

```bash
cd /opt/open-research-watch/repository
sudo git pull --ff-only
cd zapier-open-research
sudo docker compose --env-file /opt/open-research-watch/.env \
  -f compose.vps.yml up -d --build
```

Перед обновлением и после него проверяются `/health`, авторизованный `/v1/me` и логи
контейнеров. Значения секретов в отчёт и скриншоты не попадают.
