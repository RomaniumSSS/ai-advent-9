# Independent verification pass — 2026-09-12

Проверка началась с утверждений README, а не с повторного запуска прежней команды.

## Проверенные утверждения

| Утверждение | Скептическая проверка | Фактический результат |
| --- | --- | --- |
| OpenAlex ID стабилен | Два последовательных запроса к живому OpenAlex с одной query | 1 live test passed; одинаковые три `W…` ID |
| Polling не меняет dedupe key | Два одинаковых API-ответа через Zapier `createAppTester` | passed |
| Replay review не удваивает запись | Два HTTP action-вызова с одним source event; отдельно две записи в настоящий API handler с одним idempotency key | одна ledger row, total score остался 10 |
| Upsert не создаёт дубль | Два PUT одного OpenAlex ID через API handler и action harness | одна saved work, title обновлён |
| Unsubscribe очищает состояние | POST subscription → DELETE → прямой SELECT таблицы | 0 subscriptions |
| Ошибки различаются | 401, missing field, malformed hook и 429 через harness | clear auth error, HaltedError, HaltedError, ThrottledError |
| Integration допустима схемой | отдельный `npm run validate` | 26 checks passed, 0 failed, 0 publishing warnings, 4 advisory warnings |
| Зависимости устанавливаются из lock | `npm ci --dry-run` | success |
| VPS stack запускается | Docker build + Compose с настоящим PostgreSQL на Ubuntu 24.04 | API и DB запущены; DB healthy, API только на `127.0.0.1:8050` |
| API доступен Zapier | внешний HTTPS-запрос к Caddy, auth и два polling-запроса | health 200; invalid key 401; 3 real works; одинаковые ID |

Итог последнего полного локального прогона после добавления автоматического рейтинга:
8 API/unit tests и 12 Zapier harness tests passed. Live OpenAlex test: 1 passed.
Окружение: macOS arm64, Node.js 24.11.1;
контейнер VPS — Node.js 22, VPS — Ubuntu 24.04 amd64.

## Что review нашёл и исправил

1. `preDeployCommand` недоступен free Render web service. Миграция перенесена в
   идемпотентный start command.
2. Event ID строился из timestamp и теоретически мог совпасть у двух быстрых update.
   Теперь каждое событие получает UUID.
3. `performList` возвращал пустой массив на свежей базе. Добавлен CC0 setup sample.
4. Добавлены validation `per_page`, формат OpenAlex ID, нормализация DOI и понятный
   conflict при одном DOI у двух works.
5. После уточнения продукта добавлен детерминированный рейтинг 0–100 и отдельные
   unit-тесты его критериев; актуальные числа последнего прогона записываются ниже.

## Найденное, но не скрытое

`npm audit --omit=dev` не зелёный: Zapier Core 19.1.0 фиксирует уязвимый
`form-data@4.0.5`. Уязвимый multipart/filename путь эта интеграция не использует.
Предложенный npm fix откатывает Zapier Core до несовместимой версии 10.2.0, поэтому он
не применён. Это upstream dependency risk, записанный также в `LIMITS.md`.

## Непроверенное

- `register`, `env:set`, `push` и connection в Zapier;
- два live Zap и их run history;
- deduplication и replay через фактический Zapier scheduler/runtime;
- concurrency, >100 results between polls и durable webhook delivery.

API развёрнут по адресу `https://research.89.167.40.172.sslip.io`; секреты хранятся
только на VPS. Оставшиеся пункты нельзя честно закрыть без Zapier account/runtime.
Точные ручные шаги и имена скриншотов находятся в `SETUP.md`.
