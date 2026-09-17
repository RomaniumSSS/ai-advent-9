# День 12 — накопительный агент с профилем пользователя

Самостоятельная копия дня 11: история, три слоя памяти, области user/task/session,
reset и сохранение в SQLite. `style`, `format`, `constraints` находятся отдельно
в `user_profiles`. Один снимок профиля автоматически входит в фактические messages
и их токеновый бюджет. Профиль не записывается в историю или слои памяти.

Production использует `deepseek-v4-flash` через существующий OpenRouter SDK.
Codex — только внешний control plane; его CLI/SDK не используются runtime.
Реальный runtime развёрнут на VPS; массовая кампания из 24 вызовов, restart,
network smoke, три viewport и replay-видео проверены 16 сентября 2026 года.
Исторические reports и `demo/day12-offline.webm` относятся к test double;
актуальные доказательства находятся в `results/mass-live/day12-mass-01/`.

## Запуск

```sh
# Из корня, только при намерении вызвать реальную модель:
.venv/bin/python day12/web.py --env-file /absolute/private/openrouter.env
# Локальная тестовая демонстрация, без модели:
.venv/bin/python day12/web.py --offline
.venv/bin/python day12/cli.py --offline
```

Реальный запуск читает `OPENROUTER_API_KEY` из окружения либо явно указанного
`--env-file`; соседние .env автоматически не ищутся. Нет fallback на OfflineClient.
Панель — `http://127.0.0.1:8042`. Токенизатору нужен заранее установленный кеш.
`--offline` — только test double, а не production и не доказательство полезности.

[Production runbook](deploy/README.md) задаёт private owner tunnel, два loopback
listener, read-only публичный proxy, отдельный секрет 0600 и постоянный live ledger.
Live-бюджет подключается `--live-policy FILE --live-ledger FILE` к непосредственному
SDK create; production unit включает его. Максимум 4 попытки и $0.02 reported cost.
Проверенные верхние цены обязательны; ошибки/неизвестный usage останавливают прогон.
[Runner](verify_live.py) выполняет три доказательных вызова через private runtime.

## Использование

Кнопки brief/detail открывают профили. Редактор сохраняет изменения явно;
каждый следующий вопрос получает их автоматически. Reset сохраняет профиль.
Новая сессия/задача того же пользователя сохраняет предпочтения; чужая область
не получает память другого пользователя. Это однопользовательская панель:
`user_id` обозначает область данных, а не аутентификацию. Доступ владельца — SSH.

CLI: `/profile`, `/profile {"style":"Кратко","format":"Список","constraints":"До трёх пунктов"}`,
`/context Вопрос`, `/reset`. Предпочтения не дают разрешений и не отменяют системные
ограничения; текст профиля не является защитой от prompt injection.

## Проверки и доказательства

Из day12 (в scratch-копии, поскольку старый test_profile пишет свой A/B artifact):

```sh
../.venv/bin/python test_memory.py
../.venv/bin/python test_profile.py
../.venv/bin/python test_web.py
../.venv/bin/python test_deploy.py
../.venv/bin/python test_live_budget.py
../.venv/bin/python test_verify_live.py
../.venv/bin/python test_runtime.py
node --check web/app.js
node --check demo/record.cjs
```

Offline tests проверяют механизм и границы, не ответы DeepSeek.
Текущая реализация и проведённые локальные проверки:
[implementation](results/mass-implementation.md) и
[validation](results/local-offline-validation.json).
Реальная массовая кампания завершила 24/24 cases: 17 pass, 7 quality_fail,
0 safety_fail. Память прошла 8/8, состояние 4/4, adversarial 4/4, строгая
профильная рубрика — 1/8. Общий расход с тремя прежними попытками — $0.00032573.
[Полный отчёт](results/mass-live/day12-mass-01/live-report.md) и
[видео](demo/README.md) воспроизводят сохранённые ответы без новых вызовов.
Human semantic rubric расширенного eval остаётся отдельным ручным gate и не входит
в исходное условие учебного задания «Видео + Код».

## Массовая live-кампания

Отдельная реализация: [mass_live.py](mass_live.py), [mass_checkpoint.py](mass_checkpoint.py),
[mass_fixture.py](mass_fixture.py), [mass_grade.py](mass_grade.py), [24 fixtures](mass_cases.json).
Она использует существующие Agent.build_messages/request_options и SQLite-модель памяти.
Codex отсутствует в runtime/grading. Старый LiveBudget/manual_resume не меняет свои правила.
Campaign dispatch сохраняет raw response перед проверкой телеметрии и атомарно записывает
реальный turn вместе с request ID receipt. Синтетическая история имеет отдельный provenance.

Новый ledger содержит manifest с hash кода, fixtures, policy и трёх старых отчётов.
Каждый SDK send находится под межпроцессным lock и durable in_flight. Повтор того же ID
возвращает evidence; response_recorded дооценивается без сети. Неопределённый in_flight
становится indeterminate и закрывает всю кампанию. .created seal запрещает случайно
получить новый бюджет удалением ledger. Файлы ledger/.created/.lock сохранять вместе.

Качество оценивается правилами; quality_fail, включая length, не останавливает следующие
cases. Provider/usage/cost/scope/injection/persistence failure закрывает дальнейшие sends.
Неизвестная стоимость не приравнивается нулю: report содержит cost_complete=false и
unresolved_reservations_usd. Человек заполняет отдельную human rubric со ссылкой на response hash;
она не перезаписывает deterministic результат. Всегда сохраняются исходные неудачные ответы.

Лимит: 24 новых вызова, 3 прежних и $0.00013246 учтены ровно один раз; общий cap $0.02.
Тарифы в policy исторические и требуют свежего preflight. При указанных ceilings резерв
$0.00035328 на send, максимум с prior $0.00861118; это расчёт, а не live расход.

[Runbook](deploy/README.md#mass-live) описывает отдельный opt-in drop-in, owner-only
preflight и точную остановку после S02. Кампания выполнена на production VPS;
raw network/restart evidence и итоговый отчёт сохранены в
`results/mass-live/day12-mass-01/`.
Офлайн-проверка: `python -m unittest test_mass_grade test_mass_live`.
Replay: `node demo/record.cjs results/mass-live/day12-mass-01/report.json`;
видео показывает также quality failures и blocked cases, все browser requests запрещены.
