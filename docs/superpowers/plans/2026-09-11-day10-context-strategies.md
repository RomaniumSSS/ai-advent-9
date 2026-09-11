# День 10 — три стратегии контекста. План реализации

> **Для агентов:** выполнять по задачам, шаги отмечены `- [ ]`.

**Цель:** агент с тремя стратегиями управления контекстом (Sliding Window,
Sticky Facts, Branching), переключателем между ними и сравнением на одном
сценарии.

**Архитектура:** `day10/` — самостоятельная копия дня 9 без суммаризации.
Сборка запроса делегируется объекту стратегии; архив в SQLite не режется
никогда. Ветки — отдельные сессии в том же файле базы.

**Стек:** Python 3.12, `openai` SDK через OpenRouter, `tiktoken`, SQLite,
`http.server`. Тесты — обычные скрипты с `main()`, не pytest.

## Общие ограничения

- Комментарии, докстринги, README — по-русски. Коммиты — по-английски.
- Дни 1–9 не трогать. Правки живут только в `day10/`.
- Импорта между днями нет: `day10` копирует, а не импортирует из `day09`.
- Модель `deepseek/deepseek-v4-flash-0731`, провайдер `open-inference/fp8`,
  `allow_fallbacks: False`, reasoning выключен, `max_retries=0`.
- Бюджет $0.50, резерв берётся до каждого платного вызова.
- Ключи facts фиксированы: `проект`, `цель`, `ограничение`, `срок`, `бюджет`,
  `решение`, `отменённое_решение`, `предпочтение`, `договорённость`.
- Удаление факта запрещено: пустое значение и `null` игнорируются.
- Порт панели 8040, только `127.0.0.1`.
- Ошибку не глотать: отсутствующий `usage` — `None`, не `0`.

---

### Задача 1: Каркас day10 без суммаризации

**Файлы:**
- Создать: `day10/` — копия `day09/` без `results/`, `demo/`
- Изменить: `day10/agent.py` (убрать сжатие), `day10/store.py` (схема v4 заготовка)
- Удалить из копии: `day10/experiment.py` строку определения `kind == 'summary'`

- [ ] **Шаг 1: скопировать день 9**

```bash
mkdir -p day10
cp day09/{base_agent.py,models.py,tokens.py,store.py,scenarios.py,quality.py,web.py} day10/
cp -r day09/web day10/web
```

- [ ] **Шаг 2: вырезать сжатие из `agent.py`**

Написать `day10/agent.py` заново: без `SUMMARY_PROMPT`, `CompressionConfig`,
`compact()`. Оставить `Agent(ChatAgent)` с полем `strategy`.

- [ ] **Шаг 3: убрать таблицу `compression` из `store.py`**

`SCHEMA_VERSION = 4`, таблица `compression` и методы `load_compression` /
`save_compression` удаляются, миграции дней 2 и 3 остаются (база самостоятельна,
но код миграции — часть скопированного механизма).

- [ ] **Шаг 4: проверить, что импортируется**

Запуск: `uv run python -c "import sys; sys.path.insert(0,'day10'); import agent, store"`
Ожидание: без ошибок.

- [ ] **Шаг 5: коммит**

```bash
git add day10 && git commit -m "feat(day10): copy day 9 without summarisation"
```

---

### Задача 2: strategies.py

**Файлы:**
- Создать: `day10/strategies.py`
- Тест: `day10/test_strategies.py`

**Интерфейсы:**
- Отдаёт: `STRATEGIES = ("full", "sliding", "facts")`,
  `StrategyConfig(name: str, recent_messages: int = 6)`,
  `context_history(config, history: list[dict], facts: FactsState) -> list[dict]`,
  `FACTS_PREFIX: str`.

- [ ] **Шаг 1: написать падающий тест**

```python
def test_sliding_keeps_tail():
    history = [{"role": "user", "content": f"m{i}"} for i in range(10)]
    config = StrategyConfig(name="sliding", recent_messages=4)
    result = context_history(config, history, FactsState())
    assert [m["content"] for m in result] == ["m6", "m7", "m8", "m9"]

def test_facts_block_goes_first_and_is_not_system():
    history = [{"role": "user", "content": "m1"}]
    facts = FactsState(values={"цель": "сайт записи"})
    result = context_history(StrategyConfig(name="facts"), history, facts)
    assert result[0]["role"] == "assistant"
    assert "цель: сайт записи" in result[0]["content"]

def test_full_returns_everything():
    history = [{"role": "user", "content": f"m{i}"} for i in range(10)]
    result = context_history(StrategyConfig(name="full"), history, FactsState())
    assert len(result) == 10

def test_unknown_strategy_refused():
    try:
        StrategyConfig(name="magic")
    except ValueError:
        return
    raise AssertionError("неизвестная стратегия должна отвергаться")
```

- [ ] **Шаг 2: убедиться, что падает**

Запуск: `uv run day10/test_strategies.py`
Ожидание: FAIL, модуль не найден.

- [ ] **Шаг 3: реализовать**

`FactsState` — frozen dataclass с `values: dict`, `revision: int`, методом
`render()` («- ключ: значение» построчно) и `merge(updates) -> FactsState`.
`context_history` разбирает три имени; блок facts подставляется сообщением
`role=assistant` с `FACTS_PREFIX`, затем `history[-recent_messages:]`.

- [ ] **Шаг 4: проверить**

Запуск: `uv run day10/test_strategies.py`
Ожидание: `ok`-строки, без `FAIL`.

- [ ] **Шаг 5: коммит**

```bash
git add day10/strategies.py day10/test_strategies.py
git commit -m "feat(day10): context strategies without summarisation"
```

---

### Задача 3: facts.py — извлечение и мерж

**Файлы:**
- Создать: `day10/facts.py`
- Тест: `day10/test_facts.py`

**Интерфейсы:**
- Потребляет: `FactsState` из `strategies.py`
- Отдаёт: `FACT_KEYS: tuple[str, ...]`, `FACTS_SYSTEM_PROMPT: str`,
  `parse_facts(text: str) -> dict`, `normalize(updates: dict) -> dict`

- [ ] **Шаг 1: написать падающий тест**

```python
def test_unknown_key_dropped():
    assert normalize({"погода": "дождь", "цель": "сайт"}) == {"цель": "сайт"}

def test_empty_value_does_not_delete():
    state = FactsState(values={"цель": "сайт"})
    assert state.merge(normalize({"цель": ""})).values == {"цель": "сайт"}
    assert state.merge(normalize({"цель": None})).values == {"цель": "сайт"}

def test_overwrite_changes_value_and_bumps_revision():
    state = FactsState(values={"срок": "18 октября"})
    changed = state.merge(normalize({"срок": "25 октября"}))
    assert changed.values["срок"] == "25 октября"
    assert changed.revision == state.revision + 1

def test_broken_json_returns_empty():
    assert parse_facts("не JSON вовсе") == {}
    assert parse_facts("") == {}

def test_json_in_code_fence_is_read():
    assert parse_facts('```json\n{"цель": "сайт"}\n```') == {"цель": "сайт"}
```

- [ ] **Шаг 2: убедиться, что падает**

Запуск: `uv run day10/test_facts.py`
Ожидание: FAIL.

- [ ] **Шаг 3: реализовать**

`parse_facts` снимает ограждение ```` ```json ````, разбирает JSON, при любой
ошибке возвращает `{}`. `normalize` оставляет только ключи из `FACT_KEYS`,
приводит значение к строке, обрезает до 400 символов, выбрасывает пустые.

- [ ] **Шаг 4: проверить**

Запуск: `uv run day10/test_facts.py`
Ожидание: `ok`, без `FAIL`.

- [ ] **Шаг 5: коммит**

```bash
git add day10/facts.py day10/test_facts.py
git commit -m "feat(day10): fixed-key facts extraction and merge"
```

---

### Задача 4: store.py — facts и branches, схема v4

**Файлы:**
- Изменить: `day10/store.py`
- Тест: `day10/test_store_v4.py`

**Интерфейсы:**
- Отдаёт: `load_facts() -> dict`, `save_facts(values: dict) -> None`,
  `fork(new_session: str, checkpoint: int) -> None`,
  `branches() -> list[dict]`

- [ ] **Шаг 1: написать падающий тест**

```python
def test_facts_roundtrip(tmp):
    store = SqliteStore(tmp, "main")
    store.save_facts({"цель": "сайт"})
    assert store.load_facts() == {"цель": "сайт"}

def test_fork_copies_prefix_only(tmp):
    store = SqliteStore(tmp, "main")
    for i in range(3):
        store.append_turn(f"q{i}", FakeReply())
    store.fork("main/a", checkpoint=4)
    assert len(SqliteStore(tmp, "main/a").load()) == 4
    assert len(store.load()) == 6

def test_branches_are_independent(tmp):
    store = SqliteStore(tmp, "main")
    store.append_turn("q", FakeReply())
    store.fork("main/a", checkpoint=2)
    SqliteStore(tmp, "main/a").append_turn("only-a", FakeReply())
    assert len(store.load()) == 2

def test_checkpoint_beyond_history_refused(tmp):
    store = SqliteStore(tmp, "main")
    try:
        store.fork("main/a", checkpoint=99)
    except ValueError:
        return
    raise AssertionError("граница вне истории должна отвергаться")
```

- [ ] **Шаг 2: убедиться, что падает**

Запуск: `uv run day10/test_store_v4.py`
Ожидание: FAIL.

- [ ] **Шаг 3: реализовать**

Таблицы `facts(session, key, value, updated_at)` и
`branches(session, parent, checkpoint, created_at)`. `fork` одной транзакцией
копирует первые `checkpoint` сообщений и текущие facts, пишет строку в
`branches`. `clear()` чистит обе новые таблицы.

- [ ] **Шаг 4: проверить**

Запуск: `uv run day10/test_store_v4.py`
Ожидание: `ok`.

- [ ] **Шаг 5: коммит**

```bash
git add day10/store.py day10/test_store_v4.py
git commit -m "feat(day10): store facts and branches, schema v4"
```

---

### Задача 5: agent.py — стратегия внутри агента

**Файлы:**
- Изменить: `day10/agent.py`, `day10/experiment.py`
- Тест: `day10/test_agent_strategies.py`

**Интерфейсы:**
- Потребляет: `StrategyConfig`, `context_history`, `FactsState` из `strategies.py`;
  `FACTS_SYSTEM_PROMPT`, `parse_facts`, `normalize` из `facts.py`
- Отдаёт: `Agent(config, strategy=StrategyConfig(...), store=...)`,
  `agent.facts: FactsState`, `agent.facts_event: dict | None`,
  `agent.switch_strategy(name: str) -> None`

- [ ] **Шаг 1: написать падающий тест**

```python
def test_sliding_agent_sends_only_tail():
    agent = Agent(strategy=StrategyConfig("sliding", recent_messages=2), client=FakeClient())
    for i in range(4):
        agent.ask(f"вопрос {i}")
    sent = FakeClient.last_messages
    assert len(sent) == 1 + 2 + 1  # system + хвост + новый вопрос

def test_facts_agent_makes_extra_call():
    client = FakeClient(reply_text='{"цель": "сайт записи"}')
    agent = Agent(strategy=StrategyConfig("facts"), client=client)
    agent.ask("Планируем сайт записи")
    assert client.calls == 2
    assert agent.facts.values == {"цель": "сайт записи"}

def test_broken_facts_json_keeps_previous_and_reports():
    client = FakeClient(reply_text="извините, не понял")
    agent = Agent(strategy=StrategyConfig("facts"), client=client)
    agent.ask("вопрос")
    assert agent.facts.values == {}
    assert agent.facts_event["error"]

def test_switch_strategy_keeps_history():
    agent = Agent(strategy=StrategyConfig("sliding"), client=FakeClient())
    agent.ask("вопрос")
    agent.switch_strategy("full")
    assert agent.turns == 1
```

- [ ] **Шаг 2: убедиться, что падает**

Запуск: `uv run day10/test_agent_strategies.py`
Ожидание: FAIL.

- [ ] **Шаг 3: реализовать**

`build_messages` зовёт `context_history(self.strategy, self._history, self.facts)`.
После удачного хода при `strategy.name == "facts"` — `_update_facts()`:
отдельный `ChatAgent` с `FACTS_SYSTEM_PROMPT`, ответ через `parse_facts` и
`normalize`, расход пишется `store.append_call(reply, kind="facts")`.
В `experiment.py` определение вида вызова: `kind = 'facts'`, если первый
элемент `messages` начинается с `FACTS_SYSTEM_PROMPT[:20]`, иначе `chat`.

- [ ] **Шаг 4: проверить**

Запуск: `uv run day10/test_agent_strategies.py`
Ожидание: `ok`.

- [ ] **Шаг 5: коммит**

```bash
git add day10/agent.py day10/experiment.py day10/test_agent_strategies.py
git commit -m "feat(day10): agent delegates context assembly to a strategy"
```

---

### Задача 6: branches.py — checkpoint и ветки

**Файлы:**
- Создать: `day10/branches.py`
- Тест: `day10/test_branches.py`

**Интерфейсы:**
- Отдаёт: `checkpoint(agent) -> int`,
  `fork(agent, name: str, checkpoint: int) -> None`,
  `switch(agent, session: str) -> None`,
  `branch_list(agent) -> list[dict]`

- [ ] **Шаг 1: написать падающий тест**

```python
def test_fork_then_branches_diverge(tmp):
    agent = make_agent(tmp, "main")
    agent.ask("общий вопрос")
    point = checkpoint(agent)
    fork(agent, "main/a", point)
    fork(agent, "main/b", point)
    switch(agent, "main/a")
    agent.ask("только в A")
    switch(agent, "main/b")
    assert all("только в A" != m["content"] for m in agent.history)

def test_switch_reloads_facts(tmp):
    agent = make_agent(tmp, "main")
    agent.facts = FactsState(values={"цель": "сайт"})
    agent.save_facts()
    fork(agent, "main/a", checkpoint(agent))
    switch(agent, "main/a")
    assert agent.facts.values == {"цель": "сайт"}
```

- [ ] **Шаг 2: убедиться, что падает**

Запуск: `uv run day10/test_branches.py`
Ожидание: FAIL.

- [ ] **Шаг 3: реализовать**

`switch` подменяет `agent.store` на `SqliteStore(path, session)`, перечитывает
историю и facts. `checkpoint` возвращает `len(agent.history)`.

- [ ] **Шаг 4: проверить**

Запуск: `uv run day10/test_branches.py`
Ожидание: `ok`.

- [ ] **Шаг 5: коммит**

```bash
git add day10/branches.py day10/test_branches.py
git commit -m "feat(day10): dialogue branches over sessions"
```

---

### Задача 7: панель с переключателем

**Файлы:**
- Изменить: `day10/web.py`, `day10/web/index.html`, `day10/web/app.js`
- Тест: `day10/test_web.py`

- [ ] **Шаг 1: написать падающий тест**

```python
def test_switch_strategy_endpoint():
    response = post("/api/strategy", {"name": "facts"})
    assert response["strategy"] == "facts"

def test_fork_endpoint_creates_branch():
    post("/api/branch", {"name": "a", "checkpoint": 2})
    assert "main/a" in [b["session"] for b in get("/api/state")["branches"]]

def test_unknown_strategy_rejected():
    assert post("/api/strategy", {"name": "magic"}, expect=400)["error"]
```

- [ ] **Шаг 2: убедиться, что падает**

Запуск: `uv run day10/test_web.py`
Ожидание: FAIL.

- [ ] **Шаг 3: реализовать**

Одна панель вместо двух. `POST /api/strategy`, `POST /api/branch`,
`POST /api/switch`. В `panel_state` добавить `strategy`, `facts`,
`facts_event`, `branches`, `active_messages`. На странице — переключатель,
видимый блок facts, кнопки ветвления.

- [ ] **Шаг 4: проверить**

Запуск: `uv run day10/test_web.py`
Ожидание: `ok`.

- [ ] **Шаг 5: коммит**

```bash
git add day10/web.py day10/web day10/test_web.py
git commit -m "feat(day10): panel with strategy switch and branches"
```

---

### Задача 8: живой прогон и сравнение

**Файлы:**
- Создать: `day10/run_strategies.py`, `day10/analyze.py`, `day10/README.md`
- Изменить: `README.md`, `todo.md`

- [ ] **Шаг 1: написать прогон**

`run_strategies.py --strategy sliding|facts|full --repeat N` гоняет сценарий
`project` (16 вопросов) в отдельной сессии, пишет `results/<стратегия>-rN.json`.
Ветвление — `--branching`: checkpoint после 8-го хода, две ветки по три хода.

- [ ] **Шаг 2: офлайн-проверка прогона с подставным клиентом**

Запуск: `uv run day10/run_strategies.py --dry-run`
Ожидание: три сессии отработали без сети, файлы результатов созданы.

- [ ] **Шаг 3: живой прогон**

Запуск: `uv run day10/run_strategies.py --env-file .env --all`
Ожидание: бюджет не превышен, `results/` заполнен.

- [ ] **Шаг 4: сводка и проверка фактов**

Запуск: `uv run day10/analyze.py && uv run day10/quality.py`
Ожидание: таблица по стратегиям, лексическая проверка эталонных фактов.

- [ ] **Шаг 5: README с реальными числами и коммит**

```bash
git add day10 README.md todo.md
git commit -m "docs(day10): compare three context strategies"
```

---

## Критерии готовности

1. Все офлайн-проверки зелёные: `test_strategies.py`, `test_facts.py`,
   `test_store_v4.py`, `test_agent_strategies.py`, `test_branches.py`,
   `test_web.py`.
2. Живой прогон трёх стратегий и ветвления уложился в $0.50.
3. Таблица сравнения в `day10/README.md` с реальными числами.
4. Дни 1–9 не изменены: `git diff --stat main -- day01 … day09` пуст.
5. Видео — отдельным шагом после приёмки кода Романом.
