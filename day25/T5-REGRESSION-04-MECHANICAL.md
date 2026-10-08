# T5: четвёртый regression — механический результат

04.10.2026. Пользователь явно разрешил повтор после comparison repair:2×12, новые отдельные cap$0.06 public / $0.06 all, max 24 calls, retries 0. Это regression на прежних сценариях, не независимый holdout. Старые live01–03 raw и оценки не менялись. T5 PASS здесь не утверждается.

## Preflight и выполнение

33 app tests PASS3.727с/8 preparation PASS0.005с. Read-only runtime code SHA `4f9ac6c8cce4fd2829eaeea7e6e2fbd159bc123d053d9cd6efa75223f76f4252`; scenario SHA `2438f66008ce72ccb2f2e3c27b5e33ff86eacfbd5c049b04cf5a1a84ae650430`; frozen SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`. Новые отдельные private/live-public-04 и live-all-04 с пустыми ledgers, single scopes, public только assignment:18 и cap $0.06 каждый. Max reserve 24≤$0.10816512; GET-preflight обоих dedicated servers до POST exact SHA / scope / budget PASS. Ключи не копировались/выводились.

Public12/all12 через UI. Public 6 checkpoint exit 2; настоящий SIGINT/start8054 с тем же data-dir, PID77702→78207,6 IDs / task state проверены;resume exit 0 MECHANICAL_RUN_COMPLETE. Refresh/archive без новых POST; Day24 не затронут. Mismatch/unknown/ambiguity не возникли, retries0.

| Scope | Ходы/поиски | Provider calls | Статусы | Actual cost | Prompt/completion/total tokens |
| --- | --- | --- | --- | --- | --- |
| public |12/12|12|12 verified|$0.0034581456|22494/4088/26582|
| all |12/12|12|11 verified, 1 model_refusal|$0.0086997736|41871/10316/52187|
| всего |24/24|24|23 verified, 1 model_refusal|$0.0121579192|64365/14404/78769|

Provider DeepInfra / model deepseek-v4.1-flash. Actual usage cost совпадает с ledger charged;unknown 0 / caps не превышены. Отказ all 11 относится к отсутствующему обязательному SLA, его смысловую корректность оценивает independent gate. Согласованные 24 calls выполнены; никаких дополнительных экспериментов / перезаписи ответов.

## Evidence/видео/остановка

Private/live-run-04 хранит raw all, USAGE-SUMMARY.json, CODE-SNAPSHOT.json, semantic-review.csv с NOT_REVIEWED; private/recheck-setup-04.json содержит hashes / approval / scopes / caps.

Private/live-video-04/saved-public.webm  + 2 PNG / RECORDING.json: exit 0, только GET, 0 new searches / provider calls, public ledger$0.0034581456 до = после, DOM guard PASS; publication NOT_APPROVED / fresh_search_demonstrated=false. Это saved public playback, не доказательство качества all.

Следующий шаг — независимый семантический gate Astra всех 24 ходов, особенно all10 comparison и прежних NOT PROVEN. Verified сам по себе не доказывает правильный смысл. Commit/push/deploy/publication не выполнялись.

## Independent gate

Astra: T5 A1 FAIL — all7 неверно связал day22 с message_id 4082 вместо4154; all10 не выполнил содержательное сравнение. Public9/12/all4 NOT PROVEN. Это не PASS. Recorder/cleanup завершены; собственные8053/8054 остановлены, Day24 не затронут.
