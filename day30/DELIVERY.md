# Day30 — доставка

Текущая сдача исходного задания по [SPEC](SPEC.md): **PUBLISHED_AND_READ_BACK; человеческая приёмка отдельно**.
Использован существующий profile12; исторический private semantic FAIL сохранён
как ограничение дополнительного пересказа и не блокирует этот маршрут сдачи.

| Пункт | Фактический статус | Подтверждение |
| --- | --- | --- |
| D1 · домашняя локальная LLM,API и чат | PASS — Mac M2, loopback Ollama и LAN HTTPS API/чат | [Запуск](README.md),[LAN/model preflight](results/assignment-delivery-preflight.json) |
| D2 · три последовательных ответа и same-chat follow-up | PASS — dry3 + record3, новые IDs; same-chat follow-up | [Dry3](results/assignment-dry.json); новые IDs/receipts, три done, два разговора |
| D3 · LAN HTTPS и защита | CA+hostname/main/demo PASS; реальные401/400/Host403/Origin403; другое устройство NOT PROVEN | [Preflight](results/assignment-delivery-preflight.json) |
| D4 · limits/стабильное хранение | PASS — 151 offline; live400/409; observed budgets8192/output1024 обеих стадий; API readback | [151 offline / LAN preflight](results/assignment-delivery-preflight.json),[Dry3](results/assignment-dry.json),[Record3](results/assignment-record.json);429 offline,409 live, observed budgets/readback |
| D4 · ранее выполненный restart/recovery |27 сохранённых состояний PASS; новый restart не заявлен | [restart12](results/restart-12-completed.json),[recovery12](results/recovery-profile12-completed.json) |
| Harness review | APPROVED — обе независимые проверки | [Luna](results/assignment-review-luna.md) → [Astra](results/assignment-review-astra.md); Luna→Astra, отдельно от code12 |
| D5 · новые live assignment-вопросы на видео | PASS — новый MP4 и проверенные кадры | [Record3](results/assignment-record.json),[сценарий](video/SCENARIO.md),[видео](video/README.md) |
| D6 · код опубликован | PASS — SHA и содержимое проверены | [GitHub main/day30](https://github.com/RomaniumSSS/ai-advent-9/tree/main/day30),3c6d2c19b0e9ad429bec1e7fe02892e53a5dc01a |
| D6 · видео Drive,Anyone with link/Viewer | PASS — Anyone with link / Viewer, playback | [Day30-live.mp4](https://drive.google.com/file/d/1qZXTzqn9nUa3OL_yNYksOahMt_RivTZY/view?usp=sharing),[Publication](results/assignment-publication.json) |
| D6 · две отдельные ссылки под Day30 в таблице | PASS — заголовок/владелец/сохранение/reload/readback | [Day30 · AE132](https://docs.google.com/spreadsheets/d/1eFmeejRLXnT5fic3uxagtNgQBvv6uAKUG5McRlEo-eE/edit?gid=0#gid=0&range=AE132),[Publication](results/assignment-publication.json); заголовок/сохранение/reload/readback |
| Пользовательская приёмка | Pending | Подтверждает пользователь |

Свежие ответы: dry 3,record 3; времена/токены и границы
доказательств — в [RESULT](RESULT.md). [Исторический actual12](results/live-private-12.json)
runtime PASS/semantic FAIL не переоценён. Всего15 completed private queries сохранены;
новые public assignment queries считаются отдельно. Корпус, исходные private traces,
credential, raw screenshots/receipts не включены в публичный пакет.
