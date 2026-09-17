# Массовый live-eval дня 13

- Campaign: `day13-live-04`
- Ситуаций: 64; реальных provider calls: 60; pause guards без сети: 4
- Pass rate реальных ответов: 78.3%
- Reported cost этой кампании: `$0.00050263`; вместе с failed precursor: `$0.00213769` при лимите `$0.02`
- Restart/resume live cases: 12/12
- Campaign gate: `FAIL`; stopped: `None`
- Ledger SHA-256: `39c0255f20c5b21971ae8d03e382a72f6ef6ad4464ad08072f1465c019a4f056`

Raw provider responses, requests, state snapshots, hashes и checkpoint chain находятся в `ledger.json`.
Cases со статусом `paused_pass` не являются provider evidence: они доказывают локальный запрет model call.

## Defects

- `A402` — `quality_fail`
- `A404` — `quality_fail`
- `B401` — `quality_fail`
- `B402` — `quality_fail`
- `B403` — `quality_fail`
- `B404` — `quality_fail`
- `B405` — `quality_fail`
- `B406` — `quality_fail`
- `B407` — `quality_fail`
- `B408` — `quality_fail`
- `R401` — `quality_fail`
- `R402` — `quality_fail`
- `R403` — `quality_fail`
