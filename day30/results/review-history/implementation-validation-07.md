# Day30 — independent implementation validation, profile07

**SPEC NOT SATISFIED (FAIL). CODE APPROVED отдельно.** Actual07: runtime1/1 PASS, delivered semantic0/1 PASS. Ещё два запроса не запускались. A3 и bounded quality gate FAIL. Видео/сдача не готовы; человеческая приёмка pending.

Нормативный baseline: `results/review-history/SPEC-profile07.md`, SHA `69bca5bdce93628bb30d99732f519f20987b571957ae20b753fc24d6e2fab9be`; code `results/code-baseline-07.json`,32 files/base b3e607e. Все32 hashes совпали при CODE review и после live. Protocol06 заменяет прежний anchor/missing contract, profile07 меняет только synthesis sampling и stage-options plumbing. Человеческое утверждение SPEC отдельно не заявляется.

Evidence: CODE — независимое чтение и inverse exact hashes runtime/8 existing test files. OFF102 — прежний baseline06 full102 quiet PASS20.294s; только reused evidence, не новый107/108-suite. Current Sol6 targeted PASS1.540s +79 linked PASS7.756s. Reviewer21 current targeted PASS3.587s (profile07/ordering05/protocol06); REV28 — прежние protocol06 targeted tests для неизменённых требований. LEGACY12 — прежние temp copies preserved; Store не менялся. LAN — реальные same-host CA/auth/Host/Origin checks. RESTART07 — `restart-07.json`: CA/hostname/PIDs71946/72022,15 old files unchanged,no replay. LIVE07 — `live-private-07.json` + actual private API/internal receipt. SEM07 — `private/semantic-review-07.md`, safe `semantic-summary.json`;3 original spans/metadata independently exact. Mock не заменяет real semantics.

## Полный нормативный инвентарь текущего контракта

Строки объединяют связанные требования, не создают новые. Override protocol06 учтён явно; старые requirements anchors/model missing не применяются к новым outputs.

| ID | Текущий проверяемый контракт | Evidence | Verdict | Практический предел |
|---|---|---|---|---|
| G1 | Самостоятельный Day30; private домашний сервис, без изменений Day29/runtime/imports/index/history | CODE, hashes, deployment | PASS | Другие дни не исполнялись reviewer |
| G2 | Frozen read-only DB724 chunks/663 docs и index/embedding identity | CODE, actual DB SHA, startup identity | PASS | Read-only immutable originals |
| G3 | Frozen installed Qwen3.5 9B Q4_K_M/digest, локальный Ollama, profile04 options | CODE, prior read-only metadata, LIVE07 | PASS | Требуемая version совместимость проверена; новые веса не загружались |
| G4 | Нет cloud/proxy/redirect/new framework/FSM/public exposure/покупок | CODE, OFF102, deploy config | PASS | Никакого provider fallback |
| A1.a | Отдельный процесс, question/optional conversation, request IDs/status/answer/error | server/service, OFF102, LIVE07 | PASS | Один actual API done/partial |
| A1.b | UI new conversation/follow-up/original disclosure; input1–500/body64KiB/negative pre-inference | CODE, OFF102, прежний browser fixture | PASS | Actual video UI walkthrough ещё отсутствует |
| A2.a | Fresh retrieval всего private corpus, assignment-only filter до retrieval | CODE, OFF102, LIVE07 fresh embedding/query | PASS | Retrieval не обещает смысловую полноту |
| A2.b | Два последовательных same-model chat think=false, embedding отдельно, no retry/critic | CODE, OFF102, LIVE07 | PASS | Каждый actual запрос2 completed chat |
| A2.c | Empty/unknown/clarification/error могут остановиться раньше, без free answer | CODE, negatives | PASS | Структурные unknown контракты |
| A3.a | Верный пересказ: subject/object, конкретика, числа, авторы, неопределённость, план/результат | SEM07 | FAIL | Delivered summary искажает временной план и отношение между альтернативами; конкретная проблема потеряна |
| A3.b | Вывод поддержан points, рекомендации обозначены, нет выдуманной причинности/результата | SEM07 | FAIL | Conclusion усиливает обсуждение/ожидание до неподтверждённых проблем внедрения |
| A3.c | Источники/author/date/originals код получает из immutable evidence; valid refs не автоматический semantic PASS | CODE, LIVE07/DB | PASS |3/3 passed-unit occurrences exact; это не закрывает A3.a/b |
| A3.d | Краткий summary/conclusion, unknown без свободных фактов | Renderer/limits, OFF102 | PASS | «Обычно2–4» — целевой стиль; содержательные ошибки отдельно FAIL |
| A4.a | Для обоих calls actual prompt+schema+template512+output1024≤8192,stage temperature0/0.7 | OFF102, LIVE07 budgets | PASS | Input bounds6884/6578; observed976/970 |
| A4.b | ≤3 user topic questions, no prior assistant prose as evidence; current question intact | CODE, REV28, LIVE07 prompts | PASS | Follow-up07 не запускался; прежний путь без изменений проверен offline |
| A4.c | Whole-unit pruning, history first; final schemas/IDs/coverage/projection пересобраны | CODE, REV28, LIVE07 | PASS | Отрезанных частей original text нет |
| A5.a | Одна chain; shared existing flock, concurrent409/no queue, lock release | OFF102, prior real lock check | PASS | Reviewer не повторял live contention |
| A5.b | Credential sliding6/60,429+Retry-After до inference | CODE, OFF102 | PASS | Process-local reset при restart документирован |
| A5.c | ≤300s provider deadline, shutdown/close before release, no infinite retry | CODE, targeted transport regressions, OFF102 | PASS | Compute-stop latency фактически не измерялась |
| A6.a | Explicit LAN IPv4/TLS/freeports, SAN IP/localhost, CA verified, no public bind/tunnel | LAN, RESTART07 | PASS | Только тот же физический Mac |
| A6.b | Bearer/constant compare; env/key0600 gitignored; token only UI memory | CODE, modes, OFF102 | PASS | Секреты не выведены в reports |
| A6.c | Host/Origin allowlist, CLI absent Origin allowed, no wildcard CORS | LAN, OFF102 | PASS | Actual negative checks раньше, guards неизменны |
| A6.d | Static no private source, safe text rendering/no external scripts | CODE, browser fixtures | PASS | Финальная publication scan отдельно |
| A7.a | Day30 dir0700/files0600, atomic own state, scope/new-conversation isolation | CODE, OFF102, file modes | PASS | Private traces отделены от public receipt |
| A7.b | Restart preserves completed/error receipts, interrupts unfinished, no autoreplay/migration | LEGACY12, OFF102, RESTART07 | PASS | Actual15 old hashes preserved; unfinished path mock |
| A7.c | Logs sanitized; full prompt/raw/source evidence only private | CODE, diagnostics tests, actual file boundaries | PASS | Public reports содержат категории ошибок без private case facts |
| A7.d | Separate launchd start/stop/supervision, old apps untouched | deploy review/tests, RESTART07 | PASS | Bounded job/PID lifecycle ранее исправлен |
| A8.a | Offline auth/input/rate/busy/budgets/invalid output/timeout/unlock/history/demo | OFF102, REV28 | PASS | Все model calls mock; RED draft не выдан за отдельные legacy bugs |
| A8.b | ≥3 consecutive real content requests incl private discussion/follow-up | LIVE07 | FAIL | Выполнен1, semantic FAIL; ещё2 не запускались |
| A8.c | Восстановление после контролируемого restart по завершении текущего успешного smoke | RESTART07 выполнен до live; финальный quality gate не пройден | NOT PROVEN | Старый state сохранён, новый post-smoke restart не выполнен |
| A8.d | Independent semantic audit выбранных originals/summary/conclusion | SEM07 | PASS | Аудит выполнен и выявил реальные FAIL, это не приёмка качества |
| A9.a | Real CA-verified HTTPS на LAN IP без -k; API/errors verified | LAN, RESTART07, LIVE07 | PASS | Second physical device optional NOT PROVEN, не новый blocker |
| A9.b | README точные CA commands/supervision и ограничения | CODE/docs | PASS | Финальный delivery readback pending |
| A10.a | Assignment server scope до catalog/retrieval/prompts, separate history/originals | CODE, OFF102, RESTART07 demo scope | PASS | Private inference не использовался как public demo |
| A10.b | Silent MP4≥2 real questions/input/wait/answer/conclusion/source, no staging/token/private | Actual video отсутствует | NOT PROVEN | Runner code не считается записью |
| A10.c | Final public inventory/content privacy scan | Pending publication | NOT PROVEN | Текущий review сохраняет private границу; полной финальной сдачи нет |
| R03.1 | Strict JSON duplicate keys/NaN/types/closed fields; selection keyed mapping≤8,uniqueQ≤6,exact coverage | CODE, REV28, OFF102 | PASS | Selection protocol сохранён |
| R03.2 | Question aspects различают предложение и подтверждение результата; coverage none iff no proof | CODE, tests; prior actual06 Q2none | PASS | Model semantic judgement coverage не считается доказанным |
| P04.1 | Qwen35 metadata отвергается Qwen2Tokenizer; existing ByteBound явно отмечен | Metadata/tests/LIVE07 | PASS | Не маскируется под BPE |
| P04.2 | Text-only system/user template512; inherited defaults документированы | Official renderer review, README, payload | PASS | Разные projection/pruning не чистый model benchmark |
| P04.3 | При переходе старый генератор отсутствует в RAM; no weight/global/Ollama changes | Prior ps[] and lifecycle | PASS | Auto-expiration, отдельный unload не заявляется |
| R05.1 | Provider insertion order; canonical packed/state/hash/prompt body прежние | CODE, wire tests, LIVE07 | PASS | Native-chat route guarantee не заявлена |
| R05.2 | Private order arrays от final sent schemas; no phantom stage; no public trace | REV28, error tests, LIVE07 | PASS | Arrays сохраняются при canonical save |
| P06.1 | Selection projection exact7fields, synthesis+role, full text once, stage-local context IDs, original metadata unchanged | CODE, REV28, actual prompts | PASS | Nullable attribution не восстанавливается моделью |
| P06.2 | Points exact aspects/evidence_id/text,0–4,1–300; retained proof для каждого аспекта; no model anchors/offsets | CODE, negatives, LIVE07 | PASS | Допустимый ID не гарантирует, что его text поддерживает все claims |
| P06.3 | Private full quote/start/end от backend unit; source cards неизменны, point text alone in summary | CODE, REV28, DB/source comparison | PASS | Original provenance exact; semantic support FAIL отдельно |
| P06.4 | Doubtful всегда array, unique0–6 только full; empty full-set maxItems0/no empty enum | CODE, negatives, actual empty arrays | PASS | Unknown/partial/none doubtful отвергаются |
| P06.5 | M=partial/none∪unrepresented∪doubtful; supported только noM/allfull; empty points fixed unknown | CODE, tests, LIVE07 | PASS | Actual answer code M=[Q1,Q2]; disclaimer не лечит неверные claims |
| P06.6 | Conclusion Вывод/P refs, bounded strings; exact unknown; no silent correction/truncation | CODE, negatives | PASS | Только структурный PASS; actual meaning FAIL A3.b |
| P06.7 | Ordered points→doubtful→conclusion, point aspects→evidence→text; final projection budget/rebuild | REV28, LIVE07 wire/raw trace | PASS | Реальное order наблюдено отдельно от семантики |
| P06.8 | Trace protocol06, full units/sent projection/schema/spans/derived M отдельно от raw; legacy untouched | CODE, LEGACY12, RESTART07/LIVE07 | PASS | Старые failed outputs не переинтерпретировались |
| P06.9 | Max3 unchanged known pair+transfer, no retries,3 runtime+3semantic PASS | LIVE07, SEM07 | FAIL | Runtime1 PASS, semantic1 FAIL; follow-up/transfer не запускались |
| P06.10 | Stop dependent public after any runtime/semantic FAIL, preserve prior failures | Root stop after first before next submit, archives, SEM07 | PASS | Первый semantic verdict получен до любого следующего submit |
| Z1 | Luna review/fixes + mandatory fresh independent Astra; no substituted human acceptance | review history/current audit | PASS | CODE approval не заменяет A3/gate |
| Z2 | Authorized final GitHub commit/push, day ordering, old days preserved | Pending root delivery | NOT PROVEN | Reviewer не выполнял commit/push |
| Z3 | MP4 uploaded to existing Drive folder, viewer/playback checked | Pending | NOT PROVEN | Нет actual recording/publication |
| Z4 | Day30 header/row132 verified, two links written and reloaded | Pending | NOT PROVEN | External mutation/readback не выполнены |
| Z5 | Непроверенное явно pending; human acceptance не выдумана | Current reports | PASS | Second device NOT PROVEN как установленное ограничение |

| P07.1 | Только synthesis temperature0.7/top_p0.8; selection exact previous dict, same model/digest/thinkfalse | Inverse hashes, wire fixture, actual stage trace | PASS | Остальные explicit/options/defaults без нового override |
| P07.2 | Independent dict copies; provider/budget/observed validator используют stage options | Reviewer profile07 tests, actual budgets/trace | PASS | Input contexts8192/output1024/template512,deadline300 прежние |
| P07.3 | Known-sent full parameters отдельно от attempts; no phantom stage, private trace | Success/parse-error/presend negatives, LIVE07 | PASS | Унаследованные defaults не выданы за explicitly sent |
| P07.4 | Protocol06/prompts/schema/provenance/M/renderer неизменны, no critic/retry/seed/thinkingpass | Inverse local/service hash, unchanged modules, input comparison | PASS | Новый sampling не доказывает semantic benefit |
| P07.5 | ≤3 unchanged known pair+transfer; next submit только после independent semantic PASS;3/3 для public | LIVE07/SEM07 | FAIL | Первый semantic FAIL;2 remaining NOT RUN |
| P07.6 | Stop first FAIL, no automatic retry, preserve all prior failures | Root single-step run, reviewer verdict before next | PASS | Один sample не общая оценка надёжности/причины |

## Причины итогового FAIL и пределы

A3.a — delivered summary теряет конкретную исходную проблему и искажает временные условия/отношение между предложенными альтернативами. A3.b — conclusion приписывает обсуждению неподтверждённые факты внедрения. A8.b/P06.9/P07.5 — успешный bounded gate не достигнут. Эти фактические failures требуют общего FAIL, а не NOT PROVEN.

Code provenance/M/order/stage parameters и бюджеты работают по SPEC. Новая sampling гипотеза не получила semantic PASS; один stochastic sample не доказывает общую невозможность профиля либо причинное преимущество. Prompts/schemas равны соответствующим previous first-case inputs; старый output не переоценивался.

Follow-up/transfer, post-smoke restart, video/final publication privacy/GitHub/Drive/table остаются NOT PROVEN. Root получил independent first FAIL до следующего submit; два оставшихся запроса не приняты, retries нет. Прежние failures01–06 сохранены. Новая гипотеза этим review не выбирается; дополнительных provider calls, SPEC/runtime edits или публикации reviewer не выполнял. Human acceptance pending; second device optional NOT PROVEN по A9. Usage/cost не сообщены.
