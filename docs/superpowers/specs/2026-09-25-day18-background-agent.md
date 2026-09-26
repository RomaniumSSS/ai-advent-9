# Day 18 — автономный выпуск о применении ИИ-агентов

**Status:** нормативная SPEC, обновлена по запросам пользователя 27.09.2026;
готовность определяет отдельная итоговая сверка реализации и live evidence.

**Scope:** только самостоятельный `day18/`; изменения `day17/` и runtime-импорты из него запрещены.

**Authority:** текущие запросы → [`docs/day18-requirements.md`](../../day18-requirements.md) → задание Day 18 и подтверждённые ответы автора → проектные инструкции → Day 17 как образец, но не контракт. Требования обновлены по SHA-256 `881ebed62435d6add50026c49b197afb442bbfec5fa5ffa20f5fdb22fc0c3db7`; baseline HEAD при начале работы `e1ad49df8815db94589327c1deb766346db399ce`. Внешние ограничения: [Хабр: RSS поиска и лимит 100](https://habr.com/ru/docs/help/lenta/), [Telegram Bot API: `sendMessage`](https://core.telegram.org/bots/api#sendmessage). Эти ссылки подтверждают возможности сервисов; работа интеграции доказана отдельно в `day18/results/`.

## Цель, границы и риск

На своём VPS один независимый агент Day 18 ежедневно в 18:00 `Europe/Warsaw` собирает из официального RSS поиска Хабра материалы о практическом применении ИИ-агентов в работе и личных задачах, сохраняет наблюдения и проверяемую сводку, затем отправляет одно сообщение в фиксированный личный Telegram-чат с **не более чем двумя статьями на отчёт**. Лимит относится к каждому отдельному ежедневному отчёту, а не к сумме всех отправок за календарный день после восстановления очереди; он не ограничивает чтение RSS или сохранение наблюдений. Это фоновая публикация с сетевым чтением, записью в SQLite, платным вызовом модели и внешней отправкой; отказ должен быть видимым и восстанавливаемым. Максимальная автономия — получить RSS, подготовить и один раз отправить ограниченный отчёт по настроенному адресату. Модель не получает право менять источник, адресата, политику или выполнять произвольные действия.

Не входят: полный текст статей и произвольный web-browsing, другие источники, multipart, webhook, интерактивный чат Day 17, его FSM `planning → execution → validation → done`, Git MCP, авторазбор неопределённой доставки, автодогон пропущенных cron запусков. Создание бота, `/start`, token и `chat_id` — финальный integration gate; до него реальные отправки не считаются доказанными. День 19/20 здесь не проектируется.

Допущения: один VPS, один установленный SQLite-файл на устойчивом диске, один логический recipient, один фиксированный RSS source profile `habr_ai_agents_ru_v1`. Profile закрепляет официальный RSS поиска `https://habr.com/ru/rss/search/?q=%D0%98%D0%98-%D0%B0%D0%B3%D0%B5%D0%BD%D1%82%D1%8B&order_by=date&target_type=posts&hl=ru&fl=ru&limit=100`: русский поиск публикаций по «ИИ-агенты», сортировка по дате, максимум 100. Перед интеграцией URL сверяется с `application/rss+xml` страницы поиска и ответом с VPS; иная фактическая ссылка требует явной версии profile и review coverage, не runtime-подстановки. Это узкая поисковая выборка, не весь Хабр и не гарантия нахождения каждого кейса. На runtime профиль неизменяем для модели и MCP arguments. Отсутствие `SPEC_REVIEW.md` в текущем checkout на момент написания требует отдельной пометки review, не подменяется выдуманными правилами.

## Отличия Day 17 и agent loop

Day 17 фактически ограничивает один chat turn двумя provider calls и одним MCP execution; `tool_choice="auto"`, SDK `max_retries=0`, `max_tokens=4000`, provider timeout 600 s, MCP timeout 120 s, Git subprocess timeout 10 s. Его `tool_calling.py` валидирует найденный tool, строгие аргументы и linked result; `store.py` транзакционно завершает ход, а `task_state.py` обслуживает интерактивную FSM. В Day 18 переносится принцип «модель предлагает — harness допускает и исполняет», зарегистрированный tool и строгая схема, linked result на каждый предложенный call, лимиты, валидация результата и финала, недоверие к retrieved content, честные ошибки, секреты вне модели и trace без hidden reasoning. Конкретные таймауты, Git-only/read-only реализация, chat lifecycle и хранилище Day 17 не копируются.

Нормальный loop выпуска:

`cron → agent entrypoint → model call 1 (tool_choice=auto) → MCP request → harness validation/permission/budget → MCP RSS+SQLite → structured result → model call 2 (structured draft) → harness grounding/validation+persist → Telegram adapter → receipt`.

Если модель не предложила разрешённый MCP call, успешного выпуска нет: `FAILED_BEFORE_DATA`, а не скрытый worker fallback. Discovery успешен до показа tool модели; model-visible каталог содержит только `collect_habr_agent_cases`. Harness сопоставляет model tool call ID с ровно одним структурированным result; invalid name/arguments, multiple calls, budget denial и повторный call получают локальные error results, даже если новый provider call уже запрещён (тогда result остаётся в audit, не «доставляется» третьим вызовом). Ни один отклонённый call не достигает MCP. После первого observation второй model call может только вернуть draft; новый tool call отвергается с result в audit. Секреты и endpoint Telegram не входят в prompt, tool catalog, result или trace.

## Расписание, concurrency и бюджеты

- Scheduled slot — локальная дата `YYYY-MM-DD` + `18:00` + IANA zone `Europe/Warsaw`; уникальная identity — `(source_profile_id, slot_date, timezone)`. Момент вычисляется через актуальную IANA tzdb; весенний/осенний переход меняет UTC-время и длину периода, но не создаёт второй slot. Период `[предыдущий локальный slot UTC, текущий slot UTC)`. Для первого запуска — предшествующие местные сутки; никакой бессрочной истории. Время хранится UTC, зона и локальная дата сохраняются отдельно. Если на дату 18:00 когда-либо станет nonexistent/ambiguous по правилам tzdb, процесс fail-closed до явного решения оператора, не выбирает второй slot молча.
- Cron на VPS запускает entrypoint ровно в 18:00 местного времени с настроенной зоной. Повтор trigger возвращает существующий `run_id` и статус без новой модели или batch; он не повторяет уже начатый send, но entrypoint может восстановить **ещё не начатую** отправку durable `REPORT_READY` через общий dispatcher. При уже активной фазе захват атомарного lease не удаётся; второй процесс возвращает тот же run. Устаревший lease после crash может быть восстановлен по сохранённым evidence. Выключенный VPS означает пропущенный запуск: cron не делает catch-up. Операторский явный backfill конкретной даты создаёт/возобновляет тот же slot и не дублирует отправку. Ручной диагностический запуск по умолчанию `no-send` с отдельной manual identity; публикация или backfill требуют явного операторского действия и проходят те же guards.
- Обычный scheduled attempt: максимум 2 model calls и 1 *фактический* MCP execution; `tool_choice=auto`, а не принудительный выбор tool. Автоматических model retries нет. Один explicit operator resume после failure может открыть **второй и последний generation attempt** того же run: суммарно за run ≤4 model calls и ≤2 MCP executions, причём committed batch переиспользуется без нового RSS execution. Эти общие счётчики persisted и не обнуляются после crash; idempotency key/slot/run не меняются. Если модель предлагает несколько calls, каждый получает denial result и ни один не исполняется. После неопределённого исхода MCP разрешена максимум 1 reconciliation попытка *тем же* key без повторного RSS-запроса/записи; она не считается новым RSS execution, но считается отдельным tool attempt. Если committed batch не доказан, run остаётся ошибочным. Никаких скрытых SDK retries.
- Active execution wall budget ≤480 s на generation attempt и ≤960 s суммарно за два generation attempts одного run; считаются только интервалы, когда процесс выполняет model/MCP/validation, а не календарное ожидание в persisted `REPORT_READY`/paused/unknown или между запусками. Каждый provider call ≤180 s, MCP RSS/read/write ≤60 s. Delivery имеет отдельный бюджет: каждый Telegram HTTP request ≤15 s, суммарное активное dispatch time одного report ≤60 s при ≤2 persisted send attempts. Counters и начало/конец активных фаз сохраняются; crash не обнуляет расход. Возраст очереди наблюдается отдельно и **не** запрещает отправить ожидающий report после operator resolution даже через дни. Model call 1 получает ≤1000 visible output tokens, model call 2 — ≤20000; если provider считает hidden reasoning в том же лимите, preflight должен вычесть его измеренный верхний бюджет. Tool result ≤32 KiB, из них serialized candidates ≤16 KiB; RSS response ≤2 MiB, ≤100 feed items, ≤10 переданных модели кандидатов. В SQLite хранится очищенный title ≤240 символов и RSS description ≤1000 символов; в MCP result title ≤240 символов **и** ≤512 UTF-8 bytes, excerpt ≤512 UTF-8 bytes без разрыва символа. Если candidate cap/byte cap достигнут, остаток остаётся в SQLite, `omitted_candidates/analysis_omitted` увеличиваются, report маркирует partial analysis; это **не** делает source coverage неполным само по себе. Если неполон сам feed (100-item cap, 2 MiB cap, parse gaps), это `partial_coverage`. До model call 2 harness выбирает максимальный `model_seen` ≤20, для которого worst-case компактный JSON draft со всеми обязательными полями и предельными разрешёнными escaped UTF-8 строками укладывается одновременно в 18432 bytes и доступный visible token budget по tokenizer закреплённого provider; если точный tokenizer/бюджет недоступен, применяется консервативная оценка 1 token на UTF-8 byte плюс 1024-token запас. Выбранный `model_seen` и расчёт сохраняются в trace; если не помещается даже один кандидат, `FAILED_AFTER_DATA` с `budget_exhausted` без model call 2, observations остаются backlog. Truncated/oversized draft отклоняется, не становится success. Retry HTTP RSS: максимум один после явно pre-response сетевого сбоя, в активном budget; 4xx/parse error не повторяется автоматически. Telegram: максимум **2 persisted send attempts на report** за всё время, включая pre-send failures; второй разрешён автоматически только после доказанного pre-send failure, либо явно оператором после полного definitive Bot API rejection/Telegram-side proof of non-delivery. Неизвестный исход, 5xx, timeout и простое отсутствие сообщения в UI не доказывают недоставку и не разрешают retry. Исчерпание двух attempts блокирует retry; остаётся operator retirement или quarantine по исходу.

## MCP contract и доверенная граница

Единственный зарегистрированный side-effecting tool `collect_habr_agent_cases` читает только фиксированный профиль, идемпотентно сохраняет RSS и возвращает агрегат. Он не отправляет Telegram. Model-visible input schema происходит из MCP discovery; harness дополнительно сравнивает все поля с доверенным run context. `run_id`, slot, границы, zone, profile и key не могут быть изменены моделью; значения подставляются в контекст до model call, а любое несовпадение — `invalid_request`. `tool_call_id` — ID вызова из provider envelope, фиксируется harness как metadata attempt, не доверяется полю из текста модели. Key детерминирован для `(run_id, source_profile_id, period)` и не меняется при повторе/новом model attempt.

Input JSON Schema (все строки нормализуются и проверяются harness; `format` проверяется валидатором, а не только аннотацией):

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["run_id", "scheduled_slot", "period_start_utc", "period_end_utc", "timezone", "source_profile_id", "idempotency_key"],
  "properties": {
    "run_id": {"type": "string", "format": "uuid"},
    "scheduled_slot": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
    "period_start_utc": {"type": "string", "format": "date-time", "pattern": "Z$"},
    "period_end_utc": {"type": "string", "format": "date-time", "pattern": "Z$"},
    "timezone": {"const": "Europe/Warsaw"},
    "source_profile_id": {"const": "habr_ai_agents_ru_v1"},
    "idempotency_key": {"type": "string", "pattern": "^[a-f0-9]{64}$"}
  }
}
```

Нет аргументов URL, filesystem path, SQL, recipient, token, произвольной команды или свободного search query. Harness сверяет `period_start < period_end`, соответствие slot/tzdb и `idempotency_key` доверенной записи. MCP сервер повторно проверяет запрет дополнительных свойств и source profile. Неизвестный tool name и malformed JSON получают тот же linked error-result envelope, хотя не вызывают сервер.

Output JSON Schema (транзакционные семантические guards ниже обязательны сверх schema):

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false,
  "required": ["status", "run_id", "batch_id", "source_profile_id", "period_start_utc", "period_end_utc", "read_at_utc", "counts", "coverage", "candidates", "reason_code"],
  "properties": {
    "status": {"enum": ["success_with_items", "success_empty", "success_no_matching_cases", "partial_coverage", "source_error", "storage_error", "invalid_request"]},
    "run_id": {"type": "string", "format": "uuid"},
    "batch_id": {"type": ["string", "null"], "format": "uuid"},
    "source_profile_id": {"const": "habr_ai_agents_ru_v1"},
    "period_start_utc": {"type": "string", "format": "date-time"},
    "period_end_utc": {"type": "string", "format": "date-time"},
    "read_at_utc": {"type": ["string", "null"], "format": "date-time"},
    "counts": {"type": "object", "additionalProperties": false,
      "required": ["feed_seen", "in_period", "new_observations", "repeated_articles", "eligible_candidates", "omitted_candidates", "invalid_entries", "out_of_profile"],
      "properties": {
        "feed_seen": {"type": "integer", "minimum": 0, "maximum": 100},
        "in_period": {"type": "integer", "minimum": 0, "maximum": 100},
        "new_observations": {"type": "integer", "minimum": 0, "maximum": 100},
        "repeated_articles": {"type": "integer", "minimum": 0, "maximum": 100},
        "eligible_candidates": {"type": "integer", "minimum": 0, "maximum": 100},
        "omitted_candidates": {"type": "integer", "minimum": 0, "maximum": 100},
        "invalid_entries": {"type": "integer", "minimum": 0, "maximum": 100},
        "out_of_profile": {"type": "integer", "minimum": 0, "maximum": 100}
      }},
    "coverage": {"type": "object", "additionalProperties": false,
      "required": ["kind", "feed_limit_hit", "window_complete", "oldest_entry_utc"],
      "properties": {
        "kind": {"enum": ["complete_for_profile", "partial", "unknown"]},
        "feed_limit_hit": {"type": "boolean"},
        "window_complete": {"type": "boolean"},
        "oldest_entry_utc": {"type": ["string", "null"], "format": "date-time"}
      }},
    "candidates": {"type": "array", "maxItems": 10,
      "items": {"type": "object", "additionalProperties": false,
        "required": ["article_id", "observation_id", "url", "title", "rss_excerpt", "published_at_utc"],
        "properties": {
          "article_id": {"type": "string", "maxLength": 100},
          "observation_id": {"type": "string", "format": "uuid"},
          "url": {"type": "string", "format": "uri", "maxLength": 500},
          "title": {"type": "string", "maxLength": 240},
          "rss_excerpt": {"type": "string", "maxLength": 512},
          "published_at_utc": {"type": ["string", "null"], "format": "date-time"}
        }}},
    "reason_code": {"enum": ["none", "no_feed_entries", "no_new_entries", "no_eligible_candidates", "invalid_entries", "feed_limit", "oversize", "rss_unavailable", "rss_malformed", "storage_failure", "schema_violation", "context_mismatch", "budget_exhausted", "tool_not_allowed", "multiple_calls", "timeout", "protocol_error"]}
  }
}
```

Для `success_*` и `partial_coverage` `batch_id` и `read_at_utc` обязательны и batch уже committed; для ошибок `batch_id` может указывать на *доказанный* committed batch, но ошибка не становится success. `success_empty` — валидная RSS-выдача без элементов в периоде/без новых статей; counts/reason различают эти варианты. `success_no_matching_cases` — есть **валидные** новые элементы, но все они явно вне фиксированного topical profile по детерминированному широкому gate; это не утверждение об отсутствии реальных бизнес-кейсов во всём Хабре. Tool не выполняет семантическую классификацию: `no_confirmed_cases` может определить только модель по валидным кандидатам. Любой in-period элемент с повреждённым ID/link/датой увеличивает `invalid_entries` и приводит минимум к `partial_coverage` с reason `invalid_entries`, даже если валидных кандидатов нет; если валидный batch нельзя сохранить, это `source_error`/`storage_error`. Неизвестное содержимое не объявляется «нет кейсов». `partial_coverage` также применяется при feed limit, превышении предела или неполном окне; итоговый отчёт обязан назвать неполноту и не утверждать «за сутки ничего нет». `source_error`, `storage_error`, `invalid_request` не маскируются под пустой успех. Все result envelopes, включая локальный отказ harness, ограничены по размеру и содержат безопасный `reason_code`, без stack trace/secret/raw RSS.

## SQLite, identities и идемпотентность

SQLite в WAL с FK и транзакциями — выбранный durable store; обязательны миграция схемы и восстановление по durable evidence. Все сущности ниже хранятся бессрочно в MVP до отдельной проверенной retention policy; ограничение размеров RSS исключает неограниченный рост одного run. Резервное копирование перед обновлением схемы — launch gate. Модель видит только отфильтрованные кандидаты и публичные IDs/period/counts/coverage, не таблицы целиком.

| Сущность | Identity, обязательные поля и связь | Mutability, constraint, видимость модели |
|---|---|---|
| Scheduled slot | `(profile, local_date, zone)`; UTC instant, status; `run_id` | `UNIQUE(profile, local_date, zone)`; immutable time identity; видны slot/period |
| Run + transitions | UUID; slot FK, state/version, stage/reason, created/updated UTC; transitions: from/to/time/evidence ref | Один run/slot `UNIQUE(slot_id)`; state CAS/transaction; append-only transitions; видны run ID/status |
| Model/tool attempts | UUID; run FK, generation attempt (1/2), provider call sequence, tool request ordinal, original/synthetic tool_call_id, arguments digest, outcome, usage, safe reason, timestamps | Append-only; `UNIQUE(run_id, provider_call_sequence, request_ordinal)` различает даже duplicate tool IDs; linked result хранит исходный ID и ordinal; redacted trace |
| Article | Canonical Habr article ID или нормализованный canonical URL; source profile, first_seen, latest_seen, latest RSS hash | `UNIQUE(profile, canonical_article_id)`; latest metadata может обновиться, identity immutable; видны link/title |
| Observation batch | UUID; run FK, idempotency key, tool_call_id первого attempt, period, read time, coverage/counts, commit time | `UNIQUE(run_id, idempotency_key)`; committed payload immutable; видны batch ID/aggregate |
| Observation | UUID; article FK, first batch FK, sanitized RSS excerpt/title, original pubDate, parsed UTC, seen UTC, evidence hash, source eligibility `eligible/out_of_profile` | `UNIQUE(article_id)` в MVP: повтор/изменение обновляет latest article metadata, не создаёт второе observation; evidence immutable; виден ограниченный excerpt |
| Batch membership | batch FK, observation FK, ordinal | `UNIQUE(batch_id, observation_id)`; append only within atomic batch transaction; не отдельно модели |
| Source rejection | batch FK, feed ordinal, safe reason, bounded evidence hash (без сырого XML) | append-only; invalid ID/link учитывается в coverage/counts; не виден модели как полноценная статья; invalid date у валидной статьи хранится в observation |
| Classification + disposition | UUID; run FK, observation FK, category/confidence, evidence field refs, source metric attribution, evidence hash, disposition `relevant_queued/processed_out_of_scope` | `UNIQUE(run_id, observation_id)`; классификация каждого model-seen item фиксируется с report transaction; out-of-scope исключается из backlog до явной operator reclassification; видны draft fields |
| Report + membership | UUID; run FK, validated text/payload hash, classified relevant observations, `displayed_in_payload` per member, pool/model/payload omitted counts, period, coverage | `UNIQUE(run_id)`; после `REPORT_READY` immutable; membership `UNIQUE(report_id, observation_id)`; модели не виден чужой report |
| Publication claim | observation FK, owning report FK, state `owned/delivered/quarantined/released`, changed UTC, evidence | active owner unique per observation; claim history retained; `REPORT_READY` acquires claims atomically, release only by guarded delivery/retirement; модели не виден |
| Delivery attempt | UUID; report FK, fixed recipient config fingerprint, payload hash, started/ended UTC, API status, message_id nullable, proof class `pre_send/definitive_rejection/unknown/receipt` | append-only; `SENDING` требует persisted attempt; `UNIQUE(report_id, attempt_no)`, `attempt_no≤2`; модель/МCP не видят recipient |
| Delivery checkpoint | profile+recipient; last contiguously confirmed report/slot, time; reservations отдельно | Двигается только после receipt/подтверждённого operator resolution и не перескакивает unknown gap; не виден модели |
| Operator resolution | UUID; affected run/attempt, actor, time UTC, reason, evidence, decision | append-only, без секретов; не виден модели |

`run_id + tool_call_id + idempotency_key` при повторе не создаёт второй batch; более сильный `UNIQUE(run_id,idempotency_key)` защищает и от нового tool_call_id. Duplicate/missing provider tool IDs получают synthetic audit identity по ordinal и отдельный denial result, не схлопываются. До внешнего чтения harness записывает attempt. В одной транзакции tool записывает article identities, observations, batch, memberships и coverage; batch считается committed только после commit. Повтор после timeout сначала ищет committed batch по key и возвращает его сохранённый результат без повторного чтения. При частичном сетевом/транспортном ответе после commit run остаётся `MCP_PENDING` с visible attempt failure до reconciliation и затем может перейти `DATA_READY` только по тому же committed batch. Если запись откатилась, успех запрещён. Любой retry модели/tool не меняет key. Повторная статья и одинаковые `pubDate` не теряются: сканирование и дедуп используют `(published_at_utc, canonical_article_id)` плюс overlap, а не один timestamp cursor.

## Coverage, выбор материалов и отчёт

Source coverage (что вернул конкретный RSS profile за интервал) не равно сохранённым observations, report membership или delivery checkpoint. Ingestion не зависит от Telegram; failure send ничего не удаляет. Feed ограничен 100 элементами. `feed_seen=100` консервативно даёт `partial_coverage`; также partial, если ответ обрезан или нет уверенности в охвате начала окна. Отсутствие элементов в корректно прочитанном feed — `success_empty` только в рамках профиля поиска. При RSS outage coverage `unknown`, checkpoint не двигается, повтор/явный backfill использует overlap и article identity. Если запуск пропущен, следующий штатный запуск не выдаёт пропуск за покрытые сутки: сохраняет gap, проверяет свой период; явный backfill может обработать пропущенный slot. Новая версия/повторное появление статьи обновляет latest metadata и evidence of reappearance, но для MVP не создаёт нового observation и не объявляется новой публикацией; исходное immutable evidence остаётся. Автоматическая повторная классификация изменённой статьи в MVP не производится; оператор может инициировать отдельный review, не называя старую публикацию новой. Если pubDate отсутствует/невалиден, элемент с валидным ID/link **назначается batch текущего чтения по `read_at_utc`**, даже если чтение после 18:00 и дата не попадает в `[period_start,period_end)`; `in_period` его не считает, `invalid_entries` считает, observation сохраняется с `published_at_utc=null`, модель получает его с пометкой «дата неизвестна» и классифицирует по обычным RSS evidence, а coverage минимум `partial_coverage`. Следующий batch не создаёт второй observation.

Eligibility gate tool не должен отсекать материал лишь из-за отсутствия одного из трёх признаков реального кейса: он допускает все валидные in-period записи поиска, кроме явно не-статей/дубликатов; `success_no_matching_cases` возможен только при валидных новых RSS items, явно не связанных с фиксированной агентной темой. Такой `out_of_profile` disposition сохраняется механически и не входит в будущий report pool; это не семантическая модельная категория. Неполные/невалидные items — `partial_coverage` или error, никогда «нет кейсов»; непригодные ID/link фиксируются как source rejections, а не пропадают молча. Все исключения и counts сохраняются для проверки false negatives. MCP `counts` относятся **только к текущему feed/batch** (каждое значение ≤100), не к backlog.

Report pool отдельно берёт только `eligible` unclaimed недоставленные observations предыдущих failed/partial slots и не показанные в доставленных отчётах, с исходными slot/period; уже классифицированные `processed_out_of_scope`, active ownership, delivered или unknown/quarantined claims исключены. Это не меняет coverage текущего RSS. Pool может быть больше 100; harness сохраняет `pool_total`, `model_seen`, `analysis_omitted`, `payload_displayed`, `payload_omitted` отдельно от MCP counts. Выбор модели резервирует до 15 мест для новых текущего batch и до 5 для oldest eligible backlog; пустая доля заполняется другой, внутри долей порядок `(published_at_utc DESC NULLS LAST, article_id ASC)` для новых и `(origin_slot ASC, published_at_utc DESC NULLS LAST, article_id ASC)` для backlog. Всего ≤20, при byte/token budget ещё меньше с сохранением этого порядка. Всё за пределами `model_seen` остаётся в SQLite без ложного утверждения о классификации, отчёт маркируется partial analysis. В момент `REPORT_READY` disposition фиксируется для **всех** model-seen observations: `guide/opinion/advertisement/tool_news/not_relevant` → `processed_out_of_scope` и не возвращаются в backlog; `confirmed_described_case/possible_case` → `relevant_queued` с report membership и флагом `displayed_in_payload` для реально перечисленных в одном сообщении. Только эти две категории могут попасть в payload; гайды, мнения, реклама и новости об инструментах никогда не занимают два article slots. Не показанные relevant members после confirmed delivery возвращаются в backlog; новые статьи не голодают из-за уже обработанных нерелевантных.

При формировании payload harness детерминированно выбирает **не более двух** relevant members: сначала `confirmed_described_case` из всего membership, затем, только если свободны места, `possible_case` с явной маркировкой неопределённости. Внутри каждой категории старший backlog предшествует новым статьям; сохраняются определённые выше порядки внутри каждой доли. Лимит применяется к числу фактически показанных статей/ссылок одного отчёта, включая возможные ссылки в `proposed_text`: третий article reference запрещён, а не скрывается одной лишь обрезкой текста. Если подходящих записей больше двух, `payload_omitted` показывает число не вошедших, полный membership и `displayed_in_payload` остаются в SQLite. Отбор двух не меняет `model_seen`, классификацию, source coverage или число сохранённых observations.

Если byte/token preflight допускает меньше 20 записей, места распределяются попеременно между текущим batch и oldest backlog с заполнением из непустой очереди; при `model_seen ≥2` и наличии обеих очередей каждая получает хотя бы одно место. Не вошедшие записи остаются unclassified backlog, `analysis_omitted` и причина ограничения сохраняются. Это ограничение не уменьшает сохранённый batch и не меняет source coverage.

Модель классифицирует **только переданные очищенные RSS title/description**, без скрытого fetch полного текста: `confirmed_described_case` требует (1) конкретную задачу в работе или личной жизни, (2) роль/действия агента, (3) признак применения, пилота или эксплуатации прямо в RSS evidence; иначе `possible_case`, `guide`, `opinion`, `advertisement`, `tool_news`, `not_relevant`. Отсутствие подтверждённых кейсов после модельной классификации — отдельный итог `no_confirmed_cases`, не путать с пустым RSS или `success_no_matching_cases` tool. Метрики — «по утверждению автора/источника», не независимо доказанный эффект. Каждая включённая запись содержит безопасную ссылку на Хабр и `observation_id` плюс refs к RSS-полям; harness отклоняет unsupported IDs/links/claims.

Нормативный draft contract: compact JSON object с обязательными `run_id` (UUID, равен текущему), `outcome` (`cases_found|no_confirmed_cases|empty_feed`), `coverage_label` (`complete_for_profile|partial|unknown`), `entries` (array ≤ выбранному `model_seen`, максимум 20), `proposed_text` (модельный вводный абзац ≤1024 escaped UTF-8 bytes); никаких дополнительных полей. Сериализованный raw draft целиком ≤18432 UTF-8 bytes, включая JSON syntax, escaped строки и пробелы. Каждый `entries[]` требует `observation_id`, `category` из enum выше, `evidence_refs` — непустой массив ≤3 ссылок только на поля `title|rss_excerpt`, `summary` ≤256 escaped UTF-8 bytes, `metric_claims` — массив ≤1 объекта `{text, attribution}` с полями ≤160 и ≤120 escaped UTF-8 bytes соответственно; дополнительные поля запрещены на каждом уровне. Эти ограничения измеряются по JSON-escaped UTF-8 bytes, не по числу Unicode-символов. При `cases_found` нужен ≥1 `confirmed_described_case`; `no_confirmed_cases` требует ноль confirmed и допускает `possible_case` с явной маркировкой неопределённости; `empty_feed` разрешён только при валидном `success_empty` и пустом report pool. `coverage_label` равен фактическому aggregate/analysis coverage; partial нельзя переименовать в complete. `entries` содержит каждую переданную модели observation ровно один раз либо draft отклоняется. Harness сам вычисляет period, counts, links, report membership, omitted и итоговый Telegram payload ≤3500 символов из model-generated `proposed_text`/summaries и validated SQLite data; модель действительно пишет содержание сводки, но не выбирает recipient, ссылки и counts. Harness сверяет claims с RSS, проверяет размер/recipient boundary и не доверяет предложенным model totals. Classification dispositions+report+membership+publication claims+переход `REPORT_PENDING → REPORT_READY` фиксируются **в одной транзакции** с проверкой state/version и отсутствия чужого active claim. Если процесс падает до commit, отчёта/claims/dispositions нет; если после — `REPORT_READY` уже durable, повторный model call не нужен. При недостоверном, oversized или пустом draft — `FAILED_AFTER_DATA`, не выдуманный success; при исчерпанном model budget observations остаются в unclaimed backlog.

## FSM одного выпуска

Состояние хранится в SQLite с version и append-only transition record; transition делает `BEGIN IMMEDIATE`/CAS и проверяет evidence в той же транзакции. Обычный cron только создаёт новый slot/run или возвращает существующий; он не продвигает terminal/paused run. Explicit resume/backfill/resolve — операторский action с audit. Для нового slot при `DELIVERY_UNKNOWN` другой run может дойти до `REPORT_READY`, но **глобальный send gate** блокирует `SENDING`; publication lease допускает не более одного sender во всей очереди. Dispatcher запускается после нового `REPORT_READY`, при **каждом старте entrypoint до обработки slot** и после operator resolution/quarantine; он выбирает старший по slot sendable report **даже с пустым membership** (честная нулевая сводка), не вызывает модель/MCP повторно. Это восстанавливает окно crash после committed `REPORT_READY` до первого dispatch: готовый отчёт отправляется при следующем process start без повторного model/MCP call. Неразрешённый старший `FAILED_BEFORE_SEND`/`DELIVERY_FAILED` держит очередь до retry или operator retirement; старший `DELIVERY_UNKNOWN` держит глобальный gate до resolution/quarantine. Старый report при retirement остаётся immutable и навсегда non-sendable, его claims освобождаются транзакционно, и observations попадут в **будущий** report, а не в уже frozen более новый. Lease с expiry не разрешает повторить неопределённый Telegram request.

| State | Durable evidence; allowed next | Terminal / retry, crash recovery, operator |
|---|---|---|
| `STARTED` | slot+run; → `MCP_PENDING`, `FAILED_BEFORE_DATA` | nonterminal; crash: resume entry guard; operator inspect |
| `MCP_PENDING` | model/tool attempts, trusted request/key; → `DATA_READY`, `FAILED_BEFORE_DATA` | nonterminal; reconcile batch by key before any retry; operator resume if no committed data |
| `DATA_READY` | committed batch FK+coverage; → `REPORT_PENDING`, `FAILED_AFTER_DATA` | nonterminal; restart reuses immutable batch; operator inspect partial coverage |
| `REPORT_PENDING` | second model call текущего generation attempt/draft status; → `REPORT_READY`, `FAILED_AFTER_DATA` | nonterminal; report+claims+переход атомарны; crash до commit с исчерпанным первым attempt → explicit second attempt или failed/backlog, после commit уже READY |
| `REPORT_READY` | validated report FK+immutable membership/hash; → `SENDING`, `FAILED_BEFORE_SEND` | nonterminal; restart checks global gate, no re-generation; operator may defer |
| `SENDING` | persisted delivery attempt+payload hash+send lease; → `DELIVERED`, `DELIVERY_FAILED`, `DELIVERY_UNKNOWN` | nonterminal; crash after request boundary ⇒ unknown unless durable receipt; operator resolves unknown |
| `DELIVERED` | Bot API success receipt with `message_id`, confirmed checkpoint | terminal; ordinary cron never mutates; operator audits only |
| `FAILED_BEFORE_DATA` | stage+safe reason+attempt; explicit resume → `MCP_PENDING` при оставшемся generation attempt | paused; no automatic cron retry; после 2 attempts run остаётся failed/gap, operator inspect |
| `FAILED_AFTER_DATA` | batch FK+stage/reason; explicit resume → `REPORT_PENDING` при оставшемся generation attempt | paused; committed batch reused; после 2 attempts run остаётся failed, unclaimed observations переходят в backlog следующего отчёта |
| `FAILED_BEFORE_SEND` | report FK+stage/reason, proof no request bytes left process; → `REPORT_READY` при оставшемся send budget или operator retirement | paused, claims сохраняются; ≤1 automatic retry только для proven pre-send, explicit operator retry также в общем cap 2; после retirement логически terminal |
| `DELIVERY_FAILED` | report+полное definitive Bot API rejection **либо** авторитетное Telegram-side отрицательное подтверждение для того же attempt/payload; → `REPORT_READY` только explicit operator retry при оставшемся cap 2 или retirement | paused, claims сохраняются; no checkpoint; 5xx/неясный ответ/отсутствие receipt не definitive; после retirement логически terminal |
| `DELIVERY_UNKNOWN` | report+attempt+request-start marker, no reliable receipt; operator resolution only → `DELIVERED` **with externally verified message_id** или `DELIVERY_FAILED` **with authoritative Telegram-side negative acknowledgement linked to attempt/payload**; иначе остаётся `DELIVERY_UNKNOWN` с explicit quarantine resolution | blocked until resolution; never auto-resend; actor/time/reason/evidence required; quarantine clears global gate, but reserves membership and does not move checkpoint |

Каждый failure transition сохраняет stage и safe reason code. `DATA_READY` невозможен без committed batch, `REPORT_READY` без сохранённого валидированного report, `SENDING` без persisted attempt/payload hash, `DELIVERED` без `message_id`. `DELIVERED` terminal; paused failures и unresolved unknown не продвигаются обычным cron run. Report claims фиксируются при `REPORT_READY`: ни один active claimed или delivered observation не может войти в новый ready report, даже если старый payload позже retry. Неразрешённый unknown резервирует **все** observations своего report: они не входят в следующий send и delivery checkpoint не продвигается. Новые batches/reports можно готовить, но все автоматические sends приостановлены. Operator resolution фиксирует actor/time/reason/evidence; сомнение не превращается в delivered. Quarantine даёт возможность продолжить новые sends без повторения спорного payload, сохраняя неизвестный исход и reservation. После подтверждения доставки displayed members становятся `delivered`, не показанные members возвращаются в backlog; checkpoint обновляется транзакционно только до последнего непрерывно подтверждённого slot, не перескакивая unknown/quarantined gap. После доказанного недоставленного исхода допустим контролируемый retry того же immutable payload; при retirement release claims делает старый payload навсегда non-sendable, а observations переходят в backlog следующего ещё не готового отчёта.

## Telegram, security и observability

Telegram adapter получает только persisted report, берёт token/chat_id из защищённой app config, а не из модели/RSS/MCP; token хранится вне repo с правами проекта, в логах только имя переменной/маска. `chat_id` сверяется с config fingerprint. Никакого Telegram MCP tool и webhook. Сообщение одно, без multipart, ≤3500 символов (запас до лимита Bot API 4096); plain text либо безопасно экранированная разметка. Top entries выбираются детерминированно из неизменяемого membership, при нехватке места показывается omitted count, полный состав и флаг `displayed_in_payload` остаются SQLite. Только фактически показанные entries после receipt считаются доставленными материалами; не показанные не выдаются за новые, а остаются backlog с пометкой «не показано ранее». Send request начинается только после durable `SENDING`/attempt marker. Успешный Bot API `Message.message_id` подтверждает приём API, **не прочтение человеком**. Полный definitive Bot API rejection не считается доставкой и ведёт к `DELIVERY_FAILED`; 5xx, timeout или connection loss после начала запроса — `DELIVERY_UNKNOWN`. Automatic retry допускается лишь при доказанном pre-send failure; explicit operator retry после definitive rejection или **авторитетного Telegram-side отрицательного подтверждения, однозначно связанного с тем же attempt/payload**, допускается только при общем лимите ≤2 persisted send attempts на report. Обычное отсутствие сообщения в UI, отсутствие receipt, timeout и предположение оператора не являются таким proof; если отрицательного подтверждения получить нельзя, unknown разрешается только quarantine без resend. Если attempts исчерпаны, payload не повторяется, оператор выбирает retirement или quarantine. Не делать повторный send по одному лишь отсутствию receipt.

Независимо от символьного лимита harness перед `REPORT_READY` валидирует итоговый payload: максимум две уникальные статьи/ссылки на них, ноль гайдов/мнений/рекламы, `possible_case` явно назван возможным. Модельный `proposed_text` не может добавить третью статью или обойти выбор renderer. Повторная отправка использует тот же immutable payload и hash; лимит не позволяет регенерировать иной состав при retry.

RSS — недоверенный ввод: только HTTPS разрешённого Habr host/profile без redirect на иной host, response size/time limit, безопасный XML parser без DTD/XXE, ограничение полей, очистка HTML/control/bidi и нормализация URL; raw instruction text не становится системным сообщением. Tool output и model draft валидируются строго; prompt-only запрет не считается механической гарантией. Prompt-injection, «сменить chat_id», фальшивый `tools/call`, запрос token, oversized и malformed RSS/JSON — обязательные eval fixtures. Trace сохраняет run/slot, transition, attempt IDs, имя tool, arg digest, decision/reason, counts/coverage, report/hash, delivery outcome, usage/cost **если провайдер сообщил**, но не hidden reasoning, token или полный сырой RSS. Операторские журналы показывают gap, partial, stuck lease, unknown и очередь; alerts не должны сами отправлять тот же payload через другой канал.

## Enforcement и доказательства

| Инвариант | Механизм | Требуемое доказательство |
|---|---|---|
| Один run на slot; повтор возвращает его | SQLite `UNIQUE(slot_id)` + transaction | concurrency integration test |
| Один active publication/sender | global send lease + CAS/unknown gate | overlap/crash test |
| Tool write идемпотентен | `UNIQUE(run_id,key)` + atomic batch/items + replay | timeout/crash fault injection |
| Одна статья — одно observation | canonical ID `UNIQUE` + overlap/tie ordering | repeat/edit/same-pubDate test |
| `DATA_READY` требует batch | FK + transition guard | negative transition test |
| `REPORT_READY` требует validated report | FK/hash + transition guard | negative transition test |
| Report commit не оставляет `REPORT_PENDING` | report+membership+claims+state в одной transaction | crash at commit boundaries |
| `DELIVERED` требует receipt | message_id guard | receipt/timeout test |
| Observation не принадлежит двум sendable reports | active claim unique + retirement guard | old retry/new backlog overlap test |
| Нерелевантные записи не забивают backlog | durable classification disposition + доли new/backlog | 40 guides over runs → next real case test |
| Не более двух статей в отчёте, подтверждённые описанные кейсы в приоритете | deterministic renderer + payload validator + immutable `displayed_in_payload` | 3+ confirmed/possible, third-link injection, restart/backlog test |
| Send retry не обходит cap/unknown | persisted attempts ≤2 + proof guard | pre-send/API/5xx/timeout matrix |
| Recipient фиксирован | application config only + adapter guard | adversarial integration test |
| RSS не инструкция | trust boundary + strict validators | injection eval |
| Unknown не пересылается и блокирует sends | global gate + reservation/checkpoint separation | fault injection/restart test |

Acceptance — критерии ниже **не объявляют реализацию уже проверенной**. Mock, live provider, VPS и Telegram evidence хранятся раздельно.

| ID | Критерий | Evidence |
|---|---|---|
| A01 | VPS cron в 18:00 `Europe/Warsaw` вызывает agent entrypoint; DST/выключенный VPS/ручной backfill честны | VPS config+timestamp logs, zone test, human video review |
| A02 | duplicate slot/overlap не создают второй run или sender | SQLite concurrency integration |
| A03 | реальная модель сама выбирает разрешённый MCP (`auto`), есть provider→tool→provider trace | real-model trace с настоящим MCP, отдельно от mock |
| A04 | unknown tool/args/multiple/repeat отвергаются; каждый call имеет ровно один linked result | unit+integration adversarial |
| A05 | model/tool/active-wall/dispatch/size/article/retry budgets не обходятся и не сбрасываются crash; ожидание в durable очереди не расходует active wall budget | unit+fault injection с паузой >960 s |
| A06 | batch/items атомарны; timeout replay возвращает committed batch, без duplicate article | SQLite integration+crash injection |
| A07 | empty RSS, no new entries, no eligible candidates, no confirmed cases, partial coverage и outage различаются; релевантный item с повреждённым link/ID или отсутствующим pubDate после 18:00 не даёт false empty/no cases и сохраняется в read batch | RSS fixtures+integration |
| A08 | prompt injection/recipient/token/fake tool/oversize/malformed не меняют policy и не раскрывают secrets | adversarial eval+secret scan |
| A09 | невозможен `DATA_READY` без batch и `REPORT_READY` без report; crash до/после атомарного classification+report+membership+claims+state commit не оставляет stranded report; crash после commit до dispatch восстановлен при новом entrypoint без model/MCP, в том числе для пустого membership с ровно одним send | transition tests+restart fault injection |
| A10 | unknown delivery не повторяется, не входит в следующий send и блокирует sends/checkpoint до operator resolution; после resolution через >960 s oldest ready, включая пустой report, отправляется без новых model/MCP calls | timeout/restart integration+operator audit |
| A11 | отчёт трассируется к observation evidence, links и исходным metric claims; draft invalid combinations отвергаются; feed/backlog counts и omitted/displayed различимы; из 3+ релевантных в одном отчёте показаны ≤2, confirmed described cases раньше possible, possible маркированы, третья ссылка из `proposed_text` отклонена, остальные сохранены; серия из 40 нерелевантных с новыми кейсами проверяет доли 15+5 и backlog progress; worst-case допустимый compact draft для выбранного `model_seen` помещается в 18432 bytes и provider visible-token budget, а truncated/oversized draft не даёт ложный success; multipart нет | constructive max-field unit fixture + provider-tokenizer check, classification/SQLite integration+restart, mixed-category/third-link fixtures, live-model trace отдельно |
| A12 | `DELIVERED` только с `message_id`; pre-send failure, definitive rejection, 5xx и timeout различаются; automatic/explicit retry соблюдают общий cap 2 и proof guard; отсутствие receipt само по себе отвергается как proof | adapter integration+fault injection; финально real Telegram receipt |
| A13 | `day17/` не изменён и не импортируется | git diff/path+dependency static check |
| A14 | финальная реальная Telegram-доставка и расписание показаны в видео | Telegram receipt+VPS evidence+human video review |
| A15 | failed old report retry/retirement и newer backlog report не дублируют articles; после доставки не вошедшие в лимит двух остаются backlog и могут попасть в будущий отчёт; retry сохраняет тот же состав двух; checkpoint не перескакивает unknown | ownership/queue concurrency+restart fault injection |

## Открытые решения и launch gates

Реальные модель/MCP/RSS, Telegram receipt, cron-backfill с VPS и видео описаны
в [`day18/results/vps-live-20260927.md`](../../../day18/results/vps-live-20260927.md).
Первый именно ежедневный trigger в 18:00 Warsaw после установки ещё не
наступил; его timestamp остаётся отдельной проверкой A01. `SPEC_REVIEW.md`,
запрошенный прежним quality gate, в checkout не найден; прежние независимые
reviews относятся к исходным SHA и не являются review этой редакции.
