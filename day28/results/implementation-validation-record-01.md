# Day28 — независимая проверка реализации по SPEC

**Вердикт для record-01: SPEC NOT SATISFIED.**
Матрица: **50 применимых требований — 47 PASS, 3 FAIL, 0 NOT PROVEN.**
Приложение и реальные проверки подтверждены, но три обязательных пункта показа в
согласованном видео-сценарии не выполнены. Рабочая RAG не объявляется сломанной;
неполное соответствие материалов не превращается в PASS из-за успешных запросов.

Reviewer: фактическая модель **gpt-6-astra, xhigh**, 09.10.2026. Использованы
`implementation-validation/SKILL.md` и `references/evidence-and-verdict.md`.
Это аудит агента, **human_acceptance=false**. Код, процессы и исходные результаты
не исправлялись. Новые Ollama/облачные запросы и запись не запускались.

## Baseline и происхождение требований

- Worktree: `/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28`;
  branch `day28-local-rag`, HEAD `4659e24875902d3668e48ddea9f8d96a3dd36a5c`.
  Реализация Day28 пока untracked; commit HEAD сам по себе не описывает проверенную версию.
- Текущий полный `SPEC.md`: SHA-256
  `bb7a54c40339f69f73a733d41b2f94c7ea56a0b6a292bdc5e7d99616e9f69fd5`.
  Пакет подтверждён пользователем 09.10.2026 до реализации, что записано в
  [actions.jsonl](../actions.jsonl). Текст позднее уточнил измеренное окно 8192 и
  внутренний source_refs-протокол. Это не отдельная новая человеческая приёмка:
  исходные обязательства локальности, точных источников, replay и видео сохранены.
  Предыдущий самостоятельно прочитанный SPEC имел SHA `0a252841b3a0c9f22d0ab4281acd1a664b496afbdb89d39695b87e4ba5530bb1`;
  проверка не исключает прежних требований ради нового решения.
- Неизменённый согласованный `video/SCENARIO.md`: SHA-256
  `357afbc232bbb56f912ef2591505deef69296ce46a48c6ac4d876a8f068f2630`.
  SPEC §7 требует видео по этому сценарию, поэтому его обязательные действия включены
  в inventory, а не отброшены как необязательные советы.
- [source-manifest-recording.json](source-manifest-recording.json): SHA-256
  `4de75a5c5d8d877f0c515c16d7438962237343c25c4c51ea0ade1058f9f16b84`.
  Все семь runtime-файлов независимо сверены с текущими bytes: совпадение.
  Core `61a79221fcde8178201d1f3dbadb4e06ce3736c7db34049a3b1934827c702100`;
  app `0eb275fb8bd6d6facd9a755e04e6fe5efbd783dda3ba46be16c7a74bb3fb364e`;
  evaluate `05ddeb6d8a86600536d1880e2bb543e4581ae3d2fa0c71cd029dfc6d136d5ef4`;
  JS `e66186d47535b46185cd90d5c7354ac7baf4b2a04436ae0e856aa6a6daf74ab4`.
- `video/Day28-live.mp4` и `video/runs/record-01/live.mp4` побайтно равны;
  SHA-256 `9ec715ef5ffeb718f6867df39e7ffe35a08bf85a63f5937565784af95c1df173`.
  Это проверяемый baseline видео, а не будущая исправленная запись.

## Evidence и его возможные ложные подтверждения

| Группа | Как PASS мог бы оказаться ложным | Что проверено |
| --- | --- | --- |
| Индекс/локальность | Похожее имя файла, пересчитанные векторы, proxy/cloud alias либо внешний fallback | SHA, identity/counts/vector loader, exact digests, bounded transport code, реальные URL receipts; физическое отключение сети не заявляется |
| Источники | Валидный ID скрывает непереданный текст; приложение незаметно исправляет модельную quote | Сопоставлены actual messages, selected, source_refs/map, raw_model_answer и внешний answer; replay остаётся отдельным строгим протоколом |
| Качество | completed/citations_valid или одинаковые ответы ошибочно объявлены semantic PASS | Прочитаны фактические ответы по официальным фрагментам; E02 PARTIAL и два replay error сохранены; нет заявленной человеческой приёмки |
| Replay | Исторический response другой пары; изменённый prompt/формат выдаётся за тот же эксперимент | Исходные Day24 prepared/raw/ledger, hashes и actual local messages сопоставлены; отличие decoder controls и дат оговорено |
| UI/видео | Запись старых ответов, скриншоты ожидания вместо ответов, неподтверждённый MP4 | Уникальные новые IDs, persisted receipts → public projection → visible_answer; девять PNG сверены с пикселями MP4 и прочитаны; полный decode |
| Версия/время | Старые тесты относятся к другому коду, скрытые retries/параллельная генерация искажают время | Manifest на запись, backend неизменен относительно E2E; отдельный UI delta просмотрен; 16 наблюдаемых запросов имеют непересекающиеся интервалы |

Обозначения evidence в матрице:

- **C** — собственное чтение core/app/evaluate/UI/recorder и предыдущий
  [Astra review](review-astra.md), включая новый source_refs diff и отрицательные пути.
- **T** — сохранённые [31 offline GREEN](../tests/offline-green.txt), RED/GREEN
  identity/duration/repair/refs; собственные 5 refs + 2 evaluate теста и intercepted
  Ollama payload/недопустимый public ref/неизменный strict replay (см. review).
- **I** — самостоятельная read-only загрузка настоящего Structure, SHA/identity/counts,
  доступность всех 24 public assignments под бюджетом; [preflight](preflight.json).
- **E** — `private/runs/e2e-03/{run,suite-frozen,request}.json`, run
  `344b65a15e89407582d013f5fe11d89c`; [оценка](e2e-03-assessment.json).
- **R** — `private/runs/replay-01/`, run `dbf3969ef7ed49a282602fa06c92c184`,
  `private/replay-suite.json`, исходные Day24 prepared/ledger/raw;
  [оценка](replay-assessment.json).
- **A** — `private/all-cli-check/2d1dbd822fc444f88345fcfa481323f2/abdf7b31f0184509a7c58f3a59205951.json`,
  all/done, 45.40 с, stdout только статус/путь по аудиту координатора и коду.
- **D** — `video/runs/dry-01/results.json`, run `774130f8e2d343398316926da8c45a2a`;
  [browser fixture](browser-references-2/results.json) и явно GET-only
  [cached preview](ui-unknown-cached-preview-1/results.json).
- **V** — `video/runs/record-01/results.json`, run `3ae230eb1f8741b79c3899ba0762256a`,
  raw receipts приложения `688d3db5e77547678b99635a13c092a8`, настоящий MP4 и
  `video/verification/*.png`; [video-verification](video-verification.json).
- **F** — [final-verification](final-verification.json), source manifests,
  [RESULT](../RESULT.md), [README](../README.md), [RELEASE_NOTES](../RELEASE_NOTES.md),
  [video README](../video/README.md), Git status/diff и журнал действий.

## Свежие проверки в этом финальном аудите

Среда: macOS 15.6.1 arm64, Python 3.14.0; записи получены на Apple M2 / 16 GB.
Не заменял сохранённые настоящие запросы новыми и не повторял неизменившийся полный
набор тестов. Собственные предыдущие точные команды `python3 -m unittest discover
-s day28/tests -p 'test_references.py' -v` и аналогичная `test_evaluate.py` дали 5/5
и 2/2, exit 0; версия backend с тех пор совпадает.

В финальном проходе исполнены:

1. `pwd`, `git rev-parse --show-toplevel`, `git branch --show-current`, `git status --short`,
   `git rev-parse HEAD`, `git diff --name-only`: проверена указанная рабочая папка;
   tracked diff только CLAUDE/HANDOFF/todo, Day01–27 и общие зависимости не менялись.
2. Inline Python/hashlib: все files из recording manifest совпали; оба MP4 равны;
   проверены указанные в baseline SHA, exit 0.
3. `ffprobe -v error -show_format -show_streams -of json day28/video/Day28-live.mp4`:
   exit 0, 175.12 с, 4 801 985 bytes, единственный H.264/yuv420p video stream,
   1280×1000, 25/1 fps; аудио нет.
4. `ffmpeg -v error -i day28/video/Day28-live.mp4 -f null -`: exit 0, stderr пуст;
   это собственное полное декодирование, а не только доверие строке PASS в отчёте.
5. Для каждой пары PNG/time из video-verification: `ffmpeg -v error -ss <time>
   -i day28/video/Day28-live.mp4 -frames:v 1 -f rawvideo -pix_fmt rgb24 -` сравнен
   с `ffmpeg -v error -i day28/video/verification/<file>.png -frames:v 1 -f rawvideo
   -pix_fmt rgb24 -`: все девять совпали по RGB bytes, exit 0. Затем reviewer прочитал
   start 1 s; E01 answer/source 42/50 s; E02 answer/sources 114/121/126 s;
   E03 answer/context 154/159 s; end 173 s. Waiting-кадры не использовались как ответы.
6. Inline Python с assert по 16 actual receipts (E6 + R3 + D3 + V3 + A1): уникальные
   request IDs, разные интервалы, правильные run IDs/options/digests/prompt hashes,
   frozen suite SHA, done/stop и метрики. E2E/messages/materialization пересчитаны
   из сохранённых данных без модели. D/V actual == public_result(persisted receipt),
   visible_answer == answer.answer. Replay messages/response_format/historical_response
   совпали с frozen suite, embedding/retrieval null. Все **77** сетевых записей только
   `http://127.0.0.1:11434/api/*`. Exit 0. F охватывает 13 из них/62 вызова; это
   пересекающееся evidence, не ещё 13 независимых наблюдений.
7. Независимо перечитаны по одному уникальному E01/E02/E03 answer и все local/cloud
   replay ответы; `validate_answer(..., source_key='source')` подтвердил cloud 3/3,
   local replay 1/3, ошибки Q03 quote_not_exact, Q08 source_not_in_selected_context.
   Дословность original projection и смысловая полнота оцениваются раздельно.

## Полный нормативный inventory и матрица

SPEC не содержит стабильных IDs; ниже они выведены из разделов. Строки группируют
только связанные утверждения; повторяющиеся формулировки SPEC ссылаются на один
и тот же item. Связанный сценарий раскрывает требование SPEC §7, не дублирует
дополнительную независимую приёмку.

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
| L01 — §2 | Runtime только local index/loopback Ollama, без SSH/cloud/keys/fallback | C, E, R, A, D, V, F | PASS | 77 наблюдаемых URL local; physical disconnect не заявлен |
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
| Q04 — строка84 | LLM/видео последовательно с другими днями на Mac16GB | I, интервалы16 requests, observation координатора | PASS | Координатор контролировал очередь проектных задач; это не machine-wide telemetry |
| Q05 — строка85 | Локальные index и точный embedder подготовлены | I, E, R | PASS | Реальные query embed, 639150858 bytes модели в preflight |
| Q06 — строки87–88 | Согласование пакета до кода; нет commit/push/merge/upload/paid вне scope | actions, Git HEAD, F | PASS | Approval10:22 раньше implementation10:25; не требуется выполнять исключённые публикации |
| V01 — scenario initial | Чистый public экран, модели/index готовы, private receipts не открыты | V start, raw receipts, C | PASS | На старте нет старых ответов; queue вынесена в Q04 |
| V02 — scenario п.1 | Показать URL и пояснить перенос без пересчёта/предварительное получение моделей; names/index/public | V start/end, static/index.html/app.js | FAIL | Names/index/public видны; URL и пояснение переноса не отображаются, запись без аудио |
| V03 — scenario п.2 | Новый E01, terminal ID, assignment18/original, retrieval/generation/total | V answer1/source1 + persisted receipt | PASS | 34.96 с, exact original и ответ читаемы |
| V04 — scenario п.3 | Новый E02, оба original, проверка полноты/ограничение | V answer2/source2a/source2b/end, E | PASS | 52.97 с; оба текста читаемы, summary сообщает неполную детализацию |
| V05 — scenario п.4 | Отсутствующий бюджет проверен до freeze; новый честный unknown | frozen E suite/assignment18, V answer3/context3 | PASS | 18.70 с, без суммы/подтверждающих sources |
| V06 — scenario п.5 | Сводка прежних3×2 явно подписана отдельным evaluation run ID | V end173s, JS35, public-summary.json | FAIL | UI рендерит только message; E2E ID344b… отсутствует, request run688d… другой |
| V07 — scenario п.5 | Replay quality summary, same messages/historical/local distinction, privacy, no fresh race | V end, R, public-summary | PASS | Агрегаты без private текстов; исторический характер явный |
| V08 — scenario п.6 | Времена и ограничения; явные «код проверен», «видео проверяется», «не опубликовано» | V answers/end | FAIL | Времена/ограничения/не опубликовано есть; первые два статуса отсутствуют |
| V09 — scenario automation | Одинаковый сценарий3 новых requests, wait exact ID/API results; ошибки сохраняются | recorder C, D, V | PASS | Схема взаимодействия сохранена; после dry менялись только подписи UI |
| V10 — scenario automation | Настоящий viewport, оригиналы сохранены, без неразрешённого монтажа/ускорения | recorder C, V raw/webm/mp4/hash/duration | PASS | Record01 отдельно от dry; итоговый MP4 равен исходному |
| V11 — scenario verification | ffprobe, просмотр начала/каждого ответа/конца, IDs/времена/число, читаемость/privacy | собственные fresh ffmpeg/9frames + V receipts | PASS | Все9 PNG == actual MP4 RGB; прочитаны ответы, источники и конец |

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

## Нарушения и недоказанное

**P2 — отсутствует обязательная видимая информация в видео (V02, V06, V08).**
На start1s и end173s нет URL/пояснения переноса; сводка3×2 не имеет своего run ID;
не показаны «код проверен» и «видео проверяется». `static/app.js:35` выбирает только
`summary.message`, хотя JSON содержит идентификаторы. Наличие IDs в private receipts
или в README не выполняет требование показать их в самой записи. Это конкретное
несоответствие SPEC §7/сценарию, а не замечание о стиле или предположение о риске.

Минимальное исправление: видимый metadata/status блок с URL, фактом неизменного
снимка/предварительной подготовки, отдельным E2E run ID и тремя честными статусами;
новая живая запись с тремя новыми requests и повторной проверкой кадров/IDs. Старый
record01 сохранить. Исправленная HTML-страница или cached preview сами по себе не
снимают FAIL с существующего MP4. Runtime E2E/replay повторять из-за такой UI-правки
не нужно при неизменных backend/schema/options и проверенном новом interaction flow.

**Q04 — граница evidence:** проверено отсутствие пересечения16 Day28 requests.
В ходе аудита 09.10.2026 координатор дополнительно подтвердил: все реальные вызовы
этой работы запускал последовательно; делегатам были запрещены Ollama-вызовы,
остальные роли выполняли план/код/чтение evidence. Сохранённая фаза
`local_model_preflight_and_config_freeze` в actions10:29UTC отмечает очередь и
отсутствие перезапуска Ollama. Это совместно подтверждает координацию управляемых
проектных задач и снимает первоначальный пробел Q04. Машинная телеметрия всех
процессов за прошлые интервалы не велась; отсутствие любого стороннего inference
не заявляется. `loaded_models_snapshot` сам по себе такой гарантии не даёт.

Качество: E01 факты/полнота PASS; E02 поддержанные факты PASS, полнота PARTIAL;
E03 корректный unknown. В legacy replay Q03/Q08 отклонены строгим валидатором,
Q07 сообщает нехватку старого контекста; его косвенная цитата не доказывает отсутствие
факта во всём архиве. Модельное превосходство, статистическая стабильность, peak RAM,
machine-wide network capture и физическое отключение интернета не доказаны и не заявлены.

## Детерминированный итог

Inventory содержит все применимые кандидаты из полного SPEC и обязательного сценария.
Есть **FAIL V02/V06/V08**, поэтому по правилу `any FAIL → SPEC NOT SATISFIED`
итог этого baseline — **SPEC NOT SATISFIED**. Применимых NOT PROVEN после
полученного observation координатора не осталось; его граница указана отдельно.
Положительное ревью core и успешное декодирование видео не отменяют этих строк.
Следующий аудит может быть узким: новая metadata/UI дельта, её checks, новая запись
и конкретное observation очереди для новой записи. Старые выводы не снимаются
без новых конкретных доказательств.
