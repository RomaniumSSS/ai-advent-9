# Day29 — независимое повторное ревью Astra

**Overall: APPROVED.** Финальный независимый проход, 10.10.2026.
A1/A2 исправлены; runtime evidence, семантика и новый record-02 проверены.
Полная матрица и ограничения: [implementation-validation.md](implementation-validation.md),
**SPEC SATISFIED** по критерию полноты E02. Ускорение/RSS10% не доказаны;
Q8 остановлена после ошибочного прогрева, два warm повтора не выполнены.
Публикация и человеческая приёмка не подтверждаются этим ревью.

Далее сохранён начальный проход; его ограничения относятся к моменту до
финальных проверок. Закрытие замечаний и текущие версии приведены в конце.

**Исторический overall: NEEDS CHANGES.** Начальный проход по реализации, 10.10.2026,
после Luna и исправлений Sol. Reviewer: фактическая `gpt-6-astra`, `xhigh`.
Usage/cost инструментом не предоставлены. Финальные warm/cold/Q8, смысловая
таблица и живое видео в этом проходе ещё не проверены; завершение Day29
и доказанная оптимизация этим заключением не подтверждаются.

Проверен отдельный worktree
`/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day29`, ветка
`day29-local-optimization`, база `ca9058411363c1815793c80e2f3a778e52674ad3`.
На входе: `M MCP-STUDY.md`, `?? day29/`. Прочитаны фактические AGENTS/CLAUDE,
текущие todo/HANDOFF, проектные build/deliver skills, SPEC/PLAN/TASKS/SCENARIO,
первое ревью и исходники. Применены `review` и `agents-best-practices`
(reference `evals.md`). Не заявляется отдельное человеческое подтверждение SPEC.

## Находки начального прохода — A1/A2 теперь закрыты

🟡 **[WARNING A1]** [evaluate.py:131](../evaluate.py#L131), также строка 138 —
`optimization_verdict()` допускает `unknown` для положительных E01/E02.
Явное соответствие receipt проверяется только для E03. Если оценщик ошибочно
передал `no_regression=true`, кандидат, потерявший весь ответ E01, может получить
`proven=true` по скорости. Это оставшаяся часть замечания Luna о проверке
ожидаемого `done` для E01/E02. Автоматическая проверка должна отвергать
противоречие в статусе и обязательных источниках до смысловых flags; смысловую
полноту по-прежнему проверяет отдельная оценка.

Независимое воспроизведение без inference, на существующих fixtures
`tests/test_comparison.py`: baseline 10 s, candidate 8 s; в двух candidate E01
заменены `status='unknown'` и `answer={'answer':'Не знаю по переданному контексту',
'sources':[], 'quotes':[]}`. С исходным `Q` функция вернула
`{"proven": true, "reasons": ["warm_generation_median_10_percent"]}`.
Ожидание: `proven=false` независимо от противоречащих receipt ручных flags.
Нужен regression test для E01/E02 unknown и отсутствующего обязательного источника.

🟡 **[WARNING A2]** [evaluate.py:107](../evaluate.py#L107), CLI строка 188 —
`summary` загружает все receipts из каталога, а `summarize()` группирует только
по `(profile_id, mode, case_id)`. При повторном запуске эксперимента успешные
запросы из отбракованной серии смешиваются с новой серией; run ID не показан
даже в полученной группе. Независимый пример: E01 baseline warm из
`aborted-run` — 10 s и из `fresh-final-run` — 30 s превращаются в одну группу
`values=[10,30], median=20, count=2`. Это не два повтора одной финальной серии.
Нужен явный выбор run ID либо разделение по run ID, с сохранением идентичности
серии в выводе. Root сообщил, что публикуемая финальная сводка будет строиться
из конкретных выбранных warm/cold/quant ID; это предотвращает проблему в таком
отчёте, но не исправляет общий CLI.

Оба замечания относятся к postprocessing и не требуют прерывать уже начатый
inference. Перед итоговым verdict исправить их и проверить затронутые тесты.
Если изменён только postprocessing, сохранить старый manifest измерений и новый
manifest анализа; не выдавать старые receipts за полученные новой версией.

## Что проверено самостоятельно

- `python3 -m unittest discover -s day29/tests -v`: **39/39 PASS**, 1.104 s,
  Python **3.14.0**, macOS **15.6.1 arm64**. Это mock/stdlib/локальные HTTP
  проверки; Ollama не вызывался. Lock tests используют отдельные временные пути.
- Прочитаны `core.py`, `evaluate.py`, `metrics.py`, `app.py`, profiles/suite,
  весь текущий набор `test_*.py`, browser/record scripts и UI. Результат Luna
  не принимался без самостоятельного чтения кода.
- `frozen_inputs(private/inputs-repair-v1.json)` успешно проверил suite,
  source/profile manifests, все context hashes и исходный parent hash.
- Настоящий read-only индекс загружен через `load_index`: SHA/generation,
  embedding identity, 724 чанка и 663 документа прошли проверки. Текст,
  document ID, source и day каждого замороженного выбранного чанка совпадают
  с этим индексом; E01/E03 содержат assignment18, E02 — assignment20/19.
- AST исходного Day28 без runtime-импорта подтвердил точный исходный SYSTEM
  и generation options. SHA Day28 core совпал с независимой fixture.
  На всех трёх frozen contexts текущие baseline messages полностью совпали
  с сохранёнными Day28 messages; это проверка контракта, не свежей скорости.
- Canonical baseline, единственный candidate profile, 12 уникальных IDs,
  input/model/digest/scope/timing identity, user messages, profile/prompt/payload
  hashes и E03 unknown/empty sources защищены в comparator. Прежние конкретные
  дефекты контекста, дублирующих IDs и E03 закрыты.
- RSS требует полного daemon+runner набора в каждом sample и стабильных PID
  внутри запроса. Native `llama-server` определяется по происхождению от Ollama;
  посторонний одноимённый процесс отвергается. Используется `comm`, не arguments.
  Fully-GPU размещения допускают разную allocation size; размер `/api/ps`
  не подменяет RSS. Это всё ещё наблюдаемый RSS, не полный Metal/unified peak.
- Warm требует завершённого прогрева с тем же profile/model/digest, загруженной
  модели и наличия load metric; явный reload делает запрос несопоставимым.
  Quant под общими locks выгружает только Q4, подтверждает отсутствие и выполняет
  ровно один warmup плюс два E02. Это подтверждено кодом и mocks, не новым Q8 run.
- Snapshot не обрезается при малом ctx; budget reject происходит до HTTP.
  Source refs материализуют исходный текст; public scope отбирается до поиска.
  SQLite read-only, loopback/proxy/redirect ограничения и Host/Origin проверки
  присутствуют. В UI ответы вставляются через `textContent`.
- `git diff --check` прошёл. Diff относительно базы не содержит изменений
  Day01–28; Day29 пока untracked. Поиск runtime imports/сетевых адресов не выявил
  cross-day imports или облачного inference. `private/` и `video/runs/` игнорируются.

## Проверенные версии

| Файл / объект | SHA-256 |
| --- | --- |
| `core.py` | `ffd03a0c5bc659e50783416c469c72d8f79f7d02a7d9a1309208c74875b2e24d` |
| `metrics.py` | `a4314a70bbde27b3b1abd608439ec6895b4d4623a226727a87e68b6bff65ce3d` |
| `evaluate.py` | `fbe696adf1e1bec9de0fc2cd472996cc99788cd79da3152663e4e1960f2c6a6c` |
| `app.py` | `5548e4febe572bbaac0432d38ffd0e6026acdb955e0b27e7501ed63c69cf8ef9` |
| `profiles.json` | `6ee4d3423fc3d5348425f6a12b699c712a11433108dfa143a94446eddfcce527` |
| `eval-suite.json` | `350280a45be979912200f791eea95fdd7ab1d5194e423c03bd37c7a3528004a6` |
| `static/app.js` | `63b295be417c5f8115ecf0cd3cfc986f9baf957138591fe8cb0f9ab109e93cdd` |
| `static/style.css` | `2dd1401084d05a1d7daf311d0fe7ee3ade6ef82e6b83eb2fba81c51cacdd4769` |
| `static/index.html` | `a6d810200bc3a8a63ea0f3b76c0be6cd8b6ceb22b2f0aae80c9e36638bed0574` |
| `video/run_demo.py` | `ab9a3de462d264b030638269222328df6b304ef5d6fb0276165ee9f26426266a` |
| `video/browser_check.py` | `674896cf1fef662f74b250ba1870da9efc9468fb94ac362ace2f853a9301b442` |
| candidate profile, canonical JSON | `25e4beca64a0abf112da6c97b39388df8d70b861e84aed51c44d864e107f34b4` |
| bound freeze | `efa740e08dc63b28ce6591e9649d1fb2d605d3385a254b045c23d02630ad57fb` |
| parent freeze | `c8b763f8ad2cb18950625ac79dadaee1864bbef3e6f6d36de49f93228a1aa6a2` |

## Границы начального прохода — историческая запись

Платные/облачные вызовы, локальный inference, unload/download и запись браузера
reviewer не запускал. Полнота pilot P и candidate, пригодность Q8 по фактической
памяти, все финальные ответы, агрегаты, итоговая таблица и video ещё требуют
отдельного просмотра. Browser fixtures и screenshots root здесь заново не
запускались и не подменяют живое видео.

Root исправил своё раннее предположение: assignment19 говорит «Создайте несколько
MCP-инструментов». Нельзя приписывать generic faithfulness sentence в candidate
исправление подтверждённого дефекта prompt P; такой дефект не установлен.

Следующий проход: повторно проверить исправления A1/A2, привязку итогового анализа
к неизменённым receipts/manifest, вручную прочитать ответы и источники по рубрике,
проверить warm/cold/Q8 и данные ресурсов, затем окончательный сценарий/видеофайл
и SPEC conformance. До этого ревью не является разрешением на публикацию.

## Финальное закрытие, 10.10.2026

**APPROVED.** Новых существенных открытых findings нет. Самостоятельно проверены
исправления Sol, фактические первичные ответы/источники, warm/cold/Q8,
публичный экспорт и финальный новый MP4. Применён `implementation-validation`;
полная нормативная матрица и проверенные hashes — в
[implementation-validation.md](implementation-validation.md).

| Finding | Исправление и evidence | Итог |
| --- | --- | --- |
| A1: E01/E02 unknown мог получить proven | `evaluate.py:166–176`: обязательный done, validation materialized answer и required source documents до quality flags; `tdd-postprocess-answer-red.txt` → 45 GREEN | CLOSED |
| A2: summary смешивал разные run IDs | `evaluate.py:133–145`, CLI `:245–252`: run_id входит в группу, явный `--run-id`; assessment связан с run/suite/request/receipt hashes; `tdd-summary-run-red.txt` → GREEN | CLOSED |
| Ошибка первого Q8 warmup теряла preparation/series metadata | `evaluate.py:59–71,110–126`: preparation до вызова, series в finally; `tdd-quant-stop-red.txt` → GREEN, ровно один mock generation attempt | CLOSED для текущего controller; старый пробел metadata честно сохранён |
| Record-01 не показывал численный swap, SCENARIO п.6 | Старый proof оставлен PARTIAL; новые dry-02/record-02 с четырьмя свежими ответами каждый; summary-6 показывает реальные before→after GiB/GPU, проверенные bindings | CLOSED |
| В public export были локальные blob paths внутри model_identity.modelfile | Из всех 25 projections удалено только это поле; original SHA и прочие данные сверены; metadata объясняет projection, `/Users/` отсутствует | CLOSED |
| Команда dry run в video README без обязательного `--dry-run` | Команда исправлена и согласована с argparse; существующий dry-02 предшествует record-02 | CLOSED |

`python3 -m unittest discover -s day29/tests -v`: независимо **45/45 PASS**,
1.258 s, Python 3.14.0/macOS 15.6.1 arm64. Это offline/mocks/локальные HTTP
fixtures, не model eval. После этого runtime core/sampler/payload не менялись;
новые данные UI проверены по rendered video frames и raw bindings. Итоговый
`git diff --check` — PASS. Reviewer не запускал inference/unload/download.

Текущий `evaluate.py`:
`fdd23fa66b9493c887320fac248c2af6bc78d66955c7a4c072afed7d08c6640a`.
Исторический evaluator в таблице выше не выдан за эту версию:
[postprocess evidence/diff](../tests/postprocess-evidence.json) сохраняет обе.
Core `ffd03a0c…`, metrics `a4314a70…` и canonical F `25e4beca…` совпадают
с измеренными. Файлы итоговой поставки сверены с
[source-manifest-delivery.json](source-manifest-delivery.json).

Независимая смысловая оценка всех 12 warm receipts подтверждает: E01 6/6 B/F,
E02 B — 2 полных/3 частичных группы, F — 5/5 в обоих повторах; E03 unknown,
sources/quotes пусты. У всех шести пар повторы совпали точно. Все факты F
поддержаны assignment18/19/20; валидность ссылок не использована вместо оценки
смысла. Общая generation median B/F 29.780854646/37.126610021 s, RSS median
5.959197998/5.497596741 GiB: причина `proven` только `E02_completeness`.

Q8 receipt `992e92d31af54169b02d05522efeb430` — error/length при 384 tokens,
140.812 s; два плановых warm **не выполнялись**. Применена заранее записанная
остановка при технической ошибке; успешное Q4/Q8 сравнение не заявляется.
Исходный receipt сохранён, отсутствующий старый preparation sidecar не создан.
Observed RSS не полный Metal peak, swap относится ко всей машине, cold не
означает очищенный OS file cache. Три известных кейса не доказывают обобщение.

Финальный record-02 `6f393fc7546547118052d26de2b60186` проверен по четырём
свежим raw/public/visible receipts и одинаковому E02 input/index. Независимые
ffprobe и full decode — exit 0; просмотрены девять основных кадров MP4 и два
дополнительно извлечённых кадра ожидания F/оригинала Day19. Numeric swap/GPU
видны и совпадают с raw. MP4 328.48 s, 1280×1000, H.264, 25 fps,
SHA `5082b1f0b155b01a3fced5c4dd1d643787f12bd2501855f4d09e3a4420b821c3`.
Финальный код/видео готовы локально; ZIP будет проверен координатором отдельно.
