# T5: финальный regression run07 — механический результат

04.10.2026. Пользователь явно разрешил свежие caps $0.06 public/$0.06 all, max24 provider calls, retries0. Те же2×12 сценария — regression, не independent holdout. Старые run01–06/raw/verdicts не изменены. Семантический PASS здесь не утверждается.

## Gate и выполнение

45 app tests PASS (4.702s),15 validation tests PASS (0.015s). Новая optional public запись прошла full offline2×12/restart и независимый gate:2publicsegments/12unique publicIDs/noall/noextraasks. Default runner без записи сохранён.

Runtime SHA `c542a8a1190a73aab8cbc06cca70fa8e562d804e05e72a2cab9b208331d86776`; runner SHA `de8e20d907b9da9e9378305671e3c03ab9a55a99657a6b07ffe0f42913d34614`; scenario SHA `2438f66008ce72ccb2f2e3c27b5e33ff86eacfbd5c049b04cf5a1a84ae650430`; frozen SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`. Fresh separate dirs/ledgers, approved scopes public/all docs1/663, permissions0700, exact GET scopes/SHA/caps/zerocharge и runtimehash сверены доPOST. Independent readiness PASS. Reserve upper bound24 calls $0.10816512; caps отдельные $0.06.

Обычный UI: public6 checkpoint exit2, реальный SIGINT/start public8054 на прежнем dir, PID48266→49748; resume проверил6 IDs/state и завершился exit0. Refresh безPOST/новогоcharge. Mismatch/unknown/ambiguity отсутствуют, retries0, дополнительных экспериментов нет. Day24 не затронут.

| Scope | Ходы/поиски | Calls | Статусы | Actual cost | Prompt/completion/total tokens |
| --- | --- | --- | --- | --- | --- |
| public |12/12|12|12 verified|$0.0040301128|28471/4368/32839|
| all |12/12|12|11 verified, 1 unverified|$0.0102481176|52300/11147/63447|
| всего |24/24|24|23 verified, 1 unverified|$0.0142782304|80771/15515/96286|

Provider DeepInfra / deepseek-v4.1-flash. Usage cost совпадает с ledger charged, caps не превышены, unknown0. All5 unverified `attribution_not_cited` сохранён без исправления/повтора; all12 verified. Verified означает структурные/цитатные проверки, не смысловой PASS.

## Видео и evidence

Fresh public recording во время12 обычных ask:2segments,12unique publicIDs exactmatch,0allIDs/extraasks. Recorded context закрыт доall. Private/live-fresh-video-07 содержит исходные сегменты и concatenated submission.mp4; FRESH-VIDEO-GATE.json в run07 подтверждает ID/provenance. Публикация отдельно, не выполнена.

Saved GET-only public playback private/live-video-07: recorder exit0, browser methodsGET only/newsearch/provider0, ledger before=after $0.0040301128, public DOM PASS. Это дополнительный просмотр, без новых оплаченных вызовов.

Private/live-run-07: raw all, USAGE-SUMMARY.json, CODE-SNAPSHOT.json, MECHANICAL-REPORT.json, manifest/events, semantic-review.csv. Setup private/recheck-setup-07.json. Следующий шаг — independent semantic/privacy gate и честные submission docs; human acceptance не подменяется агентской оценкой. Commit/push/publication здесь не выполнялись.

## Независимый финальный gate

Astra:22 смысловых PASS/0 FAIL/2 NOT PROVEN. A1 NOT PROVEN:all4 нужное обсуждение размера чанков не найдено; all5 ответ скрыт attribution_not_cited. A2–A6 PASS, human acceptance NOT PROVEN. Public9/all11 улучшения подтверждены агентской оценкой. T5 не закрыта.

MP4 privacy/provenance gate PASS:99.36s,1280×900,H.264/noaudio; concat только2publicsegments, duration=suminputs, independent sampled frames публичные. [Tracked submission copy](video/Day25-chat.mp4) SHA `cec4f322ed33c0bb90c125a819af97d48f3c64e67b55e7587152ed47357b8b21` совпадает с private source. Сервера8053/8054 остановлены. Docs готовы к независимому precommit gate; исполнитель commit/push не выполнял.
