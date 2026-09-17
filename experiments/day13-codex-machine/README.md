# Codex-машина качества для дня 13

Это внешний контур работы Codex, а не FSM учебного ассистента. Он переносит
проверенный цикл дня 12 и сам демонстрирует требования дня 13:

```text
PLANNING → EXECUTION → VALIDATION → LIVE_VALIDATION → REVIEW → DONE
```

В `state.json` отдельно записаны `phase`, `current_step`, `expected_action` и
`status`. Команды `pause`/`resume` сохраняют рабочую точку буквально. Каждый
переход атомарен, проходит scope-guard и требует структурированный phase result.
`LIVE_VALIDATION` обязателен: 68 ситуаций, 60 реальных calls, 4 pause guards,
4 terminal done guards, durable ledger и общий fail-closed бюджет $0.02.

Контекст этапа собирается в фиксированном порядке:

```text
task + профиль + инварианты + acceptance + durable state
```

## Команды

```bash
python3 experiments/day13-codex-machine/machine.py status
python3 experiments/day13-codex-machine/machine.py check
python3 experiments/day13-codex-machine/machine.py prompt
python3 experiments/day13-codex-machine/machine.py pause --reason "..."
python3 experiments/day13-codex-machine/machine.py resume
python3 experiments/day13-codex-machine/machine.py sync-policy
python3 experiments/day13-codex-machine/machine.py unblock --reason "..."
python3 experiments/day13-codex-machine/machine.py codex-command
python3 experiments/day13-codex-machine/test_machine.py
```

`transition TARGET --result FILE` — единственный путь смены этапа. Внешние
browser/video/review-доказательства добавляются через `record-evidence`.
`sync-policy` обновляет только текущий шаг и ожидаемое действие из политики,
не открывая завершённую задачу и не меняя phase/status.
`unblock` разрешён только после `BLOCKED` и явного решения человека: он открывает
новый repair-cycle в `EXECUTION`, обнуляет счётчик попыток и сохраняет историю.

Baseline — manifest хешей рабочей копии на момент запуска машины. Поэтому уже
существовавшие незакоммиченные файлы пользователя не считаются результатом дня
13, а любое последующее изменение вне `day13/` и control paths видно машине.
