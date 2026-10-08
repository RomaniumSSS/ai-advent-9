# Два новых сценария: общий бюджет $0.10

`session15_scenarios.json` содержит 15 публичных и 15 полнокорпусных пользовательских сообщений. Это новые сценарии, но не независимый holdout. Старые run01–07 и их оценки сохраняются.

## Порядок и границы

1. Независимо проверить свежие hashes, frozen SHA, scopes, пустые ledgers и offline evidence. До сигнала root живые POST запрещены.
2. `global_session.py activate-public GLOBAL.json`: public cap $0.07. Запустить только public сервер8056, выполнить GET preflight и независимый gate. Scoped runner выполняет public15, checkpoint после6, настоящий restart и `--resume`.
3. Остановить public сервер. `activate-all` отзывает public authorization и выдаёт all cap **$0.10 минус фактическая public charge**. Только затем запустить all8057, проверить GET и выполнить all15.
4. Остановить all8057. `manual-ready` создаёт пустой «Мой чат» в том же all data-dir и ledger. Root переносит этот сервер на8053 после остановки старого preview. Ledger и cap не сбрасываются; ручной чат расходует остаток общего бюджета.

Максимум автоматических provider calls —30, retries0; локальные no_context не вызывают provider. Максимальный резерв одного вызова $0.00450688, public15 $0.06760320, все30 $0.13520640. Поэтому общий cap $0.10 **не гарантирует30 вызовов при худшей стоимости**. Переход к all требует достаточного резерва15; иначе остановка без новых вызовов. Любой unknown/ambiguous spend, mismatch, незавершённое действие или изменение закрытого public ledger также останавливает исполнение.

## Видео

Только public browser context: реальные поиски и ответы этого сценария, изменения памяти, refresh, restart и второй изолированный чат без дополнительных ask. Две записи вокруг restart сохраняются в private до privacy review. Цель итогового монтажа2–3 минуты; допускается удалить ожидание, но не выдумывать действия/ответы. All context никогда не записывается. Старое видео не служит доказательством нового запуска.

## Офлайн-проверка

Synthetic02:30 сообщений, public15/all8 mock генераций,7 локальных all no_context, provider0. Настоящий restart,15 уникальных public IDs в2 сегментах,0 all IDs/дополнительных ask. Controller: public revoked, all cap .09985, после завершения manual-ready .09977 на том же ledger. Это механическая проверка; качество реальной модели NOT PROVEN. Tests46 app +21 validation PASS. Private evidence: `day25/private/session15-synthetic-02/SYNTHETIC-GATE.json`.
