# Day32 — результат

Готовы код и проверенное живое [видео 8:39](video/README.md). Настоящий
[PR#1](https://github.com/RomaniumSSS/ai-advent-9/pull/1) направлен в отдельную
baseline-ветку day32-pr-review. Main/merge/PR-комментарии не выполнялись.

## Что работает

GitHub polling → exact base/head SHA → merge-base diff и изменённые файлы →
FTS5/BM25 по docs+code → один Qwen request → проверка schema/путей/видимых строк/IDs
→ SQLite и браузер. Режимы diff/files/rag сохраняют разные точные входы/ответы.
Резерв создаётся до вызова; dedupe переживает перезапуск. Read-only fetch/poll можно
повторять после временного сбоя, модельные запросы автоматически не повторяются.

## Фактические проверки

macOS, существующий uv environment:

```sh
uv run --no-sync python -m unittest discover -s day32 -p 'test_*.py'
uv run --no-sync python day32/video/test_run_demo.py
```

**60+8=68 тестовых методов PASS**; последние журналы: [основные](results/final-main-tests.txt),
[recorder](results/final-recorder-tests.txt). Отдельно 100generated checks(seed320016),
9SIMULATED fault-сценариев/36assertions. Это не 100 дополнительных unittest методов
и не реальные сбои провайдера. Browser desktop/tablet/mobile проверен.
Luna → исправления Sol → обязательная Astra; scope и exact-SHA исправления
повторно независимо проверены. [Scope](results/review-scope-astra.md),
[race](results/review-race-astra.md), [история исправлений](results/review-fixes.md).

Настоящие события PR,5 новых head SHA в записи,7 новых model calls и 7dedupe
подтверждены [manifest/events](results/video-validation.json). Сохранённый
исторический error не считается новым ответом. Видео 693.72 с,H.264,1280×1000,
без ускорения;9 кадров из MP4 просмотрены отдельно.

## Качество Qwen

Основные цели 7case/mode проверок выполнены: upper×3,bool,ignored,injection
правильно диагностированы; чистый fix не получил ложного bug. Это **не 7 безупречных
ответов**: RAG добавил дубликат и необоснованный совет; встречаются неверные
альтернативы исправления, неточное объяснение -True как -1 и смешение разных
регрессий. [Независимая смысловая оценка](results/live-semantic-review.md).
Преимущество RAG не доказано. Upper — известный учебный кейс с исторической
подсказкой в diff, не слепой benchmark. Один комментарий-injection не подавил
основной finding; это не общая гарантия защиты от инъекций.

## Расходы и артефакты

Разрешённый общий лимитDay32:$0.50. **15 реальных Qwen calls,$0.111228 reported
actual**, unknown holds0; из них 7 новых ответов записи стоят$0.060414. В общий
расход включены readiness и все сухие прогоны. Прерванный первый дубль
не добавил новых model calls.
[Budget](results/budget-final.json), [точные входы/ответы 15 вызовов](results/live-20261016/INDEX.json).
SIMULATED ledger отдельный и не включён в эту сумму. Затраты coding/review моделей
не предоставлены; эта сумма относится только к приложению Qwen.

Первый dry выявил слишком ранний cap whole-tree, первый дубль — mismatch mutable
PR-ref/actual SHA; оба исправлены, исходные неудачные прогоны сохранены.
Ключи не публиковались. Пользовательская приёмка не заявляется.

По поручению пользователя подготовлена версия для сдачи 8:39: пять ожиданий
ускорены ×6 с видимой подписью, чтение ответов ×1. Исходник 11:34 сохранён.
[Интервалы и проверка](results/video-edit.json).
