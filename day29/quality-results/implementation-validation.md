# Quality runner — implementation validation

Baseline: Day29 full-chat worktree, branch day29-full-index-chat; SPEC SHA `62ea7145a6307e4eb9de47c488c14a9649197f4a2dda89145f1aa71b51a503e2`, PLAN SHA `2d0ffe7242248a52dacfc4ab6b641a99e302ddb807258c541acf2392f1f5f668`. Проверен runner SHA `329a11f5442cd02ac2a87f3bdaeb438c89e2c10e4f011af381895f4d191cb89c`. Исполнение поручено автономно; отдельное human SPEC approval не заявляется. Фактический reviewer — Astra/gpt-6-astra xhigh.

**Подготовка runner: APPROVED, 26 PASS. Полный эксперимент: SPEC PARTIALLY SATISFIED — 26 PASS, 0 FAIL, 4 NOT PROVEN.** Source audit APPROVED не подменяет code review или оценку реальных ответов. Матрица ниже относится ко всему заявленному контракту; actual-run/scoring rows ожидаемо NOT PROVEN на этапе подготовки.

## Модель ошибок доказательства

Mock accept способен скрыть неверное утверждение, поэтому семантика не выводится из валидного JSON. Совпадение вопроса не гарантирует одинаковый контекст, поэтому проверены точные transmitted поля. Completed/recovery могут скрыть повторный вызов или потерю расходов, поэтому проверены dispatch checkpoints, counters и отдельный resume-time repro. Замороженный набор24 не доказывает допустимый subset5: actual adapter и negative tests проверены отдельно. Наличие файла/старого GREEN не считается исполнением: 34 focused tests запущены независимо на указанном SHA с запретом HTTP.

## Инвентарь требований и доказательства

| SPEC item | Наблюдаемое требование | Доказательство | Статус |
| --- | --- | --- | --- |
| Q01 | Точная версия и неизменный baseline | prepare/code_hashes/Runner.__init__; actual hashes core/full_chat_core/metrics совпадают с прежними | PASS |
| Q02 | A выполняется один раз; B использует сохранённый A | Runner._run/run_b; shared draft и completed resume tests | PASS |
| Q03 | Тот же model/digest, think=false, temperature=0; A8192/1024, B512/1024/512 | protocol/critique_payload; полное чтение constants и options | PASS |
| Q04 | Точные question/query/history/sources/refs A во всех B стадиях, без нового retrieval | critique_payload копирует ровно четыре исходных поля; preservation tests | PASS |
| Q05 | Gold/чужие ответы/ожидаемые оценки не попадают в payload; инструкции источников — данные | Статический data flow + SECRET/gold negative tests; system instructions | PASS |
| Q06 | Строгий JSON/schema, stop/model/context, refs и пустые refs только с baseline unknown guard | validate_response/validate_critique; invalid JSON/duplicate keys/length/refs/unknown tests | PASS |
| Q07 | Accept завершает без repair; insufficient evidence не означает accept | run_b; false accept opinion / insufficient evidence tests | PASS |
| Q08 | Не более одного repair и одного recheck, recheck без verdict/замечаний critic | run_b и one_repair_recheck test; нет цикла repair | PASS |
| Q09 | Ошибка/неудача recheck сохраняет candidate как unverified, без fallback под видом исправления | run_b/dispatch checkpoints; invalid/recheck tests | PASS |
| Q10 | Локальный unknown/clarification без generation — B not_applicable, A error — dependency_blocked | run_b guards и no_sources/baseline_error tests | PASS |
| Q11 | Полный envelope/schema/template/output budget до dispatch; без clipping и повышения context | check_payload_budget + CheckpointClient; oversized A/B tests, dispatch_count=0 | PASS |
| Q12 | Только loopback, фиксированные model identities, отсутствие cloud/download/reindex | core.Ollama transport/verify, strict live entrypoint; wrong digest test | PASS |
| Q13 | 24 frozen cases, 4/20 split, gold originals, группы и исключение старых намерений | Отдельный source audit APPROVED, matrix/source hashes; validate_matrix | PASS |
| Q14 | Текущий subset ровно5 новых standalone из5 групп; 15 holdout и4 pilot не добавляются | Actual adapter hash/IDs checked; selected5 counters, missing dependency и mutation tests | PASS |
| Q15 | Диалоговые префиксы — только реальные предыдущие A той же цепочки, без B/gold | prefix/validate_matrix; baseline-only prefix и dependency-blocked tests; actual5 без dependencies | PASS |
| Q16 | Coverage различает selected/unselected/pending/failed/unavailable и quality NOT_CHECKED | summary/run_b; five-subset/timeout/missing metrics tests | PASS |
| Q17 | Каждый generation/embed/service dispatch учитывается, shared A один раз, missing usage nullable | CheckpointClient/counters; exact counters и missing metrics tests | PASS |
| Q18 | A latency и B=A+все добавленные стадии, ошибки не изображаются ускорением | A1 исправлен: continuous timing либо null headline + observed lower bound; собственный repro≥12s и cached-stage/no-double-count tests | PASS |
| Q19 | Глобальные Day28/29 locks и отдельный lock controller защищают вызовы/checkpoint | core.generation_lock, dispatch/controller_lock; busy и two controllers tests | PASS |
| Q20 | Atomic private checkpoints до dispatch и после стадий; completed не повторяются | save_private/CheckpointClient/dispatch; resume completed tests | PASS |
| Q21 | Crash/timeout ambiguous → interrupted_unknown, pause до operator idle, без replay | reload_recover/confirm_idle; crash/timeout/incomplete provider tests; operator assertion не auto proof | PASS |
| Q22 | Общего deadline/call cap нет; transport timeout300 не означает остановку Ollama | protocol/core.TIMEOUT; explicit idle confirmation и no global limits test | PASS |
| Q23 | Resume привязан к input/protocol/code/selection/payload hashes | Runner.__init__/dispatch; mutation tests и фактические hashes | PASS |
| Q24 | Private0700/0600, atomic writes, CLI path boundary, symlink root rejected; public без private текстов | private_dir/main/save_private; modes, symlink и stdout negative tests | PASS |
| Q25 | Неверная identity/неизвестное исполнение останавливает зависимые вызовы | Runner._run/CheckpointClient; wrong digest и incomplete provider tests | PASS |
| Q26 | Независимый source audit gate отделён от human acceptance; prepare без network | validate_audit/live gate; root audit hash и live_audit_required test | PASS |
| Q27 | Пять actual A/B попыток и реальные полный receipts/stage metrics | До разрешённого запуска отсутствуют real quality receipts; synthetic30 не доказывают это | NOT PROVEN |
| Q28 | Независимый blinded scoring actual answers: support/correctness/attribution/answerability, group completeness | Рубрика и originals готовы; actual answers/scoring ещё отсутствуют | NOT PROVEN |
| Q29 | Actual retrieval coverage selected vs transmitted vs gold, без смешения search/budget/generation omissions | Код сохраняет A evidence; нужна source-backed оценка реальных пяти | NOT PROVEN |
| Q30 | Итоговые wins/ties/regressions/false acceptance, numerators/denominators, latency/coverage/все затраты | Нужны real results и независимая оценка; critic status не quality verdict | NOT PROVEN |

## Выполненные проверки

Независимый запуск: Python3.14.0/macOS arm64, `unittest.defaultTestLoader.discover('day29/tests', pattern='test_quality_eval*.py')`, TextTestRunner verbosity2, socket.create_connection и urllib.request.urlopen patched to AssertionError. Результат: 34 tests, failures0/errors0, exit0. Чтение implementation, тестов и transport было полным для указанного scope. Реальные HTTP/generation/embedding reviewer:0. Новые тесты/модельные данные не создавались в public corpus; дополнительный синтетический A1 repro сохранён только private.

## Закрытые дефекты / недостающие доказательства

Открытых FAIL нет. A1 устранён в `quality_eval.py:366–381,399–437`: потерянное orchestration время не угадывается, headline null; все известные сохранённые стадии входят в observed lower bound без double-count. Свежие34 tests и собственный repro подтвердили исправление; подробности в [review-astra.md](review-astra.md). NOT PROVEN Q27–Q30 требуют реального исполнения выбранных пяти и независимого source-backed scoring; это следующие разрешённые этапы, не отсутствующее human approval.

## Границы применимости

Четыре pilot и полный20 holdout — условный будущий объём, не текущие обязательные вызовы. Текущий subset H05/H12/H20/H06/H11 содержит12 gold-групп; не50 атомарных claims. Все50 групп source-аудированы отдельно, данные матрицы неизменны. Full-chat UI/live correction, новая запись и публикация исключены из этого runner review и имеют отдельную поставку. Human acceptance не является достигнутым фактом. Отсутствие общего deadline/call budget не расширяет число выбранных вопросов.

Не заявлены общий hallucination rate, статистическая значимость, quality превосходство B, actual stage times или денежная экономия. Оценка времени в PLAN — условная экстраполяция, новые critic/repair/recheck ещё не измерены. Reviewer implementation и чужие runtime процессы не менял.

## Итог и version binding

Runner готов к текущему разрешённому запуску пяти после обычного свежего prepare на новом code hash. Старый prepared manifest от прежнего кода закономерно отклоняется. Весь эксперимент пока частично подтверждён: Q27–Q30 будут оценены после real run, это не требование дополнительного human approval. Применимость текущего этапа не распространяется на новые24/model retries вне выбранного scope.

- `quality_eval.py`: `329a11f5442cd02ac2a87f3bdaeb438c89e2c10e4f011af381895f4d191cb89c`
- `full_chat_core.py`: `6e887f0dd664d73d7eff0f267ed4dd505142efddfd51d20cbcc26957a5565bf1`
- `core.py`: `ffd03a0c5bc659e50783416c469c72d8f79f7d02a7d9a1309208c74875b2e24d`
- `metrics.py`: `a4314a70bbde27b3b1abd608439ec6895b4d4623a226727a87e68b6bff65ce3d`
- `QUALITY_EVAL_SPEC.md`: `62ea7145a6307e4eb9de47c488c14a9649197f4a2dda89145f1aa71b51a503e2`
- `QUALITY_EVAL_PLAN.md`: `2d0ffe7242248a52dacfc4ab6b641a99e302ddb807258c541acf2392f1f5f668`
- `QUALITY_EVAL_README.md`: `8a34179e9fe1028311ad9fa40b6ecb7ec56dd4e4e2f998c933e8ca722e0bba1d`
- `QUALITY_EVAL_TASKS.md`: `287b0d29e39b7d0b1559609824402bc13382914d14bfd459fb821cee9cc49808`
- `tests/test_quality_eval_protocol.py`: `751818837581c578fcbac4effcf26ce26eaf52a6b68531cc1225a7d6fc5163ce`
- `tests/test_quality_eval_failures.py`: `af6dc8074691225f3bc1b3a7e25413a740e12f05ab383dedaa74dc1318d13132`
- `tests/quality-evidence.json`: `74e35eed1856984d920675bea6f9564f5664afc99e813b24785d90042bdb2dc9`
- selection adapter: `1d0b34de7b50fdd4ec4d98be32ebf1dcb72e8cfd3994975046b54c13f2189adb`
- source audit freeze: `774e07bdfaa0ee166c5364660ad702143fcae4761e4ff5db1e8851579b22ca61`
- cases-v1: `7586cf21e94f394a9bc2700728ebd73f6889bf2869f2b83bf9109d4e0266efa9`
