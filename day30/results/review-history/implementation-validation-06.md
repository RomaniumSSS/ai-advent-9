# Day30 — independent implementation validation, protocol06

**SPEC NOT SATISFIED (FAIL). CODE APPROVED отдельно.** В actual06 выполнены два запроса: runtime2/2 PASS, delivered semantic0/2 PASS. Третий не запускался. A3 и bounded quality gate FAIL. Видео/сдача не готовы; человеческая приёмка pending.

Нормативный baseline: `results/review-history/SPEC-protocol06.md`, SHA `88bdd2dfa9fe2ac352529524a479286bcf4988d2d8cd94ebafa7088228bc0f2e`; code `results/code-baseline-06.json`,31 files/base b3e607e. Все31 hashes сверены при CODE gate и после actual06 без расхождений. Protocol06 явно заменяет прежние anchor/model-missing правила repair03/05; прочие требования сохранены с profile04 model override. Отдельное утверждение SPEC человеком не заявляется.

Evidence: **CODE** — самостоятельное чтение runtime/fixtures/SPEC/PLAN. **OFF102** — Sol quiet CLT Python3.9.6 full102 PASS20.294s (`protocol06-full.log`), targeted10/linked63 отдельно. **REV28** — reviewer18 PASS2.068s (protocol06/ordering05/selection03) и10 PASS0.020s (protocol03/pruning); без inference/shared flock. **LEGACY12** — Store/public_receipt на временных копиях12 actual old state files, bytes preserved. **LAN** — прежние реальные CA/auth/Host/Origin checks на одном физическом хосте. **RESTART06** — `restart-06.json`, CA/hostname/PIDs54444/54500,12 old files preserved, no replay. **LIVE06** — `live-private-06.json`, private API/internal receipts, независимое read-only DB сравнение6 unit occurrences (3 unique originals),4 delivered source occurrences. **SEM06** — private semantic-review-06.md; safe semantic-summary.json. Mock PASS не заменяет live/semantic evidence.

## Полный нормативный инвентарь текущего контракта

Строки объединяют связанные требования, не создают новые. Override protocol06 учтён явно; старые requirements anchors/model missing не применяются к новым outputs.

| ID | Текущий проверяемый контракт | Evidence | Verdict | Практический предел |
|---|---|---|---|---|
| G1 | Самостоятельный Day30; private домашний сервис, без изменений Day29/runtime/imports/index/history | CODE, hashes, deployment | PASS | Другие дни не исполнялись reviewer |
| G2 | Frozen read-only DB724 chunks/663 docs и index/embedding identity | CODE, actual DB SHA, startup identity | PASS | Read-only immutable originals |
| G3 | Frozen installed Qwen3.5 9B Q4_K_M/digest, локальный Ollama, profile04 options | CODE, prior read-only metadata, LIVE06 | PASS | Требуемая version совместимость проверена; новые веса не загружались |
| G4 | Нет cloud/proxy/redirect/new framework/FSM/public exposure/покупок | CODE, OFF102, deploy config | PASS | Никакого provider fallback |
| A1.a | Отдельный процесс, question/optional conversation, request IDs/status/answer/error | server/service, OFF102, LIVE06 | PASS | Два actual API done/partial |
| A1.b | UI new conversation/follow-up/original disclosure; input1–500/body64KiB/negative pre-inference | CODE, OFF102, прежний browser fixture | PASS | Actual video UI walkthrough ещё отсутствует |
| A2.a | Fresh retrieval всего private corpus, assignment-only filter до retrieval | CODE, OFF102, LIVE06 fresh embedding/query | PASS | Retrieval не обещает смысловую полноту |
| A2.b | Два последовательных same-model chat think=false, embedding отдельно, no retry/critic | CODE, OFF102, LIVE06 | PASS | Каждый actual запрос2 completed chat |
| A2.c | Empty/unknown/clarification/error могут остановиться раньше, без free answer | CODE, negatives | PASS | Структурные unknown контракты |
| A3.a | Верный пересказ: subject/object, конкретика, числа, авторы, неопределённость, план/результат | SEM06 | FAIL | Первый delivered summary выдаёт желаемое свойство за установленный факт |
| A3.b | Вывод поддержан points, рекомендации обозначены, нет выдуманной причинности/результата | SEM06 | FAIL | Второй delivered conclusion придумывает последовательность между отдельными предложениями |
| A3.c | Источники/author/date/originals код получает из immutable evidence; valid refs не автоматический semantic PASS | CODE, LIVE06/DB | PASS |6/6 passed-unit occurrences exact; это не закрывает A3.a/b |
| A3.d | Краткий summary/conclusion, unknown без свободных фактов | Renderer/limits, OFF102 | PASS | «Обычно2–4» — целевой стиль; содержательные ошибки отдельно FAIL |
| A4.a | Для обоих calls actual prompt+schema+template512+output1024≤8192,temperature0 | OFF102, LIVE06 budgets | PASS | Input bounds6884/6578 и6978/6458; observed976/970 и1016/926 |
| A4.b | ≤3 user topic questions, no prior assistant prose as evidence; current question intact | CODE, REV28, LIVE06 prompts | PASS | История в follow-up удалена по бюджету, fresh topic retrieval сохранён |
| A4.c | Whole-unit pruning, history first; final schemas/IDs/coverage/projection пересобраны | CODE, REV28, LIVE06 | PASS | Отрезанных частей original text нет |
| A5.a | Одна chain; shared existing flock, concurrent409/no queue, lock release | OFF102, prior real lock check | PASS | Reviewer не повторял live contention |
| A5.b | Credential sliding6/60,429+Retry-After до inference | CODE, OFF102 | PASS | Process-local reset при restart документирован |
| A5.c | ≤300s provider deadline, shutdown/close before release, no infinite retry | CODE, targeted transport regressions, OFF102 | PASS | Compute-stop latency фактически не измерялась |
| A6.a | Explicit LAN IPv4/TLS/freeports, SAN IP/localhost, CA verified, no public bind/tunnel | LAN, RESTART06 | PASS | Только тот же физический Mac |
| A6.b | Bearer/constant compare; env/key0600 gitignored; token only UI memory | CODE, modes, OFF102 | PASS | Секреты не выведены в reports |
| A6.c | Host/Origin allowlist, CLI absent Origin allowed, no wildcard CORS | LAN, OFF102 | PASS | Actual negative checks раньше, guards неизменны |
| A6.d | Static no private source, safe text rendering/no external scripts | CODE, browser fixtures | PASS | Финальная publication scan отдельно |
| A7.a | Day30 dir0700/files0600, atomic own state, scope/new-conversation isolation | CODE, OFF102, file modes | PASS | Private traces отделены от public receipt |
| A7.b | Restart preserves completed/error receipts, interrupts unfinished, no autoreplay/migration | LEGACY12, OFF102, RESTART06 | PASS | Actual12 old hashes preserved; unfinished path mock |
| A7.c | Logs sanitized; full prompt/raw/source evidence only private | CODE, diagnostics tests, actual file boundaries | PASS | Public reports содержат категории ошибок без private case facts |
| A7.d | Separate launchd start/stop/supervision, old apps untouched | deploy review/tests, RESTART06 | PASS | Bounded job/PID lifecycle ранее исправлен |
| A8.a | Offline auth/input/rate/busy/budgets/invalid output/timeout/unlock/history/demo | OFF102, REV28 | PASS | Все model calls mock; RED draft не выдан за отдельные legacy bugs |
| A8.b | ≥3 consecutive real content requests incl private discussion/follow-up | LIVE06 | FAIL | Выполнены2, оба semantic FAIL, третий остановлен |
| A8.c | Восстановление после контролируемого restart по завершении текущего успешного smoke | RESTART06 выполнен до live; финальный quality gate не пройден | NOT PROVEN | Старый state сохранён, новый post-smoke restart не выполнен |
| A8.d | Independent semantic audit выбранных originals/summary/conclusion | SEM06 | PASS | Аудит выполнен и выявил реальные FAIL, это не приёмка качества |
| A9.a | Real CA-verified HTTPS на LAN IP без -k; API/errors verified | LAN, RESTART06, LIVE06 | PASS | Second physical device optional NOT PROVEN, не новый blocker |
| A9.b | README точные CA commands/supervision и ограничения | CODE/docs | PASS | Финальный delivery readback pending |
| A10.a | Assignment server scope до catalog/retrieval/prompts, separate history/originals | CODE, OFF102, RESTART06 demo scope | PASS | Private inference не использовался как public demo |
| A10.b | Silent MP4≥2 real questions/input/wait/answer/conclusion/source, no staging/token/private | Actual video отсутствует | NOT PROVEN | Runner code не считается записью |
| A10.c | Final public inventory/content privacy scan | Pending publication | NOT PROVEN | Текущий review сохраняет private границу; полной финальной сдачи нет |
| R03.1 | Strict JSON duplicate keys/NaN/types/closed fields; selection keyed mapping≤8,uniqueQ≤6,exact coverage | CODE, REV28, OFF102 | PASS | Selection protocol сохранён |
| R03.2 | Question aspects различают предложение и подтверждение результата; coverage none iff no proof | CODE, tests, LIVE06 Q2none | PASS | Model semantic judgement coverage не считается доказанным |
| P04.1 | Qwen35 metadata отвергается Qwen2Tokenizer; existing ByteBound явно отмечен | Metadata/tests/LIVE06 | PASS | Не маскируется под BPE |
| P04.2 | Text-only system/user template512; inherited defaults документированы | Official renderer review, README, payload | PASS | Разные projection/pruning не чистый model benchmark |
| P04.3 | При переходе старый генератор отсутствует в RAM; no weight/global/Ollama changes | Prior ps[] and lifecycle | PASS | Auto-expiration, отдельный unload не заявляется |
| R05.1 | Provider insertion order; canonical packed/state/hash/prompt body прежние | CODE, wire tests, LIVE06 | PASS | Native-chat route guarantee не заявлена |
| R05.2 | Private order arrays от final sent schemas; no phantom stage; no public trace | REV28, error tests, LIVE06 | PASS | Arrays сохраняются при canonical save |
| P06.1 | Selection projection exact7fields, synthesis+role, full text once, stage-local context IDs, original metadata unchanged | CODE, REV28, actual prompts | PASS | Nullable attribution не восстанавливается моделью |
| P06.2 | Points exact aspects/evidence_id/text,0–4,1–300; retained proof для каждого аспекта; no model anchors/offsets | CODE, negatives, LIVE06 | PASS | Допустимый ID не гарантирует, что его text поддерживает все claims |
| P06.3 | Private full quote/start/end от backend unit; source cards неизменны, point text alone in summary | CODE, REV28, DB/source comparison | PASS | Original provenance exact; semantic второй point FAIL отдельно |
| P06.4 | Doubtful всегда array, unique0–6 только full; empty full-set maxItems0/no empty enum | CODE, negatives, actual empty arrays | PASS | Unknown/partial/none doubtful отвергаются |
| P06.5 | M=partial/none∪unrepresented∪doubtful; supported только noM/allfull; empty points fixed unknown | CODE, tests, LIVE06 | PASS | Обоим answers code M=[Q1,Q2]; disclaimer не лечит неверные claims |
| P06.6 | Conclusion Вывод/P refs, bounded strings; exact unknown; no silent correction/truncation | CODE, negatives | PASS | Только структурный PASS; actual meaning FAIL A3.b |
| P06.7 | Ordered points→doubtful→conclusion, point aspects→evidence→text; final projection budget/rebuild | REV28, LIVE06 wire/raw trace | PASS | Реальное order наблюдено отдельно от семантики |
| P06.8 | Trace protocol06, full units/sent projection/schema/spans/derived M отдельно от raw; legacy untouched | CODE, LEGACY12, RESTART06/LIVE06 | PASS | Старые failed outputs не переинтерпретировались |
| P06.9 | Max3 unchanged known pair+transfer, no retries,3 runtime+3semantic PASS | LIVE06, SEM06 | FAIL | Runtime2 PASS, semantic2 FAIL; transfer не запускался |
| P06.10 | Stop dependent public after any runtime/semantic FAIL, preserve prior failures | Root stop before third, archives, SEM06 | PASS | Второй уже accepted до first verdict; client stopped, server completed |
| Z1 | Luna review/fixes + mandatory fresh independent Astra; no substituted human acceptance | review history/current audit | PASS | CODE approval не заменяет A3/gate |
| Z2 | Authorized final GitHub commit/push, day ordering, old days preserved | Pending root delivery | NOT PROVEN | Reviewer не выполнял commit/push |
| Z3 | MP4 uploaded to existing Drive folder, viewer/playback checked | Pending | NOT PROVEN | Нет actual recording/publication |
| Z4 | Day30 header/row132 verified, two links written and reloaded | Pending | NOT PROVEN | External mutation/readback не выполнены |
| Z5 | Непроверенное явно pending; human acceptance не выдумана | Current reports | PASS | Second device NOT PROVEN как установленное ограничение |

## Причины итогового FAIL и границы

A3.a/b — два разных фактических semantic FAIL доставленных ответов. A8.b/P06.9 — успешный bounded gate не достигнут. Code-derived provenance/missing/order работают, но качество ими не доказано. Поэтому общий verdict FAIL, а не NOT PROVEN. Незапущенный transfer, post-smoke restart, video/final privacy/external delivery остаются NOT PROVEN отдельно от уже доказанных failures.

Все предыдущие FAIL01–05 сохранены;06 не исправляет и не переоценивает их задним числом. Driver остановлен до третьего; server завершил ранее принятый второй без retry. Новая thinking/profile гипотеза не выбрана и не одобрена этим аудитом. Никакого дополнительного inference, изменения SPEC/runtime, публикации или человеческого согласия reviewer не выполнял и не заявляет. Usage/cost не сообщены и не выдуманы.
