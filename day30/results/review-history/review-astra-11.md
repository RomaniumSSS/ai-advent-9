# Day30 — independent Astra CODE review, profile11 fixed

**Global CODE11 fixed: APPROVED.** Два pre-live detector findings устранены; существенных оставшихся дефектов не найдено. Actual11 runtime1 PASS, delivered semantic1 FAIL; remaining2 NOT RUN. Actual10 length/empty-final и прежние failures сохранены; новые вопросы reviewer не отправлял.

Frozen results/code-baseline-11-fixed.json:38/38 hashes совпали; manifest SHA `7048caee1fc1434f5c1638233c5f04e0f3a5a292c0d39dccd45c4afef1a5db86`. Normative results/review-history/SPEC-profile11-fixed.md SHA `4665565496fdaf8c806ffeb95175df83e7faf39f2cd23040e07c108b0c73a024`. Base b3e607e. Initial→fixed менялись только protocol.py и tests/test_profile11.py;36 остальных hashes равны. Reviewer не автор кода.

## Pre-live findings и regate

Первый detector принимал команду только в начале всей строки. Independent preflight обнаружил, что неизменённый первый запланированный вопрос получал8/4, поэтому эксперимент не активировал single mode. Root уточнил generic sentence/command boundary в fixed SPEC, сохранив сам вопрос. Original SPEC-profile11.md и profile11-boundary-red.log сохраняют исходную границу и failure.

После расширения boundary regex-mask пропускал imperative внутри ASCII single quotes и nested guillemets. Synthetic reproductions `Он написал: 'Что случилось? Назови один пример'.` и `Он написал: «Цитата «слово»; Назови один пример».` ошибочно давали1/1. Это concrete false positive, сокращавший обычный запрос; rejected code зафиксирован results/code-baseline-11-initial.json, оба RED — results/profile11-quotes-red.log. Никакой live inference на rejected версии не было.

Fixed outside_quotes использует stack, поддерживает вложенные delimiters, escaped delimiters и внутрисловные апострофы; маскирует quoted boundaries, сохраняя внешние. Оба исходных reproduction GREEN; дополнительно5 quote negatives/4 внешних positives. AST comparison до/после: изменён только answer_limits, добавлен outside_quotes; strict_json/unique_ids/validate_selection/retain_coverage/model_projection/synthesis_schema/materialize_synthesis неизменны. Initial finding не удалён из истории и не объявлен никогда не существовавшим.

## Quantity/native/provenance audit

Detector использует только текущий исходный question: регистр/ё/whitespace normalization для matching, без изменения отправляемого question. Поддерживает заданные imperative forms после начала/? ! . ; newline; negative/distributive и quoted forms не активируют single. Это узкий deterministic detector, не общий языковой parser. History/corpus/case IDs не участвуют. Ответ limits всегда typed integer1/1 либо8/4. Independent actual manifest comparison подтвердил неизменность всех3 вопросов относительно10 и ожидаемые quantities1/1,8/4,8/4; raw вопросы в report не внесены.

Single selection keyed evidence — oneOf exact empty + singleton per retained allowed ID, required/additionalProperties=false. Backend отдельно отвергает >1 proof без truncation; ordinary максимум8 сохранён. Context expansion остаётся background, не вторым proof/point. Synthesis single maxItems1, point_refs≤1/P1; empty unknown сохранён. Cross-aspect/source/coverage/M/provenance/strict JSON gates прежние; quantity не доказывает смысл. Отдельный Engine overcount reproduction остановился после первого generation call с invalid_selection_quantity. Test ordinary8 proofs/4 points и follow-up reset подтверждают прежнюю область.

Обе стадии think=false/native ordered format; selection1024/temp0, synthesis1024/.7/.8, deadlines300. Schema только в format, не в user content, budget actual messages+schema один раз+512 reserve/8192. Shared sum900,join910,Exit920,poll-video930. P2 builders пересобирают oneOf/enums/allowed/focus/maps/coverage/projection до каждого budget test, final send/trace/validation получают тот же snapshot. Native wire/schema-order known-sent trace и pre-send failure различены. Нет retry/third call/новых weights.

[Pinned converter](https://github.com/ggml-org/llama.cpp/blob/b10760/common/json-schema-to-grammar.cpp#L918) независимо прочитан: oneOf идёт через union, object branch учитывает required/properties/additionalProperties; maxProperties не используется как grammar limit. [Pinned Ollama route](https://github.com/ollama/ollama/blob/v0.33.3/server/routes.go#L2769) применяет immediate format при think=false для builtin thinking parser. Это source-level подтверждение выбранного пути, не измеренная backend telemetry11.

## Evidence и пределы

CLT `/usr/bin/python3`3.9.6, fake models/ephemeral loopback/mock lifecycle/lock, без real inference/shared live flock:

- Independent final `test_profile11`: **12 PASS1.070s**, включая оба quoted reproductions, boundaries, native wire/quantity/unknown/background/follow-up/P2/errors/privacy.
- Independent `test_profile09 test_privacy_shape08 test_profile08 test_ordering05`: **27 PASS7.852s** до quote-only fix. Reused для36 unchanged files и unchanged validator AST; includes native schema counting, transport deadline/cancel-before-unlock, lifecycle, opaque persistence, strict failure/no-retry/order trace.
- Дополнительно actual3-question quantity/hash preflight, direct Engine overcount rejection,5 quote negatives/4 outside positives. Initial synthetic216 positive combinations/10 negative guards — ранняя bounded проверка, не отдельная real-provider evaluation.

Sol linked116 PASS15.610s до quote fix; final12 PASS1.056s, сохранённые RED и intermediate boundary checks прочитаны отдельно. Full suite reviewer не дублировал без причины. Privacy08 positive final-shape/opaque failures остаётся, unexpected thinking отвергается и не сохраняется как final. Provider INFO preflight прежний; hidden reasoning/log bodies reviewer не читал.

## Actual11 gate

First request done/supported,2 complete generation calls/1embedding,total122.387s. Selection46.022s65eval/907prompt; synthesis74.127s184eval/753prompt; both stop. One proof/point/source, actual limits1/1, both native/thinkfalse/options1024/deadline300. Independently recomputed budgets6807+1024 and5720+1024 fit8192; native user JSON has no schema suffix. OneOf branches match retained allowlist; synthesis proof enum/projection/coverage agree. All38 hashes still match after live.

**Delivered semantic FAIL.** Immutable DB span200chars/author/date/card/provenance and API/internal answer match exactly. But summary adds a definite implementation intention and timing absent from the source; conclusion propagates that timing. Summary also weakens the concrete condition of the problem. Details only private/semantic-review-11.md. Labelled practical recommendations are allowed; this verdict concerns an unsupported commitment derived from an inaccurate paraphrase. No cross-author mixing or invented achieved result in this candidate.

Global CODE11 APPROVED remains: no new implementation defect. Supported/full coverage is structural model judgement, not semantic guarantee. Parent notified not to submit next case; remaining2 NOT RUN, not two additional failures. Safe summary records runtime1 PASS/semantic1 FAIL.

Restart11 CA/hostname verified,23 old files unchanged/no replay, before smoke. Safe final content+role, no reasoning field; API no trace. Private source facts stay private. Prior provider INFO controls reused, no hidden reasoning/log-body reading. Public dry/video/delivery/human acceptance pending; optional second device NOT PROVEN. No further repair/profile approved here; no old failure regrade.
