# HANDOFF — ai-advent-9

## Текущая точка — 11.10.2026

Publication разрешена: GitHub orderedmain/day29 + видеоDriveprimary сAnyoneViewer
+ дваотдельныхURL собственнымкомментариемЛист1!AD132. Useracceptancefalse.
Activeworktree /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day29-full-chat,
branchday29-full-index-chat, baseca90584. Mainworktreeне трогали; его4untrackeddirsсохранить.
Sourcefullcoref1b62d97…4c9e12 /quality329a11f5…cb89c /recorder947477a1…5bbd8dc8 frozen,
142offlinePASS. Luna→Astra allcodefixesAPPROVED. Fullbackendnative59881run3fa8bdb0…382c13;
originalpublic8069oldworktree+otherapps untouched.

Initial5 run405d5a5a7bac4e0da30aafccb6f600b7: H05/H12/H20/H06/H11 seeded4766433321957233838;
6gen/3embed,15supported claims,4/12full,2falseclarification. Knownresolver2 run5c2b8997…37f0d:
4gen/2embed,H11 2/3+partial,H06unknownsourceomission. Knownanchor1run9d22f02d…8bd96:
2gen/1embed,H06 0/2false_refusal despite1availablegroup; sourcegrade9bd8bac5…46bfc1.
Oldmeasurements immutable; samequestions/gold/index, onlyversionedcodehash. Remaining19unrun.
All3qualityruns12gen6embed48service0HTTPerrors/Bcompleted0; noimprovement/hallrate claim.
Details QUAL_SPEC/TASKS +quality-results/README; corpus/cases/prompts/receiptsprivate0700/0600.

RecordCOMPLETE full-record-20261011-014400/native46651exit0/run52c60273cbbf43fe8c9e822a5ef75fa9.
Canonicalvideo day29/video/Day29-live-full-chat.mp4 SHA4bfe503922a256adf22560c7f5c76cb2c8411dbe440c6d107501ebf34f9f3d10
8,715,854bytes/296.68s/H2641280×1000/25fps; full ffmpegdecode0errors,9decodedframesviewed
plus t30runningnewRID; source supportPASS, E02B2/5→F5/5, fullDay11missing2selfchecks.
Qualifiedreal dry013900/run9781ae36…2c360;3newasks each/disjointIDs/sameHTML9c2ba93c…4263e.
Failedtakes0127000asks and0131001baselineGENpreserved: caughtAPIprofileprojection+canonicalIDs
fixturemismatches beforefinalrecordercorrected. Original99files98unchanged/READMEauthorizedaddition.
Original4conversationfileSHAs preservedafterdry/record;privatecache dirs700 fixed.

Stop: finalAstraactualdeliverymatrix finishing (rootmedia proof sent; no substantive blockers).
AfterAPPROVED: safeGitcandidatecheck→commit→mainff/push→verifyremote/order→Driveupload/publicViewer
→AD1/A132readcheck→ownAD132comment2URL→reloadreadback→publicationproof/docscommit.
Currentexternalwrites0. BrowserDrivefoldertab0primaryaccountverified, SheetAD132tab2selected.
ExactdestIDs inDELIVERY/todo; rootownsallpublication. No branch/worktree deletion.

## Контекст Full chat — 10.10.2026

Развитие полного локального RAG отдельно: ветка day29-full-index-chat, worktree
/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day29-full-chat, база ca90584.
study сохранена (прежняя .DS_Store); исходный public Day29/8069 остаётся в старом worktree.
Все 99 protected файлов и immutable index SHA подтверждены root и Astra.

Sol написал additive full_chat_core.py/full_chat.py/full_chat_static, 28 focused PASS;
прежние 45 offline также PASS. Luna late UI/ellipses findings исправлены RED/GREEN;
самостоятельно выявленный bootstrap stale error исправлен captured-token + browser RED/GREEN.
Astra независимо проверила код, все 724 attribution spans, real receipts и semantics.
Три real UI cases — full-chat-results/live-summary.json; подробности private/full-chat/live/f16bc3e0fa2a4c518460cdb23b88a5a1.
Support 3 PASS; D01 completeness PARTIAL2/3, F01/P01 PASS. Hallucination rate не измерен,
human acceptance false. После resolver fix новые query/messages/payloads/source IDs точь-в-точь
совпали с измеренными, source-phase AST/API не менялись; inference повторно не запускали.

Actual idle restart загрузил final backend; 2 разговора/3 хода сохранились точно, replay нет.
8070 PID24270, native79828, run817c9143e7c141fdb6301be516bcfc9d; старый8069 PID49018.
Final actual UI/source panel proof — full-chat-results/final-browser.json; 3 viewport,
original/parts/author/date exact, final JS served, own empty new/reset, pageerrors0.
Private screenshots viewed; история/полные corpus тексты/receipts только private/full-chat.

Full_chat README/TASKS/RESULT и финальный verdict завершены. User продолжает учебный
диалог параллельно разработке. Актуальная публикация поручена 11.10, см. текущую точку.
Runtime RAG только local, Q8 не грузить, corpus/index не пересчитывать.

## Текущая точка Day29 — 10.10.2026

Day29 выполняется в `/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day29`,
ветка `day29-local-optimization`, база `ca90584`. Пользователь разрешил начать
реализацию и попросил объяснения после, поскольку сейчас не у компьютера.
Отдельное человеческое подтверждение текста SPEC не получено и не заявляется.
Требования/подробные этапы — [SPEC](day29/SPEC.md), [TASKS](day29/TASKS.md);
значимые действия — [журнал](day29/actions.jsonl). Публикация поручена 11.10.2026.

Точная текущая точка: локальная поставка завершена. 45 offline GREEN;
независимый Astra аудит [43 PASS / SPEC SATISFIED](day29/results/implementation-validation.md),
A1/A2 закрыты. Warm `a2606d8f674a48d1b7e2ec8e1549a209`: 12 scored, 4 warmups excluded;
cold `bc205ff1d4d141749152dfa9978ac552`: два E02; Q8
`df5e7e0053954e88858734c3f0a2bbb3`: failed warmup length/384, два warm не запускались.
E02 2/5→5/5, E01/E03 без регрессии; цена — E02 2.30× медленнее, RSS -7.75% ниже10%.

Финальный [MP4](day29/video/Day29-live.mp4): record-02
`6f393fc7546547118052d26de2b60186`, 328.48 s, SHA5082b1f0…, четыре новых IDs,
decode/9 кадров/receipts PASS. Численный swap/GPU показан. Первый дубль и его
SCENARIO п.6 PARTIAL сохранены. [Code ZIP](day29/Day29-code.zip) проверен отдельно
координатором; [proof](day29/results/archive-verification.json).
App остаётся на `http://127.0.0.1:8069`, PID49018, exec session77774.
Чужие Day27/28 процессы не остановлены. Запись/benchmarks закончены, lock свободен.
Следующий шаг: новый прогон пяти вопросов и свежая запись, затем разрешённая
публикация. Прежние дорогие измерения и исходные видео сохранять.

Не потерять причины: pilot sampler не распознал native llama-server, поэтому
pilot RSS daemon-only несопоставим; исправлен до formal warm. Pilot времена
смешивают загрузку/кеш. Первый mobile fixture FAIL сохранён, responsive исправлен.
Исходные frozen contexts сохранены; `inputs-repair-v1.json` — измеренная версия,
`inputs-delivery-v1.json` — тот же input + новые hashes postprocessing/selected UI.
Измеренный evaluate fbe696ad сохранён; текущий fdd23fa6 меняет only guards,
run grouping и failed quant journal durability; core/metrics/LLM payload прежние.
Не восстанавливать отсутствующий original Q8 preparation задним числом.
Q8 скачана на SSD и выгружена из RAM; Q4 и исходную 9B не удалять.

Фактические роли Astra high → Sol high → Luna medium → Astra xhigh;
usage/cost не предоставлены. [EXPLAINED](day29/EXPLAINED.md) готов для чтения
после реализации; пользователь сейчас не у компьютера, понимание не проверено.
Публикация/merge/main/Drive/таблица разрешены поручением 11.10.2026 после проверок.

Основная рабочая папка: `/Users/ramanpazharytski/Projects/ai-advent-9`, ветка `main`.
Объединены линия Day11–20 (`4f927af`) и линия Day21–26 с финальными правками Day25
(`f3ce5d9`). Папки заданий сохранены без изменений относительно соответствующих линий.
Ветки GitHub сохранены: ссылки сдачи продолжают вести на прежние версии.
После объединения удалены 12 неиспользуемых локальных day-веток; каждый commit
предварительно проверен как предок main. `day21-sol-high` удалён после полной копии
265 файлов и проверки SHA-256. Резервная копия и снимок refs:
`/Users/ramanpazharytski/.local/share/ai-advent-9/backups/worktree-cleanup-20261008-200306`.
`study` (текущая сессия) и `jellyfish` ещё используются процессами; пока сохранены.
Для завершения очистки продолжать из основной папки, закрыть старые сессии и перенести
локальные данные. Активные процессы не останавливали, другие проекты не затрагивали.

## Следующее действие

Day28 завершён локально в ветке `day28-local-rag`, папка
`/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28`, база `4659e24`.
SPEC подтверждён 09.10.2026; [подробное выполнение](/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/TASKS.md),
[результаты и ограничения](/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/RESULT.md).
Проверены 31 офлайн тест, 6 новых E2E, три historical replay и live record-02 2:59;
независимая Astra validation — 50 PASS, SPEC SATISFIED. Роли фактически выбраны
Astra high → Sol high → Luna medium → Astra xhigh; usage/cost не предоставлены.

Прежний индекс перенесён без пересчёта, тот же эмбеддер установлен. После ложных
отказов/недословных цитат Qwen новый RAG использует выбранные моделью source refs
и программный оригинальный текст; исходный строгий replay сохранён для сравнения.
E02 PARTIAL и две ошибки replay не скрывать. Record-01 сохранён после FAIL видимых
metadata; новый record-02 соответствует сценарию. Это агентская проверка, не человеческая приёмка.

Точная остановка: готовы локальные `day28/video/Day28-live.mp4` и `day28/Day28-code.zip`,
UI запущен на `http://127.0.0.1:8068`. Далее — пользовательская проверка материалов.
Day28 опубликован по новой команде пользователя 09.10.2026: implementation `6a34587`,
объединение `a5f2757`, обе ветки main/day28-local-rag проверены через GitHub API.
[Публикация](day28/results/github-publication.json). В main теперь Day01–28,
деревья Day01–26 и Day27 сохранены без правок. Новых модельных вызовов не было.
Видео загружено на основной Drive: `1lFO1qjeAPaiP_fJZbfWccZvht0yfb4uj`,
в общей папке `1CUiMGnC-BFP4JTUML8LdS9cA1yPPO0zY`; owner/Viewer по ссылке проверены.
В `Лист1!AC132` добавлен один комментарий с ровно двумя ссылками; после полного reload
прочитаны location и оба URL ([evidence](day28/results/table-submission.json)).
Старую вкладку сначала пришлось синхронизировать native Reload по явному баннеру Google;
после синхронизации comment controls стали доступны. Блокеров нет, далее — пользовательская приёмка.
Новые платные сравнения не разрешены. Приватный снимок/receipts остаются в worktree Day28.

Canonical main fast-forward выполнен с сохранением семи посторонних untracked файлов.
Полные прежние локальные заметки/инструкции сохранены в backup
`/Users/ramanpazharytski/.local/share/ai-advent-9/backups/day28-main-fast-forward-20261009-230624`
и stash `b46c9a28c6b16cf54ccb04e4518101592b04579f`; их смысл уже включён в общие документы,
автоматически повторно применять stash не нужно. `.claude`/peer-review/Drive-заметки не публиковались.


Для следующих заданий применять [проектное распределение моделей](AGENTS.md),
зафиксированное по просьбе пользователя 08.10.2026. Пары — альтернативы провайдеров;
реальный выбор задаётся инструментом, текст prompt модель не меняет.
После первого ревью Luna/Haiku обязательно повторное Opus/Astra по ошибкам,
исправлениям и возможным пропускам, включая случай без замечаний первого reviewer.
Day27 уже выполнен планировщиком/исполнителем Sol medium и независимым reviewer
Sol high до фиксации нового предпочтения; не переснимать его ради смены ролей.
На Day28 фактические роли и независимые ревью применены; эффективность по usage/cost не измерена.

Day25 и Day26 сданы пользователем. Day27 опубликован из отдельной рабочей папки
`/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day27`, ветка `day27-local-app`,
база объединённого main `4659e24875902d3668e48ddea9f8d96a3dd36a5c`.
[Результат и ограничения](/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day27/day27/RESULT.md),
[подробные задачи](/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day27/day27/TASKS.md).
Приложение запущено на `http://127.0.0.1:8067`; Qwen3 8B, без RAG.
Пользователь разрешил коммит, push и загрузку видео: выполнены, удалённый SHA и
Drive owner/Viewer проверены. [Две ссылки и подтверждение](/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day27/day27/results/github-publication.json).
Две ссылки по команде пользователя внесены комментарием в `Лист1!AB132` (Day27)
и проверены после полной перезагрузки таблицы. Следующее действие — пользовательская
приёмка; 09.10.2026 Day27 интегрирован в main вместе с Day28.
Письменный SPEC отдельно не просмотрен, но план и реализация разрешены параллельно.
Для полностью локального RAG в Day28 можно перенести существующий
индекс и ту же `qwen3-embedding:0.6b` с сервера на Mac; смена генератора не требует
пересчёта индекса. Локальное наличие индекса пока не подтверждено.

## Что нельзя потерять

- Приватные индексы, `.env`, SQLite и приватные результаты не переносятся Git-слиянием.
  Они могут оставаться в прежних рабочих папках или на сервере. Папки не удалять.
- Day25: два прогона goal-exec, `no_context` 0/24, остаток общего cap $0.0506751776
  по последнему сохранённому измерению. Независимая смысловая матрица не переснималась;
  `verified` не доказывает атрибуцию. Не запускать платные проверки автоматически.
- Day26: живое видео `day26/video/Day26-live.mp4`. В коде ответа модели есть ошибка
  объединения интервалов с зазором; исходная запись и контрпример сохранены.
- Day27: история ограничена последними восемью завершёнными ходами; ранние сообщения
  остаются в UI. Это ограничение явно указано после ревью. Первый ответ модели даёт
  общий план чата без интеграции LLM; полный текст и исходное видео сохранены.
  Индексы/корпус Day25 не использовались; реальные прогоны выполнялись последовательно.

## Подробные исходные снимки

Снимки сохранены дословно; относительные ссылки внутри них указаны от корня репозитория.

- [Day25: решения, измерения и ограничения](docs/handoffs/2026-10-08-pre-merge-study-HANDOFF.md)
- [Линия до Day20](docs/handoffs/2026-10-08-pre-merge-day20-HANDOFF.md)
- [История статусов Day21–26](docs/handoffs/2026-10-08-pre-merge-study-todo.md)
- [История статусов Day01–20](docs/handoffs/2026-10-08-pre-merge-day20-todo.md)
