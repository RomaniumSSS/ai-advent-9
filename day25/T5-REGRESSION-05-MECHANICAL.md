# T5: пятый regression — механический результат

04.10.2026. Пользователь разрешил 2×12 сообщений, два новых cap $0.06 public/all, max24 provider calls, retries0. Это regression прежних сценариев, не независимый holdout. Старые run01–04 не изменены. Семантический PASS не утверждается.

## Preflight и выполнение

40 app tests PASS (4.522 s), 15 validation tests PASS (0.015 s). Independent pre-POST readiness PASS: свежие отдельные dirs/ledger, single scopes, docs1/663, caps и exact SHA. Runtime SHA `7f9be5dd251322fa804f2a34f9957ae8941304b4021db9a032b8b4fb2e4daa05`; scenario SHA `2438f66008ce72ccb2f2e3c27b5e33ff86eacfbd5c049b04cf5a1a84ae650430`; frozen SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`. Read-only GET scopes/budget/identity/zero charge и повторный code hash до POST PASS. Reserve upper bound24 calls $0.10816512, отдельные caps $0.06.

Оба сценария через обычный UI. Public6 checkpoint exit2, реальный SIGINT/start public8054 на прежнем data-dir, PID34425→36976; resume проверил6 IDs/task state и завершился exit0. Refresh без новых POST/charge. Mismatch/unknown/ambiguity отсутствуют; дополнительные calls/retries0. Day24 не затронут.

| Scope | Ходы/поиски | Provider calls | Статусы | Cost | Prompt/completion/total tokens |
| --- | --- | --- | --- | --- | --- |
| public |12/12|12|11 verified, 1 unverified|$0.004537456|28015/4983/32998|
| all |12/12|12|9 verified, 3 unverified|$0.012303676|50476/15987/66463|
| всего |24/24|24|20 verified, 4 unverified|$0.016841132|78491/20970/99461|

Actual provider usage cost совпадает с ledger charged; caps не превышены, unknown0. Provider DeepInfra / deepseek-v4.1-flash. Public4, all1/all5/all10 unverified оставлены без исправления/повтора. Это важные ограничения приёмки новой схемы, даже при безопасной блокировке. Verified доказывает проверки источников/структуры, не смысл сравнения.

## Evidence и stop point

Raw all только `day25/private/live-run-05`, рядом CODE-SNAPSHOT.json, USAGE-SUMMARY.json, run.json/events и semantic-review.csv. Setup `private/recheck-setup-05.json`.

`private/live-video-05/saved-public.webm`, PNG и RECORDING.json: recorder exit0, только GET, new searches/provider calls0, ledger до=после $0.004537456, public DOM guard PASS. Это saved playback, fresh search не демонстрируется, публикация NOT_APPROVED.

Mechanical run complete. Следующий шаг — независимый смысловой gate Astra всех24 ответов и human acceptance; новых запусков/экспериментов не выполнять без решения. Commit/push/deploy/publication не выполнялись.
