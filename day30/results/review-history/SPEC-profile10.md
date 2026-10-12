# Day30 — частный локальный LLM-сервис

Рабочий контракт от 11.10.2026. Основание: условие Day30 и одобренный формат в
корневом HANDOFF; новый запрос «начинай день 30 там все написано» снимает прежний
стоп до CLEAR. Отдельное человеческое утверждение этого документа не заявляется.
Текущий профиль —10 ниже; его output/deadline и исправление pruning уточняют ранние редакции.

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

## Protocol06: provenance по unit ID и вычисляемое missing, 12.10.2026

Текущий контракт заменяет synthesis/bookkeeping предыдущих repair03/05;
[предыдущая SPEC repair05](results/review-history/SPEC-repair05.md) сохранена.
Последнее решение root перед freeze: **anchor/anchor_ids и partition отсутствуют**.
Существующий evidence_id уже задаёт immutable unit. Точное копирование originals и
обязательное missing полностью вычисляет код. Старые rejected outputs остаются rejected;
человеческое утверждение редакции не заявляется. Сохраняются9B/digest, две стадии,
think=false,8192/1024/512,temperature0,ByteBound,индекс/retrieval,вопросы и UI/API.

**Model source projection.** Selection получает на unit только
`evidence_id,source,author,date,attribution,context_ids,text`; synthesis — те же поля
плюс evidence_role. Text передаётся целиком ровно один раз, byte-exact, без обрезки,
strip/normalization или дополнительного представления в anchors. Backend хранит полные
неизменённые units. chunk/document IDs, hashes, offsets, part_index/source_ref модели
не передаются; остаются в backend/trace/source cards. В projection context_ids ссылаются
только на units, переданные в этой стадии; исходные metadata не переписываются.
Неизвестная атрибуция сохраняется, не восстанавливается моделью.

**Synthesis output:** ровно `points`, `doubtful_aspect_ids`, `conclusion` в этом order.
Points —0–4 объектов ровно `aspect_ids,evidence_id,text` в этом order. Aspect IDs —1–6
уникальных текущих Q; evidence_id — реально переданный proof unit, выбранный selection
для каждого указанного Q; text — непустое предложение пересказа1–300 символов.
Background/cross-aspect/unknown ID отвергаются прежним invalid_point_reference.
Ни копируемого quote, ни anchor/anchor_ids, ни генерируемых offsets в model output нет.
Для каждого point backend получает **полный exact unit.text и его start/end** из
immutable unit; source refs/cards и атрибуция строятся по прежним правилам. Эти spans
сохраняются с point в private trace; в summary попадает только point.text. Ограничения
conclusion/P1…Pn сохраняются. Валидный unit ID доказывает provenance, не поддержку
пересказа или вывода: semantic gate по originals остаётся строгим.

**Missing вычисляет код.** Модель не возвращает missing_aspect_ids. Пусть A все аспекты,
C аспект IDs валидных points, R={Q: effective coverage partial/none}. Поле
`doubtful_aspect_ids` присутствует всегда, но допускает []:0–6 уникальных **только full**
Q текущего effective coverage, которые модель консервативно считает недостаточно
раскрытыми. Enum из full Q; если их нет, array maxItems0 без пустого enum. Unknown Q,
duplicate или partial/none в этом поле — invalid_doubtful_aspects, без ignore.
Код M=R∪(A−C)∪doubtful_aspect_ids. Обязательные partial/none не теряются; doubtful
может только понижать полноту. Эта формула не проверяет смысловую полноту points.

При points=[] M=A автоматически; прежний local unknown с пустыми refs/sources и
фиксированным conclusion сохраняется. Иначе прежний renderer строит summary, оговорку
по M, conclusion и source cards; supported лишь при M=∅ и всех full, иначе partial.
Ложные субъект/объект, причинность, атрибуция или недостаточная конкретика — semantic FAIL
даже при валидном формате. Старые ответы новым контрактом не нормализовать в PASS.

**Order/budget/trace.** Selection `evidence→coverage`; synthesis
`points→doubtful_aspect_ids→conclusion`; point `aspect_ids→evidence_id→text`;
conclusion `text→point_refs`. Ordered provider serialization и schema_property_order
arrays отражают actual wire. ByteBound считает actual projected prompt + полную schema
и прежние reserves. При каждой budget итерации пересобирается projection; pruning
остаётся whole-unit с пересчётом allowed IDs/coverage, без потери части original text.
Private trace protocol_version=protocol06 хранит full units, sent projection/schema,
point→immutable unit quote/spans и derived M отдельно от raw/model doubtful.

**Gate protocol06:** offline projection/provenance/bookkeeping/wire tests → review →
новая baseline → максимум3 свежих неизменённых private вопросов (known pair+выбранный
transfer), без retries. Любой runtime/semantic FAIL останавливает зависимые public
шаги. PASS требует3 runtime и3 independent semantic PASS по полным originals.

## Profile07: sampling только synthesis, 12.10.2026

После двух semantic FAIL protocol06 root выбрал отдельную гипотезу sampling.
[SPEC protocol06](results/review-history/SPEC-protocol06.md) и прежние FAIL сохраняются;
человеческое утверждение этой редакции не заявляется. Никакого изменения формулировок
prompt, протокола, критериев качества или вопросов под известный ответ.

Изменения только второго вызова: `temperature=0.7`, `top_p=0.8`. Это non-thinking
профиль из [официальных рекомендаций Qwen3.5](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/README.md#best-practices),
а не доказательство причины ошибок или превосходства по архиву. Selection сохраняет
`temperature=0` и прежние остальные параметры. Обе стадии — та же9B/digest,
think=false, num_ctx8192, num_predict1024, template reserve512, deadline300с; никаких
seed tweaks, новых весов, reasoning/critic/третьего вызова. Model defaults top_k20,
presence_penalty1.5, repeat_penalty1.0 сохраняются; selection наследует прежний top_p0.95.

Конкретные передаваемые options: selection — прежний dict
`{num_ctx:8192,num_predict:1024,temperature:0}`; synthesis — независимая копия
`{num_ctx:8192,num_predict:1024,temperature:0.7,top_p:0.8}`. Не мутировать общий dict.
Provider получает именно options своей стадии. Private trace каждой отправленной
стадии содержит model, think и **полный фактически переданный options dict**; её budget
также содержит этот dict. Унаследованные model defaults фиксируются отдельно и не
выдаются за явно переданные параметры. Для неотправленной стадии не создавать ложное
evidence. Budget builder и observed-count validator используют actualstage num_ctx/
num_predict, а не независимо захардкоженные1024/8192; численные ограничения сохраняются.

Две non-thinking API-стадии и прежний непосредственный constrained-output путь остаются.
ByteBound, ordered schema wire, strict JSON, provenance, code-derived M, renderer/API,
immutable index и semantic gate protocol06 не меняются. Новая baseline указывает stage
options; один удачный результат не доказывает причинность или общую надёжность профиля.

Gate07: максимум3 свежих **неизменённых** private content queries: known pair и выбранный
transfer. Root ожидает независимый semantic verdict перед приёмом следующего запроса;
на первом runtime/semantic FAIL останавливает ещё не принятые случаи, без autoretry.
Уже принятый запрос не скрывается и учитывается отдельно. Только3 runtime+semantic PASS
разрешают продолжить public dry/record; старые FAIL и человеческая приёмка не меняются.

## Profile08: thinking синтеза без native format, 12.10.2026

После первого semantic FAIL07 root выбрал эту ограниченную гипотезу; следующий вопрос07
не отправлялся. [SPEC07](results/review-history/SPEC-profile07.md) и прежние FAIL сохраняются.
Этот раздел уточняет прежние think/format требования; человеческое утверждение не заявляется.
Модель9B/digest, retrieval/index, вопросы, protocol06/schema/validators, code-derived M,
provenance, UI/API и строгий semantic gate прежние. Не добавлять critic/retry или новые веса.

**Два вызова и фактический wire.** Selection остаётся think=false с native format и
options07 selection. Synthesis — think=true, options07 synthesis
`{num_ctx:8192,num_predict:1024,temperature:0.7,top_p:0.8}`; ключ `format` полностью
**отсутствует** (не null/пустая строка). Сохраняются ровно два сообщения system/user:
к прежнему user content с context JSON добавляется newline и полный динамический schema
JSON, сериализованный с сохранением порядка properties. Не пропускать schema через
canonical sort_keys и не менять её содержание. Порядок schema остаётся
points→doubtful_aspect_ids→conclusion, point aspect_ids→evidence_id→text,
conclusion text→point_refs; это инструкция модели, не enforced grammar/output order.

В [pinned Ollama0.33.3 route](https://github.com/ollama/ollama/blob/v0.33.3/server/routes.go#L2849)
дополнительный проход после thinking требует `req.Format != nil`;
отсутствие поля сохраняет один backend completion на synthesis. Итого два внешних и
два внутренних generation-вызова на успешный полный ответ, без скрытого format restart.
[Qwen3.5 parser](https://github.com/ollama/ollama/blob/v0.33.3/model/parsers/qwen35.go#L97)
разделяет reasoning и final content; reasoning не является ответом или evidence.

**Budget/trace.** ByteBound считает фактически отправляемые messages: добавленная schema
уже входит в user content **один раз**, отдельного native-format/schema слагаемого для
synthesis нет. После каждого whole-unit pruning пересобрать projection и dynamic schema.
Прежние8192 context /1024 output /512 template reserve /300с absolute deadline сохраняются.
1024 ограничивает суммарную генерацию reasoning+final в одном проходе, не1024 на каждую.
Observed-count gate и actualstage options прежние. Trace отправленной стадии хранит
think/options/budget и format_mode=`native` либо `prompt_schema`; schema_property_order
для synthesis отражает реально добавленную schema, не доказательство порядка ответа.

**Reasoning не сохраняется нигде.** До любого private/state/log/API persistence удалить
message.thinking из безопасно разобранного provider response; допускается лишь счётчик/
признак присутствия без текста. Сохранить final message, metrics и provenance. Это правило
покрывает success, error response_data/response_text, timeout и частичный transport body:
неразобранные/повреждённые/частичные raw bytes сохранять только как stage, bytecount и SHA256,
без префикса, excerpt или попытки вырезать reasoning регулярным выражением. Безопасно
разобранный final content можно сохранить отдельно. Provider debug/trace не должен писать
reasoning. Пустой final, length, неверный/дублированный JSON и schema error остаются FAIL;
reasoning не подставляется как final, repair/retry и ослабления semantic gate нет.

**Ограниченная проверка гипотезы.** Измеренные07 ~3.3 output tokens/s и ~24с prompt eval
не являются прогнозом08. При такой скорости850 суммарных output tokens требуют ~258с
плюс prompt/overhead,1024 — уже ~310с без prompt. Завершение примерно в800–850 tokens
может уложиться в300с; фактические скорость/объём reasoning неизвестны. Лимит не повышать.
Offline wire/budget/sanitization/validator → независимый review → новая baseline → максимум3
свежих неизменённых private вопросов. После каждого сначала independent semantic verdict,
потом следующий submit; первый runtime/semantic FAIL останавливает ещё не accepted cases.
Никакого autoretry. Только3 runtime+semantic PASS открывают public dry/record; даже PASS
не доказывает причинность улучшения или общее качество модели.

## Profile09: согласованные output/deadline синтеза, 12.10.2026

[Фактический gate08](results/live-private-08.json): первый запрос завершился provider
deadline на synthesis через300.003с, total380.269с; selection завершён за78.3с/161tokens.
Transport остановился при ожидании headers,0bytes: объём reasoning/final и причина
длительности **не измерены**. Остальные два вопроса не отправлялись. [SPEC08](results/review-history/SPEC-profile08.md)
и FAIL сохраняются. Это ограниченная корректировка выбранных агентами лимитов, не
человеческое утверждение и не доказательство будущего semantic PASS.

**Единственные изменения генерации:** synthesis options теперь
`{num_ctx:8192,num_predict:1408,temperature:0.7,top_p:0.8}`, absolute transport deadline600с.
Selection options прежние1024/temperature0 и deadline300с; embedding/прочие provider
routes сохраняют300с. Deadline — параметр локального transport, не Ollama options.
Та же9B/digest, think=true/format omitted только synthesis, два system/user messages,
schema в prompt ровно один раз, два внешних generation calls и прежний pinned путь без
дополнительного backend format pass. Никаких seed/prompt/schema/validator изменений.

Input8192/template512/ByteBound/whole-unit pruning и observed-count gate прежние;
output1408 включает reasoning+final вместе. На сохранённом08 input upper6738 даёт
6738+1408=8146≤8192: этот prompt помещается без дополнительной потери evidence;
1536 дало бы8274 и новое pruning. Это проверка конкретного бюджета, не гарантия
будущего одинакового selection. Для новых inputs применять прежнюю честную пересборку
schema/projection после pruning, не уменьшать output reserve и не расширять context.
При прежней измеренной скорости ~3.3tokens/s1408 требуют ~427с плюс prompt/load;
600с дают запас. Скорость thinking и достаточность1408 пока неизвестны; timeout08
сам по себе не доказывает исчерпания1024. Это гипотеза доступного времени/выхода.

**Сквозные границы.** Передавать actual stage deadline до transport; убрать скрытый
общий min(...,300), сохранив один monotonic absolute deadline через connect/headers/body.
Частичный прогресс не продлевает срок; при ошибке socket закрывается до освобождения
lock. Trace attempt/known-sent parameters и budget отражают actual deadline_seconds
рядом с actual options; неотправленная стадия не получает фиктивный sent evidence.
Сумма provider caps одной цепочки300 embedding+300 selection+600 synthesis=1200с.
Worker join1210с, launchd ExitTimeOut1220с, client/private poll и video wait1230с
согласованы с этой суммой и небольшим служебным запасом. Это не новый общий SLA:
local retrieval/storage overhead учитывается отдельно. Старые plist не меняются сами;
root регенерирует только Day30 main/demo перед разрешённым restart.

Privacy08, strict JSON/length/empty-final/source/semantic gates сохраняются полностью.
Нет восстановления final из reasoning, третьего вызова или retry. Scope «один пример»
не добавляется отдельным prompt patch в этот эксперимент: смысл исходного вопроса
и достаточность ответа по-прежнему проверяет независимый semantic reviewer.
Offline stage deadlines/budget/shutdown/poll/privacy → review → baseline → максимум3
свежих прежних вопросов, каждый следующий лишь после independent semantic PASS;
первый runtime/semantic FAIL останавливает not-yet-accepted cases. Public после3 PASS.
Старые FAIL не переоцениваются в PASS, human acceptance остаётся pending.

## Profile10: последний bounded capacity probe и исправление pruning, 12.10.2026

Фактический09 завершил synthesis за455.070с: eval1408, done_reason=length, final0;
всего532.472с, два completed generation calls. Текст reasoning не читался/не сохраняется.
Это подтверждённый незавершённый ответ при cap1408, а не оценка его смысла.
[SPEC09](results/review-history/SPEC-profile09.md) и прежние FAIL сохраняются. Root выбрал
ниже последний capacity probe; человеческое утверждение не заявляется.

**Параметры10:** synthesis
`{num_ctx:8192,num_predict:1920,temperature:0.7,top_p:0.8}`, absolute deadline900с.
Selection1024/300с и embedding/прочие routes300с прежние. Provider sum1500с;
worker join1510, launchd ExitTimeOut1520, client/private poll/video1530с. Actual options/
deadline_seconds в wire/trace/budget/observed gate согласованы, deadline не Ollama option.
Та же9B, synthesis think=true без format, одна schema в user prompt, один backend pass
на стадию по pinned normal path; два внешних generation calls, без critic/retry.
Прежние8192/512, privacy08, schema/validators/provenance/M/API/semantic gates сохраняются.
1920 **не объявляется достаточным**: это ещё непроверенная ограниченная гипотеза.

**Обязательное исправление inherited P2.** Требование пересобирать зависимые данные
после whole-unit pruning существовало до10. fit_prompt не должен повторять budget test
после удаления unit со старой schema/extra: это завышало размер и удаляло лишние units.
В обеих стадиях перед КАЖДОЙ проверкой бюджета из одного актуального списка units
строятся projection, schema и все зависимые IDs/maps/coverage/focus. Selection allowed
IDs пересекаются с retained units, dialogue_focus пересчитывается; synthesis effective
coverage каждый раз выводится из исходной validated selection coverage и retained units,
не из прошлого уже downgraded состояния. Нет удалённых ID в enum/admissibility/maps/
context_ids. Изменение истории также отражается в фактическом messages перед budget.
Первое помещающееся актуальное представление отправляется без лишнего удаления units;
trace и validator получают ровно его schema/coverage/units. Empty-proof/unknown прежние.

Reviewer offline reconstruction08/09 для5/4/3/2 units: stale input upper
8056/7548/6869/6427 против rebuilt8056/7473/6738/6240; selection wire08/09 совпал.
При1920 rebuilt3 даёт8658>8192, rebuilt2 —8160≤8192. Поэтому ожидаются те же final
evidence, что в09, но это обязательно подтвердить offline actual-wire сравнением;
не заявлять заранее как живое измерение. Global CODE до исправления P2 — NEEDS CHANGES;
прошлое одобрение узкой09 delta остаётся историческим, не подтверждает весь код.

Native-format512 не используется: [pinned route](https://github.com/ollama/ollama/blob/v0.33.3/server/routes.go#L2849)
переключается на grammar pass лишь после появления непустого final content;
length при all-thinking сам по себе restart не запускает. Это не механизм forced
«512 reasoning затем512 final» и не основание обещать завершённый ответ.

Offline P2/actual-wire/budget/deadline/privacy → независимый review → baseline → максимум3
свежих неизменённых private cases. Каждый следующий submit только после independent
semantic PASS; первый runtime/semantic FAIL останавливает not-yet-accepted cases.
Public только после3 PASS. Дальнейшее повышение caps не планируется без нового
существенного основания и выбора другого подхода: при FAIL нужен выбор scope/формата,
а не бесконечная настройка лимитов. Старые FAIL и human acceptance pending сохраняются.

## Завершение

Luna — независимое первое ревью; после исправлений обязательное fresh Astra по SPEC,
коду и результатам. Человеческую приёмку не подменять. Выполнить разрешённые private
deploy, commit/push GitHub с сохранением порядка day01–30, публикацию MP4 в прежнюю
Drive-папку и две отдельные ссылки в таблицу: сначала сверить заголовок Day30/строка132
(ожидается AE132), затем записать и перечитать после reload. Любой непроверенный
пункт остаётся явно pending/NOT PROVEN. Покупки и публичный сетевой listener не разрешены.
