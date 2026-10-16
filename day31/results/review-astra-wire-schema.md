# Второе независимое ревью wire-schema patch

Дата: 2026-10-16. Reviewer: **gpt-6-astra**.

**APPROVED — код и локальные проверки узкого исправления.** Findings нет.

Самостоятельно прочитаны request builder в `provider.py`, полный локальный контракт `ANSWER_SCHEMA`, обе точки валидации в `assistant.py`, затронутые тесты, Q1 в recorder и `video/SCENARIO.md`. Прочитан отчёт Luna; его вывод об исправлении подтверждён собственным анализом.

`build_request` делает deepcopy и удаляет ровно `properties.source_ids.uniqueItems`. Прочие ограничения, strict schema, route/reasoning и политика запросов сохранены. Общая локальная ANSWER_SCHEMA не мутируется. Assistant проверяет исходный ответ до нормализации, поэтому повторные declared source_ids отклоняются, а не скрываются дедупликацией. Проверка после нормализации также сохранена.

Конкретный Q1 про три модуля Day17 совпадает в recorder и сценарии; меняется вопрос, не полученный ответ. Новая запись по-прежнему должна выполнять новые запросы и показывать реальный текст.

Свежий собственный прогон через `uv run --no-sync python -m unittest`: **3/3 PASS, 0.015 s**:

- `ProviderTests.test_wire_schema_omits_only_unique_items_and_local_schema_still_rejects_duplicates`;
- `ProviderTests.test_exactly_one_call_pinned_provider_schema_and_usage`;
- `AssistantTests.test_schema_is_enforced_before_and_after_source_normalization`.

Последний тест включает дубли настоящего доступного source_id, поэтому подтверждает отказ непосредственно в Assistant. Новых API calls: **0**, ключи и общий ledger не читались и не менялись.

Уточнение к формулировке первого ревью: сохранённый diagnostic относится к error.code=400 внутри ответа HTTP 200; его не следует описывать как доказанный HTTP status 400. Сообщение DeepInfra `Grammar error: Unimplemented keys: ["uniqueItems"]` доказывает несовместимость для этого конкретного нового GLM5.3-вызова. Причины прежних ошибок автоматически ему не приписываются.

**NOT PROVEN:** успешная облачная обработка новой схемы, полнота/точность будущих ответов и финальное видео. Изменённые лимиты отдельных comparison profiles не входят в этот узкий review; сравнение должно явно указывать их и считать finish_reason=length неуспешным завершением. Shared ledger и старые holds сохраняются.
