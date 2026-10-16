# Первое независимое ревью Qwen 10-case quality runner

**Reviewer:** gpt-6-luna
**Worktree/branch:** `day31-qwen-eval`
**Base HEAD:** `1a9d91a0e897dfe4ed5f6a01e5831e1ffbe76431`
**Verdict:** CONDITIONAL — один integrity finding следует закрыть до выполнения frozen plan.

## Finding

**M1 — умеренный: сам eval runner не закреплён в frozen plan.** `runtime_manifest()` хэширует восемь файлов приложения и `eval/compare_models.py`, но не `eval/qwen_quality.py`. Runner в этой ветке untracked, а `plan.git.head` указывает только на базовый commit. Поэтому можно изменить код orchestration/recording/grading между `--plan` и `--execute`, сохранив совпадение всех записанных runtime/input hashes. Это ослабляет доказательство, что execute использовал тот же оценочный harness, что создал frozen plan. Перед платным запуском стоит добавить SHA256 самого runner в plan и проверять его в `execute`; переснимать контекст для этого не требуется.

## Проверенные свойства

- Набор содержит ровно 10 уникальных ID и текстов; Q1–Q6 совпадают с исходными вопросами `eval/cases.json`, Q6 и T3 сохранены буквально, P1 не добавлен.
- Final plan фиксирует 10/10 model-eligible, top-5 retrieval на каждый вопрос и реальные MCP/Git-контексты; Q5 имеет 2 найденных источника и остаётся eligible. Empty retrieval не подменяется: execute останавливается, если хотя бы один вопрос не eligible.
- В actual input находятся только question, sources и git_context; rubric/reference не попадают в prompt. Q2 final input совпадает с исходной формулировкой и содержит конкретный запуск Day17.
- Профиль прибит к `qwen/qwen3.8-max-0902`, `alibaba/us-east-1`, `max_tokens=4096`, Alibaba low reasoning, без fallback и с required parameters. Frozen plan хранит входные snapshots/hashes, корпус, SYSTEM, JSON Schema, cases, Git и runtime app files. Execute заново строит retrieval/MCP inputs и прекращает работу при расхождении.
- Общий ceiling считается до создания ledger/provider и до model calls; затем каждый вызов проходит прежний `BudgetLedger.reserve`. Ledger задаётся абсолютным путём старого `day31-dev-assistant` worktree. Read-only budget query открывает SQLite в `mode=ro`; неизвестные расходы остаются в holds, ledger не сбрасывается.
- Сохранение разделяет raw provider final, распарсенный внешний JSON, ответ Assistant/citation guards и semantic status. Внутренний JSON T3 проверяется отдельно от смысла. Unknown-cost и ошибки остаются видимыми; retry не добавлен, SDK `max_retries=0`.

## План и ограничения

Проверенный final plan имеет `blocked_budget`: 10/10 eligible, `model_calls_sent=0`, ceiling **$0.517374**, текущее остаточное место **$0.0265093576**, минимальный общий лимит для серии **$0.9908646424**. Эти цифры совпадают с сохранёнными данными plan; лимит или ledger я не менял. Plan-only код не создаёт provider и не пишет ledger; сохранённый plan уже содержит бесплатный endpoint metadata preflight. Во время ревью никаких API/metadata запросов и model calls не выполнял.

Изменённые состояния дерева: runner/cases/final-plan untracked; `HANDOFF.md` и `todo.md` уже помечены modified на входе. Код/вопросы/план/root notes/git не изменял. `8071` и ключи не трогал.

## Проверки

- Самостоятельно запустил targeted offline helper suite: `PYTHONPATH=. /Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day31-dev-assistant/.venv/bin/python day31/results/qwen-quality-plan-20261016/test_runner.py` — **8/8 PASS**, 0.094 s. Fake transport тест отдельно подтверждает 10 отдельных exact requests, 10 уникальных резервов/finish, порядок вопросов и обработку фикстур. Это не проверка качества генерации.
- Frozen input `Q2` прочитан и сопоставлен с исходной строкой `eval/cases.json`.
- Хэши прочитанных файлов:
  - `qwen_quality.py`: `6abf2cbbaa02f51335f981d91b920f4da29dd93369fdf01a500fb8467e29c827`
  - `qwen-quality-cases-20261016.json`: `956cfd93f833806b9d3d89a5d6ecb9edb862c18f75f23e951c55b3135379bb7f`
  - final `plan.json`: `062d2b227e88ea97a85ec1710abd114087f8b860e0bab5ad8ac447bfa393269a`
  - final `corpus-manifest.json`: `5eff3ee53733fb89002d8ecb0aeba2c08a169ab3e3062e7fb3d9a3b370473fb8`
  - `SPEC.md`: `3a957860b41cb3aac99e9887dc1737d163f2dd463cb5d872fe16e579b55dc63c`
  - original `eval/cases.json`: `708500f2a9b5a69fe7e90bb7ecd81549fa2db4679a4f7cea53171e6706ffb878`

No model-quality conclusion is possible until authorized live responses are separately reviewed; the offline fixture suite is not an LLM evaluation.
