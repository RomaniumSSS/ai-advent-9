# Day30 · частный локальный LLM-сервис

Самостоятельный HTTP API поверх HTTPS и браузерный чат на домашнем Mac M2/16 GiB.
Локальная Qwen3 8B Q8 отвечает по найденным источникам; UI показывает фазы,
фактические времена и входные/выходные токены двух вызовов. Оригиналы
раскрываются отдельно. Основной LAN endpoint: `https://192.168.0.100:8080/`.

По уточнённому заданию сдаётся существующий profile12: **PUBLISHED_AND_READ_BACK; человеческая приёмка отдельно**.
Код: [GitHub main/day30](https://github.com/RomaniumSSS/ai-advent-9/tree/main/day30). Видео: [Day30-live.mp4](https://drive.google.com/file/d/1qZXTzqn9nUa3OL_yNYksOahMt_RivTZY/view?usp=sharing). [Результат и измерения](RESULT.md),
[доставка](DELIVERY.md), [рабочий контракт](SPEC.md), [трекер](TASKS.md).
Дополнительный архивный пересказ имеет сохранённый private semantic FAIL;
качество не объявляется исправленным и не блокирует исходное задание.
Доступ со второго физического устройства **NOT PROVEN**.

## Проверка исходного задания

12.10.2026: 151 offline тест, OK, 30.887 с на `/usr/bin/python3` 3.9.6;
auth/rate/context/lock/history проверены mock и loopback fixtures.
[Настоящий LAN preflight](results/assignment-delivery-preflight.json) подтвердил
CA+hostname, main/demo scopes и реальные отказы auth 401, max-length 400,
Host/Origin 403. Это запросы к LAN IP с того же Mac.

Dry/record: **PASS / PASS**, 3 / 3
новых assignment-ответов. В каждом сценарии — первый вопрос, продолжение
в том же чате и третий вопрос в новом; реальные IDs, длительности, token counts,
busy 409 и limits из receipts приведены в RESULT. Видео показывает новые
ответы без аудио и ускорения. Rate-limit 429 подтверждён offline;
полнота/точность пересказа, SLA и пиковая память не объявляются доказанными.

Код требует локально настроенных моделей, источников и индекса, TLS и env.
Приватный корпус/индекс, веса, credential и полные traces не публикуются.

## Запуск частного сервиса

Python 3.9+ и стандартная библиотека; framework и новые Python-зависимости не нужны.
Фактический backend в этой среде запущен через `/usr/bin/python3` (CLT Python3.9).
Офлайн проверки выполнены также Python3.14. LAN TLS с Framework Python3.14 здесь
таймаутился до приёма соединения; причина не установлена. Поэтому plist явно
использует проверенный `/usr/bin/python3`.
Ollama уже должен работать на `127.0.0.1:11434`. Сервис не запускает/не перезапускает
Ollama, не скачивает веса и не изменяет read-only индекс.

В `day30/private/.env` (0600, gitignored) оператор задаёт:

```dotenv
DAY30_TOKEN=<длинный случайный секрет>
DAY30_BIND=192.168.0.100
DAY30_PORT=8080
DAY30_SCOPE=all
DAY30_INDEX=/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1
DAY30_PRIVATE=/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day30/day30/private/service
DAY30_CERT=/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day30/day30/private/server.crt
DAY30_KEY=/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day30/day30/private/server.key
```

Индекс/модели проверяются перед запуском: generation `5d5502c69976163325ad6c35`,
DB SHA-256 `9894d937c4bcbae653459a6fe758f231992571e436622a0cd33fcda7f707f11b`,
724 чанка/663 документа; frozen digests обеих локальных моделей. Генератор
`qwen3:8b-q8_0` (profile12; protocol06), digest
`e56358ca25dd14db6853a9f68a92d717aaa6f0a94250a72d1a0f3d86a9f30130`,
embedding `qwen3-embedding:0.6b`; remote/cloud/proxy/redirect запрещены.
Индекс не входит в публичный репозиторий.

Исторический profile04 сменил только генератор, protocol06 — внутренние projections/schema
и вычисление missing. Profile12 сохраняет native format/think=false обеих стадий и сохраняет исправленную пересборку контекста при pruning:

- selection: think=false, native format, `{num_ctx:8192,num_predict:1024,temperature:0}`, deadline300с;
- synthesis: think=false, native format, `{num_ctx:8192,num_predict:1024,temperature:0.7,top_p:0.8}`, deadline300с.

Оба вызова одной8B Q8 передают независимые copies options. Dynamic ordered schema передаётся
только в native format и не дублируется в user message. System prompts дополнены общим
требованием соблюдать answer_limits. Embedding/index, protocol06 и context8192/template reserve512 прежние; embedding/прочие provider routes сохраняют300с. Из пакета8B Q8 обе стадии
наследуют `presence_penalty0`, `top_k20`, `repeat_penalty1.0`; selection также наследует
`top_p0.95`. Эти defaults не выдаются за явно переданные options. Исторический private semantic FAIL profile12 сохранён; надёжность архивного пересказа не доказана. По уточнённому SPEC это ограничение не блокирует сдачу исходного задания.
Установленная metadata gpt2/pre=`qwen2` принимается existing Qwen2Tokenizer;
151936 tokens/151387 merges, без нового tokenizer. [Read-only preflight](results/profile12-tokenizer-preflight.json)
подтвердил BPE factory/budgets на synthetic inputs. При неподдерживаемой metadata остаётся
явно отмеченный ByteBound fallback. Переход с9B/ByteBound меняет defaults и retained context;
это сравнение deployment profiles, без precision-only причинного вывода.
Для двух текстовых system/user сообщений сохраняется template reserve512; images/tools
не передаются. Оба prompt/schema budgets проверяются до вызовов, observed count — после.
Перед сменой модели оператор проверяет idle/lock и доступную память. При историческом profile04
switch `/api/ps=[]`: прежняя8B уже auto-expired, operator unload не выполнялся. Helper
не переключает Ollama и не скачивает веса. Исторические8B FAIL/receipts остаются прежними.


Сертификат должен содержать SAN актуального LAN IPv4 и localhost; ключ — 0600.
Публичный listener, `0.0.0.0`, tunnel и port forwarding не используются.
Если IP изменился, явно обновите bind и сертификат. Ссылка на UI:
`https://192.168.0.100:8080/`; токен в password-поле, хранение только в памяти страницы.

```sh
/usr/bin/python3 day30/server.py --env day30/private/.env
```

Отдельный launchd label и собственные private логи:

```sh
/usr/bin/python3 day30/deploy.py prepare --env day30/private/.env --python /usr/bin/python3
/usr/bin/python3 day30/deploy.py start --env day30/private/.env
/usr/bin/python3 day30/deploy.py status --env day30/private/.env
/usr/bin/python3 day30/deploy.py restart --env day30/private/.env
/usr/bin/python3 day30/deploy.py stop --env day30/private/.env
```

`prepare` только пишет plist/log-файлы. Bootstrap не имеет автоматических повторов:
ошибка plist/start возвращается оператору, а не маскируется retry. `start` bootstrap-ит `org.ai-advent.day30`.
`restart` делает bootout, ждёт снятия регистрации label **и** ухода сохранённого старого PID,
затем один bootstrap. Общий timeout — ExitTimeOut920+5с; при таймауте новый процесс
не запускается. Активный ход получает время завершиться. `stop` ждёт тех же состояний
и удаляет только этот job; другие дни и Ollama не затрагиваются.
Новые plist имеют ExitTimeOut920; существующие автоматически не переписываются.
Перед09 restart оператор регенерирует только main/demo plist через prepare.
После аварийного рестарта незавершённые receipts становятся `interrupted`; генерация
автоматически не возобновляется. Завершённые разговоры сохраняются. При stopped job
перед `start` не нужен `restart`. Текущее фактическое supervision состояние см. RESULT.

Проверка реального HTTPS API с CA и hostname, без `-k`; секрет читается из env-файла,
не передаётся в argv и не выводится:

```sh
python3 day30/client.py --env day30/private/.env \
  --base-url https://192.168.0.100:8080 --cafile day30/private/server.crt
python3 day30/client.py --env day30/private/.env \
  --base-url https://192.168.0.100:8080 --cafile day30/private/server.crt \
  --question 'Какие условия задания дня 21?' --wait \
  --output day30/private/service/client-response.json
```

Для проверки с другого устройства передайте доверенный сертификат и credential
защищённым способом; установите Python 3.9+ и используйте тот же клиент. Сам запрос
к LAN IP с этого Mac доказывает listener/TLS/API на этом хосте, а не доступ второго устройства.

## API

Все `/api/*` требуют `Authorization: Bearer …`. Host и присутствующий Origin должны
входить в точный allowlist; CLI без Origin разрешён. CORS wildcard нет. Статика не содержит
архивных данных и токена; headers запрещают внешние скрипты, framing и кэширование.

| Запрос | Результат |
| --- | --- |
| `GET /api/state` | Модель, серверный scope, context и активность |
| `POST /api/chat` | JSON `question`, необязательный `conversation_id`; HTTP202 + IDs и Location |
| `GET /api/requests/{request_id}` | `accepted/running/done/unknown/error/interrupted`, phase, answer, metrics |
| `GET /api/conversations/{conversation_id}` | Разговор и его ходы, без полного internal trace |

`question`: 1–500 символов, body ≤64 KiB, `Content-Type: application/json`.
Другие JSON-поля, включая `scope`, отвергаются. Частные IDs нельзя открыть в demo scope.
Ошибки: 400 invalid_request, 401 unauthorized, 403 Host/Origin, 413 body,
415 content-type, 409 busy, 429 rate_limit с Retry-After, 404 чужой/неизвестный ID.
Одна активная цепочка embedding→selection→synthesis; общего inference flock придерживаются
и соседние локальные дни. Очереди нет. Rate-limit: 6 принятых chat-запросов за скользящие60с
на credential; неверный ввод и busy не расходуют лимит. Счётчик в памяти процесса,
после рестарта начинается заново. Абсолютный deadline: embedding/selection300с, synthesis300с (connect/headers/body), retries0.
Синхронный `http.client` уменьшает timeout перед каждой операцией чтения, а не
перезапускает stage cap после очередного байта. При timeout transport socket получает
shutdown/close до возврата и освобождения flock; фонового reader нет.
Входящие соединения: максимум16 handler workers; при заполнении новое соединение
немедленно закрывается. Абсолютный deadline15с от приёма TCP охватывает TLS, заголовки
и body: медленная передача байтов не продлевает его. Watchdog закрывает только свой socket;
место освобождается при завершении/ошибке/таймауте. Это отдельный лимит от inference lock.

В ответе `answer`: `summary`, `conclusion`, `status` (supported/partial/unknown),
`source_refs` и `sources`. Каждый source — исходный evidence unit с `text`, author/date,
attribution, document/chunk IDs и offsets. Автор/дата не берутся из генерации.
Ссылки на background-контекст недопустимы как доказательные refs.

Внутренний контракт [protocol06](SPEC.md#protocol06-provenance-по-unit-id-и-вычисляемое-missing-12102026):
selection возвращает `evidence` как объект `evidence_id → [aspect_ids]` и coverage
`full|partial|none` для каждого аспекта вопроса. Повтор JSON-ключа на любом уровне —
ошибка, без last-value-wins/dedupe. Splitter разделяет предложение и проверку выполнения
(«и есть ли/было ли/удалось ли»). Полное описание предложения отвечает вопросу
о предложении; оно не доказывает его выполнение.

Selection получает весь текст unit и только evidence_id/source/author/date/attribution/context_ids.
Synthesis получает те же существенные metadata, весь text и evidence_role.
В обеих projections text передаётся целиком ровно один раз. Backend originals/metadata
остаются неизменёнными; context_ids в projection ограничены units, реально переданными в данной стадии.

По умолчанию selection допускает до8 proof units, synthesis — до4 points. Узкая команда
текущего вопроса «назови/приведи/покажи один пример/проблему/вопрос» в начале либо после
явной границы предложения включает limits1/1; quoted spans исключены, newline сохраняется,
с optional «пожалуйста/мне/конкретный». Negative/distributive формы и ordinary follow-up
сохраняют8/4; лимит не наследуется из истории. Single selection использует exact empty
или singleton oneOf branches, поскольку pinned converter игнорирует maxProperties.
Backend отдельно отвергает >1 proof/point, без truncation. Context units остаются background,
не дополнительным proof. Подробнее — [SPEC11](SPEC.md#profile11-явное-количество-примеров-и-non-thinking-12102026).

Synthesis возвращает до4 points (single — до1): каждый связывает аспекты с выбранным proof ID
и пересказом1–300 символов. Код проверяет ID/mapping и получает полный exact unit.text
и original offsets из backend; point→source quote/span сохраняется только в private trace.
Модель не копирует цитату и не создаёт anchor IDs/offsets.
Модель возвращает необязательные сомнения только для full аспектов (`doubtful_aspect_ids`, допускает []).
Missing вычисляет код как partial/none, аспекты без points и допустимые doubts;
partial/none нельзя скрыть, full можно только понизить.
Summary соединяет texts без смыслового исправления и добавляет именованную оговорку
«Не полностью подтверждены аспекты: …». Conclusion сохраняется из модели.
Points/source spans остаются в trace; публичные поля API прежние. При пустых points —
локальный unknown и точный вывод «Вывод: уточните вопрос или нужный источник.».
Структурный supported/partial и валидные unit IDs не являются semantic PASS.

Repair05 сохранил insertion order provider schema.properties для native grammar; canonical
packed/state/hash/context JSON остаются прежними. В pinned [llama.cpp b10760 converter](https://github.com/ggml-org/llama.cpp/blob/b10760/common/json-schema-to-grammar.cpp#L956)
порядок properties задаёт native grammar order, required array его не задаёт.
Текущий12 использует структурные aliases, чтобы alphabetical Go-map serialization
сохраняла grounding-first. Selection wire: `a_evidence,b_coverage`; synthesis wire:
`a_points,b_doubtful_aspect_ids,c_conclusion`; conclusion: `a_text,b_point_refs`.
Point `aspect_ids,evidence_id,text`, сами evidence/Q/P IDs и free text не переименовываются.
После strict JSON duplicate gate нормализация только этих paths возвращает canonical06;
unknown/mixed/missing alias shape — ошибка, без canonical fallback/repair.

Private `*_wire_schema` и `schema_property_order` показывают actual alias wire после pruning;
`*_schema` и `*_response` отдельно сохраняют canonical schema/result. Safe raw final остаётся
alias JSON byte-exact; positive persistence allowlist проверяет exact wire shape, arbitrary
reasoning payload остаётся opaque. Wire schema включена в budget перед каждой pruning попыткой.
Исторические thinking profiles08–10 использовали prompt schema; старые receipts не меняются.

Обычный ответ — два последовательных `/api/chat`: selection think=false/temperature0/native,
synthesis think=false/temperature0.7/top_p0.8/native. Non-thinking native route не требует
дополнительного thinking→format pass.
Ровно два сообщения system/user для каждой стадии; critic/retry отсутствует.
`num_ctx=8192`, template reserve512 прежние. Selection резервирует1024 output/300с;
synthesis1024 output/300с. Unexpected thinking отвергается; reasoning не сохраняется.
Общие limits: provider caps суммарно900с, worker join910с, launchd920с, CLI/video poll930с.
Это границы provider calls с небольшим lifecycle запасом, не SLA всего запроса: local overhead отдельно.
Пустой поиск, уточнение, отсутствие оснований и ошибка могут остановиться раньше.
ByteBound считает actual messages и native schema ровно один раз в обеих стадиях;
user content содержит только context JSON.
Tokenizer берётся из metadata уже установленной модели, при отсутствии — явно отмеченная
консервативная UTF-8 byte-bound оценка. Сначала убираются старые вопросы (до трёх),
затем целые низкорелевантные evidence units; текущий вопрос не обрезается. Allowed IDs/schema/mapping/coverage
перестраиваются перед КАЖДЫМ budget test из актуальных units, включая focus/context IDs.
Effective coverage вычисляется из исходной validated selection coverage, без накопительного downgrade. Потеря части proof по аспекту
снижает full до partial, потеря всех — до none. Model points после вызова не обрезаются. Старый assistant prose не является фактом.

Follow-up сопоставляет только прежде цитированные `evidence_id` по неизменным
chunk/offset/text/author/date/attribution со свежими spans; изменение S-номера
не сбивает focus, соседний span не наследует его. Legacy whole-chunk fallback
применяется только к legacy `S1` refs. Пересказ сохраняет субъект/объект,
направление действия, конкретные альтернативы, существенные числа и отрицания.
Эти инструкции требуют нового live semantic review; сами по себе они не доказывают качество.

History/полные prompts/sanitized model responses хранятся только `DAY30_PRIVATE/state/`, 0700/0600,
атомарно. API возвращает разрешённые оригиналы и агрегаты, без полного trace. Логи —
ID/status/metrics; без token, вопросов, private текста или provider traceback.
Новые private traces имеют `protocol_version=protocol06`: full units, отправленные projections,
point→unit quotes/spans и code-derived missing отдельно от model doubts.
`generation_parameters` для known-sent стадий содержит model, think, format_mode
(текущий native) и полный options dict; answer_limits записаны отдельно;
каждая budget запись содержит тот же options dict и actual deadline_seconds рядом с ним.
Deadline не входит в Ollama options; provider_attempt_deadlines/provider_deadlines
отмечают attempted/known-sent стадии, включая embedding. `generation_attempt_parameters`
помечает попытки отдельно: pre-send ошибка не доказывает отправку. Всё это только private
trace; API не публикует эти поля. Прежние receipts не мигрируются.
До любого persistence удаляется message.thinking; reasoning остаётся только в RAM.
Сохраняются лишь безопасно разобранный final JSON, metadata/metrics и provenance;
допускается boolean reasoning_present без текста. False-phase thinking по-прежнему
отвергается до потери RAM-значения. Пустой/length/неверный/duplicate final — FAIL без repair.
При schema/refs failure безопасный final JSON остаётся доступен в private diagnostics.
Persistence использует positive allowlist final shape: только evidence/coverage либо
points/doubtful_aspect_ids/conclusion, exact nested keys и ожидаемые types. Любые extra
поля (включая analysis) или произвольные nested payloads сохраняются opaque. Local gate
проверяет прежний raw JSON в RAM; shape-valid invalid refs остаются диагностируемыми,
никакого удаления fields из ответа или repair нет.

Typed error сохраняет private partial snapshot: phase, validation code, budgets/prompts.
Malformed/partial transport body и неразобранный final content сохраняются только как
bytecount/SHA256/stage, без prefix/excerpt. Response_data также санитизируется перед snapshot;
reasoning никогда не подставляется как final. `generation_calls`/`embedding_calls` считают
попытки; `*_completed_calls` — вызовы, вернувшие response. При failed call сохраняется время.
API удаляет trace/query и возвращает coarse error + агрегаты. Eval_count/durations описывают
полную provider generation, включая reasoning; объём/скорость08 ещё не измерены.

В официальном [Ollama0.33.3 routes](https://github.com/ollama/ollama/blob/v0.33.3/server/routes.go#L2592)
completion использует context входящего HTTP request; [Go Request.Context](https://pkg.go.dev/net/http#Request.Context)
отменяется при закрытии клиентского соединения. Это основание механизма cancellation.
Fixture доказывает закрытие клиентского fd и прекращение своего peer, но реальная
задержка остановки computation Ollama после timeout отдельно не измерялась.

## Проверки и видео

```sh
python3 -m unittest discover -s day30/tests -v
uv run --no-project --with playwright python day30/tests/browser_offline.py
```

[RED](results/offline-red.log): приложение ещё отсутствовало; затем контрактные тесты
ловили ошибки первой реализации. Отдельный реальный TLS [RED](results/tls-stalled-red.log)
воспроизвёл stalled TCP → заблокированный handshake. Luna finding о slow fragments/workers воспроизведён [RED](results/connections-red.log)
(3 поведенческих FAIL из4) → [GREEN](results/connections-green.log): абсолютные deadlines
headers/body, немедленное capacity rejection и освобождение slots.
Launchd lifecycle [RED](results/deploy-lifecycle-red.log) →
[GREEN](results/deploy-lifecycle-green.log) проверяет ожидание registration/PID, timeout
и отсутствие скрытого bootstrap retry с подставным launchd. Реальный restart подтверждается отдельно.
Astra follow-up/error-trace/provider deadline [RED](results/astra-fixes-red.log) →
[GREEN](results/astra-fixes-green.log): настоящий формат двух turns, S-renumbering/neighbor,
private-only diagnostics selection/synthesis/timeout, partial headers/body абсолютного
provider deadline, закрытый fd, malformed provider JSON/redirect/error без retry и schema.
[Полный quiet suite](results/offline-astra-fixed.log) использует mock модели и loopback fixtures;
реальные начальные semantic FAIL/runtime error сохранены, новые ответы проверяются отдельно.
Repair03 [RED](results/protocol03-red.log) → [targeted GREEN](results/protocol03-green.log),
[quiet full suite](results/protocol03-regression.log): strict duplicate keys,
per-aspect coverage, точные anchors, invalid refs/background/conclusion, named missing,
unknown и оба budgets/pruning. Старые negative fixtures обновлены на keyed mapping/points;
проверки timeout/length/no-retry/private diagnostics сохранены. Эти mock/fixture проверки
не заменяют новый bounded live и независимый semantic review.
Profile04 [RED](results/profile04-red.log) → [targeted GREEN](results/profile04-green.log):
pinned9B identity/digest, wire/response model, wrong-model/no-retry, qwen35→ByteBound
и оба бюджета до provider. [Связанные проверки](results/profile04-regression.log) включают
pruning/mapping и observed overflow. Это mock/loopback evidence; новая9B inference/семантика
проверяются root отдельно. Прежние полные наборы относятся к сохранённым baselines.
Repair05 [RED](results/ordering05-red.log) → [targeted GREEN](results/ordering05-green.log),
[связанные regression checks](results/ordering05-regression.log): настоящий loopback wire
Ollama.request, четыре schema orders/dynamic IDs, semantic payload equality, canonical
packed/private save/prompt body, private order arrays и отсутствие выдуманной стадии.
Связанные transport/deadline/identity/budget/negative проверки используют моки и fixtures;
новая real generation этим ремонтом не запускалась.
Protocol06 [targeted GREEN](results/protocol06-green.log), [связанные проверки](results/protocol06-linked.log)
и [полный quiet suite](results/protocol06-full.log): full-text projection без opaque metadata,
whole-unit pruning/actual budgets, immutable point→unit provenance, code-derived missing,
full-only doubts и actual wire order. [История RED и границы проверки](results/protocol06-offline.md)
отделяет отменённый anchor draft от финального контракта. Эти102 stdlib mock/loopback checks
относятся к сохранённой baseline06 и не подтверждают семантику; реальные semantic FAIL
остаются историческими результатами.
Profile07 [RED](results/profile07-red.log) → [targeted GREEN](results/profile07-green.log),
[связанные79 checks](results/profile07-linked.log): actual loopback selection/synthesis options,
копии defaults, budget/observed limits по переданным options и private diagnostics при ошибках.
[Описание проверки](results/profile07-offline.md) отделяет offline evidence от нового live gate.
При profile07 полный suite102 baseline06 не повторялся; HTTP/UI/lifecycle не менялись.
Profile08 [RED](results/profile08-red.log) → [targeted GREEN](results/profile08-green-final.log),
[связанные checks](results/profile08-linked-final.log), [full suite](results/profile08-full-final.log):
actual format omission/think flag, ordered embedded schema и единственный budget accounting,
strict final gate и reasoning privacy в success/error/timeout/files/API/logs. [Evidence](results/profile08-offline.md)
отделяет mock/loopback проверки от pending реальной семантики и latency08.
Independent review нашёл P2 вне initial118 checks: parseable arbitrary analysis fields
попадали в private error snapshots. [Positive-shape repair](results/profile08-shape-offline.md),
[RED](results/profile08-shape-red.log), [targeted GREEN](results/profile08-shape-green.log),
[linked](results/profile08-shape-linked.log), [full](results/profile08-shape-full.log)
проверяют actual Application/Store error paths. Initial08 baseline/logs сохранены.
Profile09 [RED](results/profile09-red.log) → [targeted GREEN](results/profile09-green.log),
[linked](results/profile09-linked.log) и [cancel-before-unlock](results/profile09-cancel-before-unlock.log):
stage caps600/300, wire output1408, context/observed budget и lifecycle/poll waits.
[Evidence09](results/profile09-offline.md) описывает исторические mock/loopback проверки.
[Actual09](results/live-private-09.json) завершился length1408/empty final; следующие два cases не запускались.
Profile10 исправляет inherited stale-schema pruning и использует1920/900: [RED](results/profile10-red.log),
[causal pruning RED](results/profile10-pruning-red.log), [final targeted GREEN](results/profile10-green-final.log),
[linked111](results/profile10-linked.log), [evidence](results/profile10-offline.md).
[Actual10](results/live-private-10.json) — length1920/empty final, следующие два cases не запускались.
Profile11: [RED](results/profile11-red.log), [final20 PASS](results/profile11-green-final.log),
[linked116 PASS](results/profile11-linked-initial.log), [boundary13 PASS](results/profile11-boundary-green.log),
[quantity preflight](results/profile11-quantity-preflight.json), [evidence](results/profile11-offline.md).
Это mock/loopback результаты. [Actual11](results/live-private-11.json) дал runtime PASS122.387с,
но semantic FAIL; следующие2 cases не запускались. Profile12 offline:
[RED](results/profile12-red.log), [final15 PASS](results/profile12-green-final.log),
[linked127 PASS](results/profile12-linked-initial.log), [evidence](results/profile12-offline.md).
[Actual12](results/live-private-12.json) завершён: runtime PASS 163.639 с, semantic FAIL; следующие два private cases не запускались. Сдача исходного задания использует отдельно учтённые новые assignment-запросы из RESULT.
[GREEN](results/offline-green.log) —
офлайн core/HTTP/context/store/deploy и TLS с временным cert, без Ollama inference.
[Playwright](results/browser-offline.json) — mock HTTP/UI, desktop/tablet/mobile,
безопасный рендер hostile source, очистка token, новый разговор, отсутствие overflow.
Скриншоты `results/ui-mock-*.png` явно относятся к mock, не к живому демо.

Публичная запись использует отдельные env/порт8081/state с
`DAY30_SCOPE=assignment`: фильтрация перед retrieval/prompt/history,
без клиентского переключателя на private. На private сервисе `/demo` и
`/api/demo/*` также assignment-only; основной endpoint assignment-сервера
сохраняет этот scope при любом URL и JSON-поле.

Подготовка и запуск отдельного demo выполняются оператором; запись использует
уже работающий сервис и не перезапускает модель. Paths и bind задаются в env:

```sh
/usr/bin/python3 day30/deploy.py prepare --env day30/private/demo.env --python /usr/bin/python3 \
  --label org.ai-advent.day30.demo --scope assignment
/usr/bin/python3 day30/deploy.py start --env day30/private/demo.env --label org.ai-advent.day30.demo
/usr/bin/python3 day30/deploy.py status --env day30/private/demo.env --label org.ai-advent.day30.demo
uv run --offline --no-project --with playwright python day30/video/run_demo.py \
  --mode record --env day30/private/demo.env \
  --base-url https://192.168.0.100:8081 --cafile day30/private/server.crt \
  --output day30/private/video/record-20261012-01
```

[Сценарий](video/SCENARIO.md) одинаков для dry/record: три новых assignment-вопроса,
включая same-chat follow-up, ожидание по конкретным новым request IDs,
пересказ/вывод и раскрытие originals. Отдельно обозначенный блок показывает
фактические API state, auth/max-length/busy отказы и ограниченные метрики.
Скрипт требует новый каталог, CA+hostname preflight и assignment scope;
Chromium доверяет SPKI указанного сертификата. Токен в password-поле
немедленно очищается. Unknown/error/timeout останавливают прогон без retry;
raw WebM и receipts остаются private, MP4 создаётся без аудио/ускорения.
Dry+record создают шесть новых принятых запросов; не повторяйте сверх согласованного
live-бюджета. [Инструкция и проверка видео](video/README.md).

Provenance: самостоятельные копии metadata/vector/Ollama/flock, full metadata attribution,
lexical ranking/resolve_query, evidence/admissibility и byte-BPE из Day29 в базе `b3e607e`.
Runtime imports ограничены Day30. Старые дни, индекс, веса и истории не изменяются.
