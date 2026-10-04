# T5 — офлайн-подготовка, живой этап не выполнен

Дата: 04.10.2026. Область: подготовка P5/A1–A6; это не PASS T5.

**Текущая остановка:** пользователь разрешил два live сценария с отдельными cap$0.06; version2/scenario SHA `13cc7c6fb48c1beaf358cf96c4f386815027a4d28e5ff568fbe630513c63800f` подготовлена и повторно проверена synthetic. Independent pre-live Astra gate PASS; live механический прогон выполнен, см. [T5-LIVE-MECHANICAL](T5-LIVE-MECHANICAL.md). Смысловая приёмка ожидается. Нижние сведения до version2 исторические.

## Готовые артефакты

- [scenarios.json](validation/scenarios.json): два разных разговора по12 вопросов. Public assignment:18 — понять требования планировщика; all frozen corpus — RAG days21–24 и обсуждения, смена цели на проверку качества. В обоих меняются цель/уточнения/ограничения, есть короткие продолжения и поздние вопросы.
- [Инструкция и остановка](validation/README.md): выделенные серверы, два scope, журнал runner, checkpoint после public хода6, безопасное возобновление, запрет повтора неоднозначной операции и private raw all-результаты.
- [scenario_runner.py](validation/scenario_runner.py): по умолчанию только печатает план. UI execution требует выбранного offline/live режима, помеченной фикстуры для offline или ранее предоставленного разрешения и exact frozen SHA для live. Runtime authorization не создаёт и не меняет.
- [Смета](validation/BUDGET-PROPOSAL.json) и [расчёт](validation/budget.py): общий план24 вопросов/поисков, максимум24 provider calls, retries0. Public12≤$0.05408256 и all12≤$0.05408256, всего≤$0.10816512 по текущим byte/rate/output ceilings; предложенный общий новый cap$0.12 либо два$0.06. Никакого нового бюджета не предоставлено. Read-only `search.manifest()` 04.10.2026 подтвердил frozen identity SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`, 663 document IDs и `assignment:18`; live preflight проверит совпадение с авторизацией обоих серверов.
- [Ручная рубрика](validation/SEMANTIC-REVIEW.md), [CSV](validation/review-template.csv), [шаблон отчёта](validation/REPORT-TEMPLATE.md): semantic NOT_REVIEWED, реальные провайдерные критерии NOT PROVEN, поля не заполнены фиктивными одобрениями.
- [record_saved.py](video/record_saved.py): запись настоящего public-only UI по завершённому manifest, только public chat, GET-only, 0 новых searches/provider calls. All-сценарий исключён; неизвестные видимые чаты отклоняются. Raw остаётся private, publication NOT_APPROVED, запись обозначена просмотром сохранённых результатов.

## Что фактически проверено

Локальный macOS/Python3.14:

- `python3 day25/validation/test_preparation.py -v`: 8 тестов PASS. Проверены12+12, разные scope/цели и изменения памяти, формула резервов против настоящего `common.estimate` при предельных24000 packed bytes, отсутствие разрешения в смете, отклонение private public-plan/неполного сценария, запрет semantic PASS по механическим фактам, отрицательные evidence-границы unknown/foreign history/wrong source/stale state, точный all frozen identity и authorization identity.
- `python3 day25/validation/scenario_runner.py`: plan-only PASS, актуальная split-scope смета, без браузера/провайдера.
- `python3 -m py_compile day25/validation/scenario_runner.py day25/video/record_saved.py`: PASS.
- `git diff --check`: PASS.

Подготовительные тесты запрещают requests/subprocess и не пишут authorization/ledger. Добавлено только read-only поле `cloud.identity_sha256` в state приложения; существующие реальные private-данные не менялись. Реальных SSH/model calls:0; новый расход не измерен и не утверждается. Все27 тестов T1–T4 повторно PASS после добавления read-only SHA; HTTP тест подтверждает exact authorization SHA.

Полный synthetic UI runner и GET-only recorder выполнены после readiness fixes (см. ниже). Реальный24-ходовый разговор, ручная смысловая оценка и настоящее видео Day25 не выполнены; provider conformance и смысловая приёмка остаются NOT PROVEN.

## Остановка и следующие действия

Своими SIGINT остановлены только синтетические preview8053 PID12346 и8054 PID12580. После остановки lsof подтверждает, что8053/8054 не слушают. Процессы8050 не трогали; итоговый lsof не обнаружил слушателя и на8050, причина здесь не исследовалась.

Далее: отдельно определить scope public+all, exact frozen identity SHA и новый budget; обеспечить Python Playwright и проверить runner на выделенной синтетической среде. Только после согласования — выполнить живые два12-ходовых сценария через UI с реальным restart checkpoint, независимую рубрику смысла и public-only запись сохранённых результатов. Ни один live критерий T5 не закрыт этой подготовкой. TASKS/todo/HANDOFF ведёт координатор.

## Readiness fixes

Live output и любой recorder output принудительно внутри day25/private; тесты отклоняют внешний путь, traversal, корень private и symlink escape. GET-preflight обоих dedicated servers сравнивает exact authorization SHA до первого POST, затем повторяется перед сценарием. Негативный тест mismatch на каждом scope доказывает отсутствие POST; matching preflight использует два GET. Реальная search identity по-прежнему проверяется Service до генерации.

## Полный synthetic dry-run после readiness fixes

Окружение: macOS, Python3.14; временный venv `/tmp/day25-playwright-venv`, Playwright1.63.0 и Chromium153.0.8010.12 в `/tmp/day25-playwright-browsers`. Lockfiles не менялись. Pip/browser download — установка инструментов, не вызов модели.

- Runner: `--mode offline --output day25/private/synthetic-run-01`, checkpoint после public хода6 (exit2), реальный SIGINT/restart8054 с тем же private directory, `--resume` (exit0). PID80291→80649; проверены6 сохранённых IDs и task state version2. Результат MECHANICAL_RUN_COMPLETE, public12+all12, каждый ход verified; semantic NOT_REVIEWED.
- Счётчики: public12 searches/12 mock generations, all12/12; всего24/24, real provider/SSH0. Synthetic charge public$0.00012 +all$0.00012=$0.00024; это fixture cost, не реальный расход. После refresh/restart дополнительных calls нет.
- Для all включён отдельный `--private-all` fixture с `private:synthetic`/ALL_ONLY_SYNTHETIC_MARKER. Маркер есть во всех12 raw all evidence. Затем all chat/results скопированы в public fixture directory без authorization/ledger: public-only API показывает только один public chat, all archive GET404.
- Recorder `--allow-fixture` завершён (exit0): `day25/private/synthetic-video-02/saved-public.webm`, PNG и RECORDING.json. Browser methods толькоGET; counters12/12 до=после; ledger$0.00012 до=после; новых searches/generations0. Public DOM check PASS, показаны только assignment:18, all goal/маркер отсутствуют. Два PNG просмотрены инструментально по доступным кадрам; запись остаётся private, publication NOT_APPROVED.
- Первый recorder dry-run также завершён; второй добавил явные checks counters/browser methods/DOM и hostile all archive.
- После fixture/recorder изменений:27 app regression tests PASS3.620с;8 preparation tests PASS0.005с; py_compile и git diff --check PASS.

Synthetic fixture возвращает одинаковый учебный ответ: эти результаты доказывают механический UI/archive/restart путь, а не качество RAG, поиск в настоящем frozen corpus или осмысленное удержание цели моделью. Истинная T5 по-прежнему требует отдельного live разрешения,24 вызовов максимум и ручной рубрики.

## Version2 после разрешения пользователя

Ровно2×12 ходов, новые намерения перечислены в `intent` и отдельные ожидания `review`: сравнение, практический выбор, скептическое возражение, источник/цитата, отсутствующий факт, смена цели/ограничения и поздняя память. Public сохраняет assignment:18; all — дни21–24/обсуждения. Сценарии не утверждают отсутствия timezone/SLA во всём корпусе: ожидают признания границы переданного контекста.

- Scenario SHA `13cc7c6fb48c1beaf358cf96c4f386815027a4d28e5ff568fbe630513c63800f`; старый synthetic-run-01 относится к прежней версии. Budget proposal содержит новый hash и exact frozen SHA; его NOT_GRANTED обозначает, что расчёт сам не выдаёт разрешение. Фактическое новое разрешение отражено отдельно в private setup. Оценка24max≤$0.10816512, по12≤$0.05408256, отдельные cap$0.06.
- Новый `private/synthetic-run-02`:24 verified mock ответов; checkpoint6 exit2, настоящий public restart PID3189→3450, --resume exit0. Обе области по12 searches/12 mock generations; real provider/SSH0.
- Новый `private/synthetic-video-03`: recorder exit0, толькоGET, counters12/12 до=после, ledger$0.00012 до=после; public DOM PASS несмотря на скопированные all synthetic archives. Видео saved playback, publication NOT_APPROVED, semantic NOT_REVIEWED.
- `private/live-public-01` и `private/live-all-01`: новые отдельные authorization/ledger, scope по одному, cap$0.06 каждый, exact frozen SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`, retries0. Public разрешает только assignment:18; all использует663 document IDs из локальной authorization того же exact frozen snapshot (не переносит старый бюджет/ledger). Ключи не копируются и не сохраняются. Ledgers пусты; read-only Service.cloud_state и права0700/0600 проверены, servers live не запускались. Private summary `live-setup-01.json`: PREPARED_NOT_STARTED/independent_review PENDING.
-8 preparation tests PASS0.006с, включая разнообразие>=8 намерений и12 уникальных вопросов на сценарий; compile/diff PASS. Runtime приложение не менялось в version2. Synthetic не доказывает смысл: live плюс ручная рубрика остаются обязательными.

Следующий шаг принадлежит root: independent review сценариев/setup; только после PASS запустить dedicated live servers и runner с заданным SHA, затем restart checkpoint, ручную рубрику и public-only saved recorder.
