# T5 regression: предложение повторной проверки

**Авторизация нового запуска: NOT_GRANTED.** Первый live run остаётся A1 FAIL; его данные и оценка не изменены. Это regression на тех же2×12 разнообразных сценариях, не независимый holdout.

## Зачем повторять

Первый run:24 хода,23 provider calls, measured$0.0116924584 (public$0.0032485936/all$0.0084438648), unknown0. Потеря текущей цели в public5/all5/all12, потеря выбора SQLite и смешение сдачи с ответом инструмента в public12, необоснованный same-day критерий обсуждений в all10. Public8 source_key вместо source был правильно заблокирован строгим валидатором.

Локальный repair gate Astra PASS: явные task references добавляют актуальную цель/выбор в поиск; самостоятельные PostgreSQL/Берлин не заимствуют старую память; explicit day/date имеют приоритет. Генераторный контракт сохраняет пользовательский выбор, различает сдачу/результат, не требует same-day без явного периода и показывает точный JSON sources. Валидатор не ослаблен, старые ответы не переписаны.

## Предлагаемый предел

| Область | Ходы/новые поиски | Максимум provider calls | Верхняя оценка резервов | Новый cap |
| --- | --- | --- | --- | --- |
| public: только assignment:18 |12|12|$0.05408256|$0.06|
| all: тот же полный frozen snapshot, дни21–24/обсуждения |12|12|$0.05408256|$0.06|
| Всего |24|24|$0.10816512|два независимых $0.06|

Retries0. Видео сохранённых public результатов: толькоGET,0 extra provider/search calls. Это новый бюджет; остатки первого run не переносятся. Per-call reserve upper bound$0.00450688 по действующим byte/output/rate ceilings, не новая измеренная цена.

Frozen SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`. Code SHA `46e75e9f89df35a2f8fd6c3f97c762e7def338e6e0ab560532065350ce589415` — packed sorted filename→SHA mapping runtime Python/HTML/JS/CSS/requirements; snapshot в private/recheck-setup-02.json и synthetic-run-03/CODE-SNAPSHOT.json. Scenario SHA `2438f66008ce72ccb2f2e3c27b5e33ff86eacfbd5c049b04cf5a1a84ae650430`; формулировки прежние, добавлена метка regression.

## Готовность и доказательства

Отдельные private/live-public-02 и live-all-02: proposed cap$0.06 каждый, scope по одному, exact frozen SHA, approved=false/NOT_GRANTED, пустые отдельные ledgers, права0700/0600. Старые live-run-01/ledgers не переиспользуются. Ключи не копировались. Live servers не запускались; новых SSH/provider0.

Офлайн:29 app tests PASS3.683с +8 preparation PASS0.005с; privacy/preflight mismatch безPOST PASS. Fresh synthetic-run-03:24 verified mocks, public6 checkpoint, настоящий restart PID17601→18394, resume exit0;12 searches/12 mock generations на область, synthetic charge всего$0.00024. Synthetic-video-04 проверяет сохранённый public UI GET-only с all-marker archives рядом; запись exit0, browser methodsGET, counters12/12 и charge$0.00012 до=после, DOM checkPASS, новыхsearches/provider0; publicationNOT_APPROVED. Synthetic не доказывает качество новых реальных ответов.

После нового разрешения ожидается24-ходовый UI run с SHA/budget preflight обоих серверов доPOST, настоящий restart послеpublic6, архив и GET-only public видео. Ручная оценка проверит текущую цель/SQLite/формат, смысл и атрибуцию источников, подтверждение либо отказ по отсутствующим фактам; verified alone не PASS. Любой сохранившийся отказ/невалидный ответ остаётся видимым в оценке.

## Остановка

До нового ответа пользователя approved остаётсяfalse; отсутствие разрешения не обходится. Runner автоматически сверяет frozen/scenario SHA и scope; code SHA координатор повторно сверяет read-only проверкой непосредственно перед запуском. Любой mismatch, недостаточный бюджет, ошибки HTTP/сохранения/провайдера, unknown/interrupted/not_authorized или неясно отправленный запрос останавливают запуск безretry. Послеcheckpoint — только проверенный restart/resume с сохранённымиIDs; неоднозначную операцию не возобновлять автоматически. No_context/model_refusal/unverified сохраняются без исправления/повтора, являются ограничениями смысловой приёмки, а не основанием автоматического PASS. Предельное число запросов24, никаких дополнительных экспериментов в остатке бюджета. Публикация/commit/push/deploy не входят в предложение.
