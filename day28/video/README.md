# Day28 — живая запись

Один [сценарий](SCENARIO.md) выполняется [run_demo.py](run_demo.py) в dry run и record.
Каждый режим создаёт три **новых** public-запроса; запись показывает настоящий браузерный
viewport с ожиданием локальной модели, без подмены ответов и проигрывания старых receipts.

## Воспроизведение

UI должен работать на http://127.0.0.1:8068 с подготовленным индексом и моделями.
Используются уже кешированные Playwright/Chromium в отдельном uv-окружении;
для конвертации/проверки нужны ffmpeg/ffprobe. Из корня репозитория:

```sh
uv run --offline --no-project --with playwright python day28/video/run_demo.py --dry-run --output day28/video/runs/dry-new
uv run --offline --no-project --with playwright python day28/video/run_demo.py --record --output day28/video/runs/record-new
```

Каталог должен быть новым. Скрипт ждёт реальный terminal status конкретного request ID,
сверяет API-ответ/источники, показывает каждый исходный фрагмент отдельной прокруткой.
Свой context/recorder закрывает в finally, сохраняет исходный webm и новый mp4 без
ускорения; не останавливает чужие браузеры/Ollama. Размер viewport — 1280×1000,
звука нет. Журналы/сырые файлы находятся в игнорируемом `video/runs/`.

## Фактические прогоны

| Прогон | Run ID | Новые запросы / состояние |
| --- | --- | --- |
| Dry 01 | `774130f8e2d343398316926da8c45a2a` | 3: done/done/unknown; page errors 0 |
| Record 01 | `3ae230eb1f8741b79c3899ba0762256a` | Настоящие запросы/ответы; пропущены видимые metadata сценария, дубль сохранён |
| Record 02 | `727aaa505f2f42c3b6a87b7f2d4e9371` | 3 новых public-запроса: done/done/unknown; видео проверено |

Dry API total: E01 34.57 с, E02 43.76 с, E03 16.74 с. Прочитаны начальный экран,
ответы, оба источника E02 и unknown. После dry уточнены только подписи unknown:
найденный поиском контекст не выдаётся за источник, выбранный моделью.
[Целевой cached preview](../results/ui-unknown-cached-preview-1/results.json)
— GET-only сохранённого public-ответа, 0 новых модельных вызовов; это не новый live-pass.
Backend и interaction flow сохранены; новая запись проверяет текущие подписи.

## Финальная проверка

[Day28-live.mp4](Day28-live.mp4) — **178.64 с (2:59)**, 4 250 922 байт,
H.264/yuv420p, 1280×1000, 25 fps, без аудио. SHA-256
`c627d0909670e3a4a58d0f3db58c773e2a920e669e68f5a83825e1b187f181b8`.

ffprobe и полное декодирование: PASS. Ответственный агент прочитал кадры самого MP4:
начало, все три ответа, каждый исходный фрагмент (оба E02 отдельно), unknown и конец.
Кадры читаемы, private discussion-текстов/ключей и посторонних окон нет.
Три уникальных request IDs сверены с API; видимые ответы и исходные фрагменты совпали,
browser errors 0. В начале читаются URL/подготовка, в конце — отдельные E2E/replay IDs
и статусы «Код проверен», «Видео проверяется», «Не опубликовано». API total: E01 40.80 с, E02 51.80 с, E03 17.97 с;
E02 остаётся PARTIAL по полноте. [Проверка и времена кадров](../results/video-verification.json).

Итоговый MP4 совпадает по SHA с исходным MP4 record-02, без монтажа/ускорения.
Сырой webm/mp4 и журналы сохранены в `video/runs/`. Финальный MP4 опубликован на GitHub;
загрузка в Drive уточняется отдельно. [Публикация](../results/github-publication.json).
Проверка выполнена агентом, не является пользовательской приёмкой.

[Аудит record-01](../results/implementation-validation-record-01.md) сохранил три FAIL
показа metadata. Исправление UI прошло GET-only desktop/mobile preview и независимые
Luna/Astra обзоры; новые live-запросы появились только в record-02. Старые видео/кадры
и результаты сохранены, оценочные E2E/replay не переписывались.
