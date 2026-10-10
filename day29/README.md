# Day29 — локальная оптимизация Qwen3 8B

Текущая версия Day29 включает [полный локальный чат на 8070](FULL_CHAT_README.md)
и отдельный [эксперимент A / critic → repair → recheck](QUALITY_EVAL_README.md).
[DELIVERY.md](DELIVERY.md) — единая точка входа: запуск, проверенные результаты,
ограничения и текущие этапы публикации.
[Новая живая запись 4:57](video/Day29-live-full-chat.mp4),
[результаты пяти вопросов](quality-results/README.md),
[финальный аудит Astra](quality-results/delivery-validation-astra.md).

Описание ниже, параметры, исходное видео и ZIP относятся к самостоятельному
benchmark оптимизации на **8069**. Новая поставка полного чата и новое видео
отслеживаются отдельно; исходные измерения и архив не заменены.

Самостоятельный справочник учебных заданий: исходный профиль Day28 и небольшие
однофакторные пробы настроек на неизменном локальном RAG контексте.
Требования и критерий доказанной оптимизации: [SPEC](SPEC.md), протокол: [PLAN](PLAN.md).
Выбран профиль F: полнота сложного ответа улучшена, время генерации увеличилось.
[Результат и ограничения](RESULT.md), [живая запись](video/Day29-live.mp4),
[архив кода](Day29-code.zip), [release notes](RELEASE_NOTES.md).
Фактические выводы относятся к новым receipts и отдельной семантической оценке;
45 офлайн тестов проверяют обвязку, а не качество текста модели.

Нужны Python 3.12+, Ollama на `http://127.0.0.1:11434`, точные локальные модели
`qwen3:8b` и `qwen3-embedding:0.6b`, исходный индекс Day28. Новый индекс не строится,
исходная SQLite открывается read-only. Загрузка альтернативных Q8 весов — отдельная
подготовка; runtime API ограничен loopback и не следует redirect/proxy.

Из корня этого worktree:

```sh
python3 -m unittest discover -s day29/tests -v
python3 day29/app.py --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1
```

UI: `http://127.0.0.1:8069`. Кнопка выполняет новый локальный запрос. В браузере
доступен только public scope и декларативные профили; приватные receipts и пути
не имеют HTTP маршрута. Профили `baseline`, `temperature`, `max-output`, `context`,
`prompt`, `candidate` определены в [profiles.json](profiles.json); выбранный профиль
задаётся полем `selected` после оценки. Сейчас выбран `candidate`: он прошёл
критерий полноты E02 на проверенных вопросах; ускорение не получено.

Воспроизводимая оценка:

```sh
python3 day29/evaluate.py preflight --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1
python3 day29/evaluate.py freeze --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1
python3 day29/evaluate.py pilot --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1 --profile-ids baseline temperature max-output context prompt
python3 day29/evaluate.py pilot --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1 --profile-ids candidate
python3 day29/evaluate.py warm --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1 --profile-ids baseline candidate
python3 day29/evaluate.py cold --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1 --profile-ids baseline candidate
python3 day29/evaluate.py quant --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1 --profile-ids candidate
```

`freeze` отказывается перезаписывать снимок. Новый эксперимент получает другой
`--contexts` файл; все следующие команды читают его. `--output` меняет локальный
каталог receipts, `--profiles` позволяет явно передать замороженный файл профилей.
После pilots сначала выбрать и объяснить финальные settings, сохранить hash,
затем выполнять warm/cold; команды выше не разрешают бесконечный sweep.
Изменение кода или конфигурации после freeze блокирует inference. Для явно
объяснённой новой версии выполнить bind, сохраняя исходный снимок:

```sh
python3 day29/evaluate.py bind --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1 --contexts day29/private/frozen-contexts.json --bound-contexts day29/private/inputs-repair-v1.json
```

Выполненная серия использовала `inputs-repair-v1.json`. Для текущей версии после
postprocessing repairs и выбора UI сохранён `day29/private/inputs-delivery-v1.json`:
он содержит те же входы с parent hash, без повторных embedding/inference.
Следующие новые эксперименты этой версии получают
`--contexts day29/private/inputs-delivery-v1.json`. Для нового bind используйте новый
путь `--bound-contexts`; старые snapshots не перезаписываются.
Bind сохраняет parent hash и те же contexts; embedding/inference не выполняет.
Quant выполняется только после отдельной проверки пригодности второй квантизации.
`summary` читает сохранённые receipts без загрузки индекса и без inference.
Каждая группа содержит отдельный `run_id`, профиль, режим и кейс: несколько
экспериментов не объединяются в одну median. Для воспроизводимого анализа
фактической финальной серии:

```sh
python3 day29/evaluate.py summary --run-id a2606d8f674a48d1b7e2ec8e1549a209 --semantic-assessment day29/results/warm-semantic-assessment.json
python3 day29/evaluate.py summary --run-id bc205ff1d4d141749152dfa9978ac552
python3 day29/evaluate.py summary --run-id df5e7e0053954e88858734c3f0a2bbb3
```

`--output` по умолчанию `day29/private/runs`. Без ручного файла summary оставляет
`optimization=NOT_ASSESSED`. Файл семантики оценивает факты/полноту отдельно от
ссылок; CLI проверяет его run ID, suite hash, все request IDs и receipt hashes.
Правки ответа после оценки делают этот файл несовместимым. Это агентская
интерпретация исходных источников, не человеческая приёмка; отдельного платного вызова модели-судьи нет.
Усиленный verdict дополнительно требует E01/E02 `done` и обязательные исходные
assignment-источники; E03 `unknown` с пустыми источниками. Результат указанной
warm серии: улучшение по полноте E02, при большем медианном времени генерации.
Полные выводы и цена изменения — в [RESULT](RESULT.md), отдельно от фикстур.

Warm серия: 2 повтора, 3 кейса на профиль; блоки B/F, F/B, прогрев перед каждым
блоком сохранён и исключён из оценки. Cold выгружает только нужную модель под
lock и проверяет её отсутствие в `/api/ps`; это не очистка файлового кеша ОС.
Quant: один исключённый прогрев и максимум два E02 на Q8 с теми же input/options/prompt;
неуспешный прогрев останавливает серию до warm повторов. Реальная проба
`df5e7e0053954e88858734c3f0a2bbb3` остановилась на `done_reason=length`;
это не завершённый Q8 benchmark или оценка его полной смысловой точности.
Техническая ошибка останавливает серию без скрытой повторной попытки.
Новый controller сохраняет `quant-preparation.json` до прогрева и `series.json`
со stop reason даже при исключении. В старой реальной Q8 пробе preparation/series
не были сохранены; отсутствующие метаданные задним числом не создаются.

Для измерений сохраняются отдельные `run_id`/`request_id`, payload, digest,
context/prompt hashes, response, source validity и timings. Полные данные лежат
в игнорируемом `day29/private/` с правами 0700/0600. RSS — максимум наблюдавшейся
суммы daemon+runner с шагом 0.5 секунды; короткие пики могут быть пропущены,
shared pages могут быть учтены дважды, Metal/unified memory описана не полностью.
`/api/ps size/size_vram` — отдельное размещение модели, не RSS peak.
Swap/pageouts — показатели всей машины. Отсутствующие метрики — `null`.

Значимые TDD доказательства: [первый RED](tests/tdd-contract-red.txt),
[GREEN](tests/tdd-contract-green.txt), [warm missing RED](tests/tdd-warm-missing-red.txt),
[GREEN версии замеров: 39 тестов](tests/offline-green.txt). Дополнительные RED
для [сопоставимости](tests/tdd-comparison-red.txt), [freeze](tests/tdd-freeze-red.txt),
[полного набора RSS](tests/tdd-metrics-fairness-red.txt),
[реального llama-server](tests/tdd-llama-server-red.txt),
[проверки warmup](tests/tdd-warmup-proof-red.txt) и
[финальных gates](tests/tdd-comparison-gates-red.txt) сохранены отдельно. Моки проверяют обвязку;
реальную модель и полноту её ответа проверяют отдельные live receipts и рубрика.
Baseline parity сравнивается с независимым [Day28 fixture](results/baseline-reference.json),
а не с повторением текущего кода в тесте. Его прошлые timings не являются fresh baseline.

Provenance: `core.py` содержит самостоятельную адаптацию Day28 из базы `ca90584`;
поиск и identity ранее происходят из Day25 (`4659e24`). Cross-day runtime imports нет.
Day01–28 не изменяются. Commit/push/merge, видео upload и отправка в таблицу —
отдельные действия; успешные тесты не означают публикацию или человеческую приёмку.

После замеров выполнены только ограниченные controller/postprocessing repairs:
[45 свежих офлайн тестов GREEN](tests/offline-postprocess-green.txt),
[доказательства и hashes](tests/postprocess-evidence.json),
[diff измеренной и текущей версии evaluate.py](tests/postprocess-source-diff.patch).
Core, sampler, настройки профилей и реальные payload не менялись; свежие inference для
этих исправлений не выполнялись. Старый исходник evaluator с hash `fbe696ad…`
сохранён в tests, поэтому замеры остаются связаны со своей фактической версией.

Публичный экспорт фактических экспериментальных ответов и метрик:
[measurement-receipts.json](results/measurement-receipts.json), 25 projections.
Отдельно указаны mode/phase, прогревы, ошибки и SHA исходных private receipts;
экспорт имеет другие байты. В нём только public assignment scope. Полный локальный
receipt содержит дополнительные служебные поля и хранится отдельно.
