# Day30 — план реализации и проверки

Актуальная сдача: [уточнение SPEC](SPEC.md#уточнение-сдачи-по-исходному-условию--12102026), D1–D6. Последнее поручение пользователя снимает semantic-gate дополнительных пересказов для сдачи исходного задания. Runtime/model/index остаются profile12, прежние semantic FAIL сохранены. Порядок: сетевой preflight и targeted limits → dry3 → record3 → независимые Luna/Astra → код/видео/Sheet. Ниже сохранён прежний план разработки.

Источник требований — [SPEC](SPEC.md), прогресс — [TASKS](TASKS.md). Линейная работа
с коротким журналом важных действий; FSM и новый orchestration framework не нужны.
База worktree: `day30-private-service` от `b3e607e`.

## Текущее продолжение: profile12

Root выбрал уже установленнуюQwen3:8b Q8 после semantic FAIL11. Snapshot11 fixed и
старые FAIL сохраняются; это профильная гипотеза, не доказанный precision-only эффект.

1. Sol меняет MODEL/GEN_DIGEST по SPEC12; existing Qwen2Tokenizer получает actual gpt2/
   pre=qwen2 metadata. Проверить identity/rejection старого digest, Unicode/числа/пробелы
   существующего tokenizer и неизменённые source spans.8192/1024/512/300, оба native/
   thinkfalse, samplers11, limits900/910/920/930 и quantity11 fixed/P2 сохранить.
2. Canonical builders остаются; передbudget/wire schema переименовать только structural
   roots и conclusion по SPEC. Output instructions используют actual aliases. RED→GREEN
   actual HTTP wire и sorted-provider simulation: grounds→coverage/conclusion, text→refs.
   Strict decode только после strict_json: alias-only roots/conclusion→canonical06;
   unknown/mixed/missing/duplicate keys FAIL, nestedIDs/free text не изменяются. Старые
   canonical validators выполняются полностью; source/quantity/M не расслаблять.
3. Actual wire schema учитывается вBPE budget один раз; P2 rebuild→alias→budget после
   каждого удаления. Trace actual alias schema/order/raw и отдельный canonical результат.
   Meaningful systemPython3.9.6 checks: oneOf single, quantitypreflight1/1,8/4,8/4,
   earliest-fitting pruning, observedoverflow, privacy08, nativewire и API shape.
   Existing safe_final_shape должен безопасно узнавать exact aliases (через строгую
   нормализацию), чтобы сохранять valid raw final; unknown payload по-прежнему opaque.
4. Independent review всего delta, baseline; root idlePS/read-onlyRAM preflight,
   толькоDay30 restart с сохранением histories. Никаких новых весов/global settings.
   Максимум3 прежних fresh cases, verdict перед следующимsubmit, первыйFAILstop.
   Publicпосле3PASS. ПриFAIL12 остановитьmodel/parameterloop для решенияscope/формата;
   никаких заявленийhumanapproval/общегоqualityPASS по metadata или offline mocks.

## Сохранённый план profile11

10 завершился length1920/final0.11 возвращает native non-thinking и соблюдает явное
количество примеров; никакого нового cap escalation. Snapshot10/FAIL сохраняются.

1. Sol RED→GREEN узкий detector текущего question по SPEC: explicit imperative+one+noun
   в начале question либо после `? ! . ; newline`, с optional whitespace; сохранить
   newline boundary до normalization. Case/spacing и optional concrete; quoted spans,
   negatives/other cardinality/each/distributive/обычный follow-up не
   активируют single. Ни topic/case IDs, ни наследования из history. Answer limits1/1
   либо8/4 входят в extra обеих стадий и trace; generic system instruction соблюдает их.
   Synthetic multi-sentence positive и quoted/negative regression без private quotes;
   read-only preflight actual трёх неизменённых cases перед live: только quantities
   G01T1=1/1, G01T2=8/4, transfer=8/4. Original snapshot11 не перезаписывать.
2. Selection single evidence oneOf empty+exact singleton branches текущих allowedIDs,
   не maxProperties-only (pinned converter игнорирует его). Backend rejects >1proof;
   context expansion background сохраняется. Synthesis maxItems1+P1-only refs, []unknown;
   independent strict quantity reject без truncation. Safe validation codes по SPEC.
   Ordinary8proofs/4points сохраняются. Проверить >1,unknown,background/cross-aspect и M.
3. Обе actual calls thinkfalse/native; synth1024/.7/.8/300, selection1024/temp0/300.
   Удалить appended schema synthesis из messages, budgetmessages+format schema один раз.
   Limits total900/join910/Exit920/poll+video930 из существующих constants; trace native.
   Dynamic P2 builders после КАЖДОГО удаления rebuild oneOf/IDs/maps/coverage/projection
   доbudget. Проверить earliest-fitting set и actual wire, полноценный счёт expandedschema.
4. SystemPython3.9.6 meaningful suite, независимый review quantity/native/privacy/P2,
   новая baseline. Root готовит Day30 main/demo plist/runner и idle restart с сохранением
   history. Максимум3 unchanged cases, independent semantic verdict до каждого следующего
   submit. Первый FAIL останавливает not-yet-accepted. Public после3 PASS; иначе решение
   scope/формата, без автоматического увеличения caps и без ослабления semantic gate.

## Сохранённый план profile10 + inherited P2

09 дал length1408/final0; native-format512 не обеспечивает переход к final. Root выбрал
one-pass1920/900 как последний bounded capacity probe. Global CODE NEEDS CHANGES до
исправления inherited P2; прежнее09 delta approval хранится как история.

1. Sol RED: воспроизвести преждевременное лишнее pruning через настоящий fit_prompt/
   service wire для ОБЕИХ стадий. Проверка должна различать stale и rebuilt schema/maps,
   а не только проверять окончательное отсутствие уже удалённых IDs. Зафиксировать
   earliest-fitting retained set и точный согласованный prompt/schema/coverage/budget.
2. Один владелец pruning — fit_prompt; небольшой pure stage-builder текущих units
   пересобирает schema/extra перед КАЖДЫМ render/budget. Selection: allowedIDs/schema/
   dialogue_focus; synthesis: retain_coverage исходной validated coverage → schema/maps.
   Projection из тех же units. Вернуть последнее согласованное представление вызывающему
   коду; убрать поздние повторные внешние pruning loops. Без накопительного downgrade,
   мутации исходных units/coverage или нового framework. Empty-proof/unknown сохранить.
3. Synthesis actual1920/900; selection/embed прежние, shared sum1500, join1510,
   Exit1520, poll/video1530. Dynamic budget и observed check используют1920, trace actual
   deadline_seconds900. На08/09 reconstructed messages сравнить input6738/6240 и final
   retained evidence при1920, не читать reasoning. Privacy08/wire/strict validators,
   короткие mocked stalled deadlines/shutdown и meaningful systemPython3.9.6 suite.
4. Независимый review inherited P2 плюс10 delta, новая baseline. Root готовит только
   Day30 main/demo plist и private10 runner с теми же вопросами; idle controlled restart
   сохраняет histories. Максимум3 cases; перед следующим submit independent semantic
   PASS, первый FAIL останавливает not-yet-accepted. Никакого autoretry/нового cap-loop;
   при FAIL следующий шаг — решение scope/формата на новом основании. Public после3 PASS.

## Сохранённый план profile09

08 завершился timeout headers/0bytes на первом synthesis; reasoning/final объём неизвестен.
SPEC09 корректирует только synthesis output/deadline и связанные ожидания. Snapshot08
и прежние FAIL сохранены; улучшение качества не доказано.

1. Sol RED→GREEN: synthesis options num_predict1408, actual transport deadline600с;
   selection/embed и остальные routes300с, selection output1024. Передавать stage cap
   явно; убрать hardcoded min(...,300), сохранить absolute deadline и cancel-before-unlock.
   Проверить actual wire options, trace/budget deadline_seconds, no-format/think08,
   одноразовый schema budget и observed overflow. Input6738+1408=8146 помещается;
   новый input не обязан повторить selection08, прежний whole-unit pruning сохраняется.
2. Связанные limits: provider sum1200 → worker.join1210, ExitTimeOut1220,
   CLI/private poll/video1230с. Общие constants/простой accessor вместо расходящихся
   literals; никакого нового framework. Проверить generated plist и shutdown helper,
   stalled headers/body абсолютный срок, bounded lock release и privacy08 regressions
   с короткими подставными deadlines, без десятиминутного offline ожидания.
3. SystemPython3.9.6 meaningful suite, независимый review, новая baseline. Root обновляет
   только Day30 main/demo plist и контролируемо перезапускает при idle, сохраняя histories.
   Не расширять num_ctx/model/prompt/schema или читать/сохранять reasoning.
4. Максимум3 свежих неизменённых questions; после каждого independent semantic verdict
   перед следующим submit. Первый runtime/semantic FAIL останавливает not-yet-accepted;
   autoretry нет. Public dry/record лишь после3 PASS.600с — cap, не обещание latency.

## Сохранённый план profile08

Root выбрал thinking только synthesis без native format после semantic FAIL07.
Snapshot07 сохранён; SPEC08 уточняет think/format/budget/privacy, остальной protocol06 прежний.

1. Sol RED→GREEN actual-wire: selection прежний; synthesis think=true, format key отсутствует,
   options07 без изменений. Ровно system/user; user=context JSON+newline+ordered dynamic
   schema JSON. Проверить фактические bytes/schema order, неизменённое содержание schema,
   её единственный учёт в budget, пересборку после whole-unit pruning и observed-count gate.
   Trace actual options/think/format_mode, order arrays не выдавать за enforced grammar.
2. До сохранения любого response/error убрать reasoning. Отдельные sentinel-тесты success,
   safely parsed error, timeout/partial/malformed JSON и persistence путей: ни thinking,
   ни raw excerpts в файлах/API/logs; для unsafe raw только stage/bytecount/SHA256.
   Сохранить final/metrics/provenance; strict JSON/duplicate keys/length/empty final остаются
   FAIL. Никакого извлечения final из reasoning, retries или второго synthesis прохода.
3. Meaningful suite под systemPython3.9.6, независимый review privacy+wire+budget, baseline.
   Проверить отсутствие provider debug logging reasoning перед live. Лимиты8192/1024/512/
   absolute300с прежние;1024 вместе reasoning+final. При прежних3.3TPS запас ограничен:
   ~800–850 tokens может уложиться, полный1024 с prompt — нет; это оценка, не измерение08.
4. Root выполняет Day30 restart и максимум3 неизменённых fresh private cases, без retries.
   После каждого результата ждать independent semantic verdict до следующего submit.
   Первый FAIL останавливает not-yet-accepted cases; принятые requests учитывать честно.
   Public dry/record только после3 runtime+semantic PASS; прежние FAIL и human pending прежние.

## Сохранённый план profile07

Root выбрал synthesis-only non-thinking sampling после двух semantic FAIL06.
Прежняя SPEC protocol06 уже архивирована; текущие требования profile07 — в SPEC.
Это отдельная гипотеза профиля, не новый prompt patch и не доказанная причина ошибки.

1. Sol RED→GREEN actual-wire тесты: selection options прежние (temperature0), synthesis
   temperature0.7/top_p0.8; independent dict copies. Оба think=false, та же9B/digest.
   Проверить, что provider, budget и private trace видят один actualstage options dict,
   а observed-count gate использует его num_ctx/num_predict. No seed/default overrides.
2. Прежние8192/1024/512/300с, protocol06/prompts/schemas/provenance/M/renderer/retrieval
   сохранить. Meaningful suite под systemPython3.9.6, independent review, новая baseline
   с stage options; ни module-global mutation, ни фиктивного trace неотправленной стадии.
3. Root перезапускает только Day30 и выполняет максимум3 свежих прежних вопроса.
   После каждого результата **сначала independent semantic verdict**, потом следующий
   API submit. First FAIL останавливает ещё не accepted cases; никакого автоматического
   добора/retry. Уже начатые requests сохранить честно. Public только после3 runtime+
   semantic PASS; даже этот gate не является общей оценкой качества или causal proof.

## Сохранённый план protocol06

Последнее root decision перед freeze исключает anchors/anchor_ids/partition целиком.
Point возвращает только aspect_ids,evidence_id,text; существующий immutable unit ID
достаточен для provenance. Это не гарантия semantic support. Старые FAIL сохраняются.

1. Sol RED→GREEN: обе model projection содержат essential metadata и полный text ровно
   один раз; synthesis добавляет evidence_role. Backend units/атрибуция/offsets прежние.
   Whole-unit pruning, actualprojection budget; никаких sliced/normalized originals.
2. Point validator проверяет retained proof ID и каждый aspect; code получает полный
   exact quote/start/end из unit. Тесты unknown/background/cross-aspect refs, original
   identity и неизменённого API. Нет model quote copying/anchor IDs/partition tests.
3. Model doubtful_aspect_ids — только fullQ; код M=partial/none∪unrepresented∪doubtful.
   Проверить, что [] не скрывает partial, unknown сохраняется, supported не означает
   independent semantic PASS. Старый raw не переинтерпретировать как успешный.
4. Schema/prompts меняются только для нового output contract; safe codes/trace protocol06;
   actual HTTP wire order: points→doubtful→conclusion, nested aspect_ids→evidence_id→text.
   SystemPython3.9.6 suite и независимый review; остальные9B/options/2calls/retrieval прежние.
5. Root фиксирует baseline, перезапускает только Day30 и выполняет максимум3 неизменённых
   fresh private questions. Reviewer сравнивает fulloriginals, points и итог, включая
   направление действия, конкретику и отсутствие выдуманной причинности. При первом
   FAIL public ждёт, autoretry нет; после3 runtime+semantic PASS продолжить dry/record.

## Сохранённый план repair05

Profile04 остановлен после первого FAIL. Исходниками pinned Ollama0.33.3/llama.cppb10760
и raw03/04 подтверждено: canonical provider JSON переставляет properties, и грамматика
порождает conclusion до grounds. Root выбрал исправление только provider serialization.
SPEC-profile04 сохранён в review-history; точные четыре уровня order перечислены в SPEC.

1. Sol: RED wire regression через actual Ollama.request с подставным HTTPConnection,
   затем отдельный ordered JSON serializer provider body. packed/state/hash/prompt body
   прежние; AICODE-NOTE объясняет влияние order на grammar. Model/options/schema contents/
   prompts/validators (включая M)/retrieval не менять. Проверить payload semantic equality,
   canonical packed и ByteBound length invariance; observed count gate сохраняется.
2. Private trace: четыре schema-property-order arrays от реально отправляемых schemas;
   canonical map не evidence wire order. Не ставить выполненной неотправленную стадию.
3. SystemPython3.9.6 targeted/full актуальные offline checks, независимый review,
   новая baseline; root выполняет контролируемый restart только Day30.
4. Максимум3 неизменённых private вопроса: known pair + выбранный transfer, без retry.
   При FAIL остановить зависимый public; при3 runtime+semantic PASS продолжить dry/record.
   Само устранение ordering bug не считается доказательством semantic улучшения.

## Сохранённый план profile04

Repair03 на8B дал FAIL с первого запроса; оставшиеся два не запускались. Root выбрал
отдельную модельную гипотезу из уже установленных весов. Предыдущий SPEC сохранён
в `results/review-history/SPEC-protocol03.md`; точные требования profile04 — в SPEC.

1. Sol меняет только MODEL и GEN_DIGEST в local.py на Qwen3.5:9b-q4_K_M/digest56671c…;
   адаптирует документацию и ожидания tests. Prompts/schema/repair03/параметры не менять.
2. Offline проверить identity, rejection старого digest, обе chat payload с новым MODEL
   и think=false, existing pre=qwen35→ByteBound fallback, оба budgets/pruning и rejection
   observed overflow. Тесты не должны обучать Qwen2Tokenizer новому pre или вводить9B
   inference. Снова meaningful suite под действующим `/usr/bin/python3`3.9.6.
3. Независимый review этой узкой смены, новая baseline. Root при подтверждённом idle
   освобождает8B из RAM, проверяет `/api/ps`, переключает только Day30; общий Ollama,
   weights-on-disk и системные настройки сохраняются. CLI/web metadata read не считать
   живой проверкой генерации. Любые новые load/RAM/latency numbers измерить, не переносить
   результаты Day26 как текущие.
4. Gate profile04 максимум3 private content queries: неизменённый known pair + ранее
   выбранный transfer case. Два вызова той же9B, без autoretry/дополнительного critic.
   Записать retained/pruned source IDs и ByteBound: из-за консервативной оценки контекст
   может стать меньше8B BPE, поэтому это сравнение deployment profile, не чистый тест
   способности модели при идентичном prompt. После любого FAIL остановить зависимую
   публикацию и пересмотреть гипотезу; после3 runtime+semantic PASS продолжить public.

Ни запуск, ни переключение сервисов этим редактированием документов не выполнены.
Инструкции ниже о запрете model-switch относились к циклу repair03 и заменены этим
явным решением profile04; сам внутренний протокол repair03 остаётся текущим.

## Сохранённый план протокола repair03

12.10.2026 root выбрал изменение внутреннего протокола на той же8B. Точный контракт
в [SPEC, repair03](SPEC.md#уточнение-repair03-внутренний-протокол-12102026).
Это следующий ограниченный цикл; прежние FAIL и receipts сохраняются.

1. Sol сначала добавляет RED offline contracts: generic двухаспектный follow-up,
   coverage вопроса отдельно от завершения события; selection map/limits/allowed IDs;
   duplicate JSON keys на всех уровнях, включая вложенные объекты; точный anchor,
   point→aspect→selected proof, dangling conclusion refs, missing/partial/unknown.
   Использовать синтетические источники и raw сохранённых ошибок без hardcoded ответов.
2. Реализовать обе новые схемы и strict parsing, затем renderer прежнего API.
   Каждый текст summary происходит из point.text; anchor остаётся только trace.
   Никакой silent dedupe, исправления текста под эталон, вывода роли автора из prompt
   или автоматического semantic PASS. Проверить safe error-code allowlist.
3. RED→GREEN обоих budgets: pruning убирает целые units и пересобирает schema/mapping/
   coverage; ни dangling IDs, ни потерянное partial, ни ссылки на background не проходят.
   До inference проверить новый размер schema/prompt с reserves; 1024 output не увеличивать
   автоматически. Готовый overlong/invalid ответ не сокращать постфактум.
4. Проверить совместимость UI/API/history/focus/demo и targeted suite именно на
   действующем `/usr/bin/python3`3.9.6; затем независимые review по изменённому контракту,
   исправления и повтор затронутых checks. Старый runtime/индекс не менять.
5. Root фиксирует новую baseline и безопасно перезапускает только Day30. Следующий
   private gate — максимум3 дополнительных содержательных запроса: known pair и один
   новый transfer case другой темы, выбранный root/reviewer до запуска. Без autoretry
   и дополнительных проб. Gate требует3 runtime PASS и3 independent semantic PASS;
   code/anchor/schema PASS отдельно. Если FAIL — public dry/record/публикация ждут,
   причина сохраняется, четвёртый prompt patch не запускается автоматически.
6. Только после PASS — существующий public assignment dry/record и разрешённая сдача.
   Root обновляет TASKS/короткие todo/HANDOFF; автор этих SPEC/PLAN не выполняет финальное
   независимое code review. Model-switch9B/новые веса/покупки этим циклом не разрешены.

Изменения ограничены service/evidence parsing/schema/renderer и соответствующими tests;
для старых сохранённых receipt/trace новый protocol_version не проставляется.

## Архитектура и заимствования

`HTTPS UI/API → auth/validation/rate-limit → shared inference lock → fresh retrieval
→ Qwen evidence selection → проверка IDs → Qwen synthesis → проверка schema/refs
→ private store + ответ`. Каждый model call имеет собственный context budget.
Модель только читает источники и отвечает; внешних инструментов и побочных действий нет.

Самостоятельно скопировать только используемые блоки из:

- `day29/core.py`: immutable identity/vector validation, фиксированный local Ollama,
  no-proxy/no-redirect, atomic private save, общий flock. Не тянуть profiles/critic/benchmark.
- `day29/full_chat_core.py`: полные metadata, offset attribution, fresh retrieval,
  обработку темы/follow-up, evidence context и минимальную логику private conversation store.
  Перенести нужные функции, не legacy engine, evaluation controller и экспериментальные режимы.
- `day29/full_chat_retrieval.py`: lexical ranking, author forms и доказательные признаки.
- `day29/full_chat_evidence.py`: evidence units, admissibility, schema и проверку selection.
  Старый quote-only renderer не является окончательным ответом Day30.
- `day29/full_chat_tokenizer.py`: локальный BPE и бюджет с schema/template/output reserves.

Перед переносом прочитаны AICODE-заметки: не наследовать соседних авторов; не путать
день с подстрокой/историю с новой локальной темой; имена не являются topical terms;
отчёт не равен imperative; byte/BPE оценка включает wrapper/schema/template;
сохранить порядок общего inference lock. Незакрытых AICODE-ASK/QUESTION в этих файлах
не найдено. Заимствования и исходный commit записать в docstring/README Day30.

## Порядок

1. **Среда и SPEC.** Root обнаружил M2/arm64, frozen index, LAN `192.168.0.100`,
   свободный8080; прежние UI не слушали. По сообщению root существующий Homebrew
   launchagent уже поднял Ollama0.33.3, `/api/tags` подтвердил оба frozen digest.
   Использовать этот процесс, не создавать второй и не менять глобальные настройки.
   Проверить индекс и доступность tokenizer metadata перед inference; LAN IP не вечен.
2. **Минимальный TDD core.** Сначала падающие offline контракты для двух вызовов,
   передачи выбранных originals, обоих budgets и недопустимых refs; затем перенос
   проверенных блоков и новый synthesis. Отдельно negative paths: unknown/partial,
   prompt injection как данные, invalid JSON/length/timeout без retry, lock release.
3. **API, история, UI.** Тесты реального HTTP handler с подставным inference:
   неверная auth, Host/Origin, лимиты, concurrency, request-size, restart. Реализовать
   простой чат с пересказом/выводом и `<details>` оригиналов; токен в памяти страницы.
   API routes/response shape задокументировать по окончательной реализации.
4. **Private deployment.** Создать секреты/сертификат только private; bind конкретного
   LAN IP + TLS, отдельный launchd label/log paths, безопасный stop. Проверить TLS
   через CA, auth и listener. Перезапуск Day30 сохраняет историю; Ollama и Day29 не
   перезапускаются скриптом приложения. Если LAN IP изменился — listener/cert/settings
   требуют явного обновления, silent fallback на все интерфейсы запрещён.
5. **Bounded live evidence.** Сначала подобрать из read-only источников два public
   assignment-вопроса и private discussion+follow-up. Максимально совместить smoke
   с видео; ≤6 содержательных live запросов начального набора, каждый максимум два
   chat-вызова. Если дефект требует нового прогона — исправить и повторить затронутый
   случай с записанной причиной, не запускать Day29 benchmark. Проверить три успешных
   последовательных ответа и отдельный restart; concurrent busy/rate-limit/ошибки
   прежде всего offline, не создавать нагрузочный inference benchmark.
6. **Независимая проверка.** Luna проверяет SPEC/code/tests; Sol исправляет; fresh Astra
   перечитывает код и результаты и independently проверяет смысл выбранных live ответов
   по источникам. Semantic verdict отдельно от schema/citation validity и offline PASS.
   Для плохого ответа записать конкретное расхождение и исправить; отсутствие основания
   даёт unknown, а не косметическое переименование FAIL в PASS.
7. **Сдача root.** MP4 без аудио из public assignment scope, проверка проигрывания и
   отсутствия утечек; README/RESULT/DELIVERY с точными evidence paths. Только после
   проверок commit/push, GitHub day30 по порядку, Drive прежняя папка/viewer по ссылке,
   заголовок Day30 и строка132 перед записью двух URL, reload/readback. Предыдущие
   файлы/ссылки не переписывать. Обновить короткие todo/HANDOFF по результату.

## Evidence и оставшиеся фактические решения

`day30/results/` — безопасные агрегаты offline/live/review/deployment, без текстов private.
`day30/private/` — история, полный trace, semantic audit, сертификат/ключ и подробные
локальные проверки. `.env` — credential; не копировать его в журнал/команды публикации.
Короткий `day30/actions.jsonl` фиксирует время, фазу, исход, причину, ссылку;
модель роли — фактическая, usage/cost только если измерены. TASKS хранит текущий статус.

Рутинно уточняются исполнением: свободный порт, актуальный LAN IP, доступный Ollama
binary/launchd способ, SAN сертификата, вопросы из фактических originals и точные
табличные/Drive targets из прежней publication evidence. Второе устройство отсутствует;
не выдавать локальный LAN-address curl за проверку с другого устройства. Новый scope,
покупка или публичная экспозиция требуют отдельного решения пользователя.
