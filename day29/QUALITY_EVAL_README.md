# Парная проверка локальной критики

Отдельный эксперимент рядом с полным чатом; работающий `/8070` и исходный benchmark
не меняются. Сейчас выполнена подготовка и проверки на выдуманных данных.
**Реальные embedding, generation и pilot не запускались.** Требования —
[QUALITY_EVAL_SPEC.md](QUALITY_EVAL_SPEC.md), порядок — [PLAN](QUALITY_EVAL_PLAN.md).

A — один неизменный `full_chat_core.ChatEngine`. B получает сохранённый первый ответ A,
вопрос, resolved query, фактически переданные источники с refs/атрибуцией и историю.
Критик может принять ответ, потребовать одно исправление или признать нехватку
доказательств. После исправления выполняется одна повторная проверка; второго repair нет.
В B нет нового поиска, сокращения источников или gold в prompt. Следующий диалоговый
ход получает только цепочку A предыдущих кейсов, даже если B предыдущего хода улучшился.

`accepted_by_critic` / `accepted_by_recheck` — **мнение той же модели**, не доказанная
правильность. У всех ответов качество `NOT_CHECKED` до независимой сверки с originals/gold.
При провале критика/repair B unavailable; при провале recheck candidate сохранён,
B unverified. Repair с пустыми refs допускается лишь по тому же синтаксическому
правилу explicit unknown/недостатка сведений, что использует baseline; фактический
ответ без refs отклоняется до recheck. Смысл unknown не подтверждает parser.
A не выдаётся за принятый B при технической ошибке. Локальное уточнение
или unknown без generation даёт B not_applicable; ошибка A блокирует B и зависимые ходы.

Подготовленная private выборка: 24 кейса, четыре pilot и 20 holdout, семь типов,
14 intent/sequence groups, 17 original chunks и 50 gold фактов. Эти характеристики
взяты из подготовленного набора, а не из результатов модели. Source/gold audit
выполняет root независимо; его approved означает проверку происхождения gold,
не человеческую приёмку или разрешение запускать inference.

## Команды подготовки

Из корня ветки `day29-full-index-chat`:

```sh
python3 day29/quality_eval.py prepare
python3 -m unittest discover -s day29/tests -p 'test_quality_eval*.py' -v
python3 day29/quality_eval.py mock-dry-run
```

Без команды CLI выбирает `prepare`. Эта команда только читает private matrix,
проверяет порядок/зависимости/split/profile/code hashes и атомарно создаёт новый run.
Audit необязателен для подготовки; если готов `source-audit-v1.json`, он проверяется
и входит в manifest. `mock-dry-run` использует отдельный выдуманный набор и MockOllama,
а не настоящие вопросы/источники. Никаких HTTP, preflight или model downloads в этих
командах нет. Публичный stdout содержит только IDs/stages/status/counters.

Данные каждого run лежат в `day29/private/full-chat/quality-eval/runs/<run_id>/`:
`manifest.json`, `inputs.json`, `checkpoint.json`, `summary.json` после выполнения.
В checkpoint сохраняются исходный A, исходные payloads/raw responses, prefixes,
критика, candidate/recheck, budget и times. Эти файлы **private**, не копировать
в публичные логи. Каталоги 0700, атомарные JSON 0600; путь CLI ограничен quality-eval.
Input hash, protocol hash и hashes runtime-кода проверяются при открытии run;
после изменения кода, протокола или selection нужен новый prepare, старые receipts сохраняются.

## Явная выборка пяти кейсов

Пользователь поручил следующий реальный прогон пяти новых вопросов после reviews,
а не всех 24. Root выбирает пять holdout с dependency=None из разных groups
seeded random и замораживает private selection manifest. Runner сам вопросы не выбирает.
Формат файла: `{cases_file_sha256, case_ids:[ID,...], seed, method}`; текстов вопросов
в нём не требуется. Передать его при prepare:

```sh
python3 day29/quality_eval.py prepare \
  --selection-file day29/private/full-chat/quality-eval/selected-five-v1.json
```

Альтернатива — повторить `--case-id Hxx` для каждого ID при prepare. Runner сохраняет
selection.json, dataset/source-file/selection hashes и порядок из общей frozen matrix.
Он отвергает unknown/duplicate IDs и missing dependency; предыдущие кейсы не добавляет
молча. Любая цепочка должна целиком войти в явную selection. Resume проверяет тот же
selection hash. При run можно повторить все пять `--case-id` как дополнительный guard;
они должны точно совпасть с frozen subset, расширить его на run нельзя.

Run без `--case-id` использует selection из своего manifest. Summary явно содержит
selected_case_ids/count и pending_unselected_holdout: для пяти holdout это 5 и 15.
Четыре pilot также остаются unselected. Результат этого прогона только partial subset,
не whole-holdout и не качество всех 24. При условных 40–51 s на новую стадию пять
вопросов ×2..4 calls дают примерно **7–17 минут**, плюс orchestration/assessment;
реальные stage times ещё неизвестны.

## Контракт живого запуска

Следующие команды при текущей подготовке не выполнялись. Для выбранных пяти
использовать их собственный selection manifest; полный набор показан лишь как
общий контракт CLI. После финального review и source audit создать свежий
manifest, затем явно запускать выбранный split:

```sh
python3 day29/quality_eval.py prepare \
  --audit-file day29/private/full-chat/quality-eval/source-audit-v1.json
python3 day29/quality_eval.py run \
  --run-root day29/private/full-chat/quality-eval/runs/RUN_ID \
  --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1 \
  --split pilot
# После pilot и отдельного protocol freeze — holdout того же неизменного протокола:
python3 day29/quality_eval.py run \
  --run-root day29/private/full-chat/quality-eval/runs/RUN_ID \
  --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1 \
  --split holdout
python3 day29/quality_eval.py summary \
  --run-root day29/private/full-chat/quality-eval/runs/RUN_ID
```

`run` требует точный dataset SHA и approved independent-agent audit с
`human_acceptance:false`, frozen index identity и прежние Q4/model digests.
Модель всех generation stages — `qwen3:8b`, local `127.0.0.1:11434`, think false,
temperature 0. A прежний 8192/1024; critic/recheck 8192/512, repair 8192/1024.
Весь payload, schema и запас template/output проверяются до dispatch.
Не вмещающийся B envelope получает budget_rejected, без усечения и без запроса.
Служебные tags/show, embedding и generation считаются отдельно; warmup отсутствует.

Глобальные Day28/29 locks сериализуют model calls; private `runner.lock` защищает
checkpoint одного run от двух controllers. Ни daemon, ни чужой процесс runner не
выгружает и не перезапускает. Конфликт model lock сохраняется как technical failure.

## Сбой и продолжение

Checkpoint записывается **до** каждого HTTP dispatch и после результата.
Повторное открытие run не генерирует заново completed stages. После crash/timeout
неоднозначно отправленный stage — interrupted_unknown, без replay. Следующий
dispatch остановлен до явного подтверждения оператора, например:

```sh
python3 day29/quality_eval.py run \
  --run-root day29/private/full-chat/quality-eval/runs/RUN_ID \
  --index-root /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day28/day28/private/index-release-v1 \
  --split holdout \
  --confirm-idle 'Оператор проверил завершение предыдущего inference и подтвердил idle'
```

Это записанная **operator assertion**, не автоматическое доказательство idle.
Список resident моделей `/api/ps` не считается доказательством отсутствия inference.
Подтверждение не повторяет прерванный stage: он остаётся unavailable/unverified,
продолжаются разрешённые независимые кейсы. Неверная model identity также ставит
run на паузу; исправление причины и безопасное продолжение требует оператора.
Есть transport timeout 300 s; общего walltime deadline или call cap нет.
Простой после ошибки учитывается отдельно до operator confirmation, не изображается
быстрым ответом. Ошибки и исходные расходы остаются в coverage/counters.

## Проверки и оценка времени

34 focused unittest checks GREEN: shared A/gold boundaries, source/history identity,
единственный repair/recheck, strict schema/refs/JSON/stop, length/timeout/busy/digest,
budget/no dispatch, private modes, baseline-only dependencies, completed/resume,
crash/no replay, exclusive controller, nullable missing metrics и время всех stages.
[Лог](tests/quality-offline-green.txt), [RED/GREEN evidence](tests/quality-evidence.json).
Полный synthetic24 mock dry-run: 23 model pairs и одно локальное уточнение,
46 mock chat / 23 mock embed / 184 mock service calls, real network 0.
Это проверка runner, **не** оценка качества Qwen. Repair/failure/resume ветки отдельно
проверены синтетическими тестами; mock24 использует accept для всех model critics.

Предыдущие три настоящие full-chat receipts занимали около 40–51 s total каждый.
Если новые стадии стоили бы столько же, 23×2..4 = 46..92 generation calls заняли бы
примерно **31–79 минут**, плюс orchestration и независимая source-backed оценка.
Pilot входит в 24, не прибавляется сверху. Critic/repair/recheck ещё не измерены,
поэтому это условный расчёт, а не гарантированная длительность или ограничение.
После будущего pilot root сможет уточнить оценку остатка. Электричество/оборудование
и usage/cost агентских ролей не измерены; paid-provider calls runner — 0.

После resume completed stage durations сохраняются в observed lower bound B,
не суммируются повторно с текущим execution window. При потерянном orchestration
headline B_latency/pair_observed_seconds = null; новый короткий execution window
не выдаётся за полное время ответа. Missing stage/HTTP timings явно отмечаются.

Технический summary показывает coverage/counters/observed times и missing metrics;
не подсчитывает quality wins из мнения критика. Независимый assessor оценивает A/B
по originals и gold без arm labels и verdict критика; pilot отдельно от holdout.
Пропуск факта — полнота, unsupported assertion — support, ошибочная attribution
отдельно; retrieval доступность фактов в selected/transmitted context проверяется
отдельно. Не заявляются общий hallucination rate, статистическая значимость или
человеческая приёмка. Reviews Luna и Astra и настоящие прогоны — задачи root.

Свежая доставка готовится отдельным [public-only live сценарием](video/SCENARIO-full-chat.md);
quality private кейсы/голды в видеозапись не входят. Runner не подключается к UI.
