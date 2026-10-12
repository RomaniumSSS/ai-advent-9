# Day30 — independent implementation validation, actual profile09

**SPEC NOT SATISFIED (FAIL). CODE NEEDS CHANGES: inherited pruning P2 discovered after the initial09 approval.** Profile09 deadline/output delta remains implemented as specified; the earlier APPROVED checkpoint is historical evidence, not overwritten acceptance of this new defect. Actual09 runtime FAIL; delivered semantic NOT PROVEN (answer=null). Earlier failures01–08 remain unchanged.

Baseline results/code-baseline-09.json,36 hashes independently matched before and after live; manifest SHA87a0569728fb18387a9f652024fbc260f42be0c55838a0199626f9f095cd0640. Frozen SPEC-profile09.md SHAeb436f10d1131d299ef303d71970c3a50ed4e68e3b189a741fd5c5802a4ac004. No separate human SPEC approval claimed.

Evidence: REV09 independent8 PASS3.090s +19 PASS4.773s CLT3.9.6, fake/ephemeral loopback/mock lock and launchd. OFF09 Sol7+1 targeted/107 linked PASS, separate runs. OFF122/OFF102/REV28/LEGACY12 are archived checks of unchanged paths, not fresh09 suites. LIVE09 results/live-private-09.json and actual API/private state; SEM09 private/semantic-review-09.md. RESTART09 real controlled main/demo, CA verified,19 old files unchanged/no replay, prior to smoke. Prior LAN auth/Host/Origin and provider INFO logging preflight reused explicitly. Reviewer ran no inference/restarts and read no hidden reasoning/provider log bodies.

## Complete normative inventory

Related obligations grouped; protocol06/profile08/profile09 overrides applied. PASS code/offline or source-level does not claim delivered semantic success.

| ID | Current contract | Evidence | Verdict | Limit |
|---|---|---|---|---|
| G1 | Самостоятельный Day30; private домашний сервис, без изменений Day29/runtime/imports/index/history | CODE, hashes, deployment | PASS | Другие дни не исполнялись reviewer |
| G2 | Frozen read-only DB724 chunks/663 docs и index/embedding identity | CODE, actual DB SHA, startup identity | PASS | Read-only immutable originals |
| G3 | Frozen installed Qwen3.5 9B Q4_K_M/digest, локальный Ollama, profile04 options | CODE, prior read-only metadata, LIVE09 | PASS | Требуемая version совместимость проверена; новые веса не загружались |
| G4 | Нет cloud/proxy/redirect/new framework/FSM/public exposure/покупок | CODE, OFF102, deploy config | PASS | Никакого provider fallback |
| A1.a | Отдельный процесс, question/optional conversation, request IDs/status/answer/error | server/service, OFF122, LIVE09 | PASS | API invalid_model_response, answer=null |
| A1.b | UI new conversation/follow-up/original disclosure; input1–500/body64KiB/negative pre-inference | CODE, OFF102, прежний browser fixture | PASS | Actual video UI walkthrough ещё отсутствует |
| A2.a | Fresh retrieval всего private corpus, assignment-only filter до retrieval | CODE, OFF102, LIVE09 fresh embedding/query | PASS | Retrieval не обещает смысловую полноту |
| A2.b | Два последовательных same-model calls: selection thinkfalse/native, synthesis thinktrue/prompt_schema, embedding отдельно | CODE, OFF122, LIVE09 | PASS | 2 attempted/2 completed chat; no retry/critic |
| A2.c | Empty/unknown/clarification/error могут остановиться раньше, без free answer | CODE, negatives | PASS | Структурные unknown контракты |
| A3.a | Верный пересказ: subject/object, конкретика, числа, авторы, неопределённость, план/результат | SEM09 no delivered answer | NOT PROVEN | Answer=null; прежние semantic failures остаются в archives |
| A3.b | Вывод поддержан points, рекомендации обозначены, нет выдуманной причинности/результата | SEM09 no delivered answer | NOT PROVEN | Synthesis final не получен |
| A3.c | Original metadata/provenance из immutable evidence, IDs не semantic proof | CODE, OFF122, prior DB audits | PASS | Новых delivered source cards09 нет, actual semantic proof не заявлен |
| A3.d | Краткий summary/conclusion, unknown без свободных фактов | Renderer/limits, OFF102 | PASS | «Обычно2–4» — целевой стиль; содержательные ошибки отдельно FAIL |
| A4.a | Actual prompt/schema+template512+stage output≤8192, observed gate | CODE/REV09/LIVE09 budgets | PASS | Selection6884+1024; synthesis6240+1408; observed976/1093 |
| A4.b | ≤3 user topic questions, no assistant prose evidence; question intact | CODE, prior REV28, OFF122 | PASS | Follow-up09 не запускался |
| A4.c | History-first whole-unit pruning; rebuild IDs/coverage/schema after EACH removal | CODE + actual09 offline reconstruction | FAIL | Final state consistent, but stale intermediate schema removes an extra unit |
| A5.a | Одна chain; shared existing flock, concurrent409/no queue, lock release | OFF102, prior real lock check | PASS | Reviewer не повторял live contention |
| A5.b | Credential sliding6/60,429+Retry-After до inference | CODE, OFF102 | PASS | Process-local reset при restart документирован |
| A5.c | Absolute provider deadlines selection/embed300, synthesis600, close before unlock/no retry | REV09 transport/Application tests + LIVE09 parameters | PASS | Synthesis completed455.070s; actual compute-stop latency unknown |
| A6.a | Explicit LAN IPv4/TLS/freeports, SAN IP/localhost, CA verified, no public bind/tunnel | LAN, RESTART09 | PASS | Только тот же физический Mac |
| A6.b | Bearer/constant compare; env/key0600 gitignored; token only UI memory | CODE, modes, OFF102 | PASS | Секреты не выведены в reports |
| A6.c | Host/Origin allowlist, CLI absent Origin allowed, no wildcard CORS | LAN, OFF102 | PASS | Actual negative checks раньше, guards неизменны |
| A6.d | Static no private source, safe text rendering/no external scripts | CODE, browser fixtures | PASS | Финальная publication scan отдельно |
| A7.a | Day30 dir0700/files0600, atomic own state, scope/new-conversation isolation | CODE, OFF102, file modes | PASS | Private traces отделены от public receipt |
| A7.b | Restart preserves old receipts, unfinished interrupted, no autoreplay/migration | LEGACY12, OFF122, RESTART09 | PASS | 19 actual old state hashes preserved; unfinished path mock |
| A7.c | Logs sanitized; full prompt/raw/source evidence only private | CODE, diagnostics tests, actual file boundaries | PASS | Public reports содержат категории ошибок без private case facts |
| A7.d | Separate launchd start/stop/supervision, old apps untouched | deploy review/tests, RESTART09 | PASS | Bounded job/PID lifecycle ранее исправлен |
| A8.a | Offline auth/input/rate/busy/budgets/output/timeout/unlock/history/demo/privacy | OFF09 linked107 + REV09 8/19 + previous OFF122 security | PASS | Tests PASS; newly found pruning coverage gap is A4.c FAIL |
| A8.b | ≥3 consecutive real content requests incl discussion/follow-up | LIVE09 | FAIL | Первый runtime FAIL,0 delivered answers,2 оставшихся не запускались |
| A8.c | Recovery after current completed smoke | RESTART09 до live; quality gate failed | NOT PROVEN | Новый post-smoke restart не выполнялся |
| A8.d | Independent semantic reading delivered summary/conclusion by originals | SEM09: answer absent | NOT PROVEN | Runtime/privacy audit выполнен, смыслового материала нет |
| A9.a | Real CA-verified HTTPS на LAN IP без -k; API/errors verified | LAN, RESTART09, LIVE09 | PASS | Second physical device optional NOT PROVEN, не новый blocker |
| A9.b | README точные CA commands/supervision и ограничения | CODE/docs | PASS | Финальный delivery readback pending |
| A10.a | Assignment server scope до catalog/retrieval/prompts, separate history/originals | CODE, OFF102, RESTART09 demo scope | PASS | Private inference не использовался как public demo |
| A10.b | Silent MP4≥2 real questions/input/wait/answer/conclusion/source, no staging/token/private | Actual video отсутствует | NOT PROVEN | Runner code не считается записью |
| A10.c | Final public inventory/content privacy scan | Pending publication | NOT PROVEN | Текущий review сохраняет private границу; полной финальной сдачи нет |
| R03.1 | Strict JSON duplicate keys/NaN/types/closed fields; selection keyed mapping≤8,uniqueQ≤6,exact coverage | CODE, REV28, OFF102 | PASS | Selection protocol сохранён |
| R03.2 | Aspects separate proposal/result; coverage none iff no proof | CODE/OFF122; prior actual06 | PASS | Current09 synthesis semantic judgement не наблюдалось |
| P04.1 | Qwen35 metadata отвергается Qwen2Tokenizer; existing ByteBound явно отмечен | Metadata/tests/LIVE09 | PASS | Не маскируется под BPE |
| P04.2 | Text-only system/user template512; inherited defaults документированы | Official renderer review, README, payload | PASS | Разные projection/pruning не чистый model benchmark |
| P04.3 | При переходе старый генератор отсутствует в RAM; no weight/global/Ollama changes | Prior ps[] and lifecycle | PASS | Auto-expiration, отдельный unload не заявляется |
| R05.1 | Ordered provider serialization; canonical packing unchanged | CODE, wire fixture | PASS | Synthesis schema now prompt instruction, not enforced native grammar |
| R05.2 | Private sent schema order arrays, no phantom stage, no public trace | OFF122, known-sent headers error metadata | PASS | Arrays describe schema; raw synthesis order не получен |
| P06.1 | Selection projection exact7fields, synthesis+role, full text once, stage-local context IDs, original metadata unchanged | CODE, REV28, actual prompts | PASS | Nullable attribution не восстанавливается моделью |
| P06.2 | Points exact aspects/evidence_id/text,0–4,1–300; retained proof для каждого аспекта; no model anchors/offsets | CODE, negatives, LIVE09 | PASS | Допустимый ID не гарантирует, что его text поддерживает все claims |
| P06.3 | Private exact quote/span from unit and immutable source cards | CODE/OFF122/prior DB audits | PASS | Synthesis09 не вернул points, actual09 spans не вычислялись |
| P06.4 | Doubtful всегда array, unique0–6 только full; empty full-set maxItems0/no empty enum | CODE, negatives, actual empty arrays | PASS | Unknown/partial/none doubtful отвергаются |
| P06.5 | M=partial/none∪unrepresented∪doubtful; fixed empty unknown | CODE/OFF122 | PASS | Actual09 final отсутствует, M не материализован |
| P06.6 | Conclusion label/P refs, bounded strings, exact unknown, no repair/truncation | CODE/strict negatives | PASS | Actual meaning09 NOT PROVEN |
| P06.7 | Schema/property order and rebuild after each pruning removal | REV09 order; actual09 reconstruction | FAIL | Final suffix/order correct, intermediate rebuild delayed |
| P06.8 | Protocol06 trace/full units/projections/provenance/derived M, legacy preserved | CODE/OFF122/RESTART09 | PASS | Final-derived fields создаются только при полученном valid final |
| P06.9 | Max3 unchanged known pair+transfer, no retry,3 runtime+3semantic PASS | LIVE09 | FAIL | 1 runtime FAIL,2 NOT RUN; semantic NP |
| P06.10 | Stop dependent public after first FAIL, preserve history | LIVE09 first-request stop | PASS | Следующий submit не выполнялся |
| Z1 | Luna review/fixes + mandatory fresh independent Astra; no substituted human acceptance | review history/current audit | PASS | CODE approval не заменяет A3/gate |
| Z2 | Authorized final GitHub commit/push, day ordering, old days preserved | Pending root delivery | NOT PROVEN | Reviewer не выполнял commit/push |
| Z3 | MP4 uploaded to existing Drive folder, viewer/playback checked | Pending | NOT PROVEN | Нет actual recording/publication |
| Z4 | Day30 header/row132 verified, two links written and reloaded | Pending | NOT PROVEN | External mutation/readback не выполнены |
| Z5 | Непроверенное явно pending; human acceptance не выдумана | Current reports | PASS | Second device NOT PROVEN как установленное ограничение |
| P07.1 | Sampling selection0, synthesis0.7/top_p0.8; same model/digest; think override08 | CODE/actual stage parameters | PASS | Only synthesis thinktrue, no extra critic |
| P07.2 | Independent options/provider/budget/observed use actualstage settings | OFF122/LIVE09 | PASS | Selection1024/300; synthesis1408/600; context8192/template512 |
| P07.3 | Known-sent parameters separate attempts; no phantom phases; private only | Actual stage parameters + REV09 pre-send failure | PASS | Two actual provider responses complete; no invented unsent stage |
| P07.4 | Protocol06/schema/provenance/M/renderer preserved; profile08 transport/prompt suffix override | CODE frozen hashes | PASS | No semantic validator weakening/retry |
| P07.5 | Current gate max3, next only after independent verdict,3/3 for public | LIVE09 | FAIL | Первый runtime FAIL;2 not run |
| P07.6 | Stop first FAIL/no retry, preserve previous failures | Root one-step run + archives | PASS | No new route approved by this review |
| P08.1 | Selection native/thinkfalse; synthesis thinktrue/format omitted, options09 override | CODE + actual wire fixture + actual stage trace | PASS | No synthesis native schema/grammar |
| P08.2 | Two system/user messages, context JSON+newline+full ordered dynamic schema | LIVE09 independently parsed suffix | PASS | Schema contents match trace, no extra message |
| P08.3 | Schema counted once in actual messages; synthesis separate schema_tokens0; output cap includes thinking+final | OFF122 + LIVE09 budgets | PASS | Synthesis1408 total cap reached; empty final, reasoning token split unknown |
| P08.4 | Omitted format avoids structured-output restart; no third completion/retry | Pinned route guard + local wire | PASS source-level | Actual internal token/completion telemetry не получена |
| P08.5 | Dedicated thinking excluded; unsafe/unknown final shapes and transport opaque before persistence | Fixed positive allowlist +14 tests +2 original P2 repeats + LIVE09 | PASS | Observed synthesis role+opaque empty-final metadata; no persisted thinking |
| P08.6 | Final/metrics/provenance retained when safe; empty/length/duplicate/schema errors fail without repair | OFF122/current negatives | PASS | Safe invalid-ref final remains exact but rejected |
| P08.7 | Provider debug/trace/request-body logging off | provider-logging-preflight.json + independent envconfig read | PASS current configuration | No raw environment/logs exposed; future config changes need recheck |
| P08.8 | Runtime completion/strict independent semantic gate within frozen limits | LIVE09/SEM09 | FAIL | Done_reason length, answer=null, semantic NOT PROVEN |
| P08.9 | Next submit after verdict, stop first FAIL, no autoretry/new weights | Root one-step control/LIVE09 | PASS | Two remaining private cases/public steps not run |
| P09.1 | Only synthesis output1408/deadline600; selection1024/300, embed/default300 | CODE/REV09 wire/LIVE09 trace | PASS | No prompts/schema/validator/model changes from08 |
| P09.2 | One monotonic physical deadline connect/headers/body; no hidden synthesis clamp300 | REV09 fragmented fixture + actual455.070s completion | PASS | Short-cap cancellation tested offline; no real600s timeout |
| P09.3 | Stage caps/options in budget/attempt/known-sent trace; transport socket closed before lock release | REV09 8/19 + LIVE09 parameters | PASS | No deadline leaked into provider options |
| P09.4 | Output reserve honest; no unnecessary loss from failure to rebuild after pruning | Exact saved-prompt reconstruction | FAIL | 6869 stale vs6738 rebuilt: extra unit removed although8146 fits |
| P09.5 | Provider sum1200/worker1210/Exit1220/poll-video1230, legacy plist unchanged automatically | CODE/REV09 temporary plist/join/poll; RESTART09 | PASS code/offline | Actual restart confirms new jobs; no full1200s lifecycle test |
| P09.6 | Previous08 privacy, strict JSON/length/empty/schema/semantic gates retained | REV09 privacy19/LIVE09 sanitized state | PASS | Length correctly rejected; hidden reasoning not substituted |
| P09.7 | Three unchanged cases, each after independent PASS, first FAIL stops others | LIVE09/SEM09 | FAIL | 0 runtime PASS;1 FAIL;2 not run; semantic NOT PROVEN |
| P09.8 | Preserve previous failures, no extra inference/retry/public before private PASS | LIVE09 one-step stop + archives | PASS | No next profile approval from this audit |

## Actual failure and separate code defect

Selection75.177s,161eval/976prompt; synthesis455.070s,1408eval/1093prompt,3.29TPS. Two attempted/two completed provider calls, total532.472s. Synthesis done_reason=length, empty final, sanitized reasoning_present boolean. Therefore runtime gate FAIL, A3 semantics NOT PROVEN. This does not establish any flaw in deadline600 or output1408 propagation. Output cap was reached, but dedicated reasoning token count/content and benefit from a future cap/profile are unknown.

Independent offline reconstruction of saved08/09 safe prompts showed identical selection prompt/schema/projection/response, but one extra proof removed09. fit_prompt retains initial schema/mapping while popping multiple units, and Engine rebuilds only on return. Candidate stale input6869+1408=8277 rejects, whereas rebuilt6738+1408=8146 fits. Actual final6240 results from the extra removal. This violates after-each-removal rebuild and makes A4.c/P06.7/P09.4 FAIL. Causality to length or semantic failure NOT PROVEN; no model rerun or candidate regrade was made. Minimum fix: one removal followed by schema/coverage/ID rebuild before next budget decision, regression for stale-overflow/rebuilt-fit and both stage loops.

Next two cases, post-success restart, actual video/final public scan/GitHub/Drive/table remain NOT PROVEN. Reviewer has not approved a future generation mode. Human acceptance pending; second physical device optional NOT PROVEN under A9. No usage/cost invented. Initial09 approval is recorded above as the prior checkpoint; archived earlier failure reports remain unchanged.
