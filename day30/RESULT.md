# Day30 — результат

Домашний локальный LLM-сервис на Mac M2/16 GiB: HTTP API поверх HTTPS,
браузерный чат и сетевой listener на `192.168.0.100:8080`.
Сдача по уточнённому [SPEC](SPEC.md): **локальные dry/record PASS; публикация и финальная доставка ещё выполняются**.
Код: публикация в GitHub main/day30 выполняется. Видео: готовый MP4 локально; загрузка в Drive выполняется.

Использован существующий profile12 `qwen3:8b-q8_0`, digest
`e56358ca25dd14db6853a9f68a92d717aaa6f0a94250a72d1a0f3d86a9f30130`.
Embedding `qwen3-embedding:0.6b`, индекс и история сохранены. Два последовательных
вызова одной локальной модели: selection — 1024 output/temperature0,
synthesis — 1024 output/temperature0.7/top_p0.8; native format, think=false,
context8192/template reserve512, deadline300с на стадию, retries0.

Проверки 12.10.2026:

- Полный offline suite: **151 тест, OK,30.887с**, `/usr/bin/python3`3.9.6.
  Mock/loopback проверяют auth,429/Retry-After,409, независимые budgets,
  таймауты, освобождение lock, историю и privacy; это не реальные ответы модели.
  Evidence: [151 offline / LAN preflight](results/assignment-delivery-preflight.json).
- [Свежий LAN preflight](results/assignment-delivery-preflight.json): main/demo
  HTTPS с CA+hostname, авторизованный state; настоящие отказы401 без/с неверным
  bearer,400 на501 символ,403 для чужих Host/Origin. Модель/context8192/rate6/60
  и серверные scopes `all`/`assignment` совпали. Проверено на том же Mac;
  второе физическое устройство — **NOT PROVEN**.
- Demo harness: [Luna](results/assignment-review-luna.md) → [Astra](results/assignment-review-astra.md). Независимые Luna→Astra проверки
  отделены от предыдущего [CODE12](results/review-history/review-astra-12.md).
- Dry: **PASS**, 3 новых содержательных ответов;
  record: **PASS**, 3 новых ответов. В каждом сценарии
  Day21 → follow-up в том же conversation → Day24 в новом; IDs уникальны,
  API/private receipts совпадают, завершённые разговоры перечитаны без inference.
  Живой busy probe: PASS — HTTP409 на активном первом запросе; отвергнутый запрос не запускает генерацию. Evidence: [Dry3](results/assignment-dry.json), [Record3](results/assignment-record.json).

Фактические числа только из этих новых receipts:

| Прогон/ход | terminal status | Время запроса,с | selection вход/выход | synthesis вход/выход | completed generation calls |
| --- | --- | --- | --- | --- | --- |
| dry1 · Day21 | done | 128.224 | 1648 / 39 | 769 / 154 | 2 / 2 |
| dry2 · follow-up | done | 124.199 | 1642 / 39 | 794 / 165 | 2 / 2 |
| dry3 · Day24 | done | 177.048 | 1357 / 39 | 981 / 368 | 2 / 2 |
| record1 · Day21 | done | 133.369 | 1648 / 39 | 769 / 150 | 2 / 2 |
| record2 · follow-up | done | 113.914 | 1642 / 39 | 794 / 156 | 2 / 2 |
| record3 · Day24 | done | 190.046 | 1357 / 39 | 981 / 446 | 2 / 2 |

Видео: 517.0 сс,1280×1000,H264/yuv420p, без аудио и ускорения;
проверка ffprobe, кадров и воспроизведения: **PASS — ffprobe/кадры/воспроизведение/privacy**.
Код/Drive/Sheet readback: publication readback ещё не завершён. Пользовательская приёмка pending.

Ограничения: качество дополнительного архивного пересказа не доказано.
[Actual12](results/live-private-12.json) — исторический runtime PASS163.639с,
done/partial,1source/2 completed generation calls и независимый **semantic FAIL**
из-за искажения модальности; immutable original/span/metadata PASS. Все15 completed
private queries и прежние failures сохранены без переоценки. Этот FAIL исключён
из gate исходного задания уточнением пользователя; refs/валидный JSON новых
assignment-ответов также не доказывают смысловую полноту.

[Completed restart12](results/restart-12-completed.json) и
[recovery12](results/recovery-profile12-completed.json) — датированное доказательство
сохранности27 прежних состояний и API readback последнего ответа. Новый restart
при сдаче не заявляется. Пиковая RAM, SLA, нагрузочный live429 и доступ из интернета
не измерялись; rate-limit429 подтверждён offline. Приватный корпус/индекс, веса,
credential, полные prompts/traces и исходные ошибки не публикуются.
