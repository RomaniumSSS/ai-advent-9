# Day29 — итоговая независимая проверка реализации

**Verdict: SPEC SATISFIED. Code review: APPROVED.** Проверка 10.10.2026,
фактическая модель reviewer — `gpt-6-astra`, `xhigh`. Существенных открытых
замечаний нет. Вывод относится к локальной поставке и заранее установленному
критерию полноты E02. Ускорение и пороговый выигрыш RSS не доказаны.
Проба Q8 завершилась технической ошибкой прогрева и предусмотренной остановкой;
успешного парного Q4/Q8 benchmark нет. Публикация и человеческая приёмка не выполнены.

## База проверки и версии

Проверен фактический worktree
`/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day29`, ветка
`day29-local-optimization`, база `ca9058411363c1815793c80e2f3a778e52674ad3`.
На финальном входе изменены root `HANDOFF.md`, `MCP-STUDY.md`, `README.md`,
`todo.md`; `day29/` ещё untracked. Изменений Day01–28 нет.

Пользователь явно делегировал автономную реализацию. Отдельного одобрения
текста SPEC человеком не было: оно не выводится из тестов или этого заключения.
В качестве проверяемого контракта использован пакет, зафиксированный до
эксперимента, без ретроспективного изменения критериев:

| Документ | SHA-256 |
| --- | --- |
| [SPEC](../SPEC.md) | `bff9cd65b242295dbe564e763247f8b9307ee0e7037cddb428496af7006424af` |
| [PLAN](../PLAN.md) | `313855024aa0eeb6c7542048c43237b8d49b80bd693cf3b4c371a7da1f414e0c` |
| [SCENARIO](../video/SCENARIO.md) | `3f420bc3966609927887b0c676c154825425e050eb266d56d654c2323e9d14f0` |

Прочитаны применимые AGENTS/CLAUDE, актуальные todo/HANDOFF, проектные
build/deliver skills, весь пакет SPEC/PLAN/TASKS/SCENARIO, исходники и тесты.
Применены skills `review`, `agents-best-practices` и `implementation-validation`
с их правилами evidence/verdict. Реализацию reviewer не редактировал.

[Финальный manifest](source-manifest-delivery.json) проверен непосредственно:
SHA каждого перечисленного файла совпадает. Основные версии:

| Объект | SHA-256 |
| --- | --- |
| `core.py`, неизменённый после замеров | `ffd03a0c5bc659e50783416c469c72d8f79f7d02a7d9a1309208c74875b2e24d` |
| `metrics.py`, неизменённый после замеров | `a4314a70bbde27b3b1abd608439ec6895b4d4623a226727a87e68b6bff65ce3d` |
| `evaluate.py` при замерах | `fbe696adf1e1bec9de0fc2cd472996cc99788cd79da3152663e4e1960f2c6a6c` |
| `evaluate.py` после исправлений | `fdd23fa66b9493c887320fac248c2af6bc78d66955c7a4c072afed7d08c6640a` |
| `app.py` | `5548e4febe572bbaac0432d38ffd0e6026acdb955e0b27e7501ed63c69cf8ef9` |
| `eval-suite.json` | `350280a45be979912200f791eea95fdd7ab1d5194e423c03bd37c7a3528004a6` |
| F, canonical profile | `25e4beca64a0abf112da6c97b39388df8d70b861e84aed51c44d864e107f34b4` |
| Bound frozen inputs | `efa740e08dc63b28ce6591e9649d1fb2d605d3385a254b045c23d02630ad57fb` |
| [Публичные projections](measurement-receipts.json) | `0c3cdd93275286f2b8ada11327fa069af486a63916431a255f966b3240996a17` |
| [Финальный MP4](../video/Day29-live.mp4) | `5082b1f0b155b01a3fced5c4dd1d643787f12bd2501855f4d09e3a4420b821c3` |

Проверены [diff](../tests/postprocess-source-diff.patch) и
[evidence исправлений](../tests/postprocess-evidence.json): после измерений
менялись guards/сводка и сохранение оборванной quant-серии, не runtime core,
sampler, prompt или model payload. Старый evaluator сохранён отдельно.
В `profiles.json` последующий выбор `selected=candidate` меняет начальный UI,
а canonical конфигурации остаются прежними. Record-02 связан с
[manifest съёмки](source-manifest-record-02.json); отличия доставки после съёмки
ограничены подписями текущего статуса в HTML/public summary.

## Как проверялось доказательство

| Возможный ложный вывод | Выполненная проверка границы |
| --- | --- |
| Кандидату дали более удобный контекст или изменили baseline | AST исходного Day28 и независимые Day28 receipts; побайтовое равенство трёх baseline messages; реальный read-only индекс; hashes всех вопросов, текстов, порядка и source map |
| Валидные ссылки ошибочно признаны полной семантикой | Самостоятельное чтение всех шести уникальных ответов и оригиналов assignment18/19/20; сравнение обоих повторов; отдельная рубрика, не поиск ключевых слов |
| Быстрый error/unknown или чужая серия дали успешный verdict | A1/A2 RED→GREEN; статус и обязательные источники E01/E02, E03 unknown, 12 уникальных IDs, run/suite/receipt hash binding; errors и прогревы исключены |
| RSS ниже потому, что пропущен runner; warm на деле reload | Сырые process samples, `comm`/PPID для native `llama-server`, полный стабильный набор PID в каждом sample, одинаковая схема и placement; warmup ID и load duration |
| Q8 ошибку выдали за ответ или скрыто повторили | Единственный failed warmup receipt, `length`/384 tokens, 0 scored requests, сохранённый исход и stop; mock проверяет сохранение metadata будущих failed series |
| В видео показали старые ответы или не показали обязательную метрику | Четыре новых raw receipts → public projection → видимый текст; run/request IDs, E02 input identity, MP4 SHA/full decode/кадры; numeric swap из тех же исторических receipts |
| Публичный экспорт раскрыл приватный corpus/локальные пути | Все 25 projections сопоставлены с originals и SHA; выбраны только public assignments; вложенные `modelfile` удалены с явным описанием projection, `/Users/` в экспорте отсутствует |
| Новую версию кода выдали за измеренную | Старый/новый evaluator, frozen input parent chain, manifest съёмки и manifest доставки проверены отдельно |

Проверка не полагается только на отчёты других агентов. Самостоятельно прочитаны
`core.py`, `metrics.py`, `evaluate.py`, `app.py`, profiles/suite, tests, static UI,
browser/record scripts. Измерения выполнял координатор; reviewer проверял
сохранённые первичные данные и не делал новых inference, unload или download.

## Матрица применимых требований

Обозначения: **S** — SPEC, **P** — PLAN, **V** — SCENARIO, **T** — TASKS.
Пункты сгруппированы по наблюдаемому контракту; каждый статус относится ко всей
формулировке строки. Условные ветки отдельно разобраны ниже.

| SPEC item | Наблюдаемое требование | Evidence | Status | Примечание |
| --- | --- | --- | --- | --- |
| S14–21, P§1 | Самостоятельный Day29 RAG, B/F и локальный экран; Day01–28 без правок/imports | Полный bounded source/diff audit; реальные app receipts | PASS | Индекс читается по явному внешнему пути, runtime старого дня не запускается |
| S17–19, P§2 | Та же Qwen3 8B Q4_K_M, think=false, исходные 0/8192/1024 и source_refs | `profiles.json`, `profile_payload`, реальные payloads, preflight digests | PASS | F: 0/6144/384, та же модель |
| S19, S28, P60–62 | Baseline SYSTEM/messages/schema совпадают с Day28; prompt change видим | `baseline-reference.json`, `baseline-parity.json`, независимый AST/fixture check | PASS | Все 3 baseline messages имеют прежние SHA |
| S25–29, P31–44 | Read-only индекс и точный embedding digest/dimensions до запроса, индекс после серии прежний | `load_index` на настоящей DB; `test_index.py`; preflight и `index-after.json` | PASS | generation `5d5502c69976163325ad6c35`, 724 chunks/663 docs/24 public |
| S20–21, P35–37 | Только public assignments отбираются до retrieval/context; приватный corpus не в UI | `retrieve`, `test_index.py`, реальные selected chunks, кадры | PASS | Выбранные документы только assignment18/19/20 |
| S26–28, P46–58 | Три вопроса, рубрика и упорядоченные contexts заморожены до pilots; одинаковы во всех профилях | `eval-suite.json`, frozen parent/bound chain, action journal, все raw payloads | PASS | Повторный bind не меняет тексты, source map или retrieval |
| S29, P59–60, T«Бюджет» | Schema/template/output reserve учитываются; отказ до HTTP без обрезания | `check_budget`, `test_contract.py`, `test_freeze.py`, RED evidence | PASS | Текущие B/F inputs помещаются целиком |
| P52–54 | Изменение prompt общее, без эталонных Day19/20 фактов | Полный текст P/F в `profiles.json` | PASS | Нет подсказки пяти ответов/названий дней; generic faithfulness не объявлена исправлением доказанного дефекта P |
| S30–32, P66–83 | B и четыре однофакторных T/M/C/P, не более одного F, объяснён выбор | 6 pilot receipts, `pilot-assessment.json`, `candidate-pilot-assessment.json`; payload diff | PASS | T=.2; M=384; C=6144; P=SYSTEM; F объединён до основной серии |
| S31–32, P132–135 | Фактические IDs/options/model/digest/quant/prompt/context/raw/error сохраняются | Raw receipts и 25 проверенных projections | PASS | Исторические плохие RSS pilots сохранены, не приняты за улучшение |
| S33–35, P112–121 | Второе квантование той же модели проверено по происхождению, архитектуре, размеру и среде | Registry manifest, download/preflight, Q8 model identity | PASS | Официальная Qwen3 8B Q8_0, не qwen3.5; сеть только для подготовки весов |
| S33–35, P109–110/122–128 | Ограниченная quant-проба с тем же F/input; при технической ошибке stop без retry | Единственный Q8 receipt `992e92…`; assessment/unload; code и `test_quant.py` | PASS | Ветка stop применима: `length`, незавершённый JSON; два scored warm исключены, benchmark не заявлен |
| S36–38, P85–101 | Свежие 12 warm, 4 исключённых прогрева, E01→E02→E03, B/F затем F/B | 16 raw warm-run receipts, chronological order, warmup bindings | PASS | Два независимых запроса каждого кейса/профиля, без chat history |
| S38, P98–101 | Warm требует завершённого прогрева этого профиля и модели без reload | `core.generate`, tests warmup/load guards, фактические placement/load metrics | PASS | Все 12 scored warm валидны; invalid pilot/reload не смешан с ними |
| S37–38, P93–97 | По одному cold E02 B/F после подтверждённой выгрузки только нужной модели | 2 cold receipts с `absence_confirmed`, `cold-assessment.json` | PASS | OS file cache не очищался; это явно указано |
| S61, P103–108 | Последовательность под per-user и Day28 locks, одинаковый порядок, чужие процессы не убиваются | `generation_lock`, все входные точки, изолированные flock tests, серийный журнал | PASS | Внешние приложения, игнорирующие locks, не контролируются автоматически |
| P108–110, T«Режимы/ошибки» | Перед запросом metadata среды/моделей; ошибки сохраняются, без скрытого retry | `resources.system_before`, placement/identity/timestamps/options в raw; тесты; сохранённый Q8 error | PASS | Старый Q8 preparation/series sidecar отсутствует и не восстановлен; данные самой попытки сохранены |
| P§1, T«Ответы» | JSON/source_refs валидируются; materialization берёт точные source/quote; unknown/error различимы | `validate_answer`, `materialize_references`, contract tests, реальные done/unknown/error | PASS | Неизвестные/дублированные refs отвергаются; E03 sources/quotes пусты |
| S39–40, P150–152 | Поддержка фактов и полнота оцениваются отдельно от валидности | Все 12 raw answers, `warm-semantic-assessment.json`, независимая смысловая таблица ниже | PASS | Агентская оценка, не человеческая приёмка и не автоматический keyword score |
| S41–45, P137–139 | Embedding/retrieval/generation/total разделены; replay не выдаётся за RAG total | Frozen retrieval metadata, generator receipts, четыре реальные live times | PASS | Для replay отсутствующие фазы null/объяснение; median фаз не складываются |
| S42–43, P135–136 | Ollama counts/load/prompt/eval durations, ns→s, tok/s только при положительном duration | `ollama_metrics`, known-value tests, реальные raw response и metrics | PASS | Missing/zero duration не создаёт фиктивный tok/s |
| S42–44, P141–148 | Наблюдаемый RSS daemon+runner, timestamps/PID/interval/missing; корректные пределы измерения | `metrics.py`, `test_metrics_fairness.py`, raw samples всех 12 warm | PASS | Интервал 0.5 s; process set полный и стабилен в каждом scored warm |
| S43–44, P145–148 | Swap/counters до/после и placement отдельно; неизмеренное null с причиной | `system_snapshot`, raw resources, `swap-video-evidence.json`, UI | PASS | Swap всей машины; `/api/ps size` не RSS; нет утверждения полного Metal peak |
| S45, P153–159 | Individual values/median/range по case/profile; cold/warm/errors/runs не смешиваются | `summarize`, A2 tests, public summary; независимый пересчёт raw | PASS | Сводка группирует run_id; semantic CLI требует явный run ID |
| S49–50, P154–157 | Общая latency median по 6 warm; RSS только при сопоставимой схеме/placement | `optimization_verdict`, process/placement checks, пересчёт 12 receipts | PASS | GPU placement одинаковый, allocation bytes могут различаться при разном ctx |
| S46–50, T«Метрики» | Порог не скрывает regression, дубликаты/чужие contexts/неверные статусы отвергаются | Comparator guards/RED→GREEN, A1, required docs, exact receipt hash binding | PASS | Ручные quality flags не обходят E01/E02 done и source guards |
| S46–50 | На выбранном F нет factual/source/E01/E03 regression; E02 полный оба раза против неполного B | Первичные ответы/источники и смысловая таблица ниже | PASS | Причина `proven` только `E02_completeness` |
| S50–53, P78–83/157–159 | Цена улучшения рядом, отсутствие скорости/RSS10% не скрыто; baseline сохранён | RESULT, RELEASE_NOTES, public summary, кадры verdict/table | PASS | 29.781→37.127 s; 5.959→5.498 GiB, −7.75%, ниже порога |
| S59–61, P§1 | Runtime только loopback/локальная DB; нет платного/cloud inference | Fixed URL, proxy/redirect denial, model checks; HTTP tests; реальные network receipts | PASS | UI 127.0.0.1:8069, Ollama 127.0.0.1:11434 |
| P§1, T«Локальный UI» | Host/Origin, private-route защита, реальные profile/question/request; текст безопасно отображается | `app.py`, `test_http.py`, `textContent`, browser fixtures и live journal | PASS | Mock browser tests не выданы за LLM eval |
| S54, P163–165, T«TDD» | Поведенческие RED→GREEN на существенные контракты, свежие checks после правок | Сохранённые RED logs, source diff/evidence, 45 GREEN | PASS | Не фиктивный RED из-за отсутствующего import; reviewer независимо запускал suite |
| S54–56, P168–170 | Luna → Sol corrections → обязательное Astra; фактические роли без выдуманного cost | `review-luna.md`, initial/final `review-astra.md`, journal, эта матрица | PASS | Usage/cost не предоставлены; A1/A2 закрыты после исходного NEEDS CHANGES |
| S55–57, P§1/161–173 | Код/README/RESULT/RELEASE_NOTES, исходные замеры, последовательный action journal | Прочитанные документы, measurements/export/raw receipts, journal | PASS | Полные private originals сохранены локально; публичные projections помечены |
| S57, S63–65 | Статусы локального кода/видео, публикации и человеческой приёмки раздельны | Документы, UI capture/current captions, tracker | PASS | Автономная реализация не выдана за human approval; commit/push/upload не выполнены |
| V9–14/18–21 | Начало показывает модель/quant/options/index/public, прошлую серию отдельно и правдивый статус | MP4 start/pending/summary frames, recorder/state | PASS | При съёмке видео ещё проверялось; финальная подпись обновлена отдельно |
| V22–28 | Новые E02 B/F: IDs, оба оригинала, метрики, одинаковые input/order, честная полнота | Два raw/public/visible receipts record-02, source frames, same input SHA | PASS | Живая пара не подменяет 12 scored warm |
| V29–32 | Новые E01 с оригиналом и E03 unknown без ложного бюджета/источников | Raw/public/visible receipts 3–4, MP4 answer/source frames | PASS | Все 4 live generation_called=true; done/done/done/unknown |
| V33–36 | Сводка: 3 кейса/повторы/quality/individual times/median/range, cold отдельно, RSS/swap/placement | MP4 comparison-table и summary-2/4/6; raw bindings | PASS | Numeric swap исправлен новым дублем; record-01 оставлен PARTIAL |
| V38–40, P171–173 | Ошибки и прежние дубли не скрываются; «оптимизировано» только при выполненном критерии | Q8/pilot evidence, record-01 proof, final verdict | PASS | Основной критерий полноты выполнен; не заявлено ускорение/Q8 превосходство |
| V44–50 | Dry перед record, те же actions/code/profiles, 4 новых IDs, отдельные каталоги, ожидание результата | dry-02/record-02 journals, recorder code, captured manifest, pending MP4 frame | PASS | Ни фиксированный sleep, ни echo готового ответа не служат условием завершения |
| V47/51 | Нет параллельного benchmark при записи; recorder/context закрывается в finally | Времена runs и отдельные video requests; code; законченный файл/decode | PASS | Reviewer новых model calls не выполнял |
| V51–55 | ffprobe/full decode/кадры; видимое совпадает с журналом; нет обрезанных ответов/приватных сообщений | Независимые ffprobe/decode, 9 ключевых кадров + 2 дополнительных, raw projection checks | PASS | 328.48 s, 1280×1000, H.264, 25 fps; проверка визуальная выборочная, не каждый кадр |
| V55–58, S56 | Дубли/журналы сохранены; проверенное локальное видео и код доступны | record-01/02 отдельные каталоги и proofs; final MP4; README/RESULT | PASS | Публикация отдельно; ZIP ещё не предмет этой проверки |

## Условные ветки и исключения

- **Q8:** условие успешного прогрева для двух оценочных warm не выполнено.
  Применён заранее записанный stop после технической ошибки (PLAN 109–110,
  122–128, 135). Это завершённая ограниченная попытка настройки квантования,
  а не выполненные два повтора. Они исключены из применимой успешной ветки;
  отсутствие Q4/Q8 benchmark явно сохранено. Ошибка `length` не доказывает
  аппаратную невозможность Q8 и не приписана только нехватке RAM.
- Ветка cold NOT MEASURED не применяется: подтверждение отсутствия модели
  перед каждым cold имеется. Ветка budget reject не потребовалась для выбранного
  F; сам отказ до HTTP доказан офлайн тестом. Никакого урезания контекста не было.
- Ветка «оптимизация не доказана» не применяется: выполнен заранее заданный
  критерий полной E02 без regression. Скорость и RSS10% не являются обязательными
  дополнительными улучшениями: в SPEC между ними стоит «либо».
- Новый diagnostic retry не потребовался; после Q8 stop серия не расширялась.
  Старые failed metadata не достроены задним числом.
- Рекомендация интервала sampler «например, 200 мс» не задаёт обязательные
  200 мс: фактически 0.5 s явно записано. Примеры названий MCP-инструментов
  из источника — допустимые примеры, не обязательная проверка keywords.
- Переиндексация, другой embedder/framework, fine-tuning, бесконечный sweep,
  публикация/merge/сдача и проверка понимания пользователем не входят в текущий
  результат. Подготовленный EXPLAINED не равен прошедшему обучению или приёмке.
  Сборка ZIP запланирована координатором после отчёта; здесь ZIP не проверялся.

## Независимая смысловая оценка

Проверены именно originals warm run `a2606d8f674a48d1b7e2ec8e1549a209`.
Все 12 request IDs различны, шесть пар повторов имеют одинаковые model JSON
и materialized answers. Прочитаны все шесть уникальных текстов и их реальные
источники; проверено соответствие каждого assessment entry SHA своего receipt.

| Проверяемый смысл | B, оба повтора | F, оба повтора | Обоснование по ответу/источнику |
| --- | --- | --- | --- |
| E01: отложенный/периодический MCP-инструмент; JSON/SQLite; расписание; агрегированный результат; агент 24/7 со сводками; Видео + Код | 6/6 | 6/6 | Обе формулировки перечисляют все шесть групп assignment18, добавленных фактов нет |
| E02: несколько инструментов и получение → обработка → сохранение | Частично | Полностью | B говорит о «цепочке обработки данных», F явно называет все три шага assignment19 |
| E02: автоматическая цепочка и корректная передача данных | Частично | Полностью | B обобщённо говорит о проверке пайплайна; F раскрывает автоматичность и корректность передачи |
| E02: несколько MCP-серверов | Полностью | Полностью | B пишет о серверах/взаимодействии между ними; F прямо требует зарегистрировать несколько, как assignment20 |
| E02: выбор инструмента и маршрутизация | Полностью | Полностью | Явно присутствует в обоих ответах |
| E02: длинный флоу разных серверов и проверка выбора/порядка | Частично | Полностью | B не раскрывает проверку порядка; F явно указывает её и сценарий разных серверов |
| E03: точный бюджет отсутствует | unknown | unknown | «Не знаю по переданному контексту», sources/quotes пусты; ни суммы, ни ложной ссылки |

Оригинал assignment19 действительно говорит «Создайте несколько MCP-инструментов».
Следовательно, глагол «создать» в P/F не является ошибкой. Общая добавка
faithfulness в F не доказывает исправления отдельного найденного дефекта P.
Итог E02 — B: 2 полных/3 частичных группы, F: 5 полных; формат «Видео + Код»
в F также поддержан оригиналами. Публичная root-оценка с этим согласуется.

Пересчёт первичных чисел подтвердил:

| Метрика | B | F | Вывод |
| --- | --- | --- | --- |
| Median generation, все 6 scored warm | 29.780854646 s | 37.126610021 s | На 24.7% медленнее |
| E02 median generation | 43.512999709 s | 100.058389229 s | Примерно 2.30× медленнее |
| Median observed max summed RSS, 6 warm | 5.959197998 GiB | 5.497596741 GiB | −7.75%, порог 10% не достигнут |
| Cold E02, 1 запрос | 42.946108416 s | 81.196041375 s | Отдельное наблюдение, не warm median |

Текущий evaluator на этих неизменных receipts с привязанной смысловой оценкой
даёт `proven=true`, `reasons=["E02_completeness"]`, `resource_comparable=true`.
Это не независимый holdout: подбор и проверка выполнялись на трёх известных
вопросах, по два scored повтора; статистическая устойчивость не утверждается.

Q8 run `df5e7e0053954e88858734c3f0a2bbb3`, request
`992e92d31af54169b02d05522efeb430`: 140.812496791 s с загрузкой,
384 tokens, `done_reason=length`, незавершённый JSON. Наблюдённый RSS 8.57 GiB,
system swap 4.52→6.19 GiB. Это error, семантика ответа не оценена; плановые
два warm не запускались. Старый controller сохранил сам receipt, но потерял
отдельные preparation/series metadata: доказательство Q4-absence именно из
этого отсутствующего sidecar не заявляется. Исправление durability проверено
mock failure, а не новым Q8 inference. Q8 выгружена из RAM, файлы сохранены.

## Свежие проверки и финальное видео

Среда: Mac M2, 16 GiB, macOS 15.6.1 arm64, Python 3.14.0,
Ollama 0.33.3 по реальным receipts/preflight.

| Проверка reviewer | Результат и область |
| --- | --- |
| `python3 -m unittest discover -s day29/tests -v` | 45/45 PASS, независимый запуск 1.258 s после Sol fixes; stdlib/mocks/локальный fixture HTTP и изолированные locks, без LLM. Сохранённый отдельный Sol GREEN — 1.156 s |
| `git diff --check` | Exit 0; также независимо проверены границы Day01–28 и отсутствие cross-day runtime imports |
| Read-only Python проверки SHA/JSON/raw receipts | Все manifest hashes, projection/original hashes, selected input/source identity и агрегаты совпали; никакой сети/inference |
| `ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,nb_frames -of json day29/video/Day29-live.mp4` | Exit 0: H.264, 1280×1000, 8212 frames, 328.48 s, 10535892 bytes |
| `ffmpeg -v error -i day29/video/Day29-live.mp4 -f null -` | Exit 0, весь файл декодирован, ошибок нет |
| Визуальная проверка MP4 | Прочитаны 9 кадров `video/verification/*.png`; дополнительно reviewer сам извлёк MP4 на 140 s (ожидание нового F) и 190 s (оригинальный assignment19) |

После финального GREEN не повторялась неизменная suite только ради счётчика:
последующие изменения касались исторических отображаемых данных, delivery
captions и документов. Для них проверены новые rendered frames/projections/hashes.
Фикстуры браузера desktop/tablet/mobile и HTTP evidence просмотрены отдельно;
они не подменяют реальные ответы. Первоначальный mobile overflow и record-01
без численного swap не скрыты, соответствующие старые исходы сохранены.

Финальный recorder run — `6f393fc7546547118052d26de2b60186`,
app run — `7b522fd22b7b474684a9cb31e0621eb5`. У каждого нового запроса
проверены raw SHA, `generation_called=true`, loopback network, совпадение
`app.public_result(raw)` с журналом и видимым текстом:

| Новый запрос record-02 | Request ID | Статус | Generation / full RAG |
| --- | --- | --- | --- |
| E02 B | `7f62bac3d9e844268ad6a87228683be0` | done, неполный | 54.757 / 56.563 s |
| E02 F | `96363671d0694f999cd654ce329ec27f` | done, полный | 98.981 / 100.851 s |
| E01 F | `7cb457aece0146d6aacf1651d1639c7c` | done | 43.053 / 44.879 s |
| E03 F | `6bb6d5ea0d80482889754a2df1163237` | unknown | 21.023 / 23.641 s |

У обоих живых E02 совпадают input SHA
`4065b3d6cfd201c01ef73ab1dc232e83a7dbde550f15a817305c13720632c89c`,
индекс, текст и порядок. Численный swap на summary-6 связан с четырьмя
warm E02 originals через [swap evidence](swap-video-evidence.json); значения
и GiB-конверсия проверены независимо. Fully-GPU placement показан отдельно.
Длительные ожидания содержат состояние настоящего запроса, а не чёрный кадр;
готовые ответы и нужные источники читаемы. Page errors отсутствуют.

Предшествующий dry-02 имеет ещё четыре собственных IDs и тот же сценарий.
Итого в сохранённых runs: 25 генераций эксперимента + 16 live запросов двух
dry/record пар = 41; в основной оценке по-прежнему только 12 scored warm.
Reviewer не повторял эти вызовы и не измерял новый результат модели.

## Ограничения и итог

Применимых требований со статусом **FAIL** или **NOT PROVEN** в указанной
локальной поставке не осталось. Все строки матрицы — **PASS**, с применением
заранее предусмотренной ветки остановки Q8. Итог по правилам skill:
**SPEC SATISFIED**.

Этот вывод ограничен измеренным набором и предоставленным протоколом. Он не
означает успешный полный Q8 benchmark, статистическое превосходство, полную
Apple Metal/unified peak memory, изоляцию от всех внешних приложений,
человеческую приёмку или завершённую публикацию. Самостоятельная оценка смысла
выполнена агентом по исходникам; отдельная платная модель-судья не вызывалась.
Стоимость/usage инструментами не предоставлены. ZIP и внешняя доставка этим
отчётом не сертифицируются. Существенные замечания начального code review
закрыты с сохранением истории в [review-astra.md](review-astra.md).
