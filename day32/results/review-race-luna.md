# Day32 — точечное ревью GitHub SHA race fix

**Вердикт: APPROVED для просмотренного race fix.**

Проверены изменения `cli.poll()` и recorder watcher/tests. `poll()` валидирует base/head как полные SHA до fetch и загружает именно эти два объекта с фиксированного GitHub URL; изменяемый `refs/pull/N/head` больше не участвует. В recorder watcher весь результат `list(poll(...))` получают до `Runner`; ошибка чтения журналируется как `read_retry` с фазой и классом исключения, затем повторяется после паузы. Область retry не включает модельный вызов. После успешного чтения сохраняются обычные Runner dedupe и проверка повторного вызова.

Связанные офлайн-проверки прошли: `test_poll_fetches_validated_exact_api_shas_not_mutable_ref`, `test_exact_sha_fetch_survives_remote_reference_advance` и все 8 recorder guards — **10 PASS**. Race-тест использует локальный bare remote с продвинутой веткой и подтверждает, что анализируется SHA из API-снимка. В тесте poll retry ошибка чтения предшествует ровно одному provider-вызову; повтор Runner получает тот же trace без нового вызова.

Новых дефектов в этой области не обнаружил. Реальный GitHub fetch и paid calls не запускались, поэтому офлайн bare-remote race-тест не доказывает поведение GitHub upload-pack или live-trigger; новый dry-run остаётся отдельным подтверждением. Usage/cost этого ревью не измерялись.
