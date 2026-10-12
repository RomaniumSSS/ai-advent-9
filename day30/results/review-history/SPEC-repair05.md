# Day30 — частный локальный LLM-сервис

Рабочий контракт от 11.10.2026. Основание: условие Day30 и одобренный формат в
корневом HANDOFF; новый запрос «начинай день 30 там все написано» снимает прежний
стоп до CLEAR. Отдельное человеческое утверждение этого документа не заявляется.

## Результат и границы

Самостоятельная папка `day30/`: частный HTTP API поверх HTTPS и браузерный чат на
домашнем Mac M2/16 GiB. Сетевой доступ, стабильность нескольких запросов, rate-limit
и max-context; сдача — код и немое MP4 живых ответов. Ответ по архиву: локальный поиск
→ выбор оснований → короткий связный пересказ → практический вывод с источниками;
неизменённые оригиналы раскрываются отдельно. Автор/дата берутся из исходных metadata.

Индекс только read-only: `/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1`,
generation `5d5502c69976163325ad6c35`, DB SHA-256
`9894d937c4bcbae653459a6fe758f231992571e436622a0cd33fcda7f707f11b`,
724 чанка / 663 документа (24 assignment, 694 discussion, 6 personal_note).
`qwen3.5:9b-q4_K_M` (profile04 ниже) и `qwen3-embedding:0.6b` с проверкой существующих digest/options;
Ollama только `127.0.0.1:11434`, без proxy, redirect, cloud и автоматических retries.
Day29 runtime, код, индекс, история и старые прогоны не меняются и не возобновляются.
Нужный код копируется в Day30; runtime-import других дней запрещён. Нет покупки VPS,
публичного порта, нового framework, FSM, новых весов или большой переоценки Day29.

## Критерии приёмки

| ID | Проверяемый контракт |
| --- | --- |
| A1 | UI и API обслуживает отдельный процесс Day30. API принимает вопрос и необязательный ID разговора; возвращает ID запроса, статус, пересказ, вывод и структурированные источники либо конкретную ошибку. UI позволяет новый разговор, продолжение и раскрытие оригиналов. Текущий вопрос 1–500 символов, JSON body до 64 KiB; неверный ввод отвергается до inference. |
| A2 | Свежий retrieval использует весь private snapshot. Обычный содержательный ответ выполняет ровно два последовательных chat-вызова одной Qwen3.5 9B profile04, `think=false`: первый выбирает допустимые evidence IDs, второй получает выбранные оригиналы и формирует пересказ/вывод с допустимыми refs. Embedding считается отдельно. Пустой поиск, отсутствие оснований, уточнение и ошибка могут закончиться раньше; скрытого retry/третьего critic нет. |
| A3 | Пересказ обычно 2–4 коротких предложения, вывод 1–2 предложения. Вывод не приписывает источнику неподтверждённое действие или результат; рекомендация обозначена как вывод, неопределённость сохранена. Генератор не придумывает автора, дату, цитату или URL. Код проверяет JSON/завершённость/refs и точность показанных оригиналов, но не объявляет смысл автоматически доказанным. Неизвестное — честный unknown, без свободного ответа вне корпуса. |
| A4 | Для обоих вызовов независимо до отправки: полный prompt, schema, reserve шаблона 512 и выходной резерв укладываются в `num_ctx=8192`. Начальные `num_predict`: selection1024, synthesis1024; temperature0. Локальный tokenizer из metadata модели либо консервативная byte-bound оценка явно отмечены в trace. История — до трёх последних пользовательских вопросов темы, не доказательство; старый assistant prose не используется как факт. При переполнении удаляются старые вопросы, затем целые низкорелевантные источники; текущий вопрос не обрезается. Второй вызов не получает источники, исключённые из его окончательного бюджета. |
| A5 | Не более одной активной цепочки embedding→selection→synthesis; общий существующий inference flock сохраняет совместимость с локальными днями. Конкурентный запрос получает busy409 без очереди. Не более 6 принятых chat-запросов за скользящие60с на credential; превышение —429 + Retry-After, до inference. Таймауты ограничены (не более300с на вызов), lock освобождается при любой ошибке. Нет бесконечной очереди или retry. |
| A6 | Частный deployment: TLS на конкретном LAN IPv4, отдельный свободный порт (кандидат8080), без port forwarding/public tunnel/0.0.0.0. Сертификат с SAN фактического LAN IP и localhost, приватный ключ0600. API и приватные источники требуют bearer credential; UI держит его только в памяти, не в URL/localStorage/логах. Секрет — в `.env`0600, gitignored; постоянное сравнение credential. Host/Origin allowlist, отсутствующий Origin для CLI допустим, чужой Origin отвергается; CORS wildcard нет. Статика не раскрывает данные; текст рендерится безопасно, без удалённых скриптов. |
| A7 | История/trace принадлежат только Day30, dir0700/files0600, gitignored, атомарная запись. После рестарта завершённые разговоры сохранены, незавершённый ход interrupted без автоматической генерации; новый разговор не наследует другой. Логи содержат ID/статус/длительность/счётчики, без credential, prompt, приватных источников или provider traceback. Подробные ответы и semantic evidence сохраняются только private. Day30 имеет отдельный supervision/start/stop (launchd), не перезапускающий старые приложения. |
| A8 | Offline проверены auth/Host/Origin/body/JSON,429/busy, оба context budget, неверные IDs/JSON/length/timeout, освобождение lock, история/restart и изоляция demo. Короткий реальный smoke: ≥3 последовательных содержательных запроса, включая private discussion и follow-up, затем восстановление после контролируемого рестарта. Независимый смысловой просмотр пересказа/вывода по реально выбранным оригиналам фиксирует полноту, атрибуцию, числа и различие план/результат. Mock PASS не заменяет live evidence. |
| A9 | Сетевая проверка — настоящий HTTPS запрос к LAN IP с проверкой сертификата через локальную CA/сертификат, без `-k`; auth и ошибки также проверяются через API. На данном этапе доступно одно физическое устройство: такой тест доказывает LAN listener/TLS/API на этом хосте, доступ с другого устройства остаётся NOT PROVEN. README содержит точную клиентскую команду с CA и состояние supervision. |
| A10 | Public demo — отдельный явно обозначенный server-side scope `assignment`: фильтрация до retrieval и model prompts, отдельная история, только assignment originals. Запись экрана показывает ввод ≥2 вопросов, ожидание настоящей генерации, короткий ответ/вывод и раскрытие источника; без аудио, токена, private корпуса и постановочных ответов. Видео может входить в те же реальные проверки. Код/публичные отчёты не содержат приватных текстов, raw traces или ключей. |

## Уточнение repair03: внутренний протокол, 12.10.2026

Root выбрал bounded repair после двух неудачных private pair. Это уточнение A2–A4/A8;
отдельное человеческое утверждение документа не заявляется. Изначально использована Qwen3 8B; текущий генератор задаёт profile04 ниже.
Сохраняются два последовательных вызова, think=false и прежние API/формат UI. Иные модели,
третья стадия, retry, изменения retrieval/corpus и специальные ответы по кейсам не входят.

**Общие правила.** JSON обоих model responses разбирается strict parser: повтор ключа
на любом уровне — `duplicate_json_key` до schema validation; никакого last-value-wins.
У всех объектов закрытый набор полей, типы строгие. Аспекты Q1…Q6 строятся из вопроса;
generic splitter разделяет предложение и проверку его выполнения, в том числе
«и есть ли», «и было ли», «и удалось ли», без словаря тем/имён корпуса.

**Selection:** ровно два поля:

```json
{"evidence":{"S1.U1":["Q1"]},"coverage":{"Q1":"full","Q2":"none"}}
```

`evidence` — object с 0–8 ключами, только exact allowed evidence IDs текущего prompt;
каждое значение — непустой массив уникальных текущих aspect IDs (до6). Dynamic schema
перечисляет допустимые ключи и запрещает остальные; локальный validator повторяет
проверки, включая maxProperties8. Один ID объединяет относящиеся аспекты. `coverage`
содержит ровно все текущие Q IDs со значением `full|partial|none`. Для каждого Q:
none тогда и только тогда, когда ни один выбранный ID не ссылается на Q; иначе full
или partial. Покрытие относится к **вопросу**, а не к завершению события: описание
плана может полностью отвечать «что предложили», не доказывая «что сделали».
Отдельного blanket статуса not_proven больше нет. Coverage — оценка модели, не факт
независимой проверки. Invalid selection остаётся ошибкой, silent dedupe запрещён.

**Synthesis:** ровно `points`, `missing_aspect_ids`, `conclusion`:

```json
{"points":[{"aspect_ids":["Q1"],"evidence_id":"S1.U1",
 "anchor":"точная короткая подстрока original","text":"Одно предложение пересказа."}],
 "missing_aspect_ids":["Q2"],
 "conclusion":{"text":"Вывод: практический следующий шаг.","point_refs":["P1"]}}
```

`points` — 0–4 объектов ровно с указанными полями. `aspect_ids` — 1–6 уникальных Q;
`evidence_id` — один реально переданный proof ID, выбранный selection **для каждого**
указанного Q. `anchor` — непустая contiguous подстрока текста этого unit, 1–160
символов; `text` — непустой пересказ, 1–300 символов, обычно одно короткое предложение.
Смысловые роли, числа, альтернативы, условия и отрицания сохраняются; code validator
не объявляет это доказанным по наличию anchor. IDs P1…Pn назначает код по порядку
points, модель их не генерирует отдельным полем.

`missing_aspect_ids` — 0–6 уникальных Q. Обозначим C объединение point.aspect_ids,
M множество missing, A все Q. Требуется C∪M=A; любой Q с effective coverage=none
входит в M и не входит в C; любой partial входит в M, но может одновременно входить
в C (известна часть). Full допускается консервативно понизить, включив в M; нельзя
повысить partial/none или скрыть неприведённый аспект. Для каждого Q в C существует
point с допустимым proof ID. Сам факт присутствия Q не доказывает смысловой полноты.

`conclusion` имеет ровно `text` (1–1000 символов, начинается «Вывод:») и `point_refs`
(уникальные P1…Pn, максимум4). Для непустых points требуется ≥1 действительная ссылка;
вывод не может ссылаться на несуществующий point или новое основание. Для пустых
points обязательны M=A, point_refs=[] и точный текст
«Вывод: уточните вопрос или нужный источник.»; это unknown, без свободной генерации фактов.

**Renderer и совместимость.** Для непустых points summary — их texts в исходном
порядке, соединённые пробелом; при M≠∅ добавляется короткая детерминированная оговорка
с текстами соответствующих аспектов. Общая длина ≤1800; превышение — validation error,
не обрезание. Conclusion переносится из валидированного text без смысловых исправлений.
source_refs — уникальные point.evidence_id в порядке появления; sources материализуются
из immutable originals с metadata. Anchor/points не вставляются в публичный UI/API:
сохраняются прежние answer `{status,summary,conclusion,source_refs,sources}` и request
`done|unknown|error`. Answer status supported лишь при M=∅ и всех effective coverage=full;
иначе partial. Это структурный model-reported статус, не semantic PASS. При points=[]
answer status/request status unknown, summary начинается «Не знаю по переданному контексту»,
refs/sources пусты. Если selection пуст или после pruning не осталось proof, завершить
этим же локальным unknown без второго вызова. Старые receipts не мигрировать; новые
private traces имеют `protocol_version=repair03` и сохраняют raw output/ошибки.

**Budget/pruning.** Оба вызова сохраняют num_ctx8192, output1024 и template reserve512.
До selection при pruning пересобираются allowed IDs/schema; до synthesis сначала
убираются старые вопросы, затем целые низкорелевантные units. После каждого удаления
пересобираются proof IDs, evidence→aspect mapping и schema. Coverage Q становится
none при потере всех его proof, partial при потере части, иначе сохраняется; не повышается.
Background не превращается в proof. Points строятся только по окончательно переданным
units; готовые model points/anchors после вызова не обрезаются и не выбрасываются ради
успеха. Длинный/незавершённый вывод — ошибка без retry. Budget/pruning сохраняются в trace.

Новые safe validation codes минимум: `duplicate_json_key`, `invalid_selection_mapping`,
`invalid_selection_coverage`, `invalid_synthesis_points`, `invalid_point_aspects`,
`invalid_point_reference`, `invalid_point_anchor`, `invalid_missing_aspects`,
`invalid_conclusion_refs`, `invalid_unknown_points`, `rendered_summary_too_long`.
Публичная ошибка остаётся invalid_model_response; подробный код — в private trace
через allowlist, без текстов/секретов в служебных логах.

**Gate repair03:** после offline/review максимум **3 дополнительных приватных
содержательных запроса**: известный pair + один новый transfer case, подобранный
root/reviewer без подгонки prompt. Все три должны дать runtime PASS и независимый
semantic PASS summary/conclusion по originals. Иначе остановить зависимые public
dry/record/публикацию, сохранить FAIL и пересмотреть гипотезу; дополнительных retries
этот лимит не разрешает. Public dry/record начинается только после PASS этого gate.

## Profile04: отдельная гипотеза генератора, 12.10.2026

После FAIL первого запроса repair03 root выбрал установленную Qwen3.5; оставшиеся
два запроса repair03 не выполнялись. Это новая гипотеза модели, а не четвёртая правка
prompt. Архив [SPEC protocol03](results/review-history/SPEC-protocol03.md) сохранён.
Отдельное человеческое утверждение этой редакции не заявляется.

- Единственные runtime-константы изменения в `local.py`: `MODEL='qwen3.5:9b-q4_K_M'`,
  `GEN_DIGEST='56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90'`.
- Протокол repair03, обе schema/prompts, retrieval, frozen embedding/index, два
  последовательных вызова одной модели, think=false, temperature0, num_ctx8192,
  num_predict1024 и вопросы следующего gate сохраняются. Покупки, pull новых весов,
  tokenizer rewrite и сервисные/global изменения не входят в эту правку.
- Read-only `/api/show` подтвердил GGUF Q4_K_M9.0B, architecture/pre=qwen35,
  tokenizer model=gpt2,248320 tokens/247587 merges, все256 byte-symbols. Qwen2Tokenizer
  обязан отклонить pre=qwen35; используется уже существующий `ByteBound` fallback,
  метод в trace `conservative_utf8_byte_bound_with_reserves`, без маскировки под BPE.
- Template reserve512 остаётся для **двух текстовых сообщений system/user**, без
  images/tools/assistant prefill. Модель умеет vision, но Day30 передаёт только текст.
  Полный UTF-8 prompt + schema +512 +output1024 должен пройти ≤8192 до каждого вызова;
  actual prompt_eval_count +1024+512 также проверяется после ответа. Ни silent
  truncation, ни автоматического расширения контекста при консервативном pruning нет.
- Модель заявляет requires0.30.0; текущий Ollama0.33.3 совместим по этому ограничению.
  Реальный Day26 на0.33.3 уже выполнял её `/api/chat`, think=false,8192 в synthetic tool
  cases ([сохранённый run](../day26/results/agent-comparison/run01/run.json)); это
  подтверждение прошлого запуска, не новый PASS repair03/semantic/schema.
- `/api/show` template `{{ .Prompt }}` неполон как описание обёртки: Modelfile выбирает
  renderer/parser qwen3.5. В [официальном renderer v0.33.3](https://github.com/ollama/ollama/blob/v0.33.3/model/renderers/qwen35.go)
  для текущей text-only формы служебная обёртка меньше512 UTF-8 байт; это основание
  сохранить запас, не точный подсчёт prompt tokens. Фактические options также наследуют
  model defaults presence_penalty1.5/top_p0.95/top_k20; их не менять отдельным patch.
- После offline/review root проверяет idle и освобождение inference lock, выгружает
  только старую8B из RAM, затем допускает9B; не держать два генератора на16GiB одновременно.
  Существующий Ollama не перезапускать, другие процессы/веса не менять. Выгрузка/загрузка
  этой архитектурной проверкой не выполнялась.
- Новый bounded gate profile04: тот же известный private pair и тот же уже выбранный
  transfer case, максимум3 дополнительных содержательных запроса без retry. После
  любого runtime/semantic FAIL зависимые public dry/record/публикация ждут; вопросы,
  требования и валидаторы под результат не менять. Старые FAIL остаются FAIL, новая
  baseline фиксирует generator digest и budget method отдельно от protocol_version=repair03.

## Repair05: порядок provider schema, 12.10.2026

После первого FAIL profile04 root выбрал узкое исправление сериализации; прежняя
[SPEC profile04](results/review-history/SPEC-profile04.md) сохранена. Человеческое
утверждение этой редакции не заявляется. Генератор9B, options, prompts, содержимое
schema, validators/критерий missing, retrieval, вопросы и число стадий сохраняются.

Только provider HTTP body сериализуется с сохранением insertion order, без sort_keys.
Canonical `packed` для state/hash/prompt body остаётся прежним. Причина: pinned
[llama.cpp b10760 converter](https://github.com/ggml-org/llama.cpp/blob/b10760/common/json-schema-to-grammar.cpp#L956)
в explicit-renderer пути Ollama0.33.3 использует порядок properties для required fields.
До исправления сортировка задавала conclusion перед points; это подтверждённый
дефект порядка, но его исправление ещё не доказывает semantic улучшения.

Обязательный порядок `schema.properties` в реальном provider wire:

- selection root: `evidence → coverage`;
- synthesis root: `points → missing_aspect_ids → conclusion`;
- point: `aspect_ids → evidence_id → anchor → text`;
- conclusion: `text → point_refs`.

Порядок внешних request keys не является новым требованием. Dynamic evidence IDs
сохраняют существующий порядок построения; их состав/лимиты/coverage не меняются.
В private trace сохранить `schema_property_order` с массивами `selection_root`,
`synthesis_root`, `point`, `conclusion`, извлечёнными из фактически отправляемых schemas.
Arrays сохраняют порядок при canonical save; порядок ключей сохранённого map сам
по себе не доказывает wire order. При ранней ошибке не выдумывать synthesis evidence:
поля для ещё не отправленной стадии null/отсутствуют. Секреты в metadata не входят.

Regression перехватывает реальный HTTPConnection body из Ollama.request, проверяет
четыре уровня на реальных schemas и semantic equality payload; canonical packed/state
не меняется. ByteBound учитывает ту же полную schema: её длина инвариантна перестановке;
num_ctx8192/output1024/template512 и actual prompt_eval_count gate сохраняются.
AICODE-NOTE у provider serializer объясняет отличие от canonical state packing.

Gate repair05: новая baseline, максимум3 **тех же** private content queries (known pair
и выбранный transfer), без retries. После любого runtime/semantic FAIL зависимые public
dry/record/публикация ждут пересмотра гипотезы. После3 runtime+independent semantic PASS
можно продолжить public. Raw response order проверяется отдельно от качества смысла.

## Завершение

Luna — независимое первое ревью; после исправлений обязательное fresh Astra по SPEC,
коду и результатам. Человеческую приёмку не подменять. Выполнить разрешённые private
deploy, commit/push GitHub с сохранением порядка day01–30, публикацию MP4 в прежнюю
Drive-папку и две отдельные ссылки в таблицу: сначала сверить заголовок Day30/строка132
(ожидается AE132), затем записать и перечитать после reload. Любой непроверенный
пункт остаётся явно pending/NOT PROVEN. Покупки и публичный сетевой listener не разрешены.
