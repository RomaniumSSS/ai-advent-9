# Day21: frozen-rubric holdout runner

01.10.2026. Локальный прогон завершён: 20/20 кейсов сохранены.
Разработчик/оператор не выводил тексты holdout и не интерпретировал их смысл.
Рубрика v3 заморожена и не изменялась.

## Подготовка входа

`prepare_development_context.py --split holdout` программно выделяет только
holdout из разрешённого expanded-v2 input. Development остаётся режимом по
умолчанию; его прежние артефакты повторно не генерировались. Build параметризован
только split и ожидаемым размером. Сам sampler и parser Sol не изменены.

Создан `day21/private/semantic-expanded-v3-holdout-input.json`: 20 кейсов,
51 ID. Все прежние поля, ID, UTF-8 text/source_role и связи сохранены.
Пересечений с development и исходным пилотом нет. Metadata: 47 none,
3 photo, 1 video, все content_read=false. Вложения не открывались.

Хеш входа v3:
`166d9f119ac0f357b7e2526f5558b068ace64c96b0312dbbb3298fb40298c00e`.
Хеш исходного expanded-v2:
`ae5e4bf97d479ba50be77e7167d3491fd3c065a136522826cbe805f5d88eb55e`.
Артефакт фиксирует parent/source/parser/preparer/rubric hashes; проверены
source HTML hashes и строки разрешённых ID. Файл 0600, private 0700.

## Runner и guard

- `run_local_sample.py`: `--rubric` принимает только имя файла внутри review;
  default остаётся v2. Выбранные rubric filename/SHA, системный промпт и режим
  schema проверяются checkpoint. Runner_version=3; старые результаты не заменены.
- Контейнер messages должен быть list; неверный тип элемента/ID, дубли,
  пропущенный case ID, неверные boolean metadata или reply отвергаются явно.
  Эти проверки выполняются до любого API-запроса.
- `diagnose_context` больше не возвращает ложный PASS для dict вместо list.
  Структурная проверка и context_diagnostics записываются отдельно.
  Диагностика контекстной ссылки не является semantic accuracy.
- Checkpoint сохраняется атомарно после каждого кейса. Завершённые записи,
  включая ошибки, повторно не запускаются скрыто.

## Офлайн-проверки

Прошли в Python 3.14/macOS:

```text
python3 day21/review/test_holdout_runner.py
python3 day21/review/test_local_sample.py
python3 day21/review/test_development_context.py
python3 -m py_compile day21/review/prepare_development_context.py day21/review/run_local_sample.py day21/review/pilot_validation.py
```

Целевые проверки: default/v3 selection, rubric/hash/schema checkpoint mismatch,
неверный container/type/missing-ID guard, malformed input до API, 20/51
неизменённых holdout IDs/texts, disjointness development/pilot, права 0600.
Прежний test_development_context уточнён: integer 1 больше не принимается вместо
boolean attachment_presence. Старые модельные запросы не повторялись.

## Реальный запуск

Перед запуском других local runner не было. Подтверждён Ollama PID69410,
слушающий только 127.0.0.1:11435. Установка/скачивание не выполнялись.

```text
python3 day21/review/run_local_sample.py --input semantic-expanded-v3-holdout-input.json --output semantic-expanded-v3-holdout-local.json --rubric semantic-rubric-v3.txt --schema
```

Модель qwen3:8b; think=false; temperature=0; ctx8192; predict2048; schema;
stream=false. Rubric SHA:
`7c80878682472e328428c36c34a0b7d1dee8f157f5342666c58d6cead3317076`.
Начальные session47098 / PID33248; при продолжении проверить реальные процессы.
Output: `day21/private/semantic-expanded-v3-holdout-local.json`, 0600.

Итоговые локальные счётчики приведены ниже.
Никаких выводов о смысловом качестве разработчик не делает: аудит ведёт родитель.
Корпус, VPS, платные API и рубрика не изменялись.

## Дополнительные инструменты сравнения

Подготовлен отдельный `run_openrouter_sample.py` (default dry-run, live запускает
родитель). Две pinned-модели/провайдера: deepseek/deepseek-v4.1-flash через
DeepInfra fp8 и z-ai/glm-5.3-flash через DeepInfra fp4. Общий ledger с cap $1,
резерв durable до каждого запроса, unknown cost сохраняет reserve, flock,
без hidden retry. Dry-run: 40 запросов, upper reserve $0.239448.

DeepSeek использует reasoning enabled=false. У GLM reasoning обязателен по
подтверждённому родителем API-контракту: используется effort=low. Reasoning tokens
могут занимать часть того же лимита max_tokens2048. Это ограничение сопоставимости;
нельзя описывать GLM как reasoning-off. Параметры/рубрикa не настраивались на holdout.

Mock-тест `test_openrouter_sample.py` прошёл: pinned params/TLS, общий budget,
unknown cost, pending/no-retry, checkpoint, key privacy, malformed JSON/length,
provider mismatch, HTTP stop, timeout reserve и actual-over-reserve stop.
Сам разработчик OpenRouter live не запускал.

`resume_openrouter_429.py` разрешает одно явно запрошенное родителем продолжение
после подтверждённого HTTP429. Старый failed-case не повторяется, reserve и ledger
сохраняются; continuation-event фиксирует UTC, prior stop, case/model, no_retry
и pacing30s. Пауза до reserve не входит в measured elapsed_seconds. Dry-run
первой остановки показал remaining17, previous429/E06. Mock-тест подтверждает
сохранение record/резерва, skip, начальную паузу и flock. Wrapper codehash не менялся.
API reliability отделяется от ошибок смыслового вывода.

`compare_holdout.py` читает результаты программно без вывода текстов. Он проверяет
input/rubric hashes каждого run, покрытие/дубли/unknown IDs, структуру и context
guard; сохраняет parent diagnostic deviations/flags и условные связи include.
Agreement считается только на ID структурно валидных кейсов с явным знаменателем
и количеством пропусков. Missing elapsed/cost остаются неизвестными. Ledger
unknown reserved costs показаны отдельно. Parent expectations не являются
human gold; проценты accuracy не рассчитываются.

`test_compare_holdout.py` прошёл на direct/wrapped/partial/malformed данных,
missing/unknown IDs, неизвестном времени/cost, условных связях и hash mismatch.
HTTP/transport errors и output parse errors имеют отдельные счётчики.
Промежуточный отчёт: `day21/private/semantic-holdout-comparison.json` (0600);
при новых завершениях его нужно обновить.


## Итог локального прогона

Процесс PID33248 завершён, активного local runner больше нет. Приватный результат
содержит все 20 кейсов и решения всех 51 входных ID, без дублей/пропусков.

| Измерение | Результат |
| --- | --- |
| Сохранённые кейсы | 20/20 |
| Решения входных ID | 51/51 |
| Структурно валидные кейсы | 18/20 |
| Сумма elapsed_seconds запросов | 1895.334 с (31 мин 35.334 с) |
| Ollama prompt_eval_count | 57542 |
| Ollama eval_count | 5809 |
| done_reason=length | 0 |
| Request/parse/API exceptions | 0 |
| Валидные кейсы с предупреждением context guard | 1/18 |

Структурные ошибки: E28 review_groups_coverage/review_groups_membership;
E35 document_groups_coverage/document_groups_membership. Они сохранены без retry.
На этих двух кейсах context guard обозначает, что требуется валидная структура;
их нельзя считать прошедшими контекстную проверку.

E36 проходит структуру, но имеет четыре диагностики контекста: у ID1743 и
ID1746 отсутствуют incomplete_context и context_ids непрочитанного родителя.
Это проверка явной связи, без чтения содержимого фото или смысловой оценки ответа.

Токены — измеренные поля Ollama, не usage агента разработки. Денежная стоимость
локального прогона не измерена. Структурная полнота 51/51 не является accuracy.

## Отдельный NextBit-прогон

После второго HTTP429 родитель явно остановил GLM/DeepInfra: 5 записей,
3 нормальных структурно валидных ответа, 2 API-ошибки, 15 невыполненных кейсов.
Причина 429 не установлена; это частичное сравнение сервиса, а не полный результат
модели. Его исходные ledger и результаты сохранены.

По отдельному разрешению пользователя подготовлен `run_nextbit_sample.py`:
новый GLM5.3Flash run на тех же 20 кейсах через only[nextbit/fp8], reasoning low,
без fallback/retry. Provider guard ожидает реальное имя NextBit; ответ DeepInfra
не переименовывается. Новый ledger фиксирует SHA frozen prior ledger и prior_bound;
перед каждой отправкой проверяет прежний SHA и общий cap $1. Используется тот же
flock. Результат `semantic-holdout-glm-nextbit.json`, ledger
`semantic-nextbit-budget.json`; оба приватные 0600.

Dry-run: prior_bound $0.017616147; own reserve upper $0.119694;
combined upper $0.137310147. Это консервативные резервы, не списанная стоимость.
Mock-тест `test_nextbit_sample.py` прошёл: явный NextBit guard, неизменность prior
SHA/ledger, общий budget, unknown reserve, duplicate/pending/no-retry, отсутствие
ключа в stdout, malformed envelope/JSON. Сам разработчик live не запускал;
родитель начал отдельный процесс. Wrapper/shared code зафиксированы на время run.

Comparator добавляет glm_nextbit отдельной строкой и учитывает frozen prior bound
ровно один раз. Его целевой тест подтверждает отсутствие двойного счёта бюджета.
После завершения cloud/NextBit родителю нужно обновить comparison snapshot.

Свежий snapshot после завершения NextBit: 20/20 структурно валидных кейсов,
51/51 ID, measured elapsed sum 109.024 с; reported NextBit cost $0.013133395.
Reported actual двух ledger суммарно $0.019879342; prior unknown reserve
$0.0108702 остаётся учтённым; combined bound $0.030749542. Pending нет.
Cloud на момент snapshot имеет 17/20 кейсов, measured elapsed не сообщён.
Эти числа описывают фактическую полноту/время/стоимость; смысловой аудит отдельно.
