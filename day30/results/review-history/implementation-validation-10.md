# Day30 — independent implementation validation, actual profile10

**SPEC NOT SATISFIED (FAIL). Global CODE10 APPROVED; delivered semantics NOT PROVEN.** Inherited P2 correction confirmed; actual10 first request length/empty-final runtime FAIL. No new implementation defect established. Archived09 NEEDS CHANGES and earlier runtime/semantic failures remain unchanged.

Frozen results/code-baseline-10.json,37/37 hashes matched before and after live; manifest SHA7f4e7505bbe22fab01d86d70c850527b970859bcc3e6910e8556dae1ae7265f8. Normative SPEC-profile10.md SHA67ad919b73f6e27eca49bca0ac257c6c0737862f8609f5f673263d5d67d05113. Separate human SPEC approval not claimed.

Evidence: REV10 independent25 PASS6.831s CLT3.9.6, fake/ephemeral loopback/mock lock/lifecycle, plus safe actual09/10 source reconstruction and actual fixture wire comparison. OFF10 Sol11 targeted PASS4.105s/111 linked PASS13.566s, separate runs. OFF122/OFF102/REV28/LEGACY12/REV09 denote historical checks of unchanged paths, not fresh10 suites. LIVE10 results/live-private-10.json + actual API/private state; SEM10 private/semantic-review-10.md. RESTART10 real controlled main/demo,21 old files unchanged/no replay/CA verified, before smoke. Prior actual LAN negative checks and provider INFO logging preflight reused explicitly. Reviewer performed no real inference/restart or hidden-reasoning/log-body reading.

## Complete normative inventory

Related obligations grouped with profile10 overrides. PASS code/offline/source-level does not imply successful delivered semantics. Historical failures retain their prior verdicts.

| ID | Current contract | Evidence | Verdict | Limit |
|---|---|---|---|---|
| G1 | Самостоятельный Day30; private домашний сервис, без изменений Day29/runtime/imports/index/history | CODE, hashes, deployment | PASS | Другие дни не исполнялись reviewer |
| G2 | Frozen read-only DB724 chunks/663 docs и index/embedding identity | CODE, actual DB SHA, startup identity | PASS | Read-only immutable originals |
| G3 | Frozen installed Qwen3.5 9B Q4_K_M/digest, локальный Ollama, profile04 options | CODE, prior read-only metadata, LIVE10 | PASS | Требуемая version совместимость проверена; новые веса не загружались |
| G4 | Нет cloud/proxy/redirect/new framework/FSM/public exposure/покупок | CODE, OFF102, deploy config | PASS | Никакого provider fallback |
| A1.a | Отдельный процесс, question/optional conversation, request IDs/status/answer/error | server/service, OFF122, LIVE10 | PASS | API invalid_model_response, answer=null |
| A1.b | UI new conversation/follow-up/original disclosure; input1–500/body64KiB/negative pre-inference | CODE, OFF102, прежний browser fixture | PASS | Actual video UI walkthrough ещё отсутствует |
| A2.a | Fresh retrieval всего private corpus, assignment-only filter до retrieval | CODE, OFF102, LIVE10 fresh embedding/query | PASS | Retrieval не обещает смысловую полноту |
| A2.b | Два последовательных same-model calls: selection thinkfalse/native, synthesis thinktrue/prompt_schema, embedding отдельно | CODE, OFF122, LIVE10 | PASS | 2 attempted/2 completed chat; no retry/critic |
| A2.c | Empty/unknown/clarification/error могут остановиться раньше, без free answer | CODE, negatives | PASS | Структурные unknown контракты |
| A3.a | Верный пересказ: subject/object, конкретика, числа, авторы, неопределённость, план/результат | SEM10 no delivered answer | NOT PROVEN | Answer=null; прежние semantic failures остаются в archives |
| A3.b | Вывод поддержан points, рекомендации обозначены, нет выдуманной причинности/результата | SEM10 no delivered answer | NOT PROVEN | Synthesis final не получен |
| A3.c | Original metadata/provenance из immutable evidence, IDs не semantic proof | CODE, OFF122, prior DB audits | PASS | Новых delivered source cards10 нет, actual semantic proof не заявлен |
| A3.d | Краткий summary/conclusion, unknown без свободных фактов | Renderer/limits, OFF102 | PASS | «Обычно2–4» — целевой стиль; содержательные ошибки отдельно FAIL |
| A4.a | Actual prompt/schema+template512+stage output≤8192, observed gate | CODE/REV10/LIVE10 budgets | PASS | Selection6884+1024; synthesis6240+1920; observed976/1093 |
| A4.b | ≤3 user topic questions, no assistant prose evidence; question intact | CODE, prior REV28, OFF122 | PASS | Follow-up10 не запускался |
| A4.c | History-first whole-unit pruning; rebuild IDs/coverage/schema before each budget test | CODE/REV10 both stages + actual10 reconstruction | PASS | Inherited09 P2 fixed; historical09 FAIL unchanged |
| A5.a | Одна chain; shared existing flock, concurrent409/no queue, lock release | OFF102, prior real lock check | PASS | Reviewer не повторял live contention |
| A5.b | Credential sliding6/60,429+Retry-After до inference | CODE, OFF102 | PASS | Process-local reset при restart документирован |
| A5.c | Absolute deadlines selection/embed300, synthesis900, sync close before unlock/no retry | REV10 shortened transport fixtures + LIVE10 parameters | PASS | Synthesis completed610.521s; actual compute-stop latency unknown |
| A6.a | Explicit LAN IPv4/TLS/freeports, SAN IP/localhost, CA verified, no public bind/tunnel | LAN, RESTART10 | PASS | Только тот же физический Mac |
| A6.b | Bearer/constant compare; env/key0600 gitignored; token only UI memory | CODE, modes, OFF102 | PASS | Секреты не выведены в reports |
| A6.c | Host/Origin allowlist, CLI absent Origin allowed, no wildcard CORS | LAN, OFF102 | PASS | Actual negative checks раньше, guards неизменны |
| A6.d | Static no private source, safe text rendering/no external scripts | CODE, browser fixtures | PASS | Финальная publication scan отдельно |
| A7.a | Day30 dir0700/files0600, atomic own state, scope/new-conversation isolation | CODE, OFF102, file modes | PASS | Private traces отделены от public receipt |
| A7.b | Restart preserves old receipts, unfinished interrupted, no autoreplay/migration | LEGACY12, OFF122, RESTART10 | PASS | 21 actual old state files preserved; unfinished path mock |
| A7.c | Logs sanitized; full prompt/raw/source evidence only private | CODE, diagnostics tests, actual file boundaries | PASS | Public reports содержат категории ошибок без private case facts |
| A7.d | Separate launchd start/stop/supervision, old apps untouched | deploy review/tests, RESTART10 | PASS | Bounded job/PID lifecycle ранее исправлен |
| A8.a | Offline auth/input/rate/busy/budgets/output/timeout/unlock/history/demo/privacy | OFF10 linked111 + REV10 25 + prior OFF122 security | PASS | Models fake/loopback; actual answers graded separately; P2 regate PASS |
| A8.b | ≥3 consecutive real content requests incl discussion/follow-up | LIVE10 | FAIL | Первый runtime FAIL,0 delivered answers,2 оставшихся не запускались |
| A8.c | Recovery after current completed smoke | RESTART10 до live; quality gate failed | NOT PROVEN | Новый post-smoke restart не выполнялся |
| A8.d | Independent semantic reading delivered summary/conclusion by originals | SEM10: answer absent | NOT PROVEN | Runtime/privacy audit выполнен, смыслового материала нет |
| A9.a | Real CA-verified HTTPS на LAN IP без -k; API/errors verified | LAN, RESTART10, LIVE10 | PASS | Second physical device optional NOT PROVEN, не новый blocker |
| A9.b | README точные CA commands/supervision и ограничения | CODE/docs | PASS | Финальный delivery readback pending |
| A10.a | Assignment server scope до catalog/retrieval/prompts, separate history/originals | CODE, OFF102, RESTART10 demo scope | PASS | Private inference не использовался как public demo |
| A10.b | Silent MP4≥2 real questions/input/wait/answer/conclusion/source, no staging/token/private | Actual video отсутствует | NOT PROVEN | Runner code не считается записью |
| A10.c | Final public inventory/content privacy scan | Pending publication | NOT PROVEN | Текущий review сохраняет private границу; полной финальной сдачи нет |
| R03.1 | Strict JSON duplicate keys/NaN/types/closed fields; selection keyed mapping≤8,uniqueQ≤6,exact coverage | CODE, REV28, OFF102 | PASS | Selection protocol сохранён |
| R03.2 | Aspects separate proposal/result; coverage none iff no proof | CODE/OFF122; prior actual06 | PASS | Current10 synthesis semantic judgement не наблюдалось |
| P04.1 | Qwen35 metadata отвергается Qwen2Tokenizer; existing ByteBound явно отмечен | Metadata/tests/LIVE10 | PASS | Не маскируется под BPE |
| P04.2 | Text-only system/user template512; inherited defaults документированы | Official renderer review, README, payload | PASS | Разные projection/pruning не чистый model benchmark |
| P04.3 | При переходе старый генератор отсутствует в RAM; no weight/global/Ollama changes | Prior ps[] and lifecycle | PASS | Auto-expiration, отдельный unload не заявляется |
| R05.1 | Ordered provider serialization; canonical packing unchanged | CODE, wire fixture | PASS | Synthesis schema now prompt instruction, not enforced native grammar |
| R05.2 | Private sent schema order arrays, no phantom stage, no public trace | OFF122, known-sent headers error metadata | PASS | Arrays describe schema; raw synthesis order не получен |
| P06.1 | Selection projection exact7fields, synthesis+role, full text once, stage-local context IDs, original metadata unchanged | CODE, REV28, actual prompts | PASS | Nullable attribution не восстанавливается моделью |
| P06.2 | Points exact aspects/evidence_id/text,0–4,1–300; retained proof для каждого аспекта; no model anchors/offsets | CODE, negatives, LIVE10 | PASS | Допустимый ID не гарантирует, что его text поддерживает все claims |
| P06.3 | Private exact quote/span from unit and immutable source cards | CODE/OFF122/prior DB audits | PASS | Synthesis10 не вернул points, actual10 spans не вычислялись |
| P06.4 | Doubtful всегда array, unique0–6 только full; empty full-set maxItems0/no empty enum | CODE, negatives, actual empty arrays | PASS | Unknown/partial/none doubtful отвергаются |
| P06.5 | M=partial/none∪unrepresented∪doubtful; fixed empty unknown | CODE/OFF122 | PASS | Actual10 final отсутствует, M не материализован |
| P06.6 | Conclusion label/P refs, bounded strings, exact unknown, no repair/truncation | CODE/strict negatives | PASS | Actual meaning10 NOT PROVEN |
| P06.7 | Schema order retained, schema/projection/maps rebuild after each pruning removal | REV10 wire/builders + actual10 reconstruction/suffix | PASS | Final and intermediate snapshots consistent; model final absent |
| P06.8 | Protocol06 trace/full units/projections/provenance/derived M, legacy preserved | CODE/OFF122/RESTART10 | PASS | Final-derived fields создаются только при полученном valid final |
| P06.9 | Max3 unchanged known pair+transfer, no retry,3 runtime+3semantic PASS | LIVE10 | FAIL | 1 runtime FAIL,2 NOT RUN; semantic NP |
| P06.10 | Stop dependent public after first FAIL, preserve history | LIVE10 first-request stop | PASS | Следующий submit не выполнялся |
| Z1 | Luna review/fixes + mandatory fresh independent Astra; no substituted human acceptance | review history/current audit | PASS | CODE approval не заменяет A3/gate |
| Z2 | Authorized final GitHub commit/push, day ordering, old days preserved | Pending root delivery | NOT PROVEN | Reviewer не выполнял commit/push |
| Z3 | MP4 uploaded to existing Drive folder, viewer/playback checked | Pending | NOT PROVEN | Нет actual recording/publication |
| Z4 | Day30 header/row132 verified, two links written and reloaded | Pending | NOT PROVEN | External mutation/readback не выполнены |
| Z5 | Непроверенное явно pending; human acceptance не выдумана | Current reports | PASS | Second device NOT PROVEN как установленное ограничение |
| P07.1 | Sampling selection0, synthesis0.7/top_p0.8; same model/digest; think override08 | CODE/actual stage parameters | PASS | Only synthesis thinktrue, no extra critic |
| P07.2 | Independent options/provider/budget/observed use actualstage settings | REV10/OFF10/LIVE10 | PASS | Selection1024/300; synthesis1920/900; context8192/template512 |
| P07.3 | Known-sent parameters separate attempts; no phantom phases; private only | Actual stage parameters + REV09 pre-send failure | PASS | Two actual provider responses complete; no invented unsent stage |
| P07.4 | Protocol06/schema/provenance/M/renderer preserved; profile08 transport/prompt suffix override | CODE frozen hashes | PASS | No semantic validator weakening/retry |
| P07.5 | Current gate max3, next only after independent verdict,3/3 for public | LIVE10 | FAIL | Первый runtime FAIL;2 not run |
| P07.6 | Stop first FAIL/no retry, preserve previous failures | Root one-step run + archives | PASS | No new route approved by this review |
| P08.1 | Selection native/thinkfalse; synthesis thinktrue/format omitted, options10 override | CODE + actual wire fixture + actual stage trace | PASS | No synthesis native schema/grammar |
| P08.2 | Two system/user messages, context JSON+newline+full ordered dynamic schema | LIVE10 independently parsed suffix | PASS | Schema contents match trace, no extra message |
| P08.3 | Schema counted once in actual messages; synthesis separate schema_tokens0; output cap includes thinking+final | OFF122 + LIVE10 budgets | PASS | Synthesis1920 total cap reached; final empty; reasoning token split unknown |
| P08.4 | Omitted format avoids structured-output restart; no third completion/retry | Pinned route guard + local wire | PASS source-level | Actual internal token/completion telemetry не получена |
| P08.5 | Dedicated thinking excluded; unsafe/unknown final shapes and transport opaque before persistence | Fixed positive allowlist +14 tests +2 original P2 repeats + LIVE10 | PASS | Observed synthesis role+opaque empty-final metadata; no persisted thinking |
| P08.6 | Final/metrics/provenance retained when safe; empty/length/duplicate/schema errors fail without repair | OFF122/current negatives | PASS | Safe invalid-ref final remains exact but rejected |
| P08.7 | Provider debug/trace/request-body logging off | provider-logging-preflight.json + independent envconfig read | PASS current configuration | No raw environment/logs exposed; future config changes need recheck |
| P08.8 | Runtime completion/strict independent semantic gate within frozen limits | LIVE10/SEM10 | FAIL | Done_reason length, answer=null, semantic NOT PROVEN |
| P08.9 | Next submit after verdict, stop first FAIL, no autoretry/new weights | Root one-step control/LIVE10 | PASS | Two remaining private cases/public steps not run |
| P09.1 | Stage overrides10: synthesis1920/900, selection1024/300, embed/default300 | CODE/REV10 wire/LIVE10 parameters | PASS | No model/prompts/validators change; pruning corrected |
| P09.2 | One monotonic physical deadline connect/headers/body; no hidden synthesis300 clamp | REV10 fragmented fixture + actual610.521s completion | PASS | Short-cap cancellation tested offline; real900s expiry not exercised |
| P09.3 | Stage caps/options in budget/attempt/known-sent trace; transport socket closed before lock release | REV10 Application/wire + LIVE10 parameters | PASS | No deadline leaked into provider options |
| P09.4 | Actual reserve and fresh schema/mapping before pruning budget decision | REV10 + exact actual10 source reconstruction | PASS | 3 units6738+1920=8658 fail;2 units6240+1920=8160 fit |
| P09.5 | Updated provider sum1500/worker1510/Exit1520/poll-video1530; legacy plist own timeout | Shared limits/REV10 mock and temporary plist; RESTART10 | PASS code/offline | Actual pre-smoke restart21 unchanged; no full1500s lifecycle test |
| P09.6 | Previous08 privacy, strict JSON/length/empty/schema/semantic gates retained | REV10 privacy14/LIVE10 sanitized state | PASS | Length correctly rejected; hidden reasoning not substituted |
| P09.7 | Three unchanged cases, each after independent PASS, first FAIL stops others | LIVE10/SEM10 | FAIL | 0 runtime PASS;1 FAIL;2 not run; semantic NOT PROVEN |
| P09.8 | Preserve previous failures, no extra inference/retry/public before private PASS | LIVE10 one-step stop + archives | PASS | No next profile approval from this audit |
| P10.1 | Exactly synthesis1920/900, default routes300, unchanged sampling/model | CODE/REV10/LIVE10 | PASS | No extra calls or native synthesis format |
| P10.2 | One pruning owner, fresh builders every render/budget, return coherent snapshot | CODE/REV10 instrumented both stages | PASS | Both production callers use builders; fallback only helper/tests |
| P10.3 | Allowed IDs/focus/maps/context IDs reflect retained units; coverage from original validated selection | REV10 input immutability/history/maps assertions | PASS | No cumulative downgrade/background promotion |
| P10.4 | First fitting prompt sent/traced/validated; no stale intermediate schema | Actual10 reconstruction + Engine loopback capture | PASS | Fresh attempts5→4→3→2 at1920; messages/schema/units match actual |
| P10.5 | Saved09 final context preserved at1920 after corrected pruning | Independent exact09/10 safe comparison | PASS | Selection and synthesis context equal; no causal quality claim |
| P10.6 | Context8192/template512/output1920 honest; strict observed boundary5760/5761 | REV10 fixtures + actual input1093 | PASS | Length rejected before materialization; no forced repair |
| P10.7 | Privacy08/no reasoning persistence and previous validators/gates retained | REV10 Application→Store and LIVE10 safe metadata | PASS | Final empty; hidden reasoning not inspected |
| P10.8 | Bounded real gate3 runtime+semantic successes before public | LIVE10/SEM10 | FAIL | 1 runtime FAIL,0 delivered answers,2 not run |
| P10.9 | Next only after semantic PASS; stop first FAIL/no retry/further cap-loop | LIVE10 first-request stop + contract | PASS current stop | Future profile not evaluated/approved by this report |

## Actual outcome and limits

Selection77.085s,161eval/976prompt; synthesis610.521s,1920eval/1093prompt,3.26TPS. Total689.838s,2 generation attempts/2 complete provider responses. Sanitized done_reason=length, reasoning_present=true, empty final bytecount0. Output cap reached with no answer; runtime gate FAIL, A3 delivered semantics NOT PROVEN. Dedicated reasoning count/content unknown, no rejected final candidate to semantically assess.900s transport deadline did not expire; strict completion validation correctly rejected length.

P2 repair remains proven: actual09/10 selection prompt/schema/response and synthesis prompt/schema/units/projection/effective are identical. Fresh current reconstruction from actual10 selection performs5→4→3→2 with coverage/maps/schema rebuilt each time. Final input6240+1920=8160 and final context exactly match actual. Three units would require8658, so current removal is justified. This proves code conformance, not model quality or causal explanation of absent final. No old output rerender/regrade.

Privacy observed PASS: safe provider metrics/role and opaque final metadata only, no thinking field; public API excludes trace, private state0600. Restart10 preserved21 old files; it is pre-smoke evidence, not completed recovery after a successful smoke.13 completed private queries across earlier profiles are not13 successes; current10 executed1, remaining2 not run.

Public dry/video/final privacy inventory/GitHub/Drive/table and human acceptance remain NOT PROVEN. Future profile11 is not evaluated or approved here. No further cap recommendation, automatic retry or hidden-reasoning diagnosis. Optional second physical device NOT PROVEN under A9; actual compute-stop latency unmeasured; model usage/cost not invented.
