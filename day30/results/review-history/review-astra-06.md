# Day30 — independent Astra CODE review, protocol06

**CODE: APPROVED, baseline06.** Существенных дефектов в замороженной реализации не обнаружено. Actual06: два runtime PASS, два delivered semantic FAIL; gate06 FAIL. Исторические FAIL01–05 сохранены; rejected candidates не пересмотрены новым renderer.

Baseline `results/code-baseline-06.json`: 31 hash, base b3e607e, все независимо сверены без расхождений. Нормативный источник `results/review-history/SPEC-protocol06.md`, SHA `88bdd2dfa9fe2ac352529524a479286bcf4988d2d8cd94ebafa7088228bc0f2e`; архив также проверен. Редакция явно заменяет прежние model anchor/missing правила; отдельное человеческое утверждение SPEC не заявляется.

Самостоятельно прочитаны protocol.py, изменённый service.py, связанные evidence/budget/API/Store участки и revised fixtures. Model projection содержит только essential metadata и полный неизменённый unit.text один раз; synthesis добавляет evidence_role. Opaque backend identifiers/offsets остаются backend. context_ids фильтруются по фактически переданным units, исходная metadata не переписывается. fit_prompt пересобирает projection при whole-unit pruning; внешние циклы обновляют allowlist, mappings, coverage и schema до отправки. История остаётся только пользовательскими вопросами; dialogue_focus передаёт указатели, не старый ответ.

Point validator принимает ровно aspect_ids/evidence_id/text. Proof должен сохраниться после pruning и относиться к каждому указанному аспекту; background, unknown и cross-aspect IDs отклоняются. Quote/start/end private provenance берутся из полного immutable unit, а не model output. Модельные quote/anchor/offset fields отвергаются. Backend M объединяет partial/none, аспекты без valid points и doubtful; doubtful допускает только effective-full IDs и может лишь понизить полноту. Пустые points сохраняют local unknown. Вывод, P refs, лимиты длины, duplicate keys и public API shape остаются проверяемыми отдельно от смысла.

Private trace содержит protocol06, final sent projections/schema, order arrays, исходные full units, point spans и derived M. Public receipt исключает trace/query. Raw failure diagnostics и двухстадийные counters сохранены; никаких retries/дополнительных calls не добавлено. Новый wire order points→doubtful_aspect_ids→conclusion и aspect_ids→evidence_id→text проверен через реальный Ollama.request с HTTP fixture. Canonical state/prompt serializer, provider ordered serializer, модель/digest/options, tokenizer, retrieval, server/UI/deploy не изменились относительно baseline05.

Независимые проверки `/usr/bin/python3` (CLT3.9.6):

- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_protocol06 test_ordering05 test_selection03 -v`: 18 PASS за2.068s.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_protocol03 -v`: 10 PASS за0.020s, включая multi-iteration pruning.
- Store/public_receipt на временных копиях всех12 прежних state files: bytes неизменны, private trace исключён; actual state не изменялся.

Эти проверки используют fake models, чистые функции и ephemeral loopback HTTP; общего live flock/inference нет. Прочитаны Sol logs: targeted10 PASS0.017s, linked63 PASS6.212s, full102 PASS20.294s. Полный suite reviewer не дублировал. `protocol06-offline.md` честно отличает intermediate RED от отменённого anchor draft: десять NameError не выданы за десять различных дефектов baseline05. Revised negatives продолжают проверять proof/context, duplicate JSON, conclusion, unknown, output lengths и bookkeeping по новому контракту.

Код готов к предусмотренному controlled restart и максимум трём свежим прежним private вопросам без retry. Structural/provenance PASS не подтверждает смысл: attribution, действия, конкретика, числа, отрицания, план/результат и причинность требуют независимого сравнения новых ответов с originals. После любого runtime/semantic FAIL зависимые public шаги останавливаются. Человеческая приёмка и второе физическое устройство pending/NOT PROVEN.

## First actual06 semantic checkpoint

Первый доставленный ответ done/partial,2 completed chat/222.658s. Независимое чтение всех3 original spans/metadata подтвердило точный provenance, но summary превратил желаемое свойство будущего применения в наблюдавшийся факт. Это semantic FAIL по A3, несмотря на корректные code-derived missing и wire order. Подробности только в `private/semantic-review-06.md`; безопасный aggregate — `semantic-summary.json`. CODE approval сохраняется отдельно. Второй запрос был принят до этого заключения и ещё не оценён; первый FAIL уже останавливает зависимые public шаги.

## Final actual06 checkpoint

Оба доставленных ответа независимо проверены: runtime2/2 PASS, semantic0/2 PASS. Второй ответ смешивает сведения разных originals под одним cited proof и добавляет неподтверждённую последовательность в conclusion. Все6 occurrences фактически переданных originals и metadata exact (3 unique units); API answers совпали с internal receipts. Structural/provenance/M/order и budgets исполняются по SPEC, но A3 фактически нарушен. Driver остановлен до третьего запроса; уже принятый второй завершён без retry. Третий transfer не запускался.

Все31 hashes повторно совпали после live. Restart06 сохранил12 старых state files, CA/hostname verified, auto-replay отсутствует. CODE APPROVED остаётся отдельным вердиктом; общая SPEC conformance FAIL. Отчёты: `private/semantic-review-06.md`, `semantic-summary.json`, `implementation-validation.md`. Новая thinking/profile гипотеза этим review не выбирается; public dry/record/publication не готовы.
