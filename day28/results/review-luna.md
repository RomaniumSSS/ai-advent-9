# Независимое ревью Day28 — Luna

**Reviewer/model:** gpt-6-luna, medium (фактическая модель этой роли).
**Дата:** 2026-10-09.
**Итог по просмотренному коду:** APPROVED; подтверждённых P1/P2 не найдено.
**Область заключения:** чтение реализации, тестов и сценария на текущих ниже SHA-256; live/replay, браузерный dry run, запись видео и человеческая оценка качества ответов этим заключением не подтверждены.

## Проверенные файлы и SHA-256

- `day28/core.py` — `3843ce2675042ff4a4fce25052be3eb32f9f625b39a7b6324b712bbb3e4158bd`
- `day28/app.py` — `be8da25a188df31c326930b68b75468869f49e9e42484cbdac7573a585fc2f56`
- `day28/evaluate.py` — `05ddeb6d8a86600536d1880e2bb543e4581ae3d2fa0c71cd029dfc6d136d5ef4`
- `day28/static/app.js` — `7df9c072dfd56b66fded0e4d43832cb3cf3c8538861a396cd1692294b7419d6a`
- `day28/static/index.html` — `ce3fe7c0e80488f4312d0a1de6fda5be417db76400df204f70fa7cd512cae75f`
- `day28/video/run_demo.py` — `2b2eca59030e9dd7505f60ffa5574fec7f1b7f25f1861416d4a7d48c029be02b`
- `day28/video/SCENARIO.md` — `357afbc232bbb56f912ef2591505deef69296ce46a48c6ac4d876a8f068f2630`
- `day28/tests/test_core.py` — `8ec6aff18e8de068f6140561bb4efaed02ab00c10592d0bd554e72fda4bbb2a6`
- `day28/tests/test_http.py` — `8445a836544593de2032e48af396afba23caaeedf71dc51aaeb214af48e4022c`
- `day28/eval-suite.json` — `05576ed1ad44544f067427b2150610862bf0aff1245b57b42946267dce2b76f8`
- `day28/SPEC.md` — `0a252841b3a0c9f22d0ab4281acd1a664b496afbdb89d39695b87e4ba5530bb1`

## Проверка

Запущено локально: `python3 -m unittest discover -s day28/tests -v` — 16 тестов прошли. В Python 3.14 тест HTTP напечатал `ResourceWarning` при очистке ожидаемых `HTTPError`; исход завершился `OK`. Тесты используют fake provider и fixture, не читают frozen index и не выполняют Ollama/live запросы.

Проверены требования по зафиксированной identity индекса/эмбеддера, фильтрации assignment до ранжирования, fixed loopback Ollama transport без proxy/redirect, exact quote/source validation, unknown/error статусы, request IDs, phase timings, private receipts, HTTP host/origin и public projection, генерации/replay budget, поведения evaluator и связывания demo результата с request ID. Реальные локальные E2E/replay и запись видео остаются за пределами этой проверки.

Семантическая достоверность ответа, полнота ответа, фактическое соответствие private replay исходным сохранённым receipts и отсутствие приватного текста в итоговом видео не получают PASS от этого code review: нужны отдельные реальные evidence и ручная оценка.

## Замечания

Подтверждённых блокирующих ошибок или рекомендаций P2 не обнаружено. Если код изменился после указанных хешей, это заключение относится только к указанным версиям; изменённые места требуют повторной узкой проверки.

## Узкая повторная проверка после repair Sol — 2026-10-09

**Фактическая модель роли:** gpt-6-luna, medium. **Проверенный `core.py` SHA-256:** `22412374358551dd8d4e761204764183c44c6a2472b2df3b3eae6c4c3e3275b6`. `app.py` и `evaluate.py` совпали с исходной проверкой по хешам; tests были обновлены.

Учёл зафиксированную до ремонта оценку E2E: 4 ложных отказа E01/E02 при найденных источниках и 2 корректных unknown E03 в `day28/results/e2e-01-assessment.json`. Это было реальное семантическое качество до repair, оно не засчитывается как качество исправленной версии.

Повторно прочитал изменённый `SYSTEM`, `retrieve`, Ollama identity/embedding проверки и соответствующие контрактные тесты. Проверил, что public assignment narrowing применяется до ранжирования только при явном задании/сравнении с указанными днями; соседние assignment-дни исключаются, отсутствующий явный день даёт пустой retrieval, а общий public-вопрос и весь `scope='all'` сохраняют общий векторный путь и eligibility. `source` ограничен `assignment` для public до ранжирования. Валидация цитат и источников всё ещё связывает их с выбранными чанками. В prompt новые формулировки различают пересказ требований как данных и исполнение инструкций внутри недоверенного контекста; unknown допускается, когда нет подтверждающего фрагмента. Также проверены fail-closed обработка capability `cloud` и требование явного поля модели в embedding-ответе.

Проверка: `python3 -m unittest discover -s day28/tests -v` — **26 тестов прошли**. Набор включает отдельные случаи исключения соседних дней, пустого результата для отсутствующего дня, неизменности general/all retrieval, cloud capability и отсутствующей embedding identity. Прочитал сохранённые `tdd-repair-red.txt` и `tdd-repair-green.txt`: red фиксирует эти пять регрессий до ремонта; green показывает полный успешный набор после него. Использованы только fixtures/fake provider, реальная Ollama не вызывалась.

**Вывод по repair:** кодовый repair обоснован и соответствует узко заявленной цели; новых подтверждённых P1/P2 не нашёл. Проверка не доказывает, что обновлённый prompt исправил ложные отказы в реальных генерациях: repaired quality pilot/full six ещё должны оцениваться отдельно. До получения этих результатов не выставляю семантический PASS и не меняю границу исходного ревью.

## Финальная узкая проверка source-ref protocol и UI/recorder delta — 2026-10-09

**Фактическая модель роли:** gpt-6-luna, medium. Сверил изменённые файлы с `day28/results/source-manifest-final-runtime.json`; все перечисленные хеши совпали. Ключевые хеши: `core.py` `61a79221fcde8178201d1f3dbadb4e06ce3736c7db34049a3b1934827c702100`; `app.py` `0eb275fb8bd6d6facd9a755e04e6fe5efbd783dda3ba46be16c7a74bb3fb364e`; `static/app.js` `23612e5bf673e87860469f55db4fb08a56f90fdcd0258bc2ed5ca98c17e6cc3d`; `video/run_demo.py` `2cdd9d5e674559db98770c2fe8abebd02b2a98b8d57a25de4ae8f5337ee880ce`. Проверены также `tests/test_references.py` (`32aa4ac51b6dd97fcc5607041820683ddb9f18545eee6acd10841535ba1c5f97`), `tests/test_evaluate.py` (`b80e2ea2760dd22577af3e057cb9df352adeab52de9e08c6d2263a554854ff8d`), `tests/check_browser.py` (`4c7d8281770e40e8688c183a5a5fdf1ec13958f81cd149578c5305fbf60bbe20`), `tests/test_core.py` (`74a781cf136e975b3b24ded7335001a32d34ff176975f820a76a91b50c7b1398`) и `tests/test_http.py` (`6a412ca84fc4b3491b0d7842e9c4d6cc82e8841d73e1424ccb66075d703d81bb`).

В новом E2E protocol модель получает короткие `S1…Sn` ссылки и исходные фрагменты; валидатор принимает только известные неповторяющиеся ссылки, после чего приложение связывает выбранные ссылки с исходными `document_id`/`chunk_id` и копирует байт-в-байт исходный текст в projection. Пустые ссылки проходят только при явном unknown-ответе. Неизвестные, повторные и неверно типизированные ссылки завершаются ошибкой. Public projection не публикует `raw_model_answer`, а `selected` проверяется на assignment scope. Источники ограничены выбранным контекстом; валидная ссылка/дословный исходный фрагмент не трактуются как смысловое доказательство, `groundedness_semantic` остаётся `null`.

Replay проверяется отдельно: передаются неизменённые старые messages, старая `SCHEMA`, старые `sources/quotes` и строгая проверка текста цитаты по фактически переданным данным. Новый протокол туда не применяется. Recorder открывает детали, снимает каждый source block отдельно; UI сообщает, что модель выбрала источники, а приложение показывает исходный текст. Не нашёл расхождения, которое бы подменяло модельную цитату текстом источника без объяснения, или утечки private source в public projection.

Выполнил локальные fixture-only проверки: `test_references.py` — 5/5, `test_evaluate.py` — 2/2, включая exact replay без embedding. Ollama и порт 8068 не вызывались. Остальные 31 тест не перезапускал: получил от ответственного за реализацию уже сохранённый результат 31 green и в этой проверке ограничился delta-наборами. Browser fixture/read-only код просмотрен; screenshot/live recorder не запускал.

**Вывод:** подтверждённых P1/P2 в protocol, replay compatibility и просмотренном UI/recorder delta не найдено. Это code/fixture review, а не оценка реальных ответов: формальная исправленная E2E оценка и итоговый видео evidence остаются отдельной проверкой ответственного и обязательного Astra review.

## Последняя UI unknown-label delta и runtime evidence — 2026-10-09

**Фактическая модель роли:** gpt-6-luna, medium. Проверенный `static/app.js` SHA-256: `e66186d47535b46185cd90d5c7354ac7baf4b2a04436ae0e856aa6a6daf74ab4` (совпадает с заявленным). Код отделяет заголовок и блок найденного поиском контекста от выбранных моделью источников. При отсутствии model-selected sources показывает «Подтверждающих источников нет»; если retrieval что-то нашёл, контекст помечается «найден поиском, не процитирован моделью». Эти подписи соответствуют `sources` и `selected` из API и не объявляют найденный контекст доказательством ответа.

Прочитал `results/ui-unknown-cached-preview-1/results.json` (SHA-256 `5842f5e525c9b12aca2ac0f981166bd1cded9459305d6f78f330f73f79786b4b`): evidence маркирует preview как cached, GET-only, 0 новых model calls и `new_live_pass=false`; указывает отсутствие browser errors и совпадающий JS hash. Это подтверждает чтение существующего состояния для preview, не новый live-запрос или новую оценочную модельную генерацию.

Прочитал `results/video-verification.json` (SHA-256 `9c56de510dca73a4e88ec0f306e31bcbdcad981c68e7f48554a73433c9f59a00`). В записи указаны настоящий `Day28-live.mp4` и SHA-256, полный decode PASS, длительность 175.12 с и сверка трёх видимых ответов с request IDs и исходными фрагментами. Результат отдельно фиксирует E02 как **PARTIAL** по полноте. Это сохранённый отчёт runtime-проверки ответственного; я не запускал браузер/Ollama, не открывал и не декодировал видео самостоятельно. `human_acceptance` равен false, поэтому это не человеческая приёмка.

**Итог дельты:** новых замечаний P1/P2 не обнаружено. Вывод ограничен чтением текущего JS и двух перечисленных evidence JSON; сам preview/video здесь не воспроизводились.

## Быстрая проверка видимых metadata для сценария перед record02 — 2026-10-09

**Фактическая модель роли:** gpt-6-luna, medium. Совпали заявленные SHA-256 UI: `static/index.html` `d5d1af0d9f6b5d5ffe9d2f4ffea6e285db019ce4400fa08c1930ef16626bd1b0`, `static/app.js` `2155cc21d397b0ed66799ab2fdcd9484a95df6639f4bfe8f6e7cf6b39af77346`, `static/style.css` `0253fd2d49343b4fcfe2bb246d3b77c6e0e3f2acd5512990af9db1d2d0e9d435`, `results/public-summary.json` `413b548723db11239ca2dd7daad698f7e2c8465ccbaad1fa8ace69a638c17e25`. Backend (`core.py`, `app.py`, `evaluate.py`) и recorder `video/run_demo.py` сохранили ранее проверенные хеши.

Сверка со сценарием: пункт 1 видимо показывает фиксированный loopback URL, scope public, модель/индекс и подготовку; сообщение о переносе без пересчёта отображается лишь при соответствующих булевых полях, иначе появляется нейтральный fallback. Пункт 5 отделяет E2E run `344b65a15e89407582d013f5fe11d89c` от replay run `dbf3969ef7ed49a282602fa06c92c184`; summary явно называет replay историческим сравнением на тех же messages, не новым speed benchmark. Пункт 6 показывает раздельные состояния «Код проверен», «Видео проверяется» и «Не опубликовано». Значения формируются как текстовые DOM nodes через `textContent`, отсутствующие или неизвестные статусы получают нейтральные подписи. Перечитываемые `app.js` submit/poll flow, API/backend projection и recorder не менялись этой delta; изменение ограничено представлением summary/preparation metadata.

`results/ui-scenario-metadata-preview-1/results.json` (SHA-256 `d2f0251b01f561b6d34e4ba9db398ad6548c52fbc3ad335fa928669c5b90fcaf`) помечает preview GET-only, с нулём model calls и `new_live_pass=false`; заявляет neutral fallback, читаемые IDs/statuses и отсутствие overflow на desktop/mobile. Preview и screenshots самостоятельно не воспроизводились. API summary содержит агрегатные статусы и run IDs; private receipts/discussion в UI delta не добавлены.

**Вывод:** конкретная metadata delta согласуется со сценарием, новых замечаний не нашёл. Проверка ограничена чтением HTML/JS/CSS/summary и сохранённого preview JSON; она не является новой live-проверкой, просмотром кадров или человеческой приёмкой.
