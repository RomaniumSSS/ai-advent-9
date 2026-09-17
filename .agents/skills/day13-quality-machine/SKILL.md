---
name: day13-quality-machine
description: Use when Roman asks to implement, continue, pause, resume, or inspect AI Advent day 13 through the project-local Codex state machine. This controls Codex's work on day13; it is separate from the task-state machine implemented inside the teaching agent.
---

# Машина качества дня 13

Источник состояния работы Codex — `experiments/day13-codex-machine/`, а не
история чата. Машина хранит этап, текущий шаг, ожидаемое действие и паузу.

## Порядок

1. Перед работой прочитай `README.md` машины, затем выполни `status` и `check`.
2. Получай контекст текущего этапа только командой `prompt`.
3. Текст модели — предложение. Этап меняет только `transition` после проверки
   JSON-результата. Не редактируй `state.json` вручную.
4. `pause` и `resume` обязаны сохранить phase, current_step и expected_action.
   Исправленное описание этапа применяй только через `sync-policy`, не ручной
   правкой state.
5. Для реального `machine.py run` сначала покажи `codex-command`; запуск
   отдельного `codex exec` требует явного согласования Романом. Текущий Codex
   может выполнять этап сам, но обязан сохранить структурированный result и
   пройти тот же `transition`.
6. Соблюдай sandbox и разрешённые пути текущего этапа. При нарушении инварианта
   остановись и покажи нарушение.

## Границы

- Продуктовые изменения — только `day13/`; дни 01–12 защищены.
- Контур машины меняется только для исправления самой обвязки, а не ради обхода gate.
- Commit, push, deploy, платный API и внешние мутации требуют отдельного запроса.
- `DONE` требует офлайн-тестов, обязательного массового live-eval, браузерной
  проверки, видео и отдельного review. Live gate нельзя подменять mock-тестом.
