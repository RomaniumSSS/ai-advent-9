# Day30 — independent Astra CODE review, profile10

**Global CODE10: APPROVED.** Inherited P2 pruning исправлен и независимо воспроизведён как GREEN в обеих стадиях. Существенных оставшихся дефектов не обнаружено. Actual10 runtime FAIL (length/empty final), delivered semantics NOT PROVEN; archived09 NEEDS CHANGES/runtime FAIL и все прежние failures сохраняются без переоценки.

Frozen results/code-baseline-10.json:37/37 hashes независимо совпали, base b3e607e; manifest SHA `7f4e7505bbe22fab01d86d70c850527b970859bcc3e6910e8556dae1ae7265f8`. Normative results/review-history/SPEC-profile10.md SHA `67ad919b73f6e27eca49bca0ac257c6c0737862f8609f5f673263d5d67d05113`. Reviewer самостоятельно читал builders/Engine/transport/limits/tests и relevant PLAN/README/SPEC. Не автор исправления.

## P2 исправление

fit_prompt — единственный production pruning loop. Перед каждым render и budget test stage builder строит schema/extra из текущих units. Selection пересекает allowed IDs, пересчитывает dialogue_focus; synthesis каждый раз выводит effective coverage/maps из исходной validated selection, не из уже downgraded state. Projection использует тот же набор; context_ids фильтруются. История удаляется первой; следующее сообщение отражает её новый состав. Возвращаются согласованные messages/units/history/budget/context, их же Engine использует для send/trace/validation. Поздние внешние циклы удалены. Источники/coverage не мутируются. Empty/unknown пути и строгие validators сохранены.

Совместимый вызов fit_prompt без builder используется только тестами/helper checks; оба production callers передают builders. Его stale behavior служит отрицательным контролем, не маршрутом Engine.

Independent reproduction на сохранённых09 source/projection данных, без чтения reasoning и без inference:

- Synthesis с reserve1408: попытки5→4→3 units, первый fit input6738, всего8146; лишнее удаление исчезло.
- Synthesis с current1920:5→4→3→2, input6240, всего8160. Три units требуют8658, поэтому удаление здесь обосновано. Final messages/schema/coverage/units точно совпадают с сохранённым09 состоянием.
- Selection на тех же units с явно synthetic system/history padding: попытки(5,history1)→(5,0)→(4,0)→(3,0), retained3/input7138, тогда как stale control retained2. На каждой итерации actual enums/allowed/context IDs согласованы; исходные inputs не изменены.
- Дополнительно настоящий Ollama.request отправлен только в ephemeral loopback fixture: один HTTP call, captured synthesis messages равны saved09, output1920/thinktrue/format omitted. Provider Ollama не вызывался. Это offline wire evidence, не новый model answer.

## Capacity, privacy и checks

Synthesis1920/900, selection1024/300, embedding/default300; shared sum1500, join1510, launchd1520, CLI/video1530. Context8192/template512 прежние. One absolute deadline connect/headers/body и short TIMEOUT fixtures сохранены; sync close до lock release. Actual options используются в budget/observed gate: prompt5760 допустим с1920+512,5761 отвергается. Deadline идёт transport argument, не provider option; attempts/known-sent остаются раздельными.

Model/digest/sampling/system prompts/protocol06/evidence/retrieval/tokenizer/static unchanged; synthesis schema в user message ровно один раз, native format отсутствует. Positive-shape privacy08 и opaque error metadata сохранены; empty/length/duplicate/schema/ref failures не ремонтируются, reasoning не заменяет final. Повторённые actual Application→Store tests проверяют эту границу.

Independent CLT `/usr/bin/python3`3.9.6: `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile10 test_profile09 test_privacy_shape08 test_profile08 -v` — **25 PASS,6.831s**. Fake models, ephemeral loopback, mock locks/launchd; real shared flock/inference не использовались. Плюс отдельная private reconstruction и loopback wire equality выше. Sol final11 PASS4.105s и linked111 PASS13.566s прочитаны как отдельные runs. RED3/causal Engine RED1 и initial fixture focus collision сохранены; fixture получил уникальные chunk IDs без изменения focus contract. Полный suite без новой причины не дублировался.

## Actual10 и граница одобрения

Первый request завершился invalid_model_response/incomplete_model_response: selection77.085s,161eval/976prompt; synthesis610.521s,1920eval/1093prompt,3.26TPS; total689.838s,2 attempted/2 completed generation. Sanitized done_reason=length, final bytecount0, reasoning_present=true. Достигнут output1920 cap, финального ответа нет; A3 delivered semantics NOT PROVEN. Этот runtime failure не устанавливает новый code defect.900s deadline не истёк, strict length/empty-final gate сработал.

Все37 frozen hashes после live совпали. Actual09/10 selection prompt/schema/response и synthesis prompt/schema/units/projection/effective совпадают. Current reconstruction из actual10 даёт свежие попытки5→4→3→2 и final input6240+1920=8160, exact actual snapshot. P2 исправлен; дополнительное удаление относительно repaired1408 обосновано1920 budget. Качество внутреннего reasoning или причина отсутствия final не выводятся из этого сравнения.

Known-sent trace подтверждает1024/300 и1920/900, think/format modes; schema suffix exact, native schema count0. Actual packets отдельно не перехватывались: wire подтверждается code/loopback и recorded stage parameters. Private state0600; API без trace; hidden reasoning не читался и не сохранялся, synthesis имеет только разрешённые metrics/role/opaque empty-final metadata. Restart10 сохранил21 old file/no replay, CA/hostname verified; это pre-smoke restart.

Global CODE10 APPROVED сохраняется. Два оставшихся cases/public dry/record/delivery не запускались. Никакого autoretry/regrade старых FAIL или следующего cap/profile approval. Human acceptance pending, optional second device NOT PROVEN. Dedicated reasoning count и actual compute-stop latency неизвестны; usage/cost не придуманы.
