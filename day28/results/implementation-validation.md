# Day28 — финальная независимая проверка реализации по SPEC

**Вердикт: SPEC SATISFIED для локального baseline record-02.**
Полный inventory сохранён: **50 применимых требований — 50 PASS, 0 FAIL, 0 NOT PROVEN**.
Это не утверждение об идеальном качестве модели: E02 остаётся PARTIAL по полноте,
два локальных legacy replay ответа отклонены строгим валидатором. SPEC требует
честную оценку этих недостатков, а не выдуманный стопроцентный порог качества.
**Human acceptance и публикация не выполнены и не приписаны этому аудиту.**

Reviewer: фактическая модель **gpt-6-astra, xhigh**, 09.10.2026. Применены
`implementation-validation/SKILL.md` и `references/evidence-and-verdict.md`.
Предыдущий полный FAIL-аудит сохранён без изменений в
[implementation-validation-record-01.md](implementation-validation-record-01.md),
SHA `ed3001c022d7220dc2c7d0bba8766f2a04988b5f380b9ba12d75b007aa939732`.
Три прежних FAIL сняты по новому настоящему видео, не по cached preview или обещанию.

## Точный baseline и происхождение требований

- Worktree `/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28`, branch
  `day28-local-rag`; HEAD `4659e24875902d3668e48ddea9f8d96a3dd36a5c`.
  Day28 untracked, поэтому версия связана с content hashes, а не только с HEAD.
- Полный текущий SPEC SHA `bb7a54c40339f69f73a733d41b2f94c7ea56a0b6a292bdc5e7d99616e9f69fd5`;
  SCENARIO SHA `357afbc232bbb56f912ef2591505deef69296ce46a48c6ac4d876a8f068f2630`.
  Требования и сценарий подтверждены пользователем09.10 до реализации; поздние
  уточнения окна/source_refs объясняют реализацию и не снимают исходные обязательства.
  Сценарий не менялся для обхода найденных FAIL. Baseline и полный нормативный
  inventory проверены ранее; в этом проходе неизменность обоих hashes подтверждена.
- [source-manifest-recording.json](source-manifest-recording.json), SHA
  `1e3c1c99d93b1a2bf75471ac32c1d91af35e8753f80916038c99a2df972b8045`,
  содержит восемь файлов, **все самостоятельно сверены с текущими bytes**.
  Backend/evaluate/recorder не изменялись после проверенных E2E/replay; изменились
  только HTML/JS/CSS/public summary. Последние код/рендер-дельты независимо
  просмотрены Luna и Astra, см. [review-astra](review-astra.md).
- Record02 run `727aaa505f2f42c3b6a87b7f2d4e9371`; app run
  `688d3db5e77547678b99635a13c092a8`. Видео [Day28-live.mp4](../video/Day28-live.mp4)
  побайтно равно `video/runs/record-02/live.mp4`, SHA
  `c627d0909670e3a4a58d0f3db58c773e2a920e669e68f5a83825e1b187f181b8`.
  **178.64 с, 4 250 922 bytes, H.264/yuv420p,1280×1000,25 fps, без аудио.**
- Manifest описывает фазу записи с `video_status=checking`. Последующее отражение
  уже выполненной проверки в рабочей summary не является правкой записанного MP4;
  исторический manifest/record02 journal должны сохранять состояние съёмки.

Проверенные runtime/content hashes:

| Файл | SHA-256 |
| --- | --- |
| core.py | `61a79221fcde8178201d1f3dbadb4e06ce3736c7db34049a3b1934827c702100` |
| app.py | `0eb275fb8bd6d6facd9a755e04e6fe5efbd783dda3ba46be16c7a74bb3fb364e` |
| evaluate.py | `05ddeb6d8a86600536d1880e2bb543e4581ae3d2fa0c71cd029dfc6d136d5ef4` |
| static/app.js | `2155cc21d397b0ed66799ab2fdcd9484a95df6639f4bfe8f6e7cf6b39af77346` |
| static/index.html | `d5d1af0d9f6b5d5ffe9d2f4ffea6e285db019ce4400fa08c1930ef16626bd1b0` |
| static/style.css | `0253fd2d49343b4fcfe2bb246d3b77c6e0e3f2acd5512990af9db1d2d0e9d435` |
| video/run_demo.py | `2cdd9d5e674559db98770c2fe8abebd02b2a98b8d57a25de4ae8f5337ee880ce` |
| results/public-summary.json | `413b548723db11239ca2dd7daad698f7e2c8465ccbaad1fa8ace69a638c17e25` |

## Evidence failure model

| Группа | Как мог бы появиться ложный PASS | Контроль |
| --- | --- | --- |
| Индекс/локальность | Другое содержимое под знакомым именем, пересчитанные vectors, proxy/cloud fallback | Frozen SHA/identity/counts, digests/options, bounded transport code, actual URL receipts; без заявления physical disconnect |
| Источники | ID указывает не на переданный текст; модельную quote незаметно исправили | Actual messages/selected/ref map/raw/projection сверены; E2E app-copy явно обозначена, strict historical replay отделён |
| Семантика | completed/citations_valid или одинаковая пара выдаются за полноту | Собственное чтение ответов по источникам; E02 PARTIAL и replay2 errors сохранены; human acceptance=false |
| Replay | Чужой historical response, подмена messages/времени/decoder conditions | Day24 prepared/raw/ledger + SHA и actual local messages; даты/аппаратные/decoder различия раскрыты |
| Видео | Старый response/скриншот ожидания выдаётся за новую генерацию; metadata есть только в коде | Три новых unique IDs, raw receipt → public result → visible answer; actual MP4 hashes/RGB frames; лично прочитаны start/end и остальные7 кадров |
| Версия/очередь | Старые tests относятся к другой реализации; параллельные calls искажают latency | Hash-bound backend неизменен; отдельное UI review;19 project requests не пересекаются, coordinator observation/queue snapshot имеют явно указанную границу |

## Проверенная evidence цепочка

- **C** — собственное чтение core/app/evaluate/UI/recorder и [Astra review](review-astra.md),
  source_refs и последующие UI delta. Транспорт, guards, source validator, schema/budget
  рассмотрены независимо, не скопирован вердикт первой модели.
- **T** — [31 offline GREEN](../tests/offline-green.txt) и значимые RED/GREEN.
  Собственные команды `python3 -m unittest discover -s day28/tests -p 'test_references.py' -v`
  и `python3 -m unittest discover -s day28/tests -p 'test_evaluate.py' -v` дали5/5+2/2,
  exit0. Дополнительный intercepted Ollama.request сценарий проверил фактические payload,
  недопустимый public ref и неизменный strict replay. Тесты не вызывали модель.
- **I** — самостоятельная read-only загрузка реального Structure, SHA/identity/counts,
  24 public assignments под budget; [preflight](preflight.json) фактического embedder/generator.
- **E** — `private/runs/e2e-03/`, run `344b65a15e89407582d013f5fe11d89c`,
  шесть новых запросов по frozen suite; [assessment](e2e-03-assessment.json).
- **R** — `private/runs/replay-01/`, run `dbf3969ef7ed49a282602fa06c92c184`,
  Q03/Q08/Q07 и исходные historical prepared/raw/ledger; [assessment](replay-assessment.json).
  Уточнение причины Q08 соответствует raw: первый отказ — повторный/невалидный source,
  дополнительно есть недословная quote. Метрики/raw/messages не переписывались.
- **A** — all CLI request `abdf7b31f0184509a7c58f3a59205951`,
  `private/all-cli-check/2d1dbd822fc444f88345fcfa481323f2/`, done45.40с;
  stdout статус/путь, raw private.
- **D** — `video/runs/dry-01/results.json`, run `774130f8e2d343398316926da8c45a2a`,
  три real requests; browser fixture и явно GET-only cached previews отдельно.
- **V** — `video/runs/record-02/results.json`, текущий MP4, фактические frames,
  три raw receipts приложения и [video-verification](video-verification.json).
- **F** — [final-verification](final-verification.json), manifests, Git diff,
  [RESULT](../RESULT.md), [README](../README.md), [RELEASE_NOTES](../RELEASE_NOTES.md),
  [video README](../video/README.md), [actions](../actions.jsonl).

Свежий узкий проход выполнен на macOS15.6.1 arm64/Python3.14.0; inference/запись
получены на Apple M2/16GB. Reviewer не запускал новых model calls, браузерную запись
или полный неизменённый test suite. Контроль версии, negative paths, index, E/R/A/D
сохранены из предыдущего полного аудита, поскольку backend и входы не изменились.

Заново исполнены hash/receipt/frame проверки (inline Python, exit0):

1. Все8 файлов recording manifest совпали; SPEC,SCENARIO и прежний FAIL snapshot
   сохранили SHA. Runtime tests/результаты связаны с неизменным backend, UI — с новой записью.
2. `ffprobe -v error -show_format -show_streams -of json day28/video/Day28-live.mp4`
   дал exit0 и параметры baseline. Полное `ffmpeg -v error -i <mp4> -f null -`
   выполнено координатором на этом SHA с exit0 и отражено в V; reviewer не повторял
   весь decode нового дубля, самостоятельно извлёк и проверил его9 ключевых кадров.
3. Для каждой пары frame/time выполнены `ffmpeg -v error -ss <time> -i <mp4>
   -frames:v 1 -f rawvideo -pix_fmt rgb24 -` и соответствующий decode PNG в RGB.
   **Все9 массивов pixels совпали.** Reviewer лично прочитал start1s; answer1/source1
   47.61/55.61s; answer2/source2a/source2b118.18/125.18/130.18s;
   answer3/context3 157.64/162.64s; end176.64s. Waiting-кадры не использованы.
4. Новые V actual == public_result(persisted receipt); visible_answer == answer.answer;
   messages/prompt hash/map/materialize совпали, original text exact, scope public,
   GENERATION_OPTIONS/SOURCE_SCHEMA/done/stop корректны. Каждый request ID новый
   относительно E6+R3+A1+D3+record01(3); все19 наблюдаемых project requests имеют
   непересекающиеся интервалы. Новые15 HTTP calls только loopback Ollama.
5. В совокупности оба прохода рассмотрели19 receipts/92 local URL, включая dry/старое
   видео. F перечисляет16 receipts/77 URL (без dry); это пересекающиеся наборы,
   не дополнительные независимые измерения. Физическое отключение сети не проверялось.

Три новых ответа текущего видео:

| Кейс | Request ID | Статус / API total | Факты / полнота |
| --- | --- | --- | --- |
| E01 | `60fbc9ae48cc4602a8a9011a3e3eb99a` | done /40.804с | PASS/PASS |
| E02 | `55fbd6f373324e2796f7d1a7c3020514` | done /51.801с | PASS/PARTIAL |
| E03 | `c4e0390a480e423dbe76de7aa6c440d6` | unknown /17.974с | PASS/PASS |

## Полный нормативный inventory

Сохранены все50 применимых item исходного полного аудита. Stable labels выведены
из полного SPEC и связанного обязательного сценария; повторяющиеся требования
сопоставлены одному item. Никакие требования не удалялись ради нового PASS.

| SPEC item | Наблюдаемое требование | Evidence | Статус | Примечание |
| --- | --- | --- | --- | --- |
| O01 — ввод/объём, строки 7–16 | Standalone локальный embedding → прежний индекс → локальная генерация, код Day28 | C, I, E, A | PASS | Прежний индекс недели 5, без runtime импортов соседних дней |
| O02 — строки 15–16; §3 | Короткие ссылки выбирает модель, оригинал подставляет приложение, raw отделён | C, T, E, V | PASS | Совпали actual messages/text, map, refs и projection |
| O03 — строки 17–18 | CLI/UI показывают вопрос, ответ, фрагменты, ошибки и реальные времена | C, T, E, A, D, V | PASS | All CLI публикует статус/путь, полный ответ остаётся private |
| O04 — строки 18–19 | Один независимый вопрос за раз, без истории/goal-harness | C, T, E, D, V | PASS | Job guard/isolated lock; каждый prompt независим |
| O05 — строка 19 | Day01–27 не менять и не импортировать | C, F, Git diff | PASS | Соседние файлы и pyproject/uv.lock неизменны |
| O06 — строки 21–22 | Qwen3:8b Q4_K_M, think=false, temperature=0, ctx8192/predict1024 | C, I, E, R, V | PASS | Payload и фактическая model identity; quantization в preflight |
| O07 — строки 23–26 | Окно обосновано до оценок, input/output ограничены, нет тихого усечения | C, T, I, E, R | PASS | Byte bound + schema/template/output, whole-chunk exclusion; observed prompt/stop |
| O08 — строки 27–30 | Public только 24 assignments; all явно CLI/private; видео дни18–20 | C, T, I, A, V | PASS | Private discussion не выбран/не показан public |
| I01 — §1 | Exact Structure generation/SHA/size, 724 chunks/663 docs и corpus identity | I, F | PASS | SHA9894…11b, 12 435 456 bytes; loader выполнен самостоятельно |
| I02 — §1 | Индекс read-only, исходные vectors не пересчитываются | C, T, I, F | PASS | Immutable ro SQLite, bytes/SHA неизменны; embed вызывается только для query |
| I03 — §1 | Точный embedding model/digest, 1024 unit values, options и truncate=false | C, T, I, E | PASS | Preflight реальной модели плюс runtime checks |
| I04 — §1 | Несовместимый индекс/эмбеддер блокирует запрос | C, T | PASS | Negative identity/SHA/vector/returned-model/cloud checks |
| L01 — §2 | Runtime только local index/loopback Ollama, без SSH/cloud/keys/fallback | C, E, R, A, D, V, F | PASS | 92 наблюдаемых URL local в совокупном наборе; physical disconnect не заявлен |
| L02 — §2 | Слушать 127.0.0.1:8068, адреса ограничены кодом | C, T, D, V | PASS | Fixed bind/URL, no proxy/redirect, Host/Origin guard |
| L03 — §2 | Scope применяется до поиска/контекста; public не раскрывает discussion | C, T, E, D, V | PASS | Public API и frames подтверждают только assignment |
| C01 — §3 | Каждый источник выбран, исходный текст дословен и проверен кодом | C, T, E, V | PASS | Program-copied full original, не model-authored quote |
| C02 — §3 | Неизвестная/повторная ref, неверная схема/цитата дают error | C, T, R | PASS | Отрицательные pure/Engine checks; реальные legacy ошибки сохранены |
| C03 — §3 | Исторический replay не меняет messages/протокол/слова модели | C, T, R | PASS | Legacy SCHEMA/raw сохранены, нет materialization в replay |
| C04 — §3 | Timeout, недоступная модель и незавершённый вывод дают error | C, T | PASS | Mock negative paths; это не утверждение о живом timeout-инциденте |
| C05 — §3 | Нехватка сведений явно unknown; пустой retrieval без общих знаний | C, T, E, D, V, R | PASS | E03 без суммы/refs; empty retrieval пропускает generation |
| C06 — §3 | Корпус трактуется как недоверенные данные | C, actual messages E/R | PASS | System/data separation, только ответные schemas; нет исполнения document commands |
| N01 — §4 | IDs, full/raw answer, scope, model/digest/options/index/chunks/prompt hash/status | C, E, R, A, D, V | PASS | Проверены реальные persisted receipts, ошибки сохраняют raw |
| N02 — §4 | Фактические времена фаз и Ollama metrics, отсутствующее null | C, T, E, R, V | PASS | Replay embedding/retrieval null; missing fake metrics null |
| N03 — §4 | Private тексты/raw receipts только private | C, T, R, A, Git ignore | PASS | 0600 receipts; public projection/агрегаты и public video journal не содержат private raw |
| E01 — §5 | До запусков frozen прямой/составной/неизвестный cases, каждый дважды | suite SHA, actions, E | PASS | Шесть разных новых requests; frozen suite0557…76f8 |
| E02 — §5 | Оценка фактов/полноты/цитат/unknown; транспорт и ошибки отдельно | E, R, RESULT | PASS | E02 PARTIAL явно сохранён; SPEC требует оценку, не 100% полноты модели |
| E03 — §5 | Времена/различия повторов и все недостатки сохранены, без статистических обобщений | E, старые E01/E02, RESULT | PASS | Три одинаковые пары не объявлены общей гарантией |
| R01 — §6 | Найти три пригодных historical cases с question/context/messages/response | R, исходные Day24 prepared/raw/ledger | PASS | Q03/Q08/Q07; пригодность входа не равна успеху локальной генерации |
| R02 — §6 | Три отдельные local генерации на тех же messages, hashes/рубрика | R | PASS | 3 actual calls, 2 error сохранены; новая E2E оценивается отдельно |
| R03 — §6 | Replay input помещается или отклоняется без скрытого среза | C, T, R | PASS | Bounds6801/6895/5312 +1024 <8192; exact message equality |
| R04 — §6 | Historical times только из метрики с датой/ограничениями; нет нового cloud benchmark/оплаты | C, R, RESULT, V | PASS | Day24 ledger times, 03.10 vs09.10, hardware/decoder differences, 0 новых cloud calls |
| M01 — §7 | Рабочие код/README/RESULT/RELEASE_NOTES | C, T, E, A, F | PASS | Ограничения качества и provenance описаны; локальный ZIP не требуется SPEC |
| M02 — §7 | Новые видео-ответы, historical receipts обозначены, публикация/сдача отдельно | R, V, docs/footer | PASS | Published/user acceptance false; видео по сценарию раскрыто строками V ниже |
| Q01 — строки80–81 | TDD существенных identity/scope/payload/quote/empty/error/timeout/final/loopback/size | T | PASS | Сохранены смысловые RED→GREEN, не только тесты существования файлов |
| Q02 — строка82 | Mocks и реальные E2E/replay разделены | T, E, R, docs | PASS | Mock успех не объявлен качеством Qwen |
| Q03 — строка83 | Dry run/record отдельные прогоны со своими журналами | D, V | PASS | 3 + 3 новых уникальных IDs; cached preview отдельно, 0 calls |
| Q04 — строка84 | LLM/видео последовательно с другими днями на Mac16GB | I, интервалы19 requests, coordinator observation/record02 queue | PASS | Управляемые проектные задачи последовательны; machine-wide telemetry не заявлена |
| Q05 — строка85 | Локальные index и точный embedder подготовлены | I, E, R | PASS | Реальные query embed, 639150858 bytes модели в preflight |
| Q06 — строки87–88 | Согласование пакета до кода; нет commit/push/merge/upload/paid вне scope | actions, Git HEAD, F | PASS | Approval10:22 раньше implementation10:25; не требуется выполнять исключённые публикации |
| V01 — scenario initial | Чистый public экран, модели/index готовы, private receipts не открыты | V start, raw receipts, C | PASS | На старте нет старых ответов; queue вынесена в Q04 |
| V02 — scenario п.1 | Показать URL и пояснить перенос без пересчёта/предварительное получение моделей; names/index/public | V start1s, UI metadata | PASS | URL8068, подготовка, имена моделей/index/public прочитаны на actual MP4; прежний FAIL закрыт новой записью |
| V03 — scenario п.2 | Новый E01, terminal ID, assignment18/original, retrieval/generation/total | V answer1/source1 + persisted receipt | PASS | 40.80 с, exact original и ответ читаемы |
| V04 — scenario п.3 | Новый E02, оба original, проверка полноты/ограничение | V answer2/source2a/source2b/end, E | PASS | 51.80 с; оба текста читаемы, summary сообщает неполную детализацию |
| V05 — scenario п.4 | Отсутствующий бюджет проверен до freeze; новый честный unknown | frozen E suite/assignment18, V answer3/context3 | PASS | 17.97 с, без суммы/подтверждающих sources |
| V06 — scenario п.5 | Сводка прежних3×2 явно подписана отдельным evaluation run ID | V end176.64s, showSummary, public-summary | PASS | E2E344b… и исторический replay dbf… видны отдельно от app run688d…; прежний FAIL закрыт |
| V07 — scenario п.5 | Replay quality summary, same messages/historical/local distinction, privacy, no fresh race | V end, R, public-summary | PASS | Агрегаты без private текстов; исторический характер явный |
| V08 — scenario п.6 | Времена и ограничения; явные «код проверен», «видео проверяется», «не опубликовано» | V answers/end176.64s | PASS | Все три раздельных статуса прочитаны на actual MP4; прежний FAIL закрыт |
| V09 — scenario automation | Одинаковый сценарий3 новых requests, wait exact ID/API results; ошибки сохраняются | recorder C, D, V | PASS | Схема взаимодействия сохранена; после dry менялись только подписи UI |
| V10 — scenario automation | Настоящий viewport, оригиналы сохранены, без неразрешённого монтажа/ускорения | recorder C, V raw/webm/mp4/hash/duration | PASS | Record02 отдельно от dry/record01; итоговый MP4 равен исходному нового дубля |
| V11 — scenario verification | ffprobe, просмотр начала/каждого ответа/конца, IDs/времена/число, читаемость/privacy | собственные fresh ffprobe/9frames + V receipts/full decode root | PASS | Все9 PNG == actual MP4 RGB; reviewer прочитал ответы, источники и конец |

## Не-нормативное, исключённые условия и границы

- Дата/автор/название задания, статус «реализация начата» и историческое объяснение
  смены окна — контекст; реальные выбранные настройки проверены отдельно.
- «История диалога и goal-harness не нужны», «день не требует framework/FSM/изменений
  общих зависимостей» — границы/рекомендации минимального объёма, не требование
  добавить эти компоненты. Новых компонентов нет; scoped imports/dependencies проверены.
- Условие SPEC §6 «если три пригодных receipt не найдены» не применяется: три найдены
  и подтверждены. Ошибка локальной генерации не делает исходный receipt непригодным.
- Замена E03 отсутствующего факта по сценарию не применяется: бюджета в assignment18
  нет, исходный вопрос оставлен. Разрешение на монтаж не запрашивалось: монтажа нет.
- Human acceptance, публикация, upload/merge/commit/push не входят в требуемое
  выполнение. Их отсутствие не создаёт FAIL; они не приписаны автоматическому аудиту.
- SPEC не задаёт минимальный процент полноты/успешного legacy replay. Обязанность —
  оценить и сохранить недостатки. E02 PARTIAL и replay2/3 errors не скрыты и не
  превращены в более строгий или более мягкий выдуманный порог приёмки.


## Закрытие нарушений и оставшиеся ограничения

На предыдущем baseline были FAIL V02/V06/V08. Новый actual MP4 подтвердил:

- **V02:** в start1s видны URL `http://127.0.0.1:8068`, public/model/index и строка,
  что индекс перенесён без пересчёта, snapshot/models получены при подготовке.
- **V06:** в end176.64s сводка подписана отдельно E2E344b… и historical replay dbf…;
  это не app/request run688d…. Оба полных ID читаемы и совпадают с E/R receipts.
- **V08:** там же видны отдельные badges «Код проверен», «Видео проверяется»,
  «Не опубликовано». Во время съёмки video действительно ещё проверялось.

Исходные record01/video/frames/FAIL-аудит сохранены. Исправление ограничено UI/summary;
новая запись содержит реальные новые requests, а не монтаж старого материала.
**Открытых применимых FAIL/NOT PROVEN в этом baseline нет.**

Смысловые ограничения остаются: E02 не перечисляет все детали pipeline/порядка;
Q03/Q08 local legacy replay отвергнуты, Q07 имеет лишь косвенную цитату при отсутствии
официального задания в старом контексте. Exact original/source validation не доказывает
само по себе все выводы. Оценки сделаны агентом; пользовательская приёмка не объявлена.

Q04 подтверждён controlled sequencing:19 непересекающихся project requests,
наблюдение координатора и `record02_queue_and_state` перед запуском. Наличие свободного
lock/пустого resident list — моментальные observations, не machine-wide inference
telemetry прошлого. Никакие чужие процессы не останавливались. Не заявляются
physical disconnect, peak RAM, общее превосходство модели или статистическая стабильность.

ZIP — дополнительная локальная упаковка уже существующих кода/инструкций, не требование
SPEC. Commit/push/merge/upload/публикация исключены из данного объёма и не нужны
для положительного вердикта. Последующая смена summary.video_status на verified
отражает проверку и должна отличаться от сохранённого recording-state manifest;
будущие нерассмотренные изменения runtime автоматически этим вердиктом не покрываются.

## Детерминированный итог

50 применимых требований имеют PASS; FAIL и NOT PROVEN отсутствуют.
По правилу `all PASS → SPEC SATISFIED` итог для указанного локального baseline —
**SPEC SATISFIED**. Вердикт включает честно сохранённые ограничения качества и
проверенное новое видео; он не означает публикацию или человеческую приёмку.
