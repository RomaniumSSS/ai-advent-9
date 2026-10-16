# Исправление независимого ревью Luna

Исполнитель: gpt-6.1-sol, 16.10.2026. Исходное ревью — review-luna.md,
исторический документ не изменён.

WARNING: большие ls-tree (>200KB) и name-status (>100KB) прерывали snapshot;
вместо limited report CLI выдавал только poll_error.

Решение: отдельный GitReadLimit для bounded-read overflow. Snapshot ловит
именно его для tree/manifest, сохраняет пустую неполную соответствующую
коллекцию и явные limitations. Обрезанный NUL manifest не разбирается,
поскольку нельзя безопасно восстановить пару rename. Другие Git errors
не маскируются этими новыми обработчиками. Runner получает snapshot,
сохраняет limited report и persistent dedupe обычным путём.

Доказательство: test_large_tree_and_manifest_persist_limited создаёт настоящий
Git commit с 5000 .py файлами (длинные имена), превышающий оба caps.
Проверяет пустые manifest/corpus, обе причины limitations, limited в SQLite
и report.json, запрет повторной генерации после открытия нового Store.
Это офлайн-проверка механики со статическим Fixture, не оценка Qwen.

Команда: uv run --no-sync python day32/test_review.py — 13 PASS за 7.090с.
git diff --check -- day32 — PASS.

Browser desktop/tablet/mobile проверен родительским агентом отдельно;
настоящий PR-trigger и платные вызовы по-прежнему не выполнялись.
Обязательное повторное независимое Astra-review ещё предстоит.

## UI: чтение раскрытого контекста

По browser-наблюдению родителя polling раз в 5 секунд пересоздавал details.
refresh теперь сравнивает полный JSON rows и оставляет DOM без изменений,
если отчёты прежние. Начальная загрузка, появление/смена отчёта и ручной выбор
по-прежнему вызывают render. Browser-проверка: раскрыть «Точный модельный
контекст», подождать минимум 6 секунд, подтвердить сохранённое open и scroll;
выбрать другой trace, проверить соответствующий mode/контекст. Проверку
выполняет родитель после перезапуска сервера.

## Astra P2: ссылка на невидимую модели строку

Независимое Astra-review доказало: diff-only finding мог ссылаться на любую
строку полного локального blob, хотя модель получила только один hunk.

Добавлен helper visible_lines(data), работающий по фактическому prompt после
truncation: строки переданных files целиком; ranges переданных sources с
проверкой SHA для head/merge_base; координаты +/-/context в diff hunks.
Разбираются отдельные пути old/new, deletion /dev/null, rename, Git quoted
paths и маркеры отсутствия newline. Guard существования changed path,
версии и строки закреплённого snapshot сохранён; дополнительно finding
обязан ссылаться на строку из visible_lines. Это проверка доступности
основания, не доказательство смысла замечания.

Новые проверки: настоящий long.py на100 строк с изменением50; diff-only
отвергает1, принимает47/50/53; files принимает1 вне hunk; после полного
pruning files/diff/sources1 отвергается. Отдельно source range с правильным
и посторонним SHA; rename/delete/no-newline coordinates.

Свежая команда: uv run --no-sync python day32/test_review.py —16 PASS за8.475с.
git diff --check -- day32 —PASS. Astra повторно проверит исправление независимо.

## Astra regression: имя файла с пробелом

Git выдаёт unquoted `--- a/space name.py<TAB>`; служебный TAB ошибочно
считался частью пути. path_header теперь отделяет TAB-delimited suffix
только у unquoted заголовка, не удаляя пробелы имени. C-quoted разбор
остаётся отдельным и не изменён.

Real Git тест создаёт space name.py на100 строк, меняет50 и проверяет
настоящий TAB header: visible50 принимается, unseen1 отвергается.
Свежая команда: uv run --no-sync python day32/test_review.py —17 PASS за9.032с.
git diff --check -- day32 —PASS.
