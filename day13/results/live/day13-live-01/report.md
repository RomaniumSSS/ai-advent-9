# Массовый live-eval дня 13

- Campaign: `day13-live-01`
- Ситуаций: 64; реальных provider calls: 1; pause guards без сети: 0
- Pass rate реальных ответов: 0.0%
- Reported cost: `$0.00002707` при лимите `$0.02`
- Restart/resume live cases: 0/12
- Campaign gate: `FAIL`; stopped: `agent reply invalid after paid response`
- Ledger SHA-256: `3bb0c42b004e0babe2ffc68842ae448e372d233357d2d89462239a14e2db52fd`

Raw provider responses, requests, state snapshots, hashes и checkpoint chain находятся в `ledger.json`.
Cases со статусом `paused_pass` не являются provider evidence: они доказывают локальный запрет model call.

## Defects

- `B101` — `safety_fail`
