# Day30 — independent implementation validation, profile08 fixed

**SPEC NOT SATISFIED (FAIL). Fixed08 CODE APPROVED отдельно.** Первый actual08 запрос завершился runtime FAIL; answer=null, delivered semantics NOT PROVEN. Два оставшихся запроса не запускались. Исторические failures01–07 и initial08 privacy finding сохранены; fixed08 не меняет их задним числом.

Baseline `results/code-baseline-08-fixed.json`,34 files/base b3e607e; все hashes совпали при review и после actual08. Frozen SPEC `results/review-history/SPEC-profile08.md`, SHA `5735ef8e2012ac936af33689b6c0807f1389ecec5357a43ea61d486a6b574b40`. Profile08 явно переопределяет think/format/budget/persistence правила; protocol06 semantics/provenance/M прежние. Отдельное человеческое утверждение SPEC не заявляется.

Evidence: CODE — независимый review; OFF122 — Sol fixed08 full122 PASS24.423s, targeted14/linked93 отдельно. Reviewer fixed14 PASS2.754s +2 independent original P2 Application→Store reproductions GREEN; initial08 reviewer31 PASS6.181s переиспользуются только для неизменных wire/budget/options paths. OFF102/REV28/LEGACY12 обозначают отдельные предыдущие проверки, не повторные текущие прогоны. LAN — prior actual CA/auth/Host/Origin. RESTART08 — `restart-08.json`, CA/hostname/PIDs12931/12979,17 old state files unchanged/no replay. LIVE08 — `live-private-08.json` + actual private API/internal receipt. SEM08 — `private/semantic-review-08.md`, safe semantic-summary.json. Provider logging actual preflight и official defaults проверены отдельно; real inference reviewer не запускал.

## Полный нормативный инвентарь текущего контракта

Строки объединяют связанные требования, не создают новые. Override protocol06 учтён явно; старые requirements anchors/model missing не применяются к новым outputs.

| ID | Текущий проверяемый контракт | Evidence | Verdict | Практический предел |
|---|---|---|---|---|
| G1 | Самостоятельный Day30; private домашний сервис, без изменений Day29/runtime/imports/index/history | CODE, hashes, deployment | PASS | Другие дни не исполнялись reviewer |
| G2 | Frozen read-only DB724 chunks/663 docs и index/embedding identity | CODE, actual DB SHA, startup identity | PASS | Read-only immutable originals |
| G3 | Frozen installed Qwen3.5 9B Q4_K_M/digest, локальный Ollama, profile04 options | CODE, prior read-only metadata, LIVE08 | PASS | Требуемая version совместимость проверена; новые веса не загружались |
| G4 | Нет cloud/proxy/redirect/new framework/FSM/public exposure/покупок | CODE, OFF102, deploy config | PASS | Никакого provider fallback |
| A1.a | Отдельный процесс, question/optional conversation, request IDs/status/answer/error | server/service, OFF122, LIVE08 | PASS | Actual API вернул конкретный inference_timeout, не успешный answer |
| A1.b | UI new conversation/follow-up/original disclosure; input1–500/body64KiB/negative pre-inference | CODE, OFF102, прежний browser fixture | PASS | Actual video UI walkthrough ещё отсутствует |
| A2.a | Fresh retrieval всего private corpus, assignment-only filter до retrieval | CODE, OFF102, LIVE08 fresh embedding/query | PASS | Retrieval не обещает смысловую полноту |
| A2.b | Два последовательных same-model calls: selection thinkfalse/native, synthesis thinktrue/prompt_schema, embedding отдельно | CODE, OFF122, LIVE08 | PASS |2 attempted/1 completed chat; no retry/critic |
| A2.c | Empty/unknown/clarification/error могут остановиться раньше, без free answer | CODE, negatives | PASS | Структурные unknown контракты |
| A3.a | Верный пересказ: subject/object, конкретика, числа, авторы, неопределённость, план/результат | SEM08 no delivered answer | NOT PROVEN | Answer=null; прежние semantic failures остаются в archives |
| A3.b | Вывод поддержан points, рекомендации обозначены, нет выдуманной причинности/результата | SEM08 no delivered answer | NOT PROVEN | Synthesis final не получен |
| A3.c | Original metadata/provenance из immutable evidence, IDs не semantic proof | CODE, OFF122, prior DB audits | PASS | Новых delivered source cards08 нет, actual semantic proof не заявлен |
| A3.d | Краткий summary/conclusion, unknown без свободных фактов | Renderer/limits, OFF102 | PASS | «Обычно2–4» — целевой стиль; содержательные ошибки отдельно FAIL |
| A4.a | Actual prompt/schema+template512+output1024≤8192, stage options, observed gate | CODE/OFF122/LIVE08 budgets | PASS | Input6884/6738; observed selection976, synthesis count неизвестен |
| A4.b | ≤3 user topic questions, no assistant prose evidence; question intact | CODE, prior REV28, OFF122 | PASS | Follow-up08 не запускался |
| A4.c | Whole-unit pruning, history first; final schemas/IDs/coverage/projection пересобраны | CODE, REV28, LIVE08 | PASS | Отрезанных частей original text нет |
| A5.a | Одна chain; shared existing flock, concurrent409/no queue, lock release | OFF102, prior real lock check | PASS | Reviewer не повторял live contention |
| A5.b | Credential sliding6/60,429+Retry-After до inference | CODE, OFF102 | PASS | Process-local reset при restart документирован |
| A5.c | ≤300s configured provider deadline, synchronous socket close before release, no retry | Deadline code/fixtures + LIVE08 expiry | PASS | Observed return300.003s; backend compute-stop latency не измерена |
| A6.a | Explicit LAN IPv4/TLS/freeports, SAN IP/localhost, CA verified, no public bind/tunnel | LAN, RESTART08 | PASS | Только тот же физический Mac |
| A6.b | Bearer/constant compare; env/key0600 gitignored; token only UI memory | CODE, modes, OFF102 | PASS | Секреты не выведены в reports |
| A6.c | Host/Origin allowlist, CLI absent Origin allowed, no wildcard CORS | LAN, OFF102 | PASS | Actual negative checks раньше, guards неизменны |
| A6.d | Static no private source, safe text rendering/no external scripts | CODE, browser fixtures | PASS | Финальная publication scan отдельно |
| A7.a | Day30 dir0700/files0600, atomic own state, scope/new-conversation isolation | CODE, OFF102, file modes | PASS | Private traces отделены от public receipt |
| A7.b | Restart preserves old receipts, unfinished interrupted, no autoreplay/migration | LEGACY12, OFF122, RESTART08 | PASS |17 actual old state hashes preserved; unfinished path mock |
| A7.c | Logs sanitized; full prompt/raw/source evidence only private | CODE, diagnostics tests, actual file boundaries | PASS | Public reports содержат категории ошибок без private case facts |
| A7.d | Separate launchd start/stop/supervision, old apps untouched | deploy review/tests, RESTART08 | PASS | Bounded job/PID lifecycle ранее исправлен |
| A8.a | Offline auth/input/rate/busy/budgets/output/timeout/unlock/history/demo/privacy | OFF122, fixed reviewer14+2 reproductions | PASS | All models fake; реальные ответы отдельно |
| A8.b | ≥3 consecutive real content requests incl discussion/follow-up | LIVE08 | FAIL | Первый runtime FAIL,0 delivered answers,2 оставшихся не запускались |
| A8.c | Recovery after current completed smoke | RESTART08 до live; quality gate failed | NOT PROVEN | Новый post-smoke restart не выполнялся |
| A8.d | Independent semantic reading delivered summary/conclusion by originals | SEM08: answer absent | NOT PROVEN | Runtime/privacy audit выполнен, смыслового материала нет |
| A9.a | Real CA-verified HTTPS на LAN IP без -k; API/errors verified | LAN, RESTART08, LIVE08 | PASS | Second physical device optional NOT PROVEN, не новый blocker |
| A9.b | README точные CA commands/supervision и ограничения | CODE/docs | PASS | Финальный delivery readback pending |
| A10.a | Assignment server scope до catalog/retrieval/prompts, separate history/originals | CODE, OFF102, RESTART08 demo scope | PASS | Private inference не использовался как public demo |
| A10.b | Silent MP4≥2 real questions/input/wait/answer/conclusion/source, no staging/token/private | Actual video отсутствует | NOT PROVEN | Runner code не считается записью |
| A10.c | Final public inventory/content privacy scan | Pending publication | NOT PROVEN | Текущий review сохраняет private границу; полной финальной сдачи нет |
| R03.1 | Strict JSON duplicate keys/NaN/types/closed fields; selection keyed mapping≤8,uniqueQ≤6,exact coverage | CODE, REV28, OFF102 | PASS | Selection protocol сохранён |
| R03.2 | Aspects separate proposal/result; coverage none iff no proof | CODE/OFF122; prior actual06 | PASS | Current08 synthesis semantic judgement не наблюдалось |
| P04.1 | Qwen35 metadata отвергается Qwen2Tokenizer; existing ByteBound явно отмечен | Metadata/tests/LIVE08 | PASS | Не маскируется под BPE |
| P04.2 | Text-only system/user template512; inherited defaults документированы | Official renderer review, README, payload | PASS | Разные projection/pruning не чистый model benchmark |
| P04.3 | При переходе старый генератор отсутствует в RAM; no weight/global/Ollama changes | Prior ps[] and lifecycle | PASS | Auto-expiration, отдельный unload не заявляется |
| R05.1 | Ordered provider serialization; canonical packing unchanged | CODE, wire fixture | PASS | Synthesis schema now prompt instruction, not enforced native grammar |
| R05.2 | Private sent schema order arrays, no phantom stage, no public trace | OFF122, known-sent headers error metadata | PASS | Arrays describe schema; raw synthesis order не получен |
| P06.1 | Selection projection exact7fields, synthesis+role, full text once, stage-local context IDs, original metadata unchanged | CODE, REV28, actual prompts | PASS | Nullable attribution не восстанавливается моделью |
| P06.2 | Points exact aspects/evidence_id/text,0–4,1–300; retained proof для каждого аспекта; no model anchors/offsets | CODE, negatives, LIVE08 | PASS | Допустимый ID не гарантирует, что его text поддерживает все claims |
| P06.3 | Private exact quote/span from unit and immutable source cards | CODE/OFF122/prior DB audits | PASS | Synthesis08 не вернул points, actual08 spans не вычислялись |
| P06.4 | Doubtful всегда array, unique0–6 только full; empty full-set maxItems0/no empty enum | CODE, negatives, actual empty arrays | PASS | Unknown/partial/none doubtful отвергаются |
| P06.5 | M=partial/none∪unrepresented∪doubtful; fixed empty unknown | CODE/OFF122 | PASS | Actual08 final отсутствует, M не материализован |
| P06.6 | Conclusion label/P refs, bounded strings, exact unknown, no repair/truncation | CODE/strict negatives | PASS | Actual meaning08 NOT PROVEN |
| P06.7 | Schema order points→doubtful→conclusion, point aspects→evidence→text; budgets rebuild | OFF122/LIVE08 schema suffix | PASS | Exact ordered suffix; output order не наблюдался |
| P06.8 | Protocol06 trace/full units/projections/provenance/derived M, legacy preserved | CODE/OFF122/RESTART08 | PASS | Final-derived fields создаются только при полученном valid final |
| P06.9 | Max3 unchanged known pair+transfer, no retry,3 runtime+3semantic PASS | LIVE08 | FAIL |1 runtime FAIL,2 NOT RUN; semantic NP |
| P06.10 | Stop dependent public after first FAIL, preserve history | LIVE08 first-request stop | PASS | Следующий submit не выполнялся |
| Z1 | Luna review/fixes + mandatory fresh independent Astra; no substituted human acceptance | review history/current audit | PASS | CODE approval не заменяет A3/gate |
| Z2 | Authorized final GitHub commit/push, day ordering, old days preserved | Pending root delivery | NOT PROVEN | Reviewer не выполнял commit/push |
| Z3 | MP4 uploaded to existing Drive folder, viewer/playback checked | Pending | NOT PROVEN | Нет actual recording/publication |
| Z4 | Day30 header/row132 verified, two links written and reloaded | Pending | NOT PROVEN | External mutation/readback не выполнены |
| Z5 | Непроверенное явно pending; human acceptance не выдумана | Current reports | PASS | Second device NOT PROVEN как установленное ограничение |

| P07.1 | Sampling selection0, synthesis0.7/top_p0.8; same model/digest; think override08 | CODE/actual stage parameters | PASS | Only synthesis thinktrue, no extra critic |
| P07.2 | Independent options/provider/budget/observed use actualstage settings | OFF122/LIVE08 | PASS | Context8192/output1024/template512/deadline300 прежние |
| P07.3 | Known-sent parameters separate attempts; no phantom phases; private only | Headers-stage trace/OFF122 | PASS | Отправка известна, completion не приписана |
| P07.4 | Protocol06/schema/provenance/M/renderer preserved; profile08 transport/prompt suffix override | CODE frozen hashes | PASS | No semantic validator weakening/retry |
| P07.5 | Current gate max3, next only after independent verdict,3/3 for public | LIVE08 | FAIL | Первый runtime FAIL;2 not run |
| P07.6 | Stop first FAIL/no retry, preserve previous failures | Root one-step run + archives | PASS | No new route approved by this review |


| P08.1 | Selection native format/thinkfalse; synthesis thinktrue/format key omitted, same07options | CODE + actual wire fixture + actual stage trace | PASS | No synthesis native schema/grammar |
| P08.2 | Two system/user messages, context JSON+newline+full ordered dynamic schema | LIVE08 independently parsed suffix | PASS | Schema contents match trace, no extra message |
| P08.3 | Schema counted once in actual messages; synthesis separate schema_tokens0; output cap includes thinking+final | OFF122 + LIVE08 budgets | PASS | Output1024 cap, not1024 each; completed synthesis metrics unavailable |
| P08.4 | Omitted format avoids structured-output restart; no third completion/retry | Pinned route guard + local wire | PASS source-level | Actual internal token/completion telemetry не получена |
| P08.5 | Dedicated thinking excluded; unsafe/unknown final shapes and transport opaque before persistence | Fixed positive allowlist +14 tests +2 original P2 repeats + LIVE08 | PASS | Observed synthesis only headers/count0/SHA, no body prefix |
| P08.6 | Final/metrics/provenance retained when safe; empty/length/duplicate/schema errors fail without repair | OFF122/current negatives | PASS | Safe invalid-ref final remains exact but rejected |
| P08.7 | Provider debug/trace/request-body logging off | provider-logging-preflight.json + independent envconfig read | PASS current configuration | No raw environment/logs exposed; future config changes need recheck |
| P08.8 | Runtime completion/strict independent semantic gate within frozen limits | LIVE08/SEM08 | FAIL | Deadline expired, answer=null, semantic NP |
| P08.9 | Next submit after verdict, stop first FAIL, no autoretry/new weights | Root one-step control/LIVE08 | PASS | Two remaining private cases/public steps not run |

## Причины итогового FAIL и пределы

A8.b/P06.9/P07.5/P08.8 — успешный bounded runtime/semantic gate не достигнут. Selection завершён78.3s/161 output/976 prompt; synthesis вернул provider_deadline после300.003s ожидания headers,0 body bytes; total380.269s, generation2 attempted/1 complete. Код выполнил заданный timeout и сохранил opaque metadata. Этот отказ не устанавливает новый дефект реализации deadline.

A3.a/b NOT PROVEN: final summary/conclusion отсутствуют. Нет оснований для semantic PASS или нового delivered semantic FAIL. Zero received bytes не доказывает нулевую внутреннюю генерацию. Synthesis token count/reasoning length/observed input и compute-stop latency неизвестны. Input budget PASS не обещает завершения в deadline.

Следующие два cases, post-smoke restart, actual video/final public privacy/GitHub/Drive/table остаются NOT PROVEN. Кодовое и privacy одобрение не закрывают эти пункты. Дальнейшая корректировка output/timeout требует отдельного контракта и bounded проверки:08 не доказывает достаточность конкретного нового лимита. No auto retry, no regrade old outputs. Profile09 reviewer не выбирал и не одобрял. Human acceptance pending; second device optional NOT PROVEN по A9. Usage/cost не сообщены.
