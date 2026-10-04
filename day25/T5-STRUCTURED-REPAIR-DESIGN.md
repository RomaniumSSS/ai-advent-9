# T5: attribution/comparison — локальный дизайн после live04 FAIL

04.10.2026. Live04 механический отчёт/GET-only видео завершены, собственные8053/8054 остановлены; Day24 не затронут. Astra: A1 FAIL (all7/all10), public9/12/all4 NOT PROVEN. Raw live01–04 и оценки не менялись. После live04 новых provider/SSH calls0. Пятый live не готовится.

## Диагноз

All7: assignment:22 действительно передан и связан с message_id4154. ID4082 тоже передан, но принадлежит assignment:21. Проверка «ID существует где-либо в контексте» недостаточна: нужна привязка конкретного chunk/day/message. Citation validator проверил цитату, но не произвольное утверждение об ID в answer.

All10: переданы assignment:24/22/23 и два discussion чанка (day22/day2). Условие о прямом упоминании дня24 в обсуждении не следует из запроса. Сравнить аспекты должен ассистент. Повторное усиление инструкции не обеспечило правильный результат, поэтому третий аналогичный prompt patch не выбран.

## Наименьший проверяемый структурированный контракт

| Часть | Предлагаемый инвариант | Что остаётся смысловой оценке |
| --- | --- | --- |
| Атрибуция | Типизированная ссылка `{chunk_id, message_id, day}` проверяется по конкретному transmitted snapshot/message_part с single_member attribution; UI берёт metadata из snapshot | Правильно ли модель выбрала источник для вывода |
| Machine IDs в тексте | Не выводить свободные machine IDs из model prose; показывать их только из проверенных references/metadata. Legacy буквальные message_id/ID mentions отклоняются, не переписываются | Даты/авторы и неявные ссылки в произвольном тексте требуют review; regex не полный анализ языка |
| Сравнение | Для требования versus discussion обязательны непустые rows `{aspect, requirement, discussion, relationship, analysis}`; обе стороны имеют typed ref и exact quote из соответствующего message_part; source roles assignment/discussion проверены | Поддерживают ли обе цитаты заявленную связь и содержательно ли выполнено сравнение |

Day equality между сторонами не требуется: day24 requirement может сравниваться с day22 discussion, если содержательная связь обоснована. Явный current date/day/scope продолжает ограничивать retrieval; этот прототип их не меняет. Для полного сравнения relationship принимает supports/supplements/differs. При нехватке контекста отдельный tagged variant `status=insufficient_context` содержит aspect, available_evidence, missing_sides и reason; отсутствующую сторону не требуется выдумывать. Ни enum отношения, ни reason сами по себе не доказывают правильность смысла.

## Офлайн прототип и evidence

`validation/structured_prototype.py` — изолированный prototype, НЕ импортируется application/generator. `test_structured_prototype.py`:7 тестов PASS0.011с, macOS/Python3.14; network/subprocess запрещены; compile/diff PASS.

- Exact saved all7: reference assignment22→4082 отклонён, assignment22→4154 принят; metadata renderer возвращает day22/4154 из snapshot. Raw item не меняется. Legacy answer с free message_id отвергнут proposed narrative rule.
- Exact saved all10: отсутствие rows отвергнуто; synthetic row с requirement24/discussion22 и подлинными quotes проходит структуру, wrong quote/неверная source role отклоняются. Synthetic analysis явно помечен тестом, не является новым корпусным выводом и не оценивается как semantic PASS.
- Foreign chunk, неверный day, ambiguous attribution и bool вместо ID fail closed.
- Runtime SHA/file map совпадает с live04 snapshot: приложение после прогона не менялось. Предыдущие33+8 tests относились к этому же runtime.

## Область реализации и ограничение

Надёжное включение потребует согласованного изменения generator JSON schema, parsing/validation/terminal invariant, renderer и offline HTTP/UI tests. Сегодняшний schema допускает только answer/sources/quotes; скрыто добавлять rows или атрибуции было бы несовместимым изменением. Поэтому прототип не активирован и не выдаётся за runtime fix. Возможен отдельный минимальный этап «typed attribution + structured comparison» с независимым gate, без новых платных вызовов до решения о проверке.

Даже такой контракт блокирует структурные ложные привязки/пустое сравнение, но НЕ гарантирует верный смысл analysis. Семантическое сопоставление, полнота и поддержка выводов источниками остаются обязательной ручной/независимой оценкой; подлинность цитат не заменяет её. A1 и прежние NOT PROVEN не закрыты.

Остановка — root review дизайна и области. Никакого пятого live, автоматического retry, commit/push/deploy/publication.

## Четыре уточнения после review Astra

- Free machine IDs проверяются во всех model-authored отображаемых текстах: aspect/analysis, aspect/reason в insufficient branch, quotes. Structured IDs отображаются только через validated metadata. Regex по-прежнему покрывает явные message_id/msg_id/ID mentions, не любое неявное числовое утверждение.
- Day строго positive int или None; message_id строго positive int. Bool/float/string/zero/negative отклоняются, неверный day versus snapshot тоже. Snapshot day/message metadata также не принимаются через bool/float numeric equality.
- Validator и renderer используют один resolver, включая single_member и exact quote: renderer не может выбрать первый ambiguous/другой text part того же ID. Тест с несколькими parts проверяет правильную дату выбранной quote-part.
- Отдельная insufficient_context ветка допускает одну подтверждённую сторону либо отсутствие обеих; available roles и missing_sides согласованы, available refs проверены, пустой/ложный missing set не проходит. Не требуется выдумывать обсуждение для полноценной строки.

7 targeted tests PASS0.011с; compile/diff PASS. Runtime integration отсутствует, raw не менялись, provider/SSH0. Семантика analysis и достоверность причины insufficient-context явно NOT PROVEN: структурная полнота не доказывает связь, а missing side может требовать проверки релевантности реально переданного контекста.
