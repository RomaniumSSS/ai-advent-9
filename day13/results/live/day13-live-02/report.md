# Массовый live-eval дня 13

- Campaign: `day13-live-02`
- Ситуаций: 64; реальных provider calls: 60; pause guards без сети: 4
- Pass rate реальных ответов: 76.7%
- Reported cost этой кампании: `$0.00079527`; вместе с failed precursor: `$0.00082234` при лимите `$0.02`
- Restart/resume live cases: 12/12
- Campaign gate: `FAIL`; stopped: `None`
- Ledger SHA-256: `9ec4b45d5185b8b3edc9e834608f67329f39584085d33f7d278f0d6ec2fb65af`

Raw provider responses, requests, state snapshots, hashes и checkpoint chain находятся в `ledger.json`.
Cases со статусом `paused_pass` не являются provider evidence: они доказывают локальный запрет model call.

## Defects

- `A401` — `quality_fail`
- `A402` — `quality_fail`
- `A403` — `quality_fail`
- `A404` — `quality_fail`
- `B401` — `quality_fail`
- `B402` — `quality_fail`
- `B403` — `quality_fail`
- `B404` — `quality_fail`
- `B405` — `quality_fail`
- `B406` — `quality_fail`
- `B407` — `quality_fail`
- `R401` — `quality_fail`
- `R402` — `quality_fail`
- `R403` — `quality_fail`
