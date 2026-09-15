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

## Непроверенное на 2026-09-12

- connection в Zapier;
- два live Zap и их run history;
- deduplication и replay через фактический Zapier scheduler/runtime;
- concurrency, >100 results between polls и durable webhook delivery.

API развёрнут по адресу `https://research.89.167.40.172.sslip.io`; секреты хранятся
только на VPS. На тот момент оставшиеся пункты нельзя было закрыть без Zapier
account/runtime; состояние 15.09 описано ниже.
Точные ручные шаги и имена скриншотов находятся в `SETUP.md`.

## Загрузка в Zapier — 2026-09-14

CLI авторизация проверена командой `integrations`, без вывода deploy key.
Выполнены `register`, `push` и `env:set 1.0.0`: integration ID `246309`, версия
`1.0.0`, Platform Core `19.1.0`, статус `private`. Команда `versions` подтвердила
наличие загруженной версии. HTTPS `/health` на VPS повторно ответил успешно.
Это подтверждает загрузку кода, но ещё не connection, actual Zap run или scheduler.

## Отдельный live review — 2026-09-15

Вход: утверждения текущего README. Ниже проверки, которыми скептический reviewer
попытался бы опровергнуть их; это не переименование локального `npm test` в live pass.

| Claim / возможный сбой | Проверка | Что произошло |
| --- | --- | --- |
| Реальные статьи, но даты в будущем вытесняют новые | Опрос OpenAlex и просмотр фактического Zap run | Zap run v1 содержал публикации 2028–2029; фильтр будущих дат добавлен, внешний API после deploy их не вернул |
| Рейтинг показывает релевантность запросу | Просмотр title и `score_breakdown` в live run | Fail: посторонняя статья получила 50/100 при title relevance 0/40; добавлен порог ≥20/40, deployed API после правки вернул три RAG-заголовка с 40/40 |
| Stable ID для dedupe | Два независимых запроса к deployed API после фильтра | оба раза `W7211887502`, `W7211907692`, `W7212798706`; это API-level pass, не scheduler-level pass |
| Polling выполняет action в настоящем Zap | Zap History и PostgreSQL | опубликованный Zap v1 выполнил успешный пакет задач; `saved_works` выросла до 24 строк. Запись истории — `polling-run-history.png` |
| Hook subscribe и runtime работают | Проверка числа подписок; контролируемый upsert synthetic work; Zap History и ledger | одна subscription; API сообщил одну webhook delivery; Zap run `0124b144-12a3-a909-d73e-1e13106a30d4` Successful, ledger получила +10 |
| Replay не удваивает запись | Кнопка Replay для того же live run; сравнение Event ID, action output и прямой GROUP BY ledger | новый run `0124b144-63d0-af07-ab3a-c4c11357ca24` Successful, тот же Event ID, `replayed: true`; для этого Event ID ровно одна строка и сумма 10 до/после |
| Опубликованный polling v2 продолжает работать | Включение через editor/assets, перезагрузка, ручной Run; затем Zapier HTTP logs | Fail: backend оставил Zap выключенным, editor показал «partner issue», Run — «Cannot test a paused Zap». Logs раскрыли GET `/v1/works?…&per_page=325` → 422; поле нуждается в исправлении на `3`. Две автоматические итерации v2 и live scheduler dedupe не подтверждены |
| Схема и обещанные локальные случаи не сломаны фильтром | Отдельный прогон unit/harness, `zapier-platform validate`, live OpenAlex test | 11 API tests + 12 Zapier harness tests + 1 live OpenAlex test passed; после hook run validate: 15 checks passed, 0 failed, 4 general warnings. T003 исчез после настоящего task |
| API доступен извне и помечен как demo | Внешние HTTPS `/health` и `/` после deploy | 200, `{"ok":true}` и synthetic banner |

Скриншоты в `screenshots/` осмотрены: ключи и deploy credentials отсутствуют.
`retry-no-duplicate.png` показывает `replayed: true`; прямой SQL подтверждает одну
ledger row. Replay — действительный повтор Zapier run, но не ошибка сети с автоматическим
retry. Polling v1 выполнил задачи в одном пакете; отсутствие дублей между двумя
автоматическими poll пока нельзя утверждать. Email/Slack Zap не проверен и ждёт выбора
личного адресата. На момент проверки Task Usage показывал 24 billable tasks за 30 дней:
22 polling и 2 hook; Free-план имеет месячный лимит 100.
