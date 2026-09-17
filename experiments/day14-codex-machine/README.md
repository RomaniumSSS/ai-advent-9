# Codex FSM для дня 14

Внешний контур качества сохраняет процесс дня 13:

```text
PLANNING → EXECUTION → VALIDATION → LIVE_VALIDATION → REVIEW → DONE
```

FSM не является частью учебного ассистента. Она управляет самой работой Codex:
каждый переход принимает структурированный result, сверяет acceptance и scope,
а `pause/resume` сохраняет точную рабочую точку в `state.json`.

```bash
python3 experiments/day14-codex-machine/machine.py status
python3 experiments/day14-codex-machine/machine.py check
python3 experiments/day14-codex-machine/machine.py prompt
python3 experiments/day14-codex-machine/test_machine.py
```
