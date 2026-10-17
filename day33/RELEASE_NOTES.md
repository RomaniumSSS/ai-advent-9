# Day33 — TeamDesk support

[Видео Day33, 68.2 с](https://drive.google.com/file/d/1CNtHo7ruiEZpUN7VGUeeQiHJGXTPJYLt/view?usp=sharing). Загрузку и доступ «Anyone with the link / Viewer»
координатор проверил через UI. Пользователь ещё должен оценить результат.

Состав публикации — [PUBLISH.md](PUBLISH.md). Упомянутые локальные live/media artifacts
не входят в Git; их историческая оценка ниже не является опубликованным сырым evidence.

Ассистент объясняет проблему авторизации по контексту конкретного тикета:
неподтверждённая почта и истёкшее приглашение дают разные шаги и FAQ-источники.
При отсутствии диагностических данных сервер просит уточнение без вызова модели.

Реализованы независимый loopback UI, read-only MCP stdio, scoped CRM-доступ,
retrieval, проверка/нормализация ссылок и общий атомарный бюджет Day33+34.
Ошибки модели сохраняют безопасный visible response/usage для диагностики;
reasoning, ключи и заголовки не сохраняются.

Текущие проверки: **25 офлайн-тестов PASS**, Luna → Astra и targeted rechecks.
Robustness live (локально: `results/robustness-live/semantic-review.json`): 15 актуальных PASS
(7 Qwen + 8 gates без модели), оценка ассистентом-координатором, user_acceptance=false.
Первичный live FAIL (локально: `results/robustness-live/fresh-markerless-conflict.json`)
с выдуманным порядком проверок сохранён; после prompt-коррекции same-case и fresh
holdout PASS. Holdout-серия: 8 вызовов, $0.032384.
Новый dry (локально: `results/robustness-video-dry/result.json`) и
текущая запись (локально: `video/robustness-record-01/viewport.mp4`) PASS: 68.2 с, 1280×1000,
три семантических PASS и шесть просмотренных кадров MP4;
проверка координатором (локально: `video/robustness-record-01/semantic-review.json`).
Старое видео сохранено как историческое evidence. Сервер 8133 остановлен.

Дополнительные проверки Day33 с dry/записью: **12 Qwen calls, $0.050812**;
полные известные расходы Day33 **$0.064990**. Общий ledger при завершении Day33
(Day34 ещё ожидается): actual $0.181326 + unknown hold $0.037338,
остаток $0.781336; открытых запросов 0. Это датированный снимок, не обещание
неизменного остатка при дальнейших прогонах.

Добавлены консервативные уточнения при неоднозначной диагностике/расхождении симптома,
строгие вложенные схемы MCP, общий сетевой дедлайн и лимит ответа, проверка операторского
потолка расходов. Lexical gates и prompt не гарантируют все формулировки или injection;
mock не заменяет семантическую проверку Qwen. [Evidence и ограничения](RESULT.md),
[запуск через uv](README.md).

Исправлены TLS-среда запуска, потеря диагностики model errors, рендеринг отсутствующих
inline-ссылок и проверка русской словоформы в runner. Старые failure artifacts сохранены.
Семантическая корректность не доказывается одной проверкой citations; демо не production auth.
Код опубликован: [код Day33](https://github.com/RomaniumSSS/ai-advent-9/tree/day33-support/day33), [коммит `c6e54e2`](https://github.com/RomaniumSSS/ai-advent-9/commit/c6e54e2ffbb8ed0cab19393c32f3f22563933075).
VPS-размещение и пользовательская сдача не выполнялись.
