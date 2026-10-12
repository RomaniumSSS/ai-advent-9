# Day30 — независимое повторное review Astra

**Overall: NEEDS CHANGES** (первый проход 11.10.2026; последующее исправление ещё не проверено).

Reviewer: fresh Astra, не автор реализации/плана и не первый reviewer. Baseline: `b3e607e`, SHA-256 всех 20 файлов совпали с `results/code-baseline-final.json`; SPEC `cf6387f952e12f2660da4927e391cb653256578830a1f1cccd24e9d38119a2cf`.

## Обнаруженные ошибки

**P2 — `evidence.py:193` — follow-up теряет указатели на уже выбранные оригиналы.** Day30 возвращает `answer.source_refs` как evidence IDs (`S1.U1`), а fallback сравнивает с `source.source_ref` (`S1`). `answer.evidence_units` Day30 не создаёт, поэтому первая ветка также недостижима для обычных Day30 receipts. Даже при повторном нахождении того же оригинала `dialogue_focus.evidence_ids=[]`. Сопоставить cited `sources` по `evidence_id` и immutable span identity с новыми units; legacy chunk fallback сохранить лишь для legacy формы. Regression должен пройти реальный формат Engine answer, смену S-number при fresh retrieval и исключение соседнего чужого span.

Repro выполнен без inference и flock: Fake Engine → обычный ответ → follow-up. Вывод: `prior_refs=["S1.U1"]`, `prior_source_ref="S1"`, `fresh_ids=["S1.U1"]`, `focus.evidence_ids=[]`. Имеющийся test_followup проверяет history/fresh embedding, но не focus.

**P2 — `service.py:140–217`, `server.py:62–70` — на ошибке валидации теряются private trace и выполненные счётчики.** Engine накапливает budgets/prompts/response в локальном result и возвращает только после полной удачи. При исключении Store получает лишь status/error; реально завершившийся модельный вызов не остаётся доступен для диагностики. Наблюдается в отдельном live follow-up: receipt содержит `answer=null`, `metrics={}`, `invalid_model_response`, без частного diagnostic artifact. Сохранить частный snapshot до/при исключении с известной фазой, безопасным validation code, количеством выполненных вызовов и raw response; API/логи по-прежнему не должны возвращать raw trace. Это нужно, чтобы проверить и исправить конкретный отказ, не гадать и не повторять вслепую.

**P2 — `local.py:75–76` — timeout не ограничивает полное время provider call (A5).** `opener.open(..., timeout=300)` ограничивает ожидание очередной socket operation. Затем `response.read()` может принимать небольшие порции и продолжаться дольше300с, удерживая общий inference flock. Независимый read-only-to-product repro с временным loopback HTTP fixture: timeout0.08с, очередной байт каждые0.04с; запрос успешно завершился через0.474с. Живая Ollama/порты сервиса не использовались. Нужен абсолютный deadline на connect/headers/body, закрывающий конкретный сетевой вызов при истечении; без retries и без оставленного фонового клиента после освобождения flock. Regression должен проверить медленные headers/body и своевременный timeout, а не только исключение mock клиента.

## Проверка исправлений Luna и lifecycle

Самостоятельно прочитаны все runtime modules, UI/video runner и offline tests из baseline. Новый сервер ограничивает handlers семафором16 и отдельным абсолютным watchdog15s; обработка TLS перенесена из accept в worker, slot освобождается finally. Reviewer выполнил `/usr/bin/python3 -m unittest test_connections test_deploy_lifecycle -v` с `PYTHONPATH=day30:day30/tests`: **11 PASS**, 3.707s, exit0, CLT Python3.9.6. Это 4 настоящих TCP/HTTP проверки slow headers/body/capacity/release и 7 mocked launchd lifecycle проверок. Общий flock/live inference не затронут.

Оба замечания Luna по connection exhaustion закрыты кодом и targeted tests. Lifecycle helper корректно ждёт unregister и исчезновение prior PID, не bootstrap-ит после timeout/неизвестной ошибки и не повторяет bootstrap. Реальный controlled restart остаётся отдельным доказательством root.

Полный свежий system-Python suite pending; contended run не засчитан GREEN. Live private smoke уже имеет одну завершённую и одну отклонённую генерацию; семантика проверяется отдельно в private report. Публикация, видео и человеческая приёмка этим review не подтверждаются. Usage/cost reviewer не предоставлены.
