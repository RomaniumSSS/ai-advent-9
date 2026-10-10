# Day29 — задачи и доказательства

Требования: [SPEC](SPEC.md); протокол: [PLAN](PLAN.md). Статус 10.10.2026:
код, 45 офлайн тестов, фактическая оценка, dry-02 и record-02 завершены;
локальная поставка готова, независимый аудит APPROVED / SPEC SATISFIED (43 PASS). Автономное продолжение
поручено пользователем; формальное
подтверждение текста спеки не получено и не является отдельным выдуманным событием.

## Подготовка

- [x] Проверены корень/ветка `day29-local-optimization`, AGENTS/CLAUDE и актуальные
      части todo/HANDOFF; основа `ca9058411363c1815793c80e2f3a778e52674ad3`.
- [x] Выборочно изучены Day28 SPEC/core/eval-suite/RESULT и две AICODE-NOTE.
      Слабость E02 — семантическая полнота, при валидных ссылках.
- [x] Написан один пакет SPEC/PLAN/TASKS/video/SCENARIO до реализации.
- [x] Сохранены свежий preflight среды, identity read-only индекса и моделей;
      отдельная проверка наличия/пригодности альтернативного квантования.
- [x] В action journal зафиксированы реальное разрешение пользователя и роли;
      phase/status/evidence, без невыданных approvals, usage или стоимости.

## TDD и минимальный код

Каждая группа: сначала запуск RED на существующей исполнимой заготовке, причина
падения и команда в `tests/tdd-*-red.txt`, затем минимальная реализация и GREEN.
Моки не являются доказательством реальной модели или качества её текста.

- [x] **Профили/payload:** baseline передаёт исходные options, think=false,
      точный SYSTEM и schema; T/M/C/P меняют ровно заявленный фактор; ни скрытого
      fallback, ни незаписанного retry; фактический digest обязателен.
- [x] **Индекс/изоляция:** чужой SHA/generation/embedding digest/dimensions
      блокируется; SQLite действительно read-only; public фильтруется до поиска.
- [x] **Сопоставимость:** изменённые текст, порядок чанков, source map, вопрос,
      prompt вне выбранного профиля или model family дают явный mismatch.
      Сохранённые baseline-фрагменты и SYSTEM равны оригинальному контракту.
- [x] **Бюджет:** schema/template/output reserve учитываются; слишком малый ctx
      отклоняется до HTTP, snapshot не обрезается; observed overflow/length — error.
- [x] **Ответы:** неизвестные/повторные refs и невалидный JSON отклоняются;
      materialization побайтно берёт оригиналы; empty retrieval/unknown не вызывают
      выдуманных источников. Смысловую полноту не подменять форматом ответа.
- [x] **Режимы/ошибки:** холодный запуск требует подтверждённой выгрузки; warm
      требует конкретного прогрева и присутствия модели; timeout/обрыв/reload
      не превращаются в успешный замер. Все receipts имеют уникальные IDs.
- [x] **Последовательность:** второе удержание общего/Day28 lock блокирует
      inference и unload; освобождение после ошибки не оставляет вечный busy.
- [x] **Метрики:** ns→s и tok/s, нулевые duration, missing/null, отсутствующий PID,
      смена runner PID, несколько samples/RSS max; `/api/ps size` не идёт в RSS.
      Cold/warm и ошибочные серии не агрегируются вместе; min/max/median проверяются
      на известном независимом наборе, порог выигрыша не скрывает потерю фактов.
- [x] **Локальный UI:** реальные передаваемые profile/question, новый request ID,
      ошибки/unknown видимы, loopback/Host/Origin проверяются; историческая таблица
      помечена. Полные приватные receipts не выдаются HTTP/публичным экспортом.
- [x] Общее офлайн GREEN и итоговый diff: Day01–28 не изменены, cross-day runtime
      imports нет, секреты/приватный корпус не попали в отслеживаемые файлы.

## Реальные замеры

- [x] До первого pilot заморожены suite/rubric, 3 contexts, configs и manifest кода.
- [x] Сохранены B + T/M/C/P + максимум F pilot E02 либо конкретные budget rejects.
- [x] Обоснован выбранный кандидат и frozen hash до финальных повторов.
- [x] 12 warm B/F + 2 cold E02, warmup receipts и наблюдение ресурсов; ошибки и
      несопоставимые режимы сохранены, никаких скрытых повторов.
- [x] Второе квантование: ограниченная проба либо проверенная причина пропуска;
      qwen3.5 не выдана за Qwen3 8B и `Q4 уже установлена` не выдано за эксперимент.
- [x] Семантическая таблица всех финальных ответов, individual metrics/median/range;
      данные отдельно от интерпретации, статус доказательства оптимизации по SPEC.

## Ревью и материалы

- [x] Первое независимое ревью Luna medium по SPEC/коду/тестам/замерам.
- [x] Исправления Sol, связанные свежие тесты и evidence дельты.
- [x] Обязательное независимое Astra xhigh, включая случай без находок Luna;
      нет незакрытых существенных ошибок или необоснованных PASS.
- [x] README/RESULT/RELEASE_NOTES: воспроизводимые команды, выводы/ограничения,
      фактически выбранная конфигурация, отсутствующие метрики явно названы.
- [x] Новый dry run полного сценария; затем отдельная живая запись, новые IDs,
      журнал видео, ffprobe/decode и просмотр ключевых кадров самого файла.
- [x] Проверены итоговые код и видео отдельно; результаты связаны с версиями.
- [x] Root обновил короткий todo и дал объяснение Day28/29 после реализации.

Публикация (commit/push/merge, Drive, таблица) и пользовательская приёмка сейчас
не отмечаются выполненными и не выводятся из успешных тестов/видео.

## Текущее implementation evidence

Sol gpt-6.1-sol high: standalone core/profiles/evaluate/metrics и loopback UI.
Историческая версия замеров: `python3 -m unittest discover -s day29/tests -v` —
39 offline tests, Python 3.14,
stdlib. [RED options/snapshot](tests/tdd-contract-red.txt) показывает реальные
поведенческие failures исполнимой заготовки; [GREEN](tests/tdd-contract-green.txt).
Отдельный [RED missing warm metric](tests/tdd-warm-missing-red.txt) зафиксировал
ложный done при отсутствующем load duration; [общий GREEN](tests/offline-green.txt).
Independent baseline parity использует root fixture из настоящих Day28 receipts.
Моки не доказывают смысловую полноту модели или скорость; runtime измерения root.
Comparator/RSS/freeze/warmup guard repairs получили собственные RED evidence;
[финальный офлайн GREEN](tests/offline-green.txt) — 39 тестов. Сопоставимость
проверяет canonical baseline, одинаковые context/question/index/model/payload,
уникальные ID, E03 unknown и отдельную семантическую оценку. RSS требует полного
стабильного набора процессов в каждом sample; actual Ollama 0.33.3 llama-server
определяется по PPID, private args не собираются. bind сохраняет прежние contexts
и parent hash, привязывая новую версию к текущим code/config hashes без inference.
Независимое Astra ревью проверило фактическую оценку и исправления; окончательная
матрица поставки ожидает новый дубль со значениями swap.

### Ограниченные правки после замеров

Astra warnings закрыты: E01/E02 должны быть `done` с required source docs и
валидным materialized answer; summary разделяет run IDs и принимает явный
`--run-id`. `--semantic-assessment` проверяет run/suite/request/receipt hashes.
RED: [answer guard](tests/tdd-postprocess-answer-red.txt),
[run grouping](tests/tdd-summary-run-red.txt),
[failed Q8 warmup durability](tests/tdd-quant-stop-red.txt).
GREEN: [45 офлайн тестов](tests/offline-postprocess-green.txt), Python 3.14.
Controller сохраняет quant preparation до прогрева и failed series/stop reason
без retry; test first warmup failure показывает ровно один generation attempt.
[Source diff/evidence](tests/postprocess-evidence.json) сохраняет измеренную
версию evaluate.py `fbe696ad…` отдельно от postprocessing версии `fdd23fa6…`.
Core/metrics/настройки профилей/payload не изменены, новые LLM прогоны не выполнялись.
Readonly анализ actual warm run `a2606d8f674a48d1b7e2ec8e1549a209` по ручной
семантической таблице дал `proven=true` только за полноту E02; B/F generation
medians 29.780854646 / 37.126610021 s, RSS comparable. Это не ускорение.
Root владеет итоговыми RESULT/public summary/video/review; их статус здесь
не закрывается. Старые пропущенные quant preparation метаданные не создавались.

## Фактические измерения и поставка

[RESULT](RESULT.md) связывает warm/cold/Q8 с hashes и ограничениями.
[Публичные projections 25 экспериментальных receipts](results/measurement-receipts.json)
содержат исходные ответы и измерения только public assignment scope; полные
приватные originals остаются вне Git. 12 scored warm, 4 исключённых прогрева,
2 cold, 6 pilots и 1 неудачная Q8 попытка не смешиваются в общую оценку.
Astra независимо подтвердила полноту E02 и отсутствие выигрыша скорости/RSS10%.

Первый dry/record: 8 новых живых запросов; record-01 просмотрен, но не показал
численный swap, поэтому SCENARIO п.6 PARTIAL. [Ошибка и сохранённый proof](results/video-verification-record-01.json). В UI добавлены только исторические
значения swap из raw receipts: [bindings](results/swap-video-evidence.json).
Новый dry-02/record-02 не подменяет первый дубль; полный финальный proof —
в [video-verification](results/video-verification.json).

Финальный record-02: 328.48 s, 4 новых request ID, 0 page errors; decode и
9 кадров PASS, numerical swap/GPU показаны. 41 генерация всего: 25 экспериментов
и 16 dry/record live вызовов; scored warm остаётся ровно 12.

Финальный независимый аудит: [43 PASS, SPEC SATISFIED](results/implementation-validation.md), A1/A2 CLOSED. Root выполнил ZIP CRC,
побайтовое соответствие исходникам и исключение private/index/models/cache/video;
[archive proof](results/archive-verification.json). Публикация остаётся отдельной.
