# Повторная офлайн-валидация перед live-eval

Исходный `day13/` скопирован в `runs/validation-work/`. Из scratch-копии прошли:

```text
uv run python test_task_state.py
uv run python test_web.py
uv run python test_live_eval.py
node --check web/app.js
uv run python -m py_compile ./*.py
```

Все команды завершились с кодом 0. Помимо прежних FSM/API-проверок новый набор
доказал:

- manifest содержит ровно 64 уникальные ситуации: 60 live paths, 4 pause guards
  и 12 restart/resume cases;
- полный test-double campaign завершается 60/60 структурированных ответов и 4/4
  локальных pause blocks;
- provider uncertainty останавливает ledger после одного send и не допускает
  автоматический повтор;
- изменение evidence обнаруживается checkpoint chain;
- лимиты кампании закреплены в policy: 60 calls, ноль retry, максимум $0.02.

Сеть и реальный провайдер на этой фазе не использовались.
