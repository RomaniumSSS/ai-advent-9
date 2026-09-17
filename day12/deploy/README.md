# Приватный runtime DeepSeek дня 12

Этот runbook подготовлен на EXECUTION, на VPS сейчас не выполнялся.
Предыдущий `results/vps-deploy-report.md` описывает **offline** release, а не
доказательство работы реальной модели. Codex остаётся внешней машиной разработки.
Runtime использует существующий OpenRouter SDK, DeepSeek и SQLite дня 12.

## До rollout

1. Проверить SSH alias владельца и host key (`StrictHostKeyChecking=yes`), версии
   Python/systemd, свободное место, `ss -ltnp`, unit, Caddy и firewall IPv4/IPv6.
   Сохранить их конфигурации и active/enabled соседних сервисов. Не менять соседей.
2. Зафиксировать старый release и unit. Снять SQLite backup через `Connection.backup()`
   в отдельный файл, проверить `PRAGMA integrity_check`. Обычное копирование живой
   SQLite с WAL не является backup. Сохранить владельцев/права и путь отката.
3. Подготовить отдельный release из day12, venv с `deploy/requirements.txt`
   (`pip install --require-hashes`), заранее наполненный кеш `o200k_base`.
   `deploy/check_offline.py` проверяет только кеш без сети, не выбирает backend.
   Не переносить соседние .env, домашние каталоги и другие ключи.
4. Перед живым прогоном проверить доступность точного ID
   `deepseek/deepseek-v4-flash-0731` и доступный provider в каталоге OpenRouter.
   Подмена модели запрещена. Подготовить `/etc/ai-advent-day12/live-policy.json`:

```json
{
  "model": "deepseek/deepseek-v4-flash-0731",
  "provider": "REPLACE_WITH_VERIFIED_PROVIDER_SLUG",
  "prompt_usd_per_million": "REPLACE_WITH_VERIFIED_UPPER_PRICE",
  "completion_usd_per_million": "REPLACE_WITH_VERIFIED_UPPER_PRICE",
  "max_prompt_tokens": 8192,
  "max_tokens": 512,
  "price_source": "REPLACE_WITH_CATALOG_EVIDENCE_PATH_OR_URL",
  "verified_at": "REPLACE_WITH_UTC_TIMESTAMP"
}
```

Цены — USD за миллион токенов, положительный проверенный верхний тариф, с учётом
всех применимых начислений. Старые цены models.py не являются таким подтверждением.
Шаблон намеренно не запускается. Политика не содержит секретов, root:root 0644.
При отсутствии проверенной цены вызовы не разрешаются. OpenRouter routing получает
`only`, `allow_fallbacks=false`, `require_parameters=true` и `max_price`.

## Единственный секрет

Создать каталог `/etc/ai-advent-day12` root:root 0755. Отдельный
`openrouter.env` root:root **0600** содержит ровно одну строку:
`OPENROUTER_API_KEY=<значение из защищённого источника>`.
Передавать файл по аутентифицированному SSH через stdin в привилегированную
установочную команду с `umask 077`, без shell trace, значения в argv, логах или
терминале. Проверить права через `stat`, не `cat`. Не выводить `systemctl show -p
Environment`, окружение процесса или содержимое файла. Unit читает только этот
EnvironmentFile; автоматического поиска .env в runtime нет.

## Сеть и запуск

Unit `day12.service` запускается **без --offline**, с обязательным ledger
`/var/lib/ai-advent-day12/live-ledger.json`. Он не удаляется при перезапуске,
переустановке release или откате. Вся серия A/B, повтор и VPS smoke используют
этот один ledger; после лимита сервис отказывает в новых модельных вызовах.
Не снимать бюджет для обхода остановки.

Оба listener слушают `127.0.0.1`: read-only 8035, управление 8036.
Caddy публикует только read-only listener:

```caddy
YOUR_DAY12_HOST {
    reverse_proxy 127.0.0.1:8035
}
```

В firewall закрыть прямые 8035/8036 для IPv4 и IPv6. Запрещены proxy-маршруты
на 8036, wildcard bind и публичный SSH port forwarding. Host/Origin защищают
браузер, аутентификация владельца обеспечивается SSH-ключом и туннелем:

```sh
ssh -N -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -L 127.0.0.1:8036:127.0.0.1:8036 VERIFIED_OWNER_ALIAS
```

Проверить новый release отдельно, `systemd-analyze verify`, tokenizer preflight,
секретные права и маршруты без POST /api/chat. Переключить release/unit после
готовности отката; `systemctl daemon-reload`, restart, проверить `ss`, состояние
процесса, GET /api/state (`offline=false`, модель DeepSeek). Любой публичный POST,
включая неизвестный путь, обязан вернуть 403 до чтения тела. Публичный
GET /api/evidence должен вернуть 404. Проверить это с внешней машины; GET не
вызывает модель. Read-only страница показывает общие данные: использовать только
демонстрационные профили и вопросы, не личную историю владельца.

## Один доказательный прогон

При свободной панели и пустом **первоначальном** ledger выполнить локально через
туннель, только на разрешённом VALIDATION этапе:

```sh
python day12/verify_live.py --url http://127.0.0.1:8036 --report day12/results/live-deepseek.json
```

Runner делает A/B с одинаковой пустой историей и третий вопрос в новой сессии
без повторного сохранения B. Это одновременно три реальных VPS smoke-вызова.
Не нажимать чат параллельно. Четвёртая попытка — только заранее описанный резерв;
runner её автоматически не использует. Перезапуск runner не сбрасывает ledger.
Ошибка провайдера, неизвестный usage/cost, обрыв, выход за резерв или незавершённый
ответ останавливают серию. При HTTP timeout проверять ledger, не повторять POST.
Сбой процесса с in-flight попыткой запрещает дальнейшие вызовы. Reported cost
сверх резерва честно фиксируется как нарушение, не выдаётся за соблюдение бюджета.

После успешной механической проверки человек заполняет rubric: A — деловой стиль,
три коротких пункта без аналогий; B и повтор — два абзаца, понятное объяснение,
бытовая аналогия, без списков. Проверить фактическое различие ответов, request ID,
модель/provider, usage, сумму <= $0.02, attempts <= 4. Не использовать model judge.
Сохранить отдельно внешний network smoke и признаки VPS процесса: один JSON
runner не доказывает конфигурацию внешнего proxy/firewall.

## Откат

Остановить новый сервис, вернуть сохранённый release/unit и только изменённые
настройки proxy/firewall. При необходимости восстановить согласованный SQLite
backup при остановленном сервисе, вернуть права. **Не откатывать ledger**.
Проверить прежнее состояние соседей. Старый offline release — аварийный откат,
не выполненный результат задания. Ключ и policy хранятся отдельно от releases.

## Mass-live

Этот раздел — подготовленная процедура будущего разрешённого live-этапа, не свидетельство
развёртывания. Не включать mass mode до сохранения release/unit/config/SQLite WAL backup,
проверки старых evidence hashes и offline validation. Готовый opt-in шаблон:
[mass-live.conf](mass-live.conf), policy: [mass-live-policy.json](mass-live-policy.json).
Старый live-ledger.json остаётся неизменным. Новый путь фиксирован в DAY12_MASS_LEDGER;
legacy CLI/get_client и все обычные HTTP mutations в campaign mode отключены.
Не запускать параллельно старую release или процесс с API key вне systemd unit.

Установить drop-in и policy только в рамках разрешённого rollout. Unit остаётся прежним,
оба listener — 127.0.0.1:8035/8036. Публичный read listener не обслуживает ни campaign POST,
ни campaign/legacy evidence GET. У Caddy не должно быть маршрута на 8036.
Owner tunnel: `ssh -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -L 127.0.0.1:8036:127.0.0.1:8036 OWNER_HOST`.
Runner допускает только HTTP 127.0.0.1 с явным портом, без proxy/redirect и retry.

Сначала сервис создаёт manifest (без сети); получить его hash через owner GET
`/api/campaign/evidence`. Создать на VPS `/var/lib/ai-advent-day12/mass-gate.json` (0600).
Это owner attestation на основании сохранённых команд/выводов, **не автоматическое
доказательство самим значением true**. Validation/review должны проверить raw evidence.
Обязательные поля:

```json
{
  "campaign_id": "day12-mass-01",
  "manifest_hash": "HASH_FROM_PRIVATE_EVIDENCE",
  "db_path": "/var/lib/ai-advent-day12/history.db",
  "verified_at": "UTC_ISO_TIMESTAMP",
  "public_mutations_denied": true,
  "public_evidence_denied": true,
  "direct_ports_denied": true,
  "loopback_listeners": true,
  "sqlite_integrity": true,
  "neighbours_healthy": true,
  "owner_ssh_tunnel": true,
  "legacy_paid_disabled": true,
  "parameters_supported": true,
  "provider_raw_names": ["open-inference", "OpenInference"],
  "prompt_usd_per_million": "0.04",
  "completion_usd_per_million": "0.10",
  "network_evidence": {"path": "/PRIVATE/network.txt", "sha256": "HASH"},
  "tariff_evidence": {"path": "/PRIVATE/provider-metadata.json", "sha256": "HASH"},
  "prior_ledger": {"path": "/var/lib/ai-advent-day12/live-ledger.json", "sha256": "ACTUAL_BYTE_HASH"}
}
```

Gate живёт максимум 24 часа, после первого prepared его hash неизменен. Provider metadata
должны подтвердить точное имя/alias, параметры none/max_tokens/provider routing и ceilings.
Raw old ledger обязан совпасть с anchored embedded ledger прежнего repaired report;
не использовать report file вместо ledger file. SHA байтов проверяется отдельно.
Отсутствующий или просроченный gate закрывает dispatch без paid send.

Network evidence: публичные POST chat/profile/save/forget/scope/reset/resume/campaign routes
получают отказ до чтения body; evidence/checkpoint/raw paths не доступны. Проверить Host/Origin,
alternative methods, внешние IPv4/IPv6 прямые порты, `ss -ltnp` без wildcard listener,
firewall, неизменность ledger после негативных probes. Использовать невалидный chat body.
SQLite `PRAGMA integrity_check`, schema/ownership, day12 health, соседние services health
снимать до/после, без их restart. Секреты и Authorization в evidence не писать.

Запуск owner runner:

```
python mass_live.py --tunnel http://127.0.0.1:8036 --output results/mass-live/day12-mass-01/report.json
```

Строго после 18 terminal cases (S02) runner вызывает restart-prepare и выходит.
Checkpoint содержит session H с реальным S01 turn, notes/profile/DB path, completed hash,
cost, PID и systemd INVOCATION_ID. Сохранить также systemctl status/start time и ledger hash
в raw evidence. Закрыть runner; выполнить ровно один `systemctl restart day12` через owner SSH.
Если процесс оборвался, сначала сравнить InvocationID, не перезапускать и не делать seed вслепую.
Снова проверить network/SQLite/neighbours/readiness без модели и сохранить сырой отчёт 0600.
Передать runner `--restart-evidence PRIVATE_RESTART_JSON`, где:

```
{"invocation":"NEW_SYSTEMD_INVOCATION_ID","pid":12345,
 "loopback_listeners":true,"public_mutations_denied":true,"public_evidence_denied":true,
 "direct_ports_denied":true,"neighbours_healthy":true,"sqlite_integrity":true,
 "path":"/PRIVATE/restart-raw.txt","sha256":"HASH"}
```

Сервер сам сравнит PID/InvocationID и сохранённые данные. До restart_verified S03 запрещён.
Ни профиль L, ни session H при restart не создаются заново. HTTP timeout не разрешает повтор
SDK send: повторное подключение восстанавливает состояния по серверному ledger.

При failure сохранить ledger/.created/.lock, SQLite/WAL, raw reports; отключить paid dispatch.
Вернуть release/unit/config с **закрытым paid режимом**, не откатывая ledger/cost.
DB backup восстанавливать только при доказанном повреждении после сохранения текущей evidence.
После rollback повторить network/integrity/neighbour checks; rollback не разрешает paid retry.

Финальный report отдельно показывает pass rates среди выполненных и всех 24, все defects,
известные costs/неразрешённые reservations и human rubric pending. Неплатные blocked cases
не являются 24 live evidence. Visual/видео/независимый review выполняются на последующих этапах.
