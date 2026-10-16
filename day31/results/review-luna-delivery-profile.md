# Узкое ревью delivery-profile patch — Day31

**Reviewer:** gpt-6-luna
**Вердикт:** APPROVED для диагностики API ошибок и production prompt.

## Findings

Замечаний не найдено. При HTTP 200 с `response.error` адаптер распознаёт upstream-ошибку до обработки ответа как incomplete. SDK HTTP errors тоже классифицируются как upstream errors. В журнал попадают только allowlisted `code`, `type`, `status` и имя класса исключения; raw body/message, reasoning content и ключи не сохраняются. Сообщение `ProviderError` остаётся фиксированным и не раскрывает upstream body. Неоднозначный HTTP сбой оставляет прежний резерв в ledger; SDK retry отключён.

Production SYSTEM совпадает байт-в-байт с `results/prompt-diagnostic-20261016/tested-system.txt`; default profile остаётся `z-ai/glm-4.7-flash` через `venice/fp8`, с reasoning отключённым. Исправление не меняет лимит/схему ledger и не затрагивает неизвестные резервы предыдущего сравнения.

## Проверки

- Самостоятельно запустил `uv run --frozen python -m unittest day31.tests.test_provider -v`: **19/19 PASS**, 0.975 s.
- Новые регрессии используют установленный OpenAI SDK и `httpx2.MockTransport`: HTTP 200 error envelope и SDK HTTP 404; каждый сценарий делает ровно один запрос, сохраняет только ожидаемую диагностику, не сохраняет synthetic body/reasoning, не считает неизвестную стоимость нулевой и удерживает резерв.
- Проверка совпадения SYSTEM прошла; `git diff --check` прошёл.
- Платных вызовов не выполнял, ключи и общий ledger не читал и не менял.

Это локальное подтверждение обработки ошибок. Причина предыдущих production API ошибок и фактическое списание за них остаются неизвестными; этот patch сам по себе не подтверждает семантическое качество ответов.
