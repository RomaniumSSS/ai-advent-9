# Day30 — independent implementation validation, baseline05

**Вердикт: SPEC NOT SATISFIED.** Repair05 CODE APPROVED. Первый live запрос gate05 — runtime FAIL, остальные два не выполнялись. Доставленного ответа нет: его семантика NOT PROVEN. Видео/публикация не готовы; человеческая приёмка pending.

## Baseline и evidence

Нормативный источник: `results/review-history/SPEC-repair05.md`, SHA `a500a3382e5b0b0b6d29a1c8d7e1b43eaafcdcb01941e4168f838af95df1db2f`, зафиксирован в `results/code-baseline-05.json`, 29 файлов, base b3e607e. Все29 hashes сверены при CODE gate, runtime hashes повторно после live: расхождений нет. Рабочий контракт основан на пользовательском результате/HANDOFF; отдельное человеческое утверждение SPEC не заявляется. Будущий protocol06 исключён из этого заключения.

CODE — независимое чтение runtime/SPEC/PLAN и official converter source. Reviewer repair05: 5 targeted PASS за2.045s, CLT Python3.9.6, плюс четыре synthetic diagnostics проверки; Sol5 PASS2.043s и33 linked PASS6.173s. Прежние OFF81 (protocol03, quiet17.602s), reviewer13 protocol checks, profile04 reviewer6 и предыдущие provider/HTTP/lifecycle regressions переиспользованы только для неизменённых компонентов. Новый полный suite не заявляется. Mock не заменяет live.

LAN — CA-verified HTTPS/auth/Host/Origin/API. RESTART05 — `restart-05.json`: новые PID21564/21649,10 старых state files неизменны, replay отсутствует. PRIVATE05 — `live-private-05.json`, private receipts и независимое immutable DB чтение двух originals/metadata. Оба spans exact; anchors:1 exact,1 invalid. Неизменённый offline replay дал invalid_point_anchor. Все четыре порядка полей raw output соответствуют SPEC05/trace. UI logic неизменна, прежний browser evidence mock.

Ошибка API не считается успешным ответом. Raw candidate не является показанным ответом; точные refs не доказывают смысл. Historical FAIL01–04 сохранены. One-host LAN не доказывает второе устройство; код video runner не доказывает actual video.

## Нормативный инвентарь полного SPEC

Каждая строка объединяет только связанные наблюдаемые требования; A1–A10 сохранены как исходные IDs. Строки G и Z покрывают нормативные границы и раздел «Завершение» вне таблицы SPEC.

| SPEC item | Наблюдаемый контракт | Evidence | Статус | Граница доказательства |
|---|---|---|---|---|
| G1 | Самостоятельный Day30, API+чат, M2/16GiB, runtime imports только своего дня | CODE, LAN, environment report | PASS | Не доказательство качества ответов |
| G2 | Read-only frozen generation/DB724chunks663docs и source counts | local/archive, deployed startup identity | PASS | DB только ro+immutable, hash verification before reads |
| G3 | Frozen Qwen3.5 9B Q4_K_M + embedding/options, local loopback, no proxy/redirect/cloud/retry | local.py, OFF81, live metrics | PASS | Никаких provider failovers |
| G4 | Day29/index/history/tests не изменены; нет нового framework/FSM/весов/VPS/public exposure | bounded diff, runtime imports, launchd configuration | PASS | В пределах обозримой Day30 работы |
| A1.a | Отдельный process Day30, API question+optional conversation, IDs/status/answer/error | server/service, OFF81, LAN | PASS | Actual live ответ и конкретный error наблюдались |
| A1.b | UI new conversation/follow-up/original details | app.js, UI | PASS | UI mock; semantic follow-up отдельно A8.b |
| A1.c | question1–500, body≤64KiB, invalid before inference | OFF81, handler checks | PASS | Negative HTTP contracts |
| A2.a | Fresh retrieval весь private snapshot; assignment scope отделён | catalogs/retrieve, OFF81, PRIVATE | PASS | Не означает поиск всегда семантически полон |
| A2.b | Два sequential calls same Qwen think=false, selection IDs→originals→synthesis; embedding separately | local/service, OFF81, completed live receipt | PASS | Unknown/error разрешено закончить раньше |
| A2.c | No hidden retry/critic; invalid/empty stops | exhaustive calls in CODE, OFF81 | PASS | Фактический error не повторён автоматически |
| A3.a | Source-grounded пересказ/вывод, uncertainty, no unsupported attribution/action/result | PRIVATE05 rejected response only | NOT PROVEN | API не доставил answer; нельзя выдать отклонённый candidate за финальный ответ |
| A3.b | JSON/done/refs validation; shown immutable original metadata; no automatic semantic PASS | parse_response/validators/source_units, OFF81, DB comparison | PASS | Не переносить этот PASS на A3.a |
| A3.c | Unknown disclosed, no free out-of-corpus answer; recommendation labelled Вывод | validators/prompts, OFF81 | PASS | Гарантия кода о формате; реальная смысловая поддержка A3.a |
| A4.a | Separate full prompt/schema/template512/output1024 ≤8192 before both calls,temperature0 | fit_prompt/check_budget, OFF81, private budgets | PASS | BPE или явная conservative byte fallback |
| A4.b | ≤3 user history questions, no assistant factual evidence; oldest history then complete low-ranked units, current question intact | resolve_query/fit_prompt, OFF81 | PASS | Focus исправлен и проверен ранее; история не является factual evidence |
| A4.c | Synthesis receives only final retained originals/refs | rebuilt schema/coverage, OFF81 | PASS | Final selected IDs constrained |
| A5.a | One chain, shared existing flock, busy409/no queue, release on errors | generation_lock/Application, OFF81 | PASS | Mock error release; real model quality отдельно |
| A5.b | Sliding credential6/60s,429+Retry-After before inference | OFF81, accepted deque | PASS | Process-local rate state, documented reset at restart |
| A5.c | ≤300s total provider call, no infinite wait/retry | DeadlineSocket/Connection + reviewer regression12 | PASS | Полный deadline, FD closed/peerEOF; live compute-stop latency не измерялась |
| A6.a | TLS explicit private LAN IPv4/free port, no public bind/tunnel; SAN actual IP+localhost,key0600 | LAN, server bind check, file modes | PASS | Другой физический device не тестировался |
| A6.b | API/private bearer, constant compare; env0600/gitignored; UI token memory only | guards/load_env/UI, OFF81, file modes+gitignore | PASS | Credential values не читались в public audit |
| A6.c | Host/Origin allowlist, absent Origin CLI allowed, foreign forbidden,no wildcard CORS | OFF81+LAN | PASS | Real auth401/Host403/Origin403 |
| A6.d | Static contains no private data; safe textContent/no remote scripts | static CODE+UI hostile-text test | PASS | Public publication scan ещё Z2/A10.c |
| A7.a | Own private dir0700/files0600, atomic store, namespaces/new conversations isolated | save_private/Store, OFF81,file modes | PASS | Private failure trace сохранён; public trace исключён |
| A7.b | Restart preserves completed conversations; unfinished interrupted, no regeneration | OFF81+RESTART05+before hash comparison | PASS | Прежние 10 state files сохранились; interrupted проверен mock store, replay не выполнялся |
| A7.c | Sanitized ID/status/duration/counters logs; private full evidence | code/log inspection, OFF81 | PASS | Raw failure trace сохранён только private; public error sanitization проверена |
| A7.d | Own launchd supervision/start/stop, old apps untouched | deploy CODE, REV11,RESTART05 | PASS | Actual new PIDs 21564/21649 после stop/bootstrap, CA-verified state |
| A8.a | Offline auth/Host/Origin/body/JSON/rate/busy/both budgets/invalid model/timeout/unlock/history/demo | OFF81+reviewer protocol13; previous targeted regressions retained | PASS | Quiet CLT3.9.6; mock inference отдельно от live |
| A8.b | ≥3 successive real content responses incl private discussion+follow-up | PRIVATE05 receipts+trace | FAIL | Первый запрос отклонён за invalid_point_anchor;0 delivered content responses; ещё 2 не запускались |
| A8.c | Recovery after controlled restart | RESTART05+PRIVATE05 | PASS | CA-verified new process accepts new requests, old 10 state files preserved |
| A8.d | Independent semantic reading checks completeness/author/date/numbers/plan-v-result | PRIVATE audit | PASS | Originals+raw candidate независимо проверены; no delivered answer, A3 NOT PROVEN |
| A9.a | Actual HTTPS LAN CA verification,no -k,auth/errors through API | LAN | PASS | One physical host only, exactly specified limitation |
| A9.b | README exact CA client command and supervision state | README commands+deployment report | PASS | Final state still needs root readback before delivery |
| A10.a | Explicit server assignment scope before retrieval/prompt,separate history,only assignment originals | CODE+OFF81+LAN demo scope | PASS | Server-side boundary, not UI-only selector |
| A10.b | Live silent MP4 ≥2 questions/input/wait/answer/conclusion/opened original, no token/private/staging | video runner only | NOT PROVEN | Need actual MP4/rendered frames/fresh receipts/ffprobe |
| A10.c | Public code/reports contain no private text/raw traces/keys | current bounded code review/gitignore | NOT PROVEN | Final publication inventory/content scan required |
| Z1 | Luna independent review→fixes→mandatory fresh Astra, no invented human acceptance | review-luna/review-astra baseline05 | PASS | CODE approved repair05; actual runtime failure independently retained |
| Z2 | Authorized deploy+commit/push, GitHub day01–30 ordered, old days preserved | pending root | NOT PROVEN | No commit/push executed by reviewer |
| Z3 | MP4 existing Drive folder, viewer link/playback checked | pending root | NOT PROVEN | Publication evidence absent |
| Z4 | Verify Day30 header+row132, two URLs, reload/readback | pending root | NOT PROVEN | Actual external mutation/readback absent |
| Z5 | All unverified explicit pending; no substituted human acceptance/public purchase | TASKS and audit limitations | PASS | Human acceptance pending |

| R03.1 | Модель profile04 согласно явному override; two calls/think=false/API, no retry/new retrieval/case-specific answers | CODE+PRIVATE05 | PASS | Изменение модели ограничено профилем P04; протокол repair03 сохранён |
| R03.2 | Strict JSON duplicate keys any level/strict types/closed fields | strict_json/local/parse_response,protocol13,OFF81 | PASS | Repeated keys отклоняются до dict/schema, no last-value-wins |
| R03.3 | Generic Q1–Q6 splitter отделяет предложение от проверки выполнения | question_aspects,protocol13 | PASS | Grammar-based, no corpus names/topics |
| R03.4 | Selection exact evidence mapping0–8keys,unique Q arrays1–6,allowed IDs,all coverageQ,none iff no assignments | validate_selection/response_schema,protocol13+OFF81 | PASS | Model coverage не принимается за independent semantic proof |
| R03.5 | Coverage означает ответ на аспект,план не требует результата если вопрос о предложении | revised prompts and protocol | NOT PROVEN | Structural rules выполнены; качество этой инструкции в live не доказано |
| R03.6 | Points0–4,exact fields,aspect IDs,one passed proof ID selected for every Q,anchor1–160 exact,text1–300 | materialize_synthesis,protocol13,independent stored replay | PASS |Два retained original spans/metadata совпали; один anchor exact, другой правильно отвергнут; logical support не следует автоматически |
| R03.7 | C∪M=A;none missing/not covered;partial must missing;full may downgrade | validator,protocol13,PRIVATE05 | PASS | В live05 дополнительно выявлено missing=[] при обоих partial; первым сработал invalid_point_anchor, правило missing неизменно |
| R03.8 | Conclusion exactfields1–1000,Вывод label,uniqueexistingP refs≥1forpoints,unknown exactempty contract | materialize_synthesis,protocol13 | PASS | Смысл заключения отдельно A3 |
| R03.9 | Summary pointtexts in order + deterministic missing disclaimer≤1800,no truncation;conclusion unchanged;refsunique/sourceimmutable | renderer,protocol13 | PASS | No semantic correction or silent dedupe |
| R03.10 | Public API no points/anchor,old shape/status;unknown nofreefacts;emptyselection/prunedproof stopsbeforesecondcall | CODE+OFF81 | PASS | Private trace остаётся единственным местом structured raw |
| R03.11 | Oldreceipts no migration,newtrace protocol_versionrepair03/rawerrors | Store/trace,reviewer3copiedoldfilecheck,PRIVATE05 | PASS |Три legacy receipts проверены отдельно; actual restart05 сохранил 10 старых файлов |
| R03.12 | Budgets8192/output1024/template512;pruning rebuilds allowed/mapping/schema,downgradescoverage,no background proof | protocol13+OFF81+PRIVATE05budgets | PASS | Live05 pruning удалил один выбранный proof; coverage обоих аспектов понижено full→partial, schema перестроена |
| R03.13 | Strict validation codes safely retained private;coarse invalid_model_response public | SAFE_VALIDATION_CODES/Application,OFF81+PRIVATE05 | PASS | Actual mismatch has private code+raw; no corpus inpublicaggregate |
| R03.14 | Gate≤3additional private requests,knownpair+independenttransfer,all3runtime+semanticPASS | live-private-05.json | FAIL |1runtimeFAIL; остальные2не исполнены,3PASSне достигнуты |
| R03.15 | При FAIL остановить dependent publicdry/record/publication,no automatic additionalretry | gate stop record/current artifacts | PASS | Исполнен1request; publicdry/recordне запускались |

| P04.1 | Runtime change только MODEL/digest; protocol/prompts/retrieval/index/embedding/questions/options неизменны | 28 hashes, inverse replacement local.py, profile tests | PASS | Обратная замена двух констант даёт точный hash local.py baseline03; badge/docs/tests разрешены |
| P04.2 | Установленная 9B Q4_K_M, frozen digest, requires0.30.0 при Ollama0.33.3 | Independent read-only tags/show/version, model-profile-04.json | PASS | Новые веса не загружались; прежний Day26 run не выдан за новый semantic PASS |
| P04.3 | Qwen2Tokenizer отвергает pre=qwen35; явный существующий ByteBound fallback | metadata: все 256 byte symbols, profile tests, live trace | PASS | Conservative UTF-8 bound не выдан за BPE |
| P04.4 | Два text-only system/user сообщения; template512, full prompt/schema/output≤8192 до вызова; observed budget после | Official qwen35 renderer, budget code/tests, PRIVATE05 | PASS | Input upper bounds 6158/6522 + output1024; actual prompt_eval_count 1082 в обоих вызовах |
| P04.5 | Унаследованные presence_penalty1.5/top_p0.95/top_k20 явно документированы, без отдельного override | show metadata, README, request payload | PASS | Это иной deployment profile; чистый model-only benchmark не заявляется |
| P04.6 | Перед переходом idle, lock свободен; старый генератор отсутствует в RAM, Ollama/прочие процессы не перезапущены | ps[] before switch, root lifecycle evidence | PASS | Старая модель уже auto-expired; отдельный operator unload не выполнялся и не заявляется |
| P04.7 | Максимум три запроса: прежний known pair и transfer, без retry; нужны три runtime+semantic PASS | live-private-05.json | FAIL | Первый запрос runtime FAIL за 200.086s, два остальных не запускались |
| P04.8 | После FAIL остановлены public dry/record/publication; критерии и validator не ослаблены; прежние failures сохранены | Current stop evidence, review-history, private archives | PASS | Никакого разрешения следующего route этим аудитом не дано |

| R05.1 | Только provider body сохраняет insertion order; canonical state/hash/prompt body прежние | Inverse hash proof local/service, targeted5 | PASS | Значения schemas/prompts/options/model/validators не менялись |
| R05.2 | Wire orders selection evidence→coverage; synthesis points→missing→conclusion; point aspects→proof→anchor→text; conclusion text→refs | Actual Ollama.request fixture + PRIVATE05 raw + trace arrays | PASS | Все четыре порядка наблюдены в real output; native-chat маршрут вне гарантии |
| R05.3 | Dynamic evidence IDs сохраняют существующий порядок и состав | Wire regression, unchanged schema builders | PASS | Внешние request keys не отдельное требование |
| R05.4 | Private order arrays происходят из final sent schemas, отсутствуют для неотправленной стадии, не раскрываются public | Targeted5 + 4 synthetic failure checks + public_receipt | PASS | Canonical object order сам по себе не выдан за wire evidence |
| R05.5 | Payload semantic equality и UTF-8 length invariant; budgets/observed gate прежние; AICODE-NOTE объясняет отличие | Wire capture tests, inverse hash, PRIVATE05 budgets | PASS | Input6158/6522+output1024; observed1082 each |
| R05.6 | Не более трёх прежних private questions без retry, все runtime+semantic PASS | live-private-05.json | FAIL | Один runtime FAIL, два не выполнены, delivered answer отсутствует |
| R05.7 | После FAIL stop dependent public; raw order отдельно от semantic quality; старые FAIL сохранены | Run stop, review-history, private audit | PASS | Correct order не выдан за semantic PASS; будущий06 не одобрен |

## Условные и ненормативные положения

Второе физическое устройство недоступно по A9: optional check остаётся NOT PROVEN как ограничение среды, а не новый блокирующий requirement. Целевой стиль «обычно2–4 /1–2» не заменяет обязательную смысловую поддержку. Новые веса, VPS, публичный порт, новый framework/FSM и Day29 benchmark вне scope. Header внешней таблицы проверяет root перед разрешённой сдачей; reviewer его не проверял.

## Неуспехи и недостающие доказательства

Текущие FAIL: A8.b, R03.14, P04.7 и R05.6 — gate05 не получил три успешных ответа. Первый запрос завершился invalid_point_anchor. Дополнительно missing_aspect_ids=[] противоречит обоим partial после budget pruning; validator остановился на более ранней ошибке anchor. CODE APPROVED сохраняется: отказ соответствует действующему контракту.

A3.a/R03.5 NOT PROVEN: summary/conclusion не доставлены. Raw semantic замечания сохранены только private. Прежние semantic FAIL01/02, runtime FAIL03/04 остаются в архивах. Исправление provider order наблюдено в actual05; преимущество качества не доказано.

Видео, финальная privacy scan и external delivery NOT PROVEN. Будущий protocol06 требует собственного SPEC/baseline/review/live evidence; этот отчёт не разрешает изменение критериев и не перерабатывает старый candidate в PASS.
