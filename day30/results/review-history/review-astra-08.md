# Day30 — independent Astra CODE review, profile08 fixed

**CODE: APPROVED, fixed baseline08.** Ранее найденный P2 privacy defect исправлен и независимо воспроизведён как GREEN. Существенных оставшихся дефектов не обнаружено. Actual08 runtime gate FAIL; delivered semantic NOT PROVEN, поскольку answer=null. Historical failures01–07 не переоцениваются.

Baseline `results/code-baseline-08-fixed.json`,34 independently checked hashes/base b3e607e, расхождений нет. Frozen SPEC `results/review-history/SPEC-profile08.md`, SHA `5735ef8e2012ac936af33689b6c0807f1389ecec5357a43ea61d486a6b574b40`, неизменён. Initial `code-baseline-08.json` сохранён отдельно. Между initial/fixed08 runtime изменён только local.py sanitizer; service/tokenizer/protocol/wire/options/schema contract прежние.

## Исправление P2

Initial sanitizer сохранял любой parseable final dict за исключением трёх названий reasoning fields. Независимый Application→Store reproduction показал extra analysis в двух private JSON files при invalid_synthesis_points. Это было реальное нарушение persistence contract, хотя public API trace не раскрывал.

Теперь `safe_final_shape` разрешает только закрытые selection/synthesis root и nested keys с ожидаемыми типами; неизвестные поля/структуры/типы получают только opaque bytecount/SHA/stage. Message.thinking не копируется. Это persistence filter, не новый acceptance validator: strict original schema/ref/coverage gates по-прежнему видят исходный response и не ремонтируют его.

Reviewer повторил обе исходные P2 конструкции через настоящий Application→Store на временных каталогах с fake model и mocked generation lock: status error/invalid_synthesis_points сохранён; в обоих request/conversation файлах analysis marker отсутствует, content не сохраняется. Directories удалены. Дополнительно проверены root/nested unknowns, wrong types, selection payloads, response_data, malformed/partial transport, false-phase thinking, empty/length/duplicates и actual wire. Shape-valid invalid-ref final сохраняется byte-exact для диагностики, продолжая давать invalid_point_reference; никакого silent repair/PASS.

## Проверки и границы

Independent CLT Python3.9.6: `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_privacy_shape08 test_profile08 -v` — **14 PASS2.754s**, exit0, без inference/shared live flock. Дополнительно две исходные Application→Store reproductions GREEN. Initial08 reviewer31 targeted PASS6.181s остаются evidence для неизменённых wire/budget/options/protocol путей, а не доказательством исправления сами по себе. Sol fixed14 PASS2.770s,93 linked PASS10.495s,full122 PASS24.423s прочитаны; full reviewer не дублировал.

Wire: selection прежний think=false/native format; synthesis think=true, format key отсутствует, options07 прежние. Ровно два system/user messages, user содержит context JSON + newline + полный ordered schema. Dynamic schema count для synthesis0, поскольку она уже посчитана в actual message;8192/1024/512/300s caps сохранены. Output1024 общий для reasoning+final. Whole-unit pruning rebuild, observed counts, strict JSON/provenance/M/renderer не меняются. Schema order здесь инструкция, не native grammar enforcement.

Pinned [Ollama route](https://github.com/ollama/ollama/blob/v0.33.3/server/routes.go#L2849) требует non-nil Format для structured-output restart, поэтому omission исключает этот дополнительный проход. [Qwen35 renderer/parser](https://github.com/ollama/ollama/blob/v0.33.3/model/parsers/qwen35.go) разделяют thinking/final; text-only wrapper укладывается в прежний512 reserve. Реальный08 объём reasoning, duration и backend telemetry ещё не измерены.

`provider-logging-preflight.json` — root read-only actual launchd/process evidence: Ollama PID2132, обе debug переменные отсутствуют, filtered startup INFO/request replay false. Независимо прочитан [envconfig v0.33.3](https://github.com/ollama/ollama/blob/v0.33.3/envconfig/config.go): отсутствующий OLLAMA_DEBUG означает INFO, DebugLogRequests по умолчанию false. При этих actual controls parser LevelTrace не пишет reasoning. Reviewer raw environment/provider logs не читал/не сохранял и настройки не менял.

Код готов к controlled restart и одному неизменённому G01T1. Далее каждый submit только после независимого semantic PASS предыдущего; первый runtime/semantic FAIL останавливает оставшиеся случаи. Даже real structural success не гарантирует смысл. Video/delivery и human acceptance не закрыты этим CODE заключением.

## Actual08 gate

Первый запрос: inference_timeout/provider_deadline на synthesis,2 attempted/1 completed chat, total380.269s. Selection78.3s completed; synthesis300.003s, headers phase,0 received bytes, opaque empty-body SHA. Параметры/format_mode и финальные budgets соответствуют fixed08, schema suffix exact. Answer отсутствует; смысловая поддержка NOT PROVEN. Настроенный bounded deadline сработал, нового code defect этот отказ не доказывает.

Все34 hashes повторно совпали после live. Restart08 CA/hostname verified,17 old files unchanged,no replay. Следующие2 cases/public steps не запускались. Privacy в observed receipt выдержана: sanitized selection final, synthesis только stage/count/hash; reasoning не читался/не сохранялся reviewer. Internal synthesis token count и actual compute-stop latency неизвестны. CODE APPROVED сохраняется отдельно от SPEC/gate FAIL. Новый timeout/output профиль требует отдельного контракта и review; этим аудитом не одобрен.
