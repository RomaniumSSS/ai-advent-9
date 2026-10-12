# Day30 — independent implementation validation, baseline03

**Вердикт: SPEC NOT SATISFIED.** Protocol03 CODE APPROVED; первый live запрос gate03 — runtime FAIL, остальные2не выполнены. Доставленный summary/conclusion отсутствует: текущая семантика NOT PROVEN. Публикация/видео не готовы; человеческая приёмка pending.

## Baseline и evidence

SPEC repair03 SHA `3f8705b9cef56b8fd08e0f22515ef95fa266c1c35326f991b73121be9dc38834`, implementation `results/code-baseline-03.json` (26files,baseb3e607e). Reviewer независимо сверил26hashes до заключения и ещё раз после чтения live trace:mismatches0. Рабочий контракт основан на пользовательском результате/HANDOFF; отдельное утверждение SPEC человеком не заявляется.

CODE — самостоятельное чтение fullSPEC/PLAN и runtime/protocol/UI/security/deploy; OFF81 — `protocol03-regression.log`,81PASS17.602s quiet CLTPython3.9.6, mock inference. Reviewer `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_protocol03 test_selection03 -v`:13PASS0.026s,exit0,no commonflock/provider. Previous TCP/providerdeadline/lifecycle corrections также независимо проверены (REV11 и regression12); RED/historicalfailures сохранены. UI — прежний mock browser evidence; UI files неизменны. LAN — realCAverified auth/Host/Origin/API checks; RESTART03 — `restart-03.json`,actualnewPIDs+6oldstatehashes/noautoreplay. PRIVATE03 — `live-private-03.json`,privateAPI/internalreceipt и независимое read-onlyDB чтение4originalspans+metadata. Reviewer offline replay сохранённого synthesis дал туже `invalid_missing_aspects` без modelcall.

Failure model: mock/structural/schema/anchorPASS не доказывает смысл; ошибка API не является successful answer; raw candidate не является показанным ответом; samehostLAN не доказывает seconddevice; старые receipts не должны мигрировать или переписываться; codevideo не доказывает actualrecord; finalpublication требует отдельной privacy/readback evidence. Historical01/02FAIL не отменяются новойверсией. Новая гипотезаprofile04 даннымbaselineне покрыта.

## Нормативный инвентарь полного SPEC

Каждая строка объединяет только связанные наблюдаемые требования; A1–A10 сохранены как исходные IDs. Строки G и Z покрывают нормативные границы и раздел «Завершение» вне таблицы SPEC.

| SPEC item | Наблюдаемый контракт | Evidence | Статус | Граница доказательства |
|---|---|---|---|---|
| G1 | Самостоятельный Day30, API+чат, M2/16GiB, runtime imports только своего дня | CODE, LAN, environment report | PASS | Не доказательство качества ответов |
| G2 | Read-only frozen generation/DB724chunks663docs и source counts | local/archive, deployed startup identity | PASS | DB только ro+immutable, hash verification before reads |
| G3 | Frozen Qwen8B Q4+embedding/options, local loopback, no proxy/redirect/cloud/retry | local.py, OFF81, live metrics | PASS | Никаких provider failovers |
| G4 | Day29/index/history/tests не изменены; нет нового framework/FSM/весов/VPS/public exposure | bounded diff, runtime imports, launchd configuration | PASS | В пределах обозримой Day30 работы |
| A1.a | Отдельный process Day30, API question+optional conversation, IDs/status/answer/error | server/service, OFF81, LAN | PASS | Actual live ответ и конкретный error наблюдались |
| A1.b | UI new conversation/follow-up/original details | app.js, UI | PASS | UI mock; semantic follow-up отдельно A8.b |
| A1.c | question1–500, body≤64KiB, invalid before inference | OFF81, handler checks | PASS | Negative HTTP contracts |
| A2.a | Fresh retrieval весь private snapshot; assignment scope отделён | catalogs/retrieve, OFF81, PRIVATE | PASS | Не означает поиск всегда семантически полон |
| A2.b | Два sequential calls same Qwen think=false, selection IDs→originals→synthesis; embedding separately | local/service, OFF81, completed live receipt | PASS | Unknown/error разрешено закончить раньше |
| A2.c | No hidden retry/critic; invalid/empty stops | exhaustive calls in CODE, OFF81 | PASS | Фактический error не повторён автоматически |
| A3.a | Source-grounded пересказ/вывод, uncertainty, no unsupported attribution/action/result | PRIVATE03 rejected response only | NOT PROVEN | API не доставил answer; нельзя выдать отклонённый candidate за финальный ответ |
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
| A7.b | Restart preserves completed conversations; unfinished interrupted, no regeneration | OFF81+RESTART03+before hash comparison | PASS | Прежние6statefiles сохранились; interrupted проверен mock store, replay не выполнялся |
| A7.c | Sanitized ID/status/duration/counters logs; private full evidence | code/log inspection, OFF81 | PASS | Raw failure trace сохранён только private; public error sanitization проверена |
| A7.d | Own launchd supervision/start/stop, old apps untouched | deploy CODE, REV11,RESTART03 | PASS | Actual new PIDs85423/85513 после stop/bootstrap, CA-verified state |
| A8.a | Offline auth/Host/Origin/body/JSON/rate/busy/both budgets/invalid model/timeout/unlock/history/demo | OFF81+reviewer protocol13; previous targeted regressions retained | PASS | Quiet CLT3.9.6; mock inference отдельно от live |
| A8.b | ≥3 successive real content responses incl private discussion+follow-up | PRIVATE03 receipts+trace | FAIL | Первый запрос отклонён за invalid_missing_aspects;0delivered content responses, ещё2не запускались |
| A8.c | Recovery after controlled restart | RESTART03+PRIVATE03 | PASS | CA-verified new process accepts new requests, old6statefiles preserved |
| A8.d | Independent semantic reading checks completeness/author/date/numbers/plan-v-result | PRIVATE audit | PASS | Originals+raw candidate независимо проверены; no delivered answer, A3 NOT PROVEN |
| A9.a | Actual HTTPS LAN CA verification,no -k,auth/errors through API | LAN | PASS | One physical host only, exactly specified limitation |
| A9.b | README exact CA client command and supervision state | README commands+deployment report | PASS | Final state still needs root readback before delivery |
| A10.a | Explicit server assignment scope before retrieval/prompt,separate history,only assignment originals | CODE+OFF81+LAN demo scope | PASS | Server-side boundary, not UI-only selector |
| A10.b | Live silent MP4 ≥2 questions/input/wait/answer/conclusion/opened original, no token/private/staging | video runner only | NOT PROVEN | Need actual MP4/rendered frames/fresh receipts/ffprobe |
| A10.c | Public code/reports contain no private text/raw traces/keys | current bounded code review/gitignore | NOT PROVEN | Final publication inventory/content scan required |
| Z1 | Luna independent review→fixes→mandatory fresh Astra, no invented human acceptance | review-luna/review-astra baseline03 | PASS | CODE approved protocol03; actual runtime failure independently retained |
| Z2 | Authorized deploy+commit/push, GitHub day01–30 ordered, old days preserved | pending root | NOT PROVEN | No commit/push executed by reviewer |
| Z3 | MP4 existing Drive folder, viewer link/playback checked | pending root | NOT PROVEN | Publication evidence absent |
| Z4 | Verify Day30 header+row132, two URLs, reload/readback | pending root | NOT PROVEN | Actual external mutation/readback absent |
| Z5 | All unverified explicit pending; no substituted human acceptance/public purchase | TASKS and audit limitations | PASS | Human acceptance pending |

| R03.1 | Та же8B/two calls/think=false/API, no retry/new retrieval/case-specific answers | CODE+PRIVATE03 | PASS | Новая model-profile гипотеза не входит в этот baseline |
| R03.2 | Strict JSON duplicate keys any level/strict types/closed fields | strict_json/local/parse_response,protocol13,OFF81 | PASS | Repeated keys отклоняются до dict/schema, no last-value-wins |
| R03.3 | Generic Q1–Q6 splitter отделяет предложение от проверки выполнения | question_aspects,protocol13 | PASS | Grammar-based, no corpus names/topics |
| R03.4 | Selection exact evidence mapping0–8keys,unique Q arrays1–6,allowed IDs,all coverageQ,none iff no assignments | validate_selection/response_schema,protocol13+OFF81 | PASS | Model coverage не принимается за independent semantic proof |
| R03.5 | Coverage означает ответ на аспект,план не требует результата если вопрос о предложении | revised prompts and protocol | NOT PROVEN | Structural rules выполнены; качество этой инструкции в live не доказано |
| R03.6 | Points0–4,exact fields,aspect IDs,one passed proof ID selected for every Q,anchor1–160 exact,text1–300 | materialize_synthesis,protocol13,independent stored replay | PASS |4selectedoriginalspans+metadata exact,89charanchor exact; logical support не следует автоматически |
| R03.7 | C∪M=A;none missing/not covered;partial must missing;full may downgrade | validator,protocol13,PRIVATE03 | PASS | Реальное нарушение моделью правильно отвергнуто invalid_missing_aspects |
| R03.8 | Conclusion exactfields1–1000,Вывод label,uniqueexistingP refs≥1forpoints,unknown exactempty contract | materialize_synthesis,protocol13 | PASS | Смысл заключения отдельно A3 |
| R03.9 | Summary pointtexts in order + deterministic missing disclaimer≤1800,no truncation;conclusion unchanged;refsunique/sourceimmutable | renderer,protocol13 | PASS | No semantic correction or silent dedupe |
| R03.10 | Public API no points/anchor,old shape/status;unknown nofreefacts;emptyselection/prunedproof stopsbeforesecondcall | CODE+OFF81 | PASS | Private trace остаётся единственным местом structured raw |
| R03.11 | Oldreceipts no migration,newtrace protocol_versionrepair03/rawerrors | Store/trace,reviewer3copiedoldfilecheck,PRIVATE03 | PASS |3oldfilesunchanged; actualrestart6oldfilespreserved |
| R03.12 | Budgets8192/output1024/template512;pruning rebuilds allowed/mapping/schema,downgradescoverage,no background proof | protocol13+OFF81+PRIVATE03budgets | PASS | Реальный firstgate не потребовал pruning; tests покрывают multi-iteration |
| R03.13 | Strict validation codes safely retained private;coarse invalid_model_response public | SAFE_VALIDATION_CODES/Application,OFF81+PRIVATE03 | PASS | Actual mismatch has private code+raw; no corpus inpublicaggregate |
| R03.14 | Gate≤3additional private requests,knownpair+independenttransfer,all3runtime+semanticPASS | live-private-03.json | FAIL |1runtimeFAIL; остальные2не исполнены,3PASSне достигнуты |
| R03.15 | При FAIL остановить dependent publicdry/record/publication,no automatic additionalretry | gate stop record/current artifacts | PASS | Исполнен1request; publicdry/recordне запускались |

## Условные и ненормативные положения

Второе физическое устройство явно недоступно по A9; это исключённый optional check, **NOT PROVEN** как ограничение среды, не новый блокирующий requirement. «Обычно2–4»/«1–2» — целевой стиль, не самостоятельный абсолютный счётчик; поддержка смысла обязательна A3.a. Альтернативный VPS, новый framework/FSM, новые веса, публичный порт, Day29 benchmark вне scope; их не выполнять. Идентификатор AE132 ожидаемый: актуальный header должен подтвердить root до записи, сам reviewer его не проверял.

## Неуспехи и недостающие доказательства

Текущие FAIL: A8.b/R03.14 — первый запрос gate03 завершился runtime error, поэтому3успешных ответа не получены. A3.a/R03.5 NOT PROVEN: API не доставил ответ, semanticPASS отсутствует. Это не переклассификация старыхFAIL: baseline01/02 semanticFAIL остаются в history, а protocol03 — новая модельная структура и новый run. Кодовая защита R03.7PASS именно потому, что ошибочный candidate был отвергнут.

NOT PROVEN: actual delivered semantics, видео/финальная privacy scan и externaldelivery. CODE APPROVED,actualrestart иofflinePASS не закрывают эти строки. Будущийprofile04 — отдельныйbaseline; данный аудит не подтверждает его качество и не разрешает обход/ослабление validator.

Нормативный источник этого исторического baseline03 сохранён в `results/review-history/SPEC-protocol03.md`; последующая редакция текущего SPEC/profile04 этим заключением не покрыта. Проверка raw candidate выполнялась через materialize_synthesis с сохранёнными aspects/coverage, без проверки старого ответа будущей model-константой.
