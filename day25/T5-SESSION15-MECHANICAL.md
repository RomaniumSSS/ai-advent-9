# Day25 — новые два разговора по15 сообщений

04.10.2026; настоящая модель через обычный UI, последовательные public8056 и all8057. Frozen SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`.

| Scope | Сообщения / поиск / provider calls | Сохранённые статусы | Фактическая стоимость |
| --- | --- | --- | --- |
| Public assignment18 |15 /15 /12|10 verified,3 no_context,1 model_refusal,1 unverified|$0.0040298888|
| All frozen corpus |15 /15 /8|6 verified,7 no_context,2 unverified|$0.0068426344|
| Всего |30 /30 /20|16 verified,10 no_context,1 model_refusal,3 unverified|$0.0108725232|

Unknown и retries0. `verified` означает проверку контракта/источников, а не смысловой PASS. Смысловая оценка — отдельная независимая матрица; этот отчёт не закрывает A1.

## Общий лимит и восстановление

Пользователь разрешил общий cap $0.10 для двух сценариев, видео и последующего ручного чата. Public получил $0.07; после15 сообщений сервер остановлен, authorization отозвана и ledger заморожен. All получил ровно $0.0959701112 = $0.10 − public charge. После all15 сервер8057 остановлен; пустой «Мой чат» создан в том же all data-dir/ledger. Остаток общего бюджета на этот момент **$0.0891274768**; дальнейшая ручная работа уменьшает его, ledger не сбрасывается.

Runtime SHA `e1561e73de7db647bf4ebf1792c5a7b18ac6213a247a68d2b59358d23da268f7`, runner `ea05cfad9a6d8ff30855495bd5e5010c80bfab049cca609bbc4b24eb5b1bfad8`, canonical scenario `d7eb245f0c299d328b4907217563b0658da7560f3dd8f6cc5f13e0270f7722bd`. Свежие dirs/empty ledgers/scopes/hashes и GET preflight независимо проверены перед каждой платной фазой. Public restart после6 выполнен с тем же data-dir; второй пустой чат не получил память первого и не вызвал генерацию.

## Видео и evidence

Новая private public-only запись:2 сегмента/15 уникальных public request IDs/0 all IDs/0 дополнительных ask. Итоговый MP4178.16секунд,1280×900,H.264,без аудио; только склейка и равномерное ускорение1.05× исходных187секунд. Независимый privacy/provenance gate PASS; [сдаваемая копия](video/Day25-session15.mp4) совпадает по SHA256 `9ef07f5c5f93de977a5fa12e0fd6a5a363dde7cc503933f2d427803f88086fab`.

Private raw/матрица/ledger/manifests: `day25/private/session15-live-01`. Старые run01–07 не изменялись. Подготовка:46 app +21 validation tests PASS, полный scoped synthetic30 сообщений с restart/isolation/global controller; provider0. [План и пределы](validation/SESSION15-PLAN.md).

## Независимая оценка

14PASS/12FAIL/4NOT PROVEN; public10/4/1,all4/8/3. A1FAIL,A2–A6PASS в проверенных структурных/офлайн границах,humanNP. NP:public10,all4/all6/all10. Post-run root repair50app+21validation/10savedcontext replayPASS, новоеproviderповедениеNP; старыеraw/liveоценканеизменны.
