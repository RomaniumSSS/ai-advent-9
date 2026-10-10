# Full local chat — независимая проверка контракта

**Verdict: SPEC SATISFIED. Code review: APPROVED.** Все 25 применимых строк
матрицы PASS; существенных открытых замечаний нет. Проверены код, исправления,
первичные данные, сохранение истории, финальный UI и README. Это локальная
поставка, не человеческая приёмка и не оценка качества произвольных вопросов.

Reviewer: фактическая `gpt-6-astra`, `xhigh`, 10.10.2026. Применены `review` и
правила `implementation-validation`; человеческое одобрение текста SPEC или
приёмка не заявляются. Основание — явное поручение сделать полный локальный чат
в отдельной ветке. Старый public Day29 benchmark повторно не оценивался.

## Проверенная версия и область

Worktree: `/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day29-full-chat`,
ветка `day29-full-index-chat`, база `ca9058411363c1815793c80e2f3a778e52674ad3`.
Фактические Git root/status, AGENTS/CLAUDE, текущие todo/HANDOFF и весь пакет
[SPEC](../FULL_CHAT_SPEC.md)/[PLAN](../FULL_CHAT_PLAN.md)/[TASKS](../FULL_CHAT_TASKS.md)
прочитаны. `day29/` untracked; никакого commit/push/публикации reviewer не делал.

Прочитаны весь `full_chat_core.py`, `full_chat.py`, static UI, новые tests и
browser helper. Изменения additive: старые `core/app/metrics/evaluate/profiles`,
public static, SPEC, benchmark inputs/results, видео и ZIP сохранены.
Самостоятельная сверка preservation manifest: **99 файлов, 0 расхождений**.

| Объект | SHA-256 |
| --- | --- |
| FULL_CHAT_SPEC.md | `6b2405fd91e48b9988cbd34d36431cfbef3da8150e2adaff0a5d35210c0d64d8` |
| FULL_CHAT_PLAN.md | `26cf29492ff0b837adb0f41bb778d5ef58cd13e694ee95cbf71cceda4a0f0c29` |
| Backend при трёх live запросах | `2e75e0fbdfddac31b8f99dce80e9a1ed7065d79f43b5377b3fb5becb73b599db` |
| Текущий full_chat_core.py | `6e887f0dd664d73d7eff0f267ed4dd505142efddfd51d20cbcc26957a5565bf1` |
| full_chat.py, без изменений после live | `d970f21c3f14f5b8a258c23f8eeb12ee475c0e16a07dc55382139576892b9878` |
| Финальный full_chat_static/app.js | `3625298ddf5e3ecb7b9cc68f034d346899b5ea1c551cd41d8750318b1e05c87e` |
| full_chat_static/index.html | `66f9ca194a045c23fc729312602796c94db482be8469faaae79d5aa1d72d0eb1` |
| full_chat_static/style.css | `022f9a303efdb5f1f987e85fda8ab92d3d6c17daa2209d5247e8718e650f27cc` |
| FULL_CHAT_README.md | `d8058be2e2c1c05e4407d391aa44ff40b1b9fcec06d6b7ce87caf979afb75581` |
| Read-only structure.db | `9894d937c4bcbae653459a6fe758f231992571e436622a0cd33fcda7f707f11b` |

Последний JS fix ограничен захватом bootstrap token до асинхронного старта;
он проверен отдельным meaningful browser RED→GREEN. Runtime backend/API
после независимого focused GREEN не менялись. README прочитан полностью:
команда запуска, API, storage/reset semantics, ограничения и числа соответствуют коду.
Последняя правка README добавила ссылку на [FULL_CHAT_RESULT](../FULL_CHAT_RESULT.md);
этот итоговый документ также прочитан и совпадает с фактическими evidence.

## Проверка достоверности evidence

Возможные ложные PASS проверялись отдельно: public-only поиск под надписью all;
старый ответ вместо новой генерации; refs без смысловой поддержки; автор соседней
реплики, ошибочно приписанный целому составному чанку; перенос контекста после
reset/new; поздние ответы старого UI; незаметное удаление истории по бюджету;
private данные в публичном отчёте; старые live receipts, выданные за новую версию.

Самостоятельно загружен настоящий индекс без embedding/inference: **724 чанка,
663 документа; 24 assignment / 694 discussion / 6 personal_note**, прежние
generation/SHA. Атрибуция всех 724 чанков восстанавливает исходный текст точно.
Для трёх живых ответов каждый отображаемый excerpt/author/date совпал с metadata
реального чанка. Приватные вопросы, ответы и имена в этот отчёт не перенесены.

Независимая AST-сверка старой сохранённой версии backend с текущей показала
единственное изменение — `resolve_query`; API не менялся. Для каждого из трёх
реальных кейсов reviewer заново собрал query/messages/payload из исходных
top-5 chunks и предыдущих ходов: **exact equality**, те же selected IDs.
Это подтверждает применимость сохранённых ответов после bounded resolver fix,
без повторного модельного вызова. [Публичная сводка equivalence](fix-payload-equivalence.json).

## Матрица требований

S1–S6 — нумерованные пункты FULL_CHAT_SPEC; B — его границы; P — FULL_CHAT_PLAN.
Статусы относятся к наблюдаемому контракту и указанной области, а не обещают
безошибочный ответ модели на произвольный вопрос.

| Item | Проверяемое поведение | Evidence | Status | Граница вывода |
| --- | --- | --- | --- | --- |
| B | Отдельные entrypoint/UI на 8070; старые дни/8069/public artifacts не меняются | Source audit, 99 protected hashes, Git root/branch | PASS | Старый benchmark не переснимался |
| B, S1 | Прежний immutable индекс/embedding/Q4, think=false, отдельные options 0/8192/1024 | Реальный loader, preflight/live identities, actual payloads | PASS | Не новый benchmark profile; не текущий Telegram |
| S1 | Все 724 участвуют в semantic+lexical ranking; упоминание дня не исключает discussion/note | `retrieve_all`, focused tests, actual traces all724 | PASS | Eligibility всего снимка, не гарантия нахождения любого факта |
| S1, S6 | Mixed query сохраняет релевантные запрошенные типы; нет smoke whitelist | Полное чтение ranking; дополнительный synthetic 8 assignment + discussion beyond top-5 | PASS | Discussion сохранён; boost только при assignment intent |
| S1 | Пустой поиск unknown без generation, отсутствие найденного не равно отсутствию в архиве | Executed empty-retrieval test, код/текст сообщения | PASS | Fresh retrieval требует embedding; генератор не вызывается |
| S2 | Conversation IDs, private durable history, восстановление после перезапуска | Store tests; настоящий restart и independent GET/raw comparison | PASS | Две истории, три завершённых хода сохранены |
| S2 | Follow-up использует user anchor и свежий retrieval; новая тема имеет приоритет | Resolver tests, actual FC-F01, payload equivalence | PASS | Детерминированная грамматика, не универсальный language parser |
| S2 | Неоднозначность просит уточнение; старый assistant answer не источник фактов | Ambiguity/history tests, system/body separation, no old sources in new refs | PASS | Устойчивость LLM к любому adversarial тексту не измерена |
| S2, P3 | New/reset не наследуют контекст; late completion не возвращает удалённый ход | Store epoch/atomic tests, HTTP pending tests, delayed UI RED→GREEN | PASS | Старый raw receipt сохраняется отдельно, не прикрепляясь к reset history |
| S2 | Незавершённый ход после restart → interrupted, без автоповтора | Executed store recovery test, startup code | PASS | Crash path проверен synthetic; real restart был idle |
| S3 | Refs только текущего переданного контекста; исходный текст/type/document/chunk/author/date | Materialization tests; реальные sources versus immutable metadata | PASS | Автор/дата не генерируются моделью |
| S3 | Составной чанк атрибутируется по offsets; неизвестные/пересекающиеся части не наследуют автора | Boundary/overlap tests; все 724 text joins; три actual source checks | PASS | Неоднозначность явно обозначена |
| S3, S6 | Citation validity и semantic support разделены | UI support caption; raw NOT_CHECKED; отдельная agent semantic review | PASS | Валидная ссылка не выдаётся за проверенный смысл |
| S4 | System, history, fresh sources разделены; архивные команды не исполняются | Prompt source/history tests, bounded source audit | PASS | Runtime не имеет executor/tool действий; universal prompt-injection robustness не доказана |
| S4 | ≤3 history pairs/≤5 sources; full serialized prompt/schema/template/output budget до chat | Budget tests и actual context traces | PASS | Удаляются старые пары, затем целые низкоранговые chunks с причиной |
| S4 | Текущий вопрос не обрезается; невозможный budget/JSON/refs/length/timeout/busy видны, без retry | Focused negative tests и source audit | PASS | Unknown/errors не представлены как успешный ответ |
| S5 | Fixed loopback Ollama, Host/Origin, port8070, request limit, text-only rendering | HTTP tests, old protected transport, XSS fixture, actual network receipts | PASS | Нет cloud/fallback/proxy/redirect runtime |
| S5 | Общий lock Day28/29 и одна активная генерация; понятный busy | Реиспользуемый неизменённый lock, focused busy/timeout/HTTP tests | PASS | Внешние приложения, игнорирующие lock, не контролируются |
| S5 | Private atomic storage, каталоги0700/JSON0600, gitignored; raw не HTTP-route | Store failure/permission tests; actual durable files; API route checks | PASS | Reset очищает текущий разговор, не является secure erase старых raw receipts |
| S5 | Публичные evidence без private questions/ответов/имён/snippets | Проверены public summaries и этот отчёт | PASS | Private originals прочитаны reviewer локально |
| S6, P1–4 | Bounded TDD и свежие focused/API/browser проверки | 28 independently GREEN; сохранённые semantic RED и UI-race RED→GREEN | PASS | Mocks и реальный provider evidence разделены |
| S6 | Три новых actual UI кейса: discussion/follow-up/personal_note; проверены оригиналы | Три raw receipts/SHA/actual stop; independent semantic read | PASS | Один ответ partial2/3; hallucination rate не измерен |
| S6 | Luna → Sol fixes → mandatory Astra | review-luna, фактические fixes/tests и настоящее ревью | PASS | Агентская проверка, human acceptance false |
| P5 | Final UI после restart, sources/history/error isolation; bootstrap fix | Final-browser proof; самостоятельно просмотренные actual source/ready кадры; bootstrap RED→GREEN | PASS | Served final JS совпал с source; без новых model calls |
| P5 | README/итог объясняют запуск, границы и статусы | FULL_CHAT_README/RESULT прочитаны; live-summary, этот отчёт и review-astra | PASS | Административное закрытие TASKS/todo/HANDOFF — следующий шаг root после заключения |

## Фактические проверки

`python3 -m unittest discover -s day29/tests -p 'test_full_chat*.py' -v`:
**28/28 PASS**, 2.593 s, Python 3.14/macOS arm64. Reviewer запускал только
synthetic/offline тесты с изолированными lock paths/HTTP fixture ports.
Сохранённая root compatibility проверка прежних модулей — **45/45 PASS**;
она просмотрена, но повторно reviewer не запускалась.

Самостоятельно проверены source hashes, metadata/offsets, 99 preservation hashes,
новая mixed retrieval граница и actual storage permissions. Только GET к текущему
8070 подтвердил scope all/724/idle и новый run ID после restart; все три
`/api/requests/{id}` равны `chat_view` соответствующего исходного receipt,
истории равны durable files, число actual receipts осталось **3**.
[Публичный restart proof](restart-persistence.json).

Browser fixtures desktop1280×800/tablet768×1024/mobile375×812: сохранённые результаты
PASS для source scoping, XSS, reload, unknown/error, pending reset/new и отсутствия
overflow; reviewer прочитал helper/evidence и просмотрел desktop/mobile кадры.
Delayed send→reset/poll→new и bootstrap failure имеют meaningful RED→GREEN.
Это synthetic UI проверки с **0 real model calls**.

[Финальный actual browser proof](final-browser.json) относится к настоящему
8070 после restart и последнего JS fix. Проверены saved original source panel,
parts/attribution equality, отсутствие overflow на трёх viewport, served JS SHA
и new/reset собственного пустого разговора. Reviewer самостоятельно просмотрел
actual `desktop-source` и `ready-empty` screenshots: оригинал и раздельная
атрибуция читаемы, request IDs соответствуют receipts, пустой разговор отделён.
Screenshots остаются private; page errors и дополнительные model calls — 0.

## Реальные ответы и ограничения

| Case | Request ID | Receipt SHA-256 | Support / completeness | Total |
| --- | --- | --- | --- | --- |
| FC-D01 | `adc6bb1a8a1c474bb5fd46571728829b` | `f7c3d6fbfa12190a0a8f974be7383087959a95fa4053e17fc8a91eb33bbbcef9` | PASS / PARTIAL 2 из 3 | 51.128 s |
| FC-F01 | `51e7fae56af340b5a059d24232c43a3d` | `9007c2818bf32731da695ca62f53ca8c1ab38fd04ea045ec6b77f509b1ed080c` | PASS / 1 из 1 | 39.954 s |
| FC-P01 | `618f1d432ca94d129cb8f27b67c0dda6` | `f16892c3e651db22871195b24a259f90c6e884cb76f0577ace6e8101ab876fe3` | PASS / 2 из 2 | 43.081 s |

Reviewer прочитал каждый ответ, фактически цитируемые оригиналы и attribution;
согласен с [агентской оценкой](live-summary.json). Все три — done/JSON/stop,
ровно один локальный `/api/chat` на запрос. Первый ответ поддержан источником,
но пропускает одну ожидаемую деталь; полной полноты ему не приписано.
Во follow-up предыдущая пара удалена byte guard по бюджету: сохранённая user
anchor и новый поиск обеспечили продолжение, старый ответ не стал доказательством.
Для personal_note неизвестные author/date остались неизвестными.

Эти три целенаправленно выбранных кейса не измеряют качество произвольного чата,
hallucination rate или статистическую полноту retrieval. Эвристический resolver
не обещает разрешить все естественно-языковые продолжения; спорные случаи требуют
уточнения. Conservative byte budget может исключать историю/целые источники,
что видно в trace. Полнота снимка не означает актуальность всего Telegram.

Локальные model/embedding вызовы, download/unload, серверный restart, новые
генерации или повтор benchmark reviewer не запускал. Платная модель-судья,
новое видео/ZIP, публикация и human acceptance не входят в это расширение.
Usage/cost не предоставлены. Root обновляет административные tracker/status
после независимого заключения; это не заменяет проверенную реализацию.

Применимых **FAIL** и **NOT PROVEN** не осталось. Не входящие в контракт действия
— публикация, новый ZIP/видео, benchmark и человеческая приёмка — не получили
фиктивный PASS. Итог для указанного рабочего контракта: **SPEC SATISFIED**.
