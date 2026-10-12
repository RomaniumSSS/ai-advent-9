# Day30 — independent Astra CODE review, profile08

**NEEDS CHANGES.** Один воспроизведённый P2 privacy defect блокирует реальный profile08 gate. Новый inference/restart reviewer не выполнял. Historical FAIL01–07 сохранены; semantic08 NOT PROVEN.

Baseline `results/code-baseline-08.json`,33 hashes/base b3e607e: независимо сверены, расхождений нет. Frozen SPEC `results/review-history/SPEC-profile08.md`, SHA `5735ef8e2012ac936af33689b6c0807f1389ecec5357a43ea61d486a6b574b40`, совпал. Рабочая редакция не выдана за отдельное человеческое утверждение.

## P2 — reasoning из недопустимого final JSON сохраняется в private state

Место: `local.py:89–109`, особенно сохранение любого parsed dict в `sanitized_response`; persistence path `service.py:202` → InferenceFailure.partial_result → Application/Store. Detector отклоняет только ключи thinking/reasoning/reasoning_content, но parseable dict с явно помеченным `analysis` принимается для raw snapshot. Например, final с нормальными protocol06 полями и дополнительным `analysis` отклоняется действующим validator как invalid_synthesis_points, однако полный content остаётся в synthesis_raw_response.message.content.

Независимое воспроизведение без модели: ThinkingFake на synthesis добавляет synthetic analysis marker. Сначала два Engine variants (analysis-only dict и extra analysis рядом с protocol fields) подтвердили ошибку. Затем настоящий Application→Store с temp directory и fake generation lock: status error/invalid_synthesis_points; marker обнаружен в двух private JSON files (request и conversation). Public receipt trace не раскрывает, но SPEC08 запрещает reasoning persistence также private. Synthetic text не выводился в отчёт и временные файлы удалены.

Нужна положительная проверка допустимой формы final для persistence либо opaque metadata для произвольных schema-invalid fields; расширять короткий denylist имён недостаточно для заявленной границы. Сохранить прежний strict validator и no repair/retry. Shape-valid final с invalid refs можно оставить диагностируемым, но неизвестные analysis-поля не должны считаться безопасным final. Regression должен проверить именно Application/Store и error path, а не только удаление message.thinking.

## Что независимо проверено

Reviewer `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile08 test_profile07 test_protocol06 test_ordering05 -v`:31 PASS6.181s, CLT Python3.9.6, exit0, mock/ephemeral loopback, без общего live flock. Эти тесты не покрывали найденный analysis-field вариант. Прочитаны Sol final10 targeted/89 linked/full118 PASS и сохранённые RED/initial fixture failure; зелёный suite не закрывает новый воспроизводимый дефект.

Wire synthesis think=true, format ключ отсутствует, два system/user сообщения, ordered schema добавлена newline в конец user content. Selection прежний think=false/native format. Options07 неизменны, provider dict copies сохранены. Schema content/order равны контракту; synthesis schema_tokens=0, полная schema уже посчитана в actual messages. Budget/pruning rebuild и observed count gate,8192/1024/512/300s caps сохраняются. Protocol06/provenance/M/strict JSON/empty/length/refs validators не ослаблены, reasoning не используется вместо final.

Opaque bytes/hash/stage корректно покрывают malformed outer body, partial timeout и legacy response_text. Parsed response_data проходит sanitizer. Success/ошибки с известными thinking fields очищаются; найденный обход находится в permissive final-shape проверке. Метрики и final сохраняются отдельно; no retry и synchronous socket cancellation тестами подтверждены.

Независимо прочитаны pinned primary sources: [Ollama route](https://github.com/ollama/ollama/blob/v0.33.3/server/routes.go#L2849), [qwen35 renderer](https://github.com/ollama/ollama/blob/v0.33.3/model/renderers/qwen35.go), [parser](https://github.com/ollama/ollama/blob/v0.33.3/model/parsers/qwen35.go). Structured-output restart требует non-nil Format; omission исключает этот restart. Text-only system/user wrapper с assistant think prefill укладывается в512 reserve;1024 остаётся общим output cap. Parser отделяет thinking и имеет LevelTrace logging: фактический debug/trace-off provider preflight до live ещё должен быть подтверждён root, конфигурация reviewer не менялась. Реальные duration/reasoning volume/backend call telemetry08 не измерялись.

После исправления нужен новый hash baseline и независимый targeted regate. Новая модельная гипотеза не получает semantic PASS от wire/schema тестов; максимум3 прежних cases остаётся отдельным gate с verdict перед каждым следующим submit.
