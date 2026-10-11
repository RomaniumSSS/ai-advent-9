# План переработки качества полного чата

Контракт: [ARCHIVE_QUALITY_SPEC](ARCHIVE_QUALITY_SPEC.md). Лёгкий SDD/TDD без FSM:
существующий actions.jsonl, tracker и отдельные private run directories достаточны.

1. **Root / planner — зафиксировать входы.** Проверить worktree/branch/status,
   protected hashes, старую историю и index identity; сохранить baseline 15 ходов
   ссылкой/hash без перезаписи. Независимо собрать и source-audit новый holdout,
   закрытый для реализации. Значимые действия писать в существующий журнал без текста
   приватных вопросов. Модель роли и usage/cost — только фактически доступные значения.
2. **Sol — resolver RED→GREEN (AQ2).** Тестировать классы формулировок на других темах:
   локальный предмет с местоимением, коллективная ссылка, фамилия, короткое продолжение,
   acknowledgement, смена темы, действительно неразрешимая ссылка. Не лечить eval
   whitelist. Сохранить ID/хранилище/поведение reset и отсутствие скрытого retry.
3. **Sol — retrieval/context RED→GREEN (AQ3).** Разделить формирование кандидатов и
   выбор покрывающих аспектов вопроса. Собрать реальные source-grounded fixtures из
   открытого regression и отдельно synthetic boundary tests. Уменьшить метаданные,
   выбирать точные attributed spans, сохранять обе стороны сравнения/нужную историю.
   Выбрать честный бюджет из доступных локальных возможностей, не менять core.py;
   тестировать русский текст, JSON escaping, большой chunk, большое прошлое сообщение,
   весь prompt+schema/template/output reserve. Materialized refs должны совпадать с
   переданными spans, полный оригинал допустимо показывать дополнительно с пометкой.
4. **Sol — grounded generation (AQ4).** Уточнить prompt/контракт ответа: действия,
   отрицания, намерение/успех, точная атрибуция, частичный ответ/unknown. Не добавлять
   второй verifier-model или неограниченный agent loop. Сначала targeted offline,
   затем обычный regression API и source grading; сохранять before/after раздельно.
5. **Root / independent reviewer — real suite (AQ5).** Только после готового кода
   запустить замороженный holdout неизменным. Разобрать причину каждого FAIL:
   intent/retrieval/context/generation/validation, не путать их. После конкретных fixes
   повторить затронутые кейсы, затем итоговый combined run на одной code identity.
   Обновлять evidence, а не прежние результаты. Проверить нормальный шестизвенный
   service trace, early exits отдельно; latency/technical metrics отдельно от semantics.
6. **Luna → Sol → Astra, затем Root — готовность.** Независимое ревью требований,
   diff, реальных sources/answers и тестов; повторная проверка ошибок даже после первого
   PASS. Свежая browser/API проверка new/follow-up/ack/topic-switch/unknown/reload,
   состояние источников, protected hashes, private modes. Отчёт с per-suite score,
   ограничениями и human acceptance=pending; короткие todo/HANDOFF по результату.
   Локальный чат остаётся доступен. Публикация/коммиты не часть плана.
