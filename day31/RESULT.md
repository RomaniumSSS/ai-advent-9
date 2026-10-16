# Day31 — DevHelper

16.10.2026. Готов самостоятельный браузерный помощник и CLI `/help` по знакомому
Git MCP Day17. SQLite FTS5 ищет только README/docs, настоящий stdio MCP читает
фиксированный Git-root, затем выполняется максимум один запрос модели.
Финальный профиль: `deepseek/deepseek-v4.1-flash`, только `deepinfra/fp8`, output
1600, reasoning выключен, fallback и автоматических повторов нет.

## Проверено

- **44/44 офлайн unittest PASS, 5.721 s.** Fake transport/SDK проверяется отдельно
  от настоящего MCP временного Git: смена ветки, detached HEAD, ошибки и запрет
  произвольного repo. Полная локальная схема сохраняет uniqueItems; wire-копия
  опускает только этот unsupported keyword. Unknown source ID всегда ошибка.
- Chromium desktop/tablet/mobile, безопасный вывод HTML как текста, источники со
  строками и хешем; [Git в трёх состояниях](results/browser-git-review/current/report.json).
- Финальный профиль прошёл независимые [Luna](results/review-luna-final-deepseek.md)
  → [Astra](results/review-astra-final-deepseek.md): APPROVED для конфигурации и
  офлайн-контракта. Это не обещание безошибочных модельных ответов.
- [Живой финальный core](results/deepseek-final-core-20261016/summary.json):
  Q1–Q6 и A1, 7 новых ответов, runtime errors=0; Q5 — корректный unknown.
  **Q2 PARTIAL:** команда запуска верна и stdio назван, но в тексте ошибочное
  `.run(stdin)` вместо `.run("stdio")`. Q6 этого DeepSeek-прогона покрывает
  discovery/list_tools/model_tools/schema/limit; прежний GLM Q6 был частичным.
  Общий gold-набор не объявляется 6/6 PASS.
- [Живой CLI](results/deepseek-final-core-20261016/CLI-branch.json) проверен
  координатором отдельно; новые CLI-вызовы ради видео не делались.

## Новый сухой прогон и живая запись

В обоих случаях выполнены новые запросы через работающий UI: конкретный Q1 о
трёх файлах, текущая ветка, вопрос о погоде. Результат `ok / ok / unknown`.
На каждый прогон — 2 реальных LLM-вызова; при пустом поиске модель пропущена.
Текст не подменялся, реальное ожидание не сокращалось, hold=6 s в записи.

| Прогон | Проверки и manifest | Известный usage.cost |
| --- | --- | --- |
| Dry-run | [manifest](results/deepseek-live-dry-20261016/manifest.json), [проверка](results/deepseek-live-dry-20261016/author-check.json) | $0.000440972 |
| Новая запись | [manifest](results/deepseek-live-record-20261016/manifest.json), [Git/источники/trace](results/deepseek-live-record-20261016/author-check.json) | $0.0002292808 |

Trace ID и generation receipt записи не пересекаются с dry-run. Источники
сверены с файлами, branch/head — независимым Git; UI text = API text, JS errors=0.
Код и корпус неизменны на протяжении обоих прогонов.

**[Каноническое видео](video/Day31-live.mp4): 77.44 s, H264 1280×1000, 25 fps,
2 794 853 bytes.** SHA256:
`ecf74c20e474b308ff7490196cc7bb20ef254304cdad31c4b597edc03739513f`.
[Оригинал](results/deepseek-live-record-20261016/Day31-live.mp4) и raw WebM сохранены;
каноническая копия имеет тот же SHA. Полное ffmpeg-декодирование: exit=0, ошибок=0.
[Видео-доказательство](results/deepseek-live-record-20261016/video-proof.json):
просмотрены 6 кадров, извлечённых из MP4, на 1/6.787/12.965/25.272/33.949/61.158 s.
Читаемы ответ, реальный источник с provenance/строками, MCP result.branch/head,
именованная ветка и unknown. Координатор независимо просмотрел эти 6 кадров
и конец на 76.5 s: корректный unknown и MCP, без чёрного кадра.
**Проверка читаемости и артефактов PASS**.

## Ограничения и сравнение моделей

- DeepSeek T3: внешний JSON и source ID валидны, но пример JSON внутри text —
  псевдо-JSON. Проверка источников не проверяет смысл и синтаксис внутреннего кода.
- [Первый pilot](results/compare-models-pilot-20261016/summary.json): 9 API/response
  ошибок. [Pilot после wire-fix](results/compare-compatible-pilot-20261016/summary.json):
  DeepSeek дал 3 ответа; GLM5.3 Q6 завершился по length, P1/T3 — HTTP429.
  Недоступные ответы не ранжируются по качеству.
- [Qwen alternate endpoint probe](results/qwen-alternate-endpoint-probe.json)
  подтвердил HTTP404 и `ZDR violation (guardrail): 2 endpoints excluded`.
  На момент этого probe настройки приватности не менялись. Позже пользователь
  явно разрешил отключить ZDR «All other models»; остальные переключатели
  сохранены. [Бесплатная проверка доступности](results/qwen-availability-after-zdr.json)
  и [новый API probe](results/qwen-after-zdr-probe.json) подтвердили доступность
  Qwen. Probe использовал один provenance-чанк и output cap 1024; ответ unknown
  честно указал на недостаточный контекст. Это проверка интеграции, качество
  модели **NOT PROVEN**, с прежним pilot она не сопоставима.
  Исторические ошибки GLM4.7 и
  [неудачный dry-run](results/live-dry-delivery-20261016/manifest.json) сохранены.

## Общий бюджет

[Исторический snapshot](results/deepseek-live-record-20261016/budget-proof.json)
сделан до нового Qwen probe. Актуальный [финальный snapshot](results/budget-final.json)
сверен с ledger в read-only режиме 16.10.2026 19:30:25 UTC: лимит $0.50; известный usage.cost
**$0.0163579524**, включая $0.003622 нового probe;
**неизвестные расходы удерживают $0.45713269** (19 записей), включая исходные
9 резервов $0.2544244. Учтено $0.4734906424, остаток $0.0265093576.
Резервы не являются измеренной стоимостью; неизвестные расходы не названы нулём.
Ledger не сбрасывался, резервы не освобождались.

## Публикация

16.10.2026 код и проверенное видео опубликованы в GitHub: атомарный обычный
FF push в `main` и `day31-dev-assistant`, feature-коммит
`dbcdb2f5cd0c6476e3a0d5a388f333e65b1c608e`.
[Код](https://github.com/RomaniumSSS/ai-advent-9/tree/main/day31),
[видео](https://github.com/RomaniumSSS/ai-advent-9/blob/main/day31/video/Day31-live.mp4),
[доказательство публикации](PUBLICATION.json). Удалённые SHA и файлы GitHub
проверены; скачанное видео имеет тот же SHA256. Корневые HANDOFF/todo и runtime
в публикацию не включены.

Позднее с отдельного разрешения пользователя [видео DeepSeek загружено в Drive](https://drive.google.com/file/d/1F4f1N8ke7La7VnJOxPYiZ3wpzzr7PolG/view?usp=sharing)
в прежнюю папку с работами: Anyone/Viewer, воспроизведение и анонимное скачивание
с полным совпадением SHA проверены. [Независимая проверка](results/drive-independent-check-20261016.json).
В [Лист1!AF132](https://docs.google.com/spreadsheets/d/1eFmeejRLXnT5fic3uxagtNgQBvv6uAKUG5McRlEo-eE/edit?gid=0#gid=0&range=AF132) отправлен один собственный комментарий с двумя URL;
UI подтвердил Comment created, после перезагрузки — Saved to Drive.
**Повторное чтение текста и anchor после reload NOT PROVEN**: панель комментариев зависла.
[Фактическое подтверждение](results/drive-table-publication-20261016.json).
Пользовательская приёмка pending; отправка в чат и деплой не выполнялись.


## Дополнительная проверка Qwen: 10 вопросов

После отдельного разрешения увеличить потолок выполнена [серия из 10 вопросов](results/qwen-quality-live-20261016/summary.json)
с обычным RAG/MCP-контекстом, без урезания и ручной подстановки фрагментов.
**9 semantic PASS / 1 T3 PARTIAL**, [независимая оценка](results/qwen-quality-live-20261016/semantic-review.md).
Qwen точно воспроизвёл `.run("stdio")` и дал валидный JSON-пример, но достроил
часть подробностей схемы сверх источников. Новых API errors=0, десять разных receipt.
Оформление текста удобнее сохранённых ответов DeepSeek; новый UI/видео Qwen не снимались.

Reported cost серии **$0.0772**, сумма времени вызовов 147.928 s, диапазон 6.0–24.3 s.
Прежний ledger с явного разрешения повышен $0.50→$1.10 без сброса 79 старых записей.
После серии 89 записей: известный расход $0.0935579524, неизвестные резервы $0.45713269,
учтено $0.5506906424, доступно $0.5493093576. Неизвестные holds не являются
подтверждённым списанием. [Authorization](results/qwen-budget-authorization-20261016.json),
[независимая проверка данных](results/qwen-quality-live-20261016/coordinator-check.json).
Default/runtime/corpus опубликованного приложения не менялись; видео показывает DeepSeek.
