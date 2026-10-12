# Day30 — independent Astra CODE review, profile09

**CODE: NEEDS CHANGES — inherited P2 pruning defect, discovered during actual09 audit.** Историческое APPROVED для profile09 limit delta сохранено как предшествующий checkpoint; новый evidence меняет общий verdict. Actual09 runtime FAIL; delivered semantics NOT PROVEN, поскольку answer=null. Старые failures01–08 сохранены.

Baseline `results/code-baseline-09.json`: все36 hashes независимо совпали, base b3e607e; SHA manifest `87a0569728fb18387a9f652024fbc260f42be0c55838a0199626f9f095cd0640`. Frozen normative `results/review-history/SPEC-profile09.md`, SHA `eb436f10d1131d299ef303d71970c3a50ed4e68e3b189a741fd5c5802a4ac004`. Проверены actual code, fixtures, PLAN, README и offline evidence. Reviewer не автор реализации.

## Проверенное изменение

Synthesis получает num_predict1408 и absolute deadline600; selection остаётся1024/300, embedding/default routes300. `limits.py` связывает provider sum1200, worker join1210, launchd ExitTimeOut1220 и CLI/video polling1230. Это пределы provider/lifecycle, не обещание полного SLA с локальным retrieval/storage overhead. Старые plist читаются с собственным ExitTimeOut; автоматически не переписываются.

Stage deadline проходит от Engine через Ollama.chat/embed до одного monotonic deadline connect/headers/body, отдельно от provider options. Общего clamp300 на synthesis больше нет; короткие fixture TIMEOUT продолжают ограничивать обе стадии. Socket shutdown/close завершается синхронно до caller и освобождения Application lock; дополнительных reader threads/retries нет. Attempt и known-sent trace отделены, pre-send failure не создаёт фиктивной отправки. Deadline присутствует также в финальном budget и embedding trace.

Actual options используются при budget/pruning и observed-count validation: на сохранённой величине input6738 резерв1408 даёт8146≤8192; observed prompt6272 допустим,6273 отвергается. Это не предсказание будущего selection. Финальная schema/projection согласованы; новый аудит ниже обнаружил запоздалую пересборку между удалениями units. Context8192/template512 сохранены. Base GEN_OPTIONS не мутируется.

Profile08 wire/privacy сохранены: synthesis think=true, ключ format отсутствует, ordered schema ровно один раз в user message, native schema budget0. Selection прежний think=false/native format. Protocol06, evidence, retrieval, tokenizer, archive и static hashes совпадают с fixed08. Positive final-shape sanitizer остаётся закрытым по root/nested keys/types; malformed/unknown/transport bodies opaque. Strict duplicate/length/empty/schema/ref failures не ремонтируются. Ни reasoning, ни private facts не выносились в отчёт.

## Независимые проверки

CLT `/usr/bin/python3`3.9.6, временные loopback/fake model/mock launchd/lock; реальной inference и shared live flock нет:

- `python3 -m unittest discover -s day30/tests -p test_profile09.py -v`: **8 PASS,3.090s**, включая actual wire stage bounds, output/observed budgets, fragmented headers/body, cancel-before-unlock, legacy plist, CLI/video waits.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_privacy_shape08 test_profile08 test_ordering05 -v`: **19 PASS,4.773s**, actual Application→Store privacy/error paths, omitted format/embedded schema, strict negatives, attempt/known-sent trace и serialization.

Sol evidence отдельно: targeted7 PASS2.555s + добавленный cancellation1 PASS0.527s; linked107 PASS13.061s. Прочитаны RED и описание первого fixture failure; POST поддержка дополняет прежний slow-byte fixture, не убирает timeout assertions. Full122 fixed08 — историческая проверка неизменных путей, не текущий повторный прогон. Дополнительный полный suite без новой причины не запускался.

## P2 — rebuild schema/mapping before the next pruning decision

`service.py:89–102` удаляет несколько units внутри fit_prompt, сохраняя первоначальные schema/extra. Engine пересобирает coverage/mapping/schema только после возврата (`service.py:255–263`, аналогичный selection loop). SPEC требует пересборки после каждого удаления, чтобы следующая проверка оценивала реально остающийся prompt.

На actual09 сохранённых данных независимая reconstruction без model вызовов показала: промежуточный candidate со старой schema имеет input6869+output1408=8277 и удаляет ещё unit. После своевременной пересборки тот же candidate имел бы6738+1408=8146≤8192. Actual final input6240 соответствует лишнему удалению.08/09 selection prompt/schema/projection/response одинаковы; разницу объясняет delayed rebuild при большем output reserve, а не новый selection. Тексты/авторы/case facts здесь не раскрываются.

Минимальное исправление: после одного whole-unit удаления вернуть управление пересборке allowed/proof IDs, mapping/coverage/schema, затем снова считать бюджет; сохранить history-first и строгий final cap. Нужен offline regression на candidate, который stale schema не допускает, но rebuilt schema уже допускает; проверить оба stage loops. Это самостоятельный inherited defect, не доказанная причина length и не основание обещать успех после исправления. Reviewer код не менял.

## Actual09 gate и границы

Первый case error/invalid_model_response, validation incomplete_model_response. Selection75.177s,161eval/976prompt; synthesis455.070s,1408eval/1093prompt,3.29TPS; generation2 attempted/2 complete,total532.472s. Done_reason=length; sanitized final content bytecount0, reasoning_present boolean true.1408 output cap достигнут, итогового ответа нет. Dedicated reasoning count и содержание не исследовались. Настроенный600s deadline не истёк;09 wiring/output change работает как задано.

Все36 hashes после live совпали. Trace подтверждает actual stage parameters300/600 и budgets6884/6240; user schema suffix exact, native schema count0. API не раскрывает trace, private receipt0600. Сохранены только разрешённые provider metrics/role и opaque empty-final metadata; скрытый reasoning reviewer не читал/не сохранял. Restart09 сохранил19 old files, CA/hostname verified/no replay; это pre-smoke restart.

Смысловая поддержка NOT PROVEN: summary/conclusion отсутствуют. Два оставшихся cases/public dry/record/delivery не запускались. Historical09 limit-delta APPROVED не означает approval нового profile или игнорирование P2. Не менять старые FAIL; no automatic retry. Human acceptance pending, optional second device NOT PROVEN. Реальное compute-stop latency не измерено, модельные usage/cost не сообщены.
