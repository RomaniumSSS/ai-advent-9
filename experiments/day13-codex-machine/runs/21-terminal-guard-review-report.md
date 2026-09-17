# Независимый review terminal guard и live-eval

**Overall: APPROVED**

Блокирующих замечаний и warnings нет.

## Проверено

- `Agent.ask()` сначала блокирует paused state, затем обрабатывает `done`
  локальным `Reply(finish_reason="local_state")`; model client не вызывается,
  state и журнал FSM не меняются.
- На planning/execution/validation модель получает один task snapshot и может
  вернуть только строгий объект `{answer}`. `stage`, `step`, `action`, objective
  и решение `continue|terminal` формирует приложение.
- Отрицательный test-double case с model-supplied `decision` получает
  `quality_fail`; это не может изменить envelope.
- Ledger live-05 повторно открыт в `--report-only`: manifest/code/policy hash,
  request/response/state hashes и checkpoint chain валидны.
- В ledger ровно 68 cases: 60 реальных уникальных request hashes, 4 pause guards
  и 4 done guards без send. Все 60 responses получены от OpenInference на
  `deepseek/deepseek-v4-flash-0731`; 12 restart cases имеют provider response.
- State before/after совпадает во всех 60 calls; локальные guards сделали ноль
  model calls. Quality 60/60, safety failures 0.
- Расход live-05 `$0.00044749`, накопительный расход пяти кампаний
  `$0.00258518` при лимите `$0.02`; SDK/provider fallback и retry запрещены.
- В evidence отсутствуют значение credential и путь к env-файлу; сохраняется
  только имя переменной `OPENROUTER_API_KEY` в коде.
- UI-файлы побайтово совпадают с визуально проверенной версией. Три viewport
  существуют; видео VP8 1280×800, 11.64 с, без audio, полностью декодируется.
- Финально зелёные FSM/store/agent, web, 68-case runner и 19/19 тестов внешней
  машины; scope guard не показывает protected или unexpected changes.

## Итог

Прежний prompt-only дефект устранён на правильном уровне: terminal workflow
контролирует приложение. Реальный live-eval подтверждает полный acceptance без
повторов, скрытых model calls или ослабления бюджетного gate.
