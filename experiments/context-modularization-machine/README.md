# FSM ассистента: модульная сборка контекста

Это внешний контур разработки Codex, а не FSM задачи внутри `day13/`.

```text
PLANNING → EXECUTION → VALIDATION → LIVE_VALIDATION → REVIEW → DONE
```

`LIVE_VALIDATION` в этом контракте означает интеграционный прогон локального
runtime с fake client. Платные API-вызовы не разрешены и не требуются.

Команды выполняются общим контроллером:

```bash
python3 experiments/day13-codex-machine/machine.py \
  --config experiments/context-modularization-machine status
python3 experiments/day13-codex-machine/machine.py \
  --config experiments/context-modularization-machine check
python3 experiments/day13-codex-machine/machine.py \
  --config experiments/context-modularization-machine prompt
```

Этап меняется только командой `transition TARGET --result FILE`.
