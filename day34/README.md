# Day34 — ассистент файлов проекта

Модель выбирает `list_files`, `search_text`, `read_file`, `write_file`, `show_diff`;
Python проверяет аргументы, исполняет реальные файловые операции и возвращает
наблюдения в следующий шаг модели. Порядок live-действий не задан сценарием.

Требуется Python 3.12+ и uv. Из корня свежего клона: `uv sync`
(общие зависимости — в `pyproject.toml` и `uv.lock`). Runtime Day34 использует
стандартную библиотеку Python; браузерная запись дополнительно требует Playwright
(`uv sync --group dev`), установленный Google Chrome (runner использует
`channel="chrome"`) и ffmpeg/ffprobe в PATH для записи MP4.
Офлайн-тесты не требуют API-ключа.

```sh
uv run python day34/test_day34.py
uv run python day34/test_robustness.py
uv run python day34/web.py                 # http://127.0.0.1:8134, OFFLINE MOCK
uv run python day34/video/runner.py        # две цели, явно сценарный mock
```

Каждый запуск создаёт новую копию `fixtures/` в `day34/runs/<run_id>/sandbox`.
Сброс — новый запуск: старые результаты сохраняются. `trace.json` рядом с sandbox
содержит действия, результаты, статус, requested model/provider и отдельно actual
model/provider каждого ответа (null при отсутствии), время, доступные usage/cost.
Отсутствующие либо несовпадающие actual model/provider останавливают цикл до исполнения инструментов;
requested route не доказывает фактический endpoint, которого может не быть в ответе.
Чтение и поиск работают только в sandbox, запись — только `README.md` и `reports/`.
Абсолютные пути, traversal и symlink запрещены. Shell/сеть/удаление моделью недоступны.
Файлы рассматриваются как данные. Лимиты: 10 шагов, 20 вызовов инструментов,
180 секунд, 4096 выходных токенов (reasoning low/exclude) на запрос, 16000 байт на файл,
24000 символов на результат; обрезка отмечена и исключает успешный статус.

Live запускает только оператор после подготовки **единого общего** ledger:

```sh
uv run python day34/web.py --live --budget-ledger /absolute/shared-budget.sqlite
uv run python day34/video/runner.py --live --budget-ledger /absolute/shared-budget.sqlite
```

Ключ берётся из `OPENROUTER_API_KEY`; программа не копирует и не сохраняет ключ.
Ledger должен уже существовать: приложение никогда не создаёт новый бюджет.
Каждый запрос резервирует верхнюю оценку по UTF-8 входу и max_tokens;
неизвестная стоимость удерживает резерв. Qwen `qwen/qwen3.8-max-0902` через
OpenRouter, только `alibaba/us-east-1`, fallback и повторы отсутствуют.
Transport выполняется в отдельном процессе: общий дедлайн включает DNS/connect/TLS,
заголовки и тело; по истечении родитель прекращает процесс и закрывает соединение.
Ключ передаётся только в памяти, бюджет резервируется и учитывается в родителе.
После ошибки запроса частичный результат сохраняется с ошибочным статусом.

Офлайн-тесты используют реальные файлы, diff и HTTP, а ответы модели — mock.
Они не доказывают качество Qwen или устойчивость к prompt injection;
live-оценка и видеозапись выполняются отдельно. `video/runner.py` — прогон целей,
не запись экрана. UI явно подписывает режим mock/live и показывает actual diff.

Браузерный dry/record (каждый режим создаёт два новых запроса):

```sh
uv run --offline --with playwright python day34/video/run_demo.py --expect-mode mock --out /absolute/fresh-dry
uv run --offline --with playwright python day34/video/run_demo.py --expect-mode live --out /absolute/fresh-record --record
```

Для live нужен уже запущенный оператором live UI. Выходной каталог должен быть новым.
Скрипт сохраняет HTTP-ответы, traces, screenshots, timing; при записи также WebM,
MP4 и ffprobe. Ожидание ответа — до 240 секунд. Просмотр кадров записи и
человеческая проверка результата выполняются отдельно. [Текущий результат](RESULT.md).


Дополнительные реалистичные fixtures и семантические ожидания —
[robustness/live-manifest.json](robustness/live-manifest.json). Исходная demo fixture
не меняется. Python `run(..., fixture=Path(...))` принимает доверенный каталог
оператора; HTTP и tool schemas не дают модели выбирать host path.
Binary, не-UTF8 и слишком большие файлы не ломают старт/diff; текстовый поиск
сохраняет найденные совпадения и явно перечисляет пропуски с ошибочным статусом,
поэтому не доказывает «все использования» при неполном покрытии.

Операторский `robustness_runner.py` требует явные `--live --fixture PATH --goal TEXT
--out NEW_PATH --budget-ledger EXISTING_ABSOLUTE_PATH --accounted-cap 0.767852`.
`--max-steps` от 1 до 6; tools/time остаются ограничены 20/180 секунд.
Это последовательный операторский запуск: дополнительный accounted-cap проверяется
до reserve, общий $1 атомарно проверяет существующий Budget. Параллельные live
процессы для этого wrapper не поддерживаются. Unknown holds входят в cap.
При ошибке результат сохраняется в `result.json` и, если цикл начат, trace.json.
Офлайн-проверки не доказывают качество свободных ответов на этих новых fixtures:
их принимает оператор по коду, точным изменениям файлов и manifest.

Создание пустого файла отражается отдельной записью `new file mode` в diff.
Неизменённые symlink учитываются по метаданным ссылки без чтения её цели;
доступ через ссылку остаётся запрещён. Ошибка итогового diff даёт `diff_error`
и ошибочный статус запуска, даже если модель уже вернула финальный ответ.

Состав публикации и границы локальных материалов: [PUBLISH.md](PUBLISH.md).
