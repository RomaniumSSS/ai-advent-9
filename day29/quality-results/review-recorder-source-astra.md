# Независимое Astra review: canonical benchmark citations

**Финальный verdict: APPROVED.** Фактическая gpt-6-astra выполнила сильное ревью после Luna. Исправление соответствует реальному producer; открытых findings в этом bounded изменении нет. Fresh dry, отдельная запись и human acceptance ещё не подтверждены.

## Снимок

| Файл | SHA-256 |
|---|---|
| video/run_full_demo.py | `947477a172d8744b3396e7aa79d0b4a6b178f4ab8a9db2d60458c9495bbd8dc8` |
| Предыдущий recorder | `38b6e7761b65fead5d9d606a674590f841588033f7745a75d5fdec4dccf7e24d` |
| tests/test_full_demo.py | `466ebfd9bc263fde4ea0b604f54b1cba6a7fa2d080e93318917cb3b76670961f` |
| tests/full-demo-benchmark-source-evidence.json | `f3495cf9312ae50a8cb28d816748dffe778a45a234579bb9945def1606d77049` |
| Реальный benchmark API result | `ef16e7f1c347594a8175e4e05d051b54fae578988035e13c4f4f04b317e914cd` |
| Его исходный raw receipt | `671dc17cf5b75a66345720ce7031cb153ae74035a0564c530e6edecec173a07c` |

Public core неизменён `ffd03a0c5bc659e50783416c469c72d8f79f7d02a7d9a1309208c74875b2e24d`; app.py `5548e4febe572bbaac0432d38ffd0e6026acdb955e0b27e7501ed63c69cf8ef9`. Full core f1b62d97…/quality runner329a11f5… сохраняются.

## Причина и исправление

Прежнее предположение recorder о benchmark ID без двоеточия было ошибочным. `core.py:247–254` формирует source из canonical document_id; действительные ссылки — assignment:19 и assignment:20. `run_full_demo.py:81–82` теперь требует эти точные IDs и формат assignment:digits. Схема source/chunk/quotes и доступный контекст продолжают проверяться `core.validate_answer`; смешанные private selected по-прежнему запрещены. Исторические отчёты и failed takes сохранены.

## Что reviewer проверил самостоятельно

| Проверка | Результат |
|---|---|
| AST scope | PASS: кроме validate_benchmark, final AST точь-в-точь38b6 snapshot. |
| Реальный B без подмены | PASS: request6d8c5b0739da40899fb7f6bd49c079cf, исходные question/rid/selected/answer. Старый validator воспроизводимо отклоняет; final validate_benchmark принимает. |
| Actual producer → API | PASS: public_result исходного raw receipt точно равен сохранённому actual API result. Повтор materialize_references из настоящего raw model answer и selected точно воспроизводит answer/sources/quotes. |
| Профили и identity | PASS: unchanged validate_state соответствует трёхполевой public projection; model/digest/profile hash/options/index guards сохранены. Benchmark API не передаёт payload: его validator проверяет profile metadata, а не отсутствующее поле. |
| Full-chat producer | PASS для применимых реальных данных H05: identity, actual system/payload, materialize, chat_view и полный prefix validate_full до конкретного scenario-day gate проходят без изменения вопроса. H05 не имеет формулировки recorder, поэтому final day gate для этого receipt NOT APPLICABLE. |
| Store/API/UI contract | Прочитаны begin/finish/request/chat_view и full routes: running submission имеет conversation/request/question; terminal API сохраняет нужные поля и canonical sources. POST bodies/new/reset, pending states, source details/whole и DOM selectors соответствуют recorder. |
| Offline tests | Самостоятельно19 PASS; wrong/legacy/private source, missing source/quote, altered chunk/quote, identity/options, privacy, dry qualification и отказ fixture-only покрыты. |
| Evidence | Hashes RED/GREEN/browser logs сверены. Browser3-call PASS — заявленная synthetic fixture evidence, reviewer браузер не запускал и live qualification ей не приписывает. |

Среда Python3.14.0/macOSarm64. На всех executable проверках запрещены Ollama.request и socket.create_connection. HTTP/provider/generation/embedding calls reviewer0, серверы не запускались/не менялись. Implementation, dataset и gold не редактировались.

## Остаток исполнения

Первый failed dry012700: error,0submission/0request/0frames. Второй013100: error,1submission, в recorder item ещё submitted,4frames; настоящий raw receipt этого запроса done и сохранён. Оба проверены как исторические неудачные попытки; второй не считается успешным dry, уже выполненный вызов не исчезает из учёта.

Root может выполнить новый разрешённый dry с тремя свежими запросами на final SHA, затем отдельную свежую запись после qualify. Полный настоящий ответ сценария day11, его sources/privacy/support, итоговая qualification всех трёх ответов, видимость quality HTML, видео/кадры/decode и human acceptance остаются **NOT PROVEN** до соответствующих фактических проверок. Offline совпадение формата не доказывает качество будущего ответа. Новых quality tuning или дополнительных holdout этим отчётом не назначено.
