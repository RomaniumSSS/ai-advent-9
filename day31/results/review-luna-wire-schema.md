# Узкое ревью wire-schema compatibility patch — Day31

**Reviewer:** gpt-6-luna
**Вердикт:** APPROVED для обхода подтверждённой несовместимости `uniqueItems` на отправляемой схеме.

## Findings

Замечаний не найдено. В `results/live-core-delivery-20261016/glm53-bounded-error-diagnostic.json` сохранена причина исходного сбоя: DeepInfra ответил HTTP 400 с `Grammar error: Unimplemented keys: ["uniqueItems"]`. `build_request` теперь делает глубокую копию `ANSWER_SCHEMA` и удаляет только `properties.source_ids.uniqueItems` из копии для provider wire request. Полная локальная `ANSWER_SCHEMA` сохраняет `uniqueItems: true`; Assistant по-прежнему валидирует полученный JSON этой схемой до и после нормализации источников. Следовательно, несовместимое provider-ограничение не ослабляет локальный запрет повторяющихся `source_ids`.

Регрессионный тест сравнивает всю wire schema с исходной схемой за вычетом ровно этого ключа, проверяет неизменность исходного объекта, строгий режим и отклонение локальным валидатором ответа с повторяющимися ID. Изменение не затрагивает профиль, маршрут, тарифы, резерв ledger, retry или fallback. В recorder и `video/SCENARIO.md` Q1 одинаково формулирует конкретный вопрос про три модуля Day17; это согласованное изменение сценария, не часть provider-патча.

## Проверки

- Самостоятельно запустил `.venv/bin/python -m unittest day31.tests.test_provider day31.tests.test_assistant.AssistantTests.test_schema_is_enforced_before_and_after_source_normalization -v`: **21/21 PASS**, 0.861 s.
- `git diff --check` завершился успешно.
- Проверил исходный диагностический JSON, фактический request builder, локальную валидацию Assistant и формулировку Q1 в recorder/scenario.
- Новых API вызовов не выполнял. Тесты доказывают локальное формирование схемы и валидацию, но успешная обработка изменённой схемы облачным endpoint после патча пока **не подтверждена**.
