# Day30 — independent Astra CODE review, profile12

**Global CODE12: APPROVED.** Существенных дефектов в frozen candidate не найдено. Actual12: runtime1 PASS, delivered semantic1 FAIL; remaining2 NOT RUN. Исторический semantic FAIL11 сохранён в review-history/*-11 и private/semantic-review-11.md; он не пересмотрен.

Frozen results/code-baseline-12.json: **39/39 hashes совпали**, manifest SHA `cae6e6503e8f790483fb5b1f7df5f46ca3b55945081f095e2affdcb85e005bd5`. Normative results/review-history/SPEC-profile12.md SHA `9160b74b7ff6367d11a677f368d6db1240954b8c6ad0d67a10b39d58f5488291`. Worktree day30-private-service, base b3e607e. Reviewer не автор реализации.

## Проверенная дельта

Установленная qwen3:8b-q8_0/digest e56358ca25dd14db6853a9f68a92d717aaa6f0a94250a72d1a0f3d86a9f30130 заменяет генератор11. Обе стадии native/think=false, output1024/deadline300/context8192/template512; selection temp0, synthesis .7/top_p .8. Остальные inherited defaults не выданы за явно отправленные options. Existing Qwen2Tokenizer принимает реальные metadata gpt2/pre=qwen2,151936 tokens/151387 merges/add_bos=false; новый tokenizer не введён. Embedding/index неизменны.

Wire aliases переименованы только по заданным root/conclusion paths. Root selection a_evidence/b_coverage; synthesis a_points/b_doubtful_aspect_ids/c_conclusion; nested a_text/b_point_refs. Point fields, evidence IDs, enums, refs и свободный текст не меняются. Required/properties согласованы; deepcopy не мутирует canonical schema. Strict JSON отвергает duplicate keys на всех уровнях до normalize_wire. Unknown/mixed/missing/canonical-only roots и malformed conclusion отвергаются invalid_wire_shape; нет fallback, recursive replace, truncation или repair.

Canonical validators strict_json/unique_ids/validate_selection/retain_coverage/model_projection/synthesis_schema/materialize_synthesis сохранили AST. Quantity11 fixed, source/aspect/count/M/unknown/provenance gates прежние. Инверсия только alias words в двух generic system prompts даёт byte-identical prompts11: новых corpus facts или semantic prompt patches нет.

P2 builders пересобирают canonical schema/maps/projection, затем wire schema перед каждым budget test. Provider получает именно посчитанную wire schema один раз, без schema suffix в user content. Наблюдаемый provider token-count gate сохранён. В trace отдельно actual wire schema/raw aliases/order и canonical schema/normalized response; order arrays формируются для известной отправки, не выдумываются для несостоявшегося stage. Model/digest/options фиксируются как параметры вызова.

Persistence positive allowlist принимает только exact alias shapes после той же нормализации. Safely shaped raw сохраняется byte-exact; arbitrary/partial/mixed payload и parsed transport errors остаются opaque. Reasoning не сохраняется; unexpected thinking прежним образом отвергается. API/UI и чтение старых receipts не требуют нормализации исторических outputs. Изменений auth/TLS/worker bounds/flock/lifecycle/static/source policy не обнаружено.

[Pinned Ollama source](https://github.com/ollama/ollama/blob/v0.33.3/llm/llama_server.go#L2333) независимо прочитан: format декодируется в Go map перед downstream serialization. Выбранные aliases сохраняют grounding-first и при lexical sorting. Это source-level обоснование, не actual12 backend telemetry и не доказательство качества.

## Независимая проверка

Среда /usr/bin/python3 3.9.6 CLT; fake provider, ephemeral loopback, временный Store. Реальной inference, restart и shared live flock reviewer не выполнял.

- Final frozen: `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile12 test_privacy_shape08 test_ordering05 -v` — **15 PASS,3.209s,exit0**.
- Ранее affected: test_profile12/test_profile11/test_privacy_shape08/test_profile08/test_ordering05 — **37 PASS,6.857s**. Финальные test-only additions затем включены в отдельный15; результаты не суммируются как52 независимых теста.
- Дополнительно Engine с Fake и actual tokenizer metadata: actual wire budget selection input1219/schema134, synthesis1523/schema245, output1024. Метод local_qwen2_bpe_with_reserves; synthetic case, не реальные токены provider.
- Direct duplicate nested evidence/conclusion tests, lossless free-text/non-mutation checks, unchanged-validator AST и inverse-alias system-prompt comparisons пройдены.

Sol evidence прочитано отдельно: profile12-green-final.log15 PASS3.221s и profile12-linked-initial.log127 PASS16.659s. Unchanged security/lifecycle/transport evidence из прежних reviews reused; полный suite reviewer без новой причины не повторял.

Read-only provider/tokenizer preflights подтверждают установленный digest и совместимость metadata; PS[] — только idle snapshot, не peak RAM/load latency. Переход ByteBound→BPE может менять retained context, поэтому последующий результат нельзя приписать только весам/precision. Actual12 observed counts укладываются в upper bounds; это не доказательство точного template count для всех запросов, и наблюдаемый gate остаётся обязательным.

## Actual12 gate

First request done/partial,163.639s,1 source/point/proof;2 complete generation calls/1 embedding. Selection60.764s51eval1423prompt; synthesis100.587s239eval880prompt; both stop. Actual native/thinkfalse/model+digest/options1024/deadline300 verified. Raw alias order matches intended roots/nested fields, safe raw normalizes exactly to canonical response, canonical/wire schemas agree. Messages contain JSON context without appended schema. Rebuilding original ordered builders/messages reproduces budgets2382+1024 and1663+1024 exactly; schema388/248,512 reserve. Actual observed prompt counts fit. No pruning; quantity1/1, effective coverage/missing and source maps consistent. All39 hashes still match.

**Delivered semantic FAIL.** Read-only immutable DB span163chars/author/date/card/provenance and API/internal answer match. Summary turns a premature proposal into an established necessity, presenting that necessity as the requested concrete problem. Conclusion repeats the unsupported premise. Initial actor/object relation is preserved; no invented achieved result/fixed date/cross-author mixing in this candidate. The separate practical recommendation is allowed and is not the finding. Partial status/conservative missing alone is not failure and cannot cure the distortion. Exact private comparison stays in private/semantic-review-12.md.

CODE12 APPROVED remains: no new implementation defect. Restart12 preserved25 old files/no replay, CA verified for main/demo; API excludes trace, raw message only safe content/role, no reasoning field read. Historical11 semantic FAIL remains unchanged.

Root notified to stop: remaining2 NOT RUN, not two extra failures. SPEC12 requires ending the model/parameter loop at this failure; next scope/format decision belongs to the user. No further automatic profile, inference or relaxation approved by this audit. Public dry/video/delivery not ready; human acceptance pending, optional second device NOT PROVEN. Total15 historical completed private queries is not15 successes.
