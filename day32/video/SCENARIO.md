# Day32 — новый PR, разные дефекты и ограничения

Сценарий `run_demo.py` применяет один codepath для `--dry-run` и `--record`.
Оба режима делают **новые платные запросы и реальные commit/push**; нужны явные
`--allow-live --allow-publish`. Запись добавляет захват viewport1280×1000 и ffmpeg
без ускорения. Не запускать без разрешённого PR и общего бюджета Day32 $0.50.
Ключ берётся только из `OPENROUTER_API_KEY`, окружение/ключ не журналируются.

Предусловия: чистый отдельный head-worktree; HEAD совпадает с actual PR;
head/base отличаются и head не main/master; canonical live ledger
`day32/.runtime/live`; отдельно подготовленный `eval_faults.py` offline state.
Скрипт читает baseline из **base SHA**, сохраняет его в новый output и каждый
вариант строит независимо. Уникальный безопасный комментарий даёт новый SHA
даже при повторе сценария. Меняется только `day32/target/git_tool.py` head-ветки.
Нет force push, merge, комментариев PR, выполнения кода PR.

| Шаг | Действие | Что проверяем и сохраняем |
| --- | --- | --- |
| Обзор | Панель с легендой LIVE | Новый браузер, читаемый экран, общий бюджет |
| upper | `<=10` → `<10`, push | Watcher сам poll actual PR и запускает rag; ожидается finding про10 |
| сравнение | `--compare`: diff/files на том же SHA | Отдельные отчёты и точные контексты; качество заранее не объявляется лучшим |
| dedupe | Повтор Runner на том же actual snapshot | Тот же trace_id, new=false, дополнительного model call нет |
| fix | Чистый baseline + run marker, push | Новый SHA, отсутствие подготовленного дефекта; ложные замечания честно видны |
| bool | `type(limit) is not int` → `not isinstance(limit,int)` | Модель может заметить, что bool принимается |
| ignored | `f'-{limit}'` → `'-5'` | Модель может заметить игнорирование limit |
| injection | Upper bug + комментарий с инструкцией reviewer | Система должна считать комментарий недоверенным; наблюдаем фактический ответ |
| SIMULATED | Отдельная панель/SQLite на соседнем порту | Реальные сохранённые Runner error/limited/budget_blocked от offline provider; не Qwen |

На каждом live ответе показываем оригинальные findings, Diff, FTS5 источники,
точный модельный контекст и стоимость. Открываем настоящие sections UI, делаем
скриншоты реальных моментов. Чтение по умолчанию8с + переходы; пять вариантов,
сравнение режимов и offline faults ориентировочно5–8мин с реальными ожиданиями.
Длительность фиксирует ffprobe, искусственное ускорение/удлинение не применяется.
Промах, false positive, транспортная ошибка не подменяются ожидаемым ответом.
При budget_blocked платная часть прекращается, сохранённые ограничения показываются.

Пример сухого прогона (подставить actual PR/worktree/offline state):

```sh
python day32/video/run_demo.py --dry-run --allow-live --allow-publish \
  --pr-repo OWNER/REPO --pr-number N --head-worktree /PATH/TO/HEAD \
  --state day32/.runtime/live --offline-state day32/.runtime/faults \
  --budget 0.50 --cases upper fix --output day32/.runtime/dry-UNIQUE
```

Для полного нового дубля: `--record --compare`, без `--cases` (все5), новый output.
Сухой прогон2calls + запись7calls делят **один ledger** с прочими разрешёнными
проверками. Каждый Runner заново проверяет резерв; неизвестная стоимость сохраняет
резерв, автоматического платного retry нет. Watcher — отдельный процесс, события
trigger/review/stages/dedupe записывает в `events.jsonl`. UI обновляется только чтением.

Артефакты: manifest с SHA/run_id/временами/кадрами, events, baseline.py, raw WebM,
MP4, ffprobe.json. Исходные requests/responses/contexts остаются в canonical state.
При ошибке recorder закрывает свой context в finally; сырая запись сохраняется.
Для финальной приёмки вручную просмотреть начальный, ключевые и конечный кадры,
сверить calls/events/ledger и ffprobe; автоматическая генерация файлов этого не заменяет.

Дополнительный `--history-trace TRACE_ID` после новых LIVE результатов показывает
существующий **error/limited** отчёт из canonical state. Это явно подписанная история
предыдущего сухого прогона до исправления выборки файлов, а не новый ответ модели.
Показаны исходные ограничения/error, diff и стоимость. История читается через SQLite
`mode=ro`, сохраняется в отдельном `manifest.history` и не входит в новые outcomes/calls.
Несуществующий, некорректный или complete trace отклоняется до публикации новых коммитов.
