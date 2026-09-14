# Open Research Watch + Zapier

Самостоятельный portfolio-проект: небольшой HTTPS API берёт реальные метаданные
научных публикаций из OpenAlex, а private Zapier integration позволяет строить
автоматизации поверх этих данных. Персональные и клиентские данные не нужны.

Проект сделан на двух проверенных основах:

- deployment-схема адаптирована из MIT-шаблона
  [`render-examples/express-hello-world`](https://github.com/render-examples/express-hello-world);
- структура интеграции следует официальным примерам
  [`zapier/zapier-platform`](https://github.com/zapier/zapier-platform/tree/main/example-apps)
  (`minimal`, `custom-auth`, `rest-hooks`, `search-or-create`).

## Что демонстрирует проект

| Zapier component | Поведение |
| --- | --- |
| Authentication | API key и понятная ошибка при неверном ключе |
| New Research Work | polling реальных OpenAlex works, новейшие первыми, стабильный OpenAlex ID |
| Saved Research Work Changed | REST Hook с созданием и удалением подписки |
| Create or Update Saved Work | идемпотентный upsert по OpenAlex ID |
| Record Review Score | append-only ledger; ключ детерминирован из source event ID |
| Find Saved Work by DOI | пустой массив при отсутствии; включён search-or-create |

## Как считается рейтинг

Рейтинг детерминированный и объяснимый, от `0` до `100`:

- до 40 — доля значимых слов поискового запроса, найденных в title;
- до 30 — свежесть: 30 за последние 30 дней, 20 за год, 10 за два года;
- 20 — наличие открытой версии статьи;
- до 10 — цитируемость по логарифмической шкале, чтобы старые хиты не подавляли
  новые работы.

Trigger отдаёт `score`, четыре компонента, текст `score_explanation` и `article_url`.
Будущие даты публикации отсекаются при запросе к OpenAlex и повторно в API; в live
данных такие даты действительно встречались. Сам рейтинг не даёт им баллы за свежесть.
Ссылка выбирается в порядке: open-access URL → DOI → карточка OpenAlex. Это рейтинг
приоритета для чтения, а не научная экспертиза и не оценка достоверности выводов.

`api/` разворачивается на VPS как два изолированных Docker-сервиса: API и PostgreSQL.
Caddy публикует только API по HTTPS; база данных снаружи недоступна. `zapier/` загружается
в Zapier Platform и обращается к публичному API. На корневой странице API всегда
показано, что это synthetic portfolio environment. Публикации реальные; сохранённые
работы, заметки и оценки принадлежат только демонстрационному окружению.

## Быстрый локальный прогон

Требуются Node.js 22.12+ и PostgreSQL.

```bash
cd zapier-open-research
npm ci
cp .env.example .env
set -a; source .env; set +a
npm run migrate --workspace api
npm start --workspace api
```

В другом терминале:

```bash
curl -H "x-api-key: $API_KEY" http://127.0.0.1:3100/v1/me
npm test
npm run validate
```

`npm test` выполняет API contract-тесты, unit-тесты рейтинга и тесты интеграции через официальный
`createAppTester` (точное число выводится тест-раннером). Это доказывает только
перечисленные сценарии с in-memory Postgres
и HTTP doubles. Отдельный `npm run test:live --workspace api` дважды читает OpenAlex
и сравнивает ID; он не проверяет Zapier или deployed API.

## Важное расхождение с исходным prompt

Актуальная документация по polling прямо говорит, что Zapier не обходит следующие
страницы автоматически. Поэтому API запрашивает до 100 новейших OpenAlex works и
возвращает первую страницу в обратном хронологическом порядке; интеграция не пытается
загрузить весь архив. Иначе старые записи могли бы ошибочно выглядеть новыми.

На момент сборки npm публикует Zapier Platform `19.1.0`, хотя обзорная страница
документации всё ещё называет `18.5.1`. Core и CLI намеренно зафиксированы на одной
версии `19.1.0`.

Развёртывание API и подключение private integration описаны в [SETUP.md](SETUP.md),
а серверная схема и команды — в [DEPLOY_VPS.md](DEPLOY_VPS.md).
Честные ограничения и границы проверки — в [LIMITS.md](LIMITS.md).

## Источник данных

OpenAlex предоставляет метаданные под CC0. Проект сохраняет `id`, title, DOI,
publication date, primary source, OA URL и citation count. Авторизация OpenAlex
не является авторизацией Zapier: для небольшого demo API работает без ключа, а
собственный бесплатный OpenAlex key можно добавить как `OPENALEX_API_KEY`.

- API: <https://api.openalex.org>
- документация: <https://developers.openalex.org/api-reference/introduction>
- лицензия: <https://github.com/ourresearch/openalex-docs/blob/main/license.md>

## Структура

```text
zapier-open-research/
├── api/          # Express 5, PostgreSQL, OpenAlex proxy, hooks, ledger
├── zapier/       # Zapier Platform CLI integration
├── screenshots/  # сюда добавляются доказательства ручных Zap runs
├── compose.vps.yml # основной VPS deploy: API + PostgreSQL
├── render.yaml   # запасной Render Blueprint
├── SETUP.md
└── LIMITS.md
```
