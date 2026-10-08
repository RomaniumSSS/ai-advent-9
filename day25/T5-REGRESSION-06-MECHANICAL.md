# T5: шестой regression — механический результат

04.10.2026. Пользователь разрешил 2×12 сообщений, новые отдельные caps $0.06 public/all, max24 provider calls, retries0. Regression на прежних сценариях, не независимый holdout. Старые run01–05/raw/verdicts не изменены. Семантический PASS здесь не утверждается.

## Preflight и выполнение

43 app tests PASS (4.628s), 15 validation tests PASS (0.015s). Независимый pre-POST readiness PASS: fresh dirs/empty ledgers/chats/results, permissions0700, scopes/docs1/663, approved budgets/retries. Runtime SHA `1254d07d50c6b2297a4b560cd74ba9ce474bba47817ba267d5ec6ba531c47f6b`; scenario SHA `2438f66008ce72ccb2f2e3c27b5e33ff86eacfbd5c049b04cf5a1a84ae650430`; frozen SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`. Exact GET SHA/scopes/caps/zero charge и повторный code hash доPOST PASS. Maximum reserve24 calls $0.10816512, caps отдельно $0.06.

Обычный UI, public6 checkpoint exit2, настоящий SIGINT/start public8054 на прежнем data-dir, PID81635→83775. Resume проверил6 IDs/state и завершился exit0. Refresh безPOST/новогоcharge. Mismatch/unknown/ambiguity не возникли. Day24 не затронут. Код/caps не менялись во время run, дополнительных экспериментов нет.

| Scope | Ходы/поиски | Calls | Статусы | Actual cost | Prompt/completion/total tokens |
| --- | --- | --- | --- | --- | --- |
| public |12/12|12|12 verified|$0.0041474496|28371/4391/32762|
| all |12/12|12|11 verified, 1 unverified|$0.0103879384|51977/10884/62861|
| всего |24/24|24|23 verified, 1 unverified|$0.014535388|80348/15275/95623|

Provider DeepInfra / deepseek-v4.1-flash, actual usage costs совпадают с ledger charged. Unknown0/retries0/caps не превышены. All11 unverified сохраняется без повторов; источник, формат и смысл проверяются отдельно. Verified не означает смысловой PASS.

## Evidence и stop point

Private/live-run-06: raw all, CODE-SNAPSHOT.json, USAGE-SUMMARY.json, run/events, semantic-review.csv. Setup private/recheck-setup-06.json. Private MECHANICAL-REPORT.json содержит агрегаты и ссылку на этот отчёт.

Private/live-video-06/saved-public.webm и PNG/RECORDING.json: recorder exit0, browser methodsGET only, newsearch/provider0, ledger до=после $0.0041474496, public DOM PASS. Saved public playback, fresh_search_demonstrated=false, publication NOT_APPROVED.

Следующий шаг — независимый semantic gate Astra всех24 ответов и human acceptance. Без нового решения не запускать дополнительные provider calls. Commit/push/deploy/publication не выполнялись.
