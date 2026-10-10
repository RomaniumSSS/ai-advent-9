# Quality experiment — первое независимое ревью

**Вердикт: NEEDS CHANGES.** Разделение A/B, gold, budget envelope, model identity, locks, приватные checkpoints и frozen subset выглядят согласованными с рабочим контрактом. Нашёл один пробел в проверке ответа B: repair без единой ссылки может быть признан recheck-ом принятым, даже когда текст утверждает факт.

## Замечание

🟡 **[WARNING]** `day29/quality_eval.py:205-208` — валидатор repair-пayload проверяет форму, тип refs, принадлежность ссылок доступному контексту и дубликаты, но пропускает пустой `source_refs` при содержательном ответе. Триггер: critic выдаёт `repair`; repair возвращает `{"answer":"Факт без подтверждённой ссылки.","source_refs":[]}`; recheck отвечает `accept`. Воспроизведение через `validate_response` и `run_b` без сетевых вызовов дало `empty_ref_candidate_valid=True` и итог `accepted_by_recheck`. Это расходится с baseline-контрактом `core.validate_answer`, который допускает ответ без ссылок только при явном неизвестном/недостатке сведений. Повторно применить к B ту же структурную проверку, включая правило для пустых ссылок, либо вынести общий валидатор A/B; добавить тест с фактическим ответом без refs и контрольный случай с корректным unknown.

## Проверки и границы

Запущено `python3 -m unittest discover -s day29/tests -p 'test_quality_eval_*.py' -v`: **28 focused offline tests PASS**. Дополнительный синтетический repro использовал локальные функции валидатора и парного протокола; Ollama, embeddings и реальные данные не вызывались. Указанный frozen SHA `quality_eval.py` совпал с прочитанным файлом.

Не проверял приватные кейсы/gold и не подтверждаю их качество или происхождение: это отдельный Astra/root audit. Не запускал pilot, выбранные пять вопросов, warmup или какой-либо реальный вызов. Поэтому качество ответов, фактические stage times и human acceptance остаются непроверенными. Статический просмотр кода не подтверждает реальное поведение локальной модели.

## Снимки прочитанных файлов

SHA-256 сверены после тестов и воспроизведения; код не менялся.

```text
day29/QUALITY_EVAL_SPEC.md  62ea7145a6307e4eb9de47c488c14a9649197f4a2dda89145f1aa71b51a503e2
day29/QUALITY_EVAL_PLAN.md  2d0ffe7242248a52dacfc4ab6b641a99e302ddb807258c541acf2392f1f5f668
day29/QUALITY_EVAL_README.md  b086738cb7f30dfbff51a37e9646be0a1bc6817000af77a5d157024ededaf05a
day29/QUALITY_EVAL_TASKS.md  80ab21be7a0e79b0ec5f9d48204abaca2f85586ae840dec646e093815e120ed8
day29/quality_eval.py  f8d205afd109620072876437ae2ff0e89936e711af196ad5573e293486c2331c
day29/tests/test_quality_eval_protocol.py  751818837581c578fcbac4effcf26ce26eaf52a6b68531cc1225a7d6fc5163ce
day29/tests/test_quality_eval_failures.py  4523b70d08e043312ee7a2aaf241321c42d318214ac07e154f59bdac6286e956
day29/tests/quality-evidence.json  7ccbd86545ffdfba75e759687827085d90f11bf93ccc26196ad03ddf47efcb99
```
