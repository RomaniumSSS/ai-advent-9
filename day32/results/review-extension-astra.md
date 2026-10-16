# Day32 — независимое сильное ревью расширения

Reviewer: gpt-6-astra. **APPROVED — готовность к согласованному dry/live прогону.**
Это оценка кода и офлайн-проверок, не подтверждение завершённого видео,
настоящего PR-trigger или качества всех ответов модели.

Самостоятельно прочитаны video/run_demo.py, video/test_run_demo.py,
video/SCENARIO.md, web.py, scenario_support.py, eval_faults.py,
test_scenarios.py, замечания review-extension-luna.md. Финальные изменения
cleanup и branch preflight повторно прочитаны после сообщения исполнителя.
Неизменённый core review.py/cli.py целиком повторно не проверялся: сохраняется
предыдущее независимое APPROVED; новые сценарии дополнительно проверяют его.

## Исправления Luna и самостоятельные выводы

- Ошибка destination устранена: git push получает построенный HTTPS URL из
  проверенного owner/repo, а не изменяемый origin. Preflight требует literal
  base day32-pr-review и head day32-demo-limit10, same-repository PR,
  совпадение local branch/HEAD с actual PR и чистую рабочую папку. Публикуется
  один explicit refspec HEAD:refs/heads/<head>, без force, main, merge/comments.
  Между кейсами изменяется и добавляется только day32/target/git_tool.py.
- Блокировка бюджета сохраняется даже при report=None: watcher передаёт
  точные trace_id/mode, recorder выбирает именно эти rows, создаёт outcome,
  показывает блокировку и прекращает следующие live cases. Итог различает
  stopped_budget, scenario_finished_with_errors и scenario_completed.
- Cleanup исправлен по существу: context/video/browser/playwright очищаются
  независимо с timeout30s; owned children завершаются независимо с bounded
  terminate/wait/kill. Ошибка context.close/video.path не пропускает остальных
  ресурсов. Manifest сохраняет cleanup_errors и failed/interrupted outcome;
  ошибка cleanup не выдаётся за успешное завершение записи.

Новых существенных ошибок в согласованном сценарии не обнаружено. Generic CLI
принимает repo/state как аргументы; конкретный запуск должен использовать
разрешённый репозиторий и один canonical day32/.runtime/live. Сам скрипт ledger
не удаляет и не обнуляет. Это не разрешение менять destination или обходить
общий лимит новой state-папкой.

## Путь данных, расходы и достоверность

Watcher — отдельный процесс с реальным poll(actual PR); control задаёт ожидаемый
SHA и modes, но snapshot получается из GitHub PR, не из локальной fixture.
Каждый case создаёт новый SHA, включая новый run_id marker; каждый режим имеет
отдельный trace, повтор проверяет dedupe. Все live вызовы последовательны и
проходят прежний атомарный reserve/budget ledger. Общий cap CLI — $0.50;
существующие расходы учитываются, неизвестная стоимость удерживает резерв.

Все варианты строятся от baseline base SHA, поэтому исправление и разные
дефекты не смешиваются. Код PR не исполняется; compile тестирует только текст
генератора, offline target import относится к доверенному учебному baseline.
SIMULATED fault cases используют отдельный ledger и provider с явным именем,
легенда сообщает отсутствие Qwen. 100 seed checks не названы100 unittest tests.
Смысловое качество model findings и преимущество RAG не объявлены доказанными.

UI сохраняет GET-only и127.0.0.1; новый narrative выводится через textContent,
как и прочий недоверенный текст. Кадры и exact trace outcomes сопоставимы с
request/response artifacts в canonical state. Разрешённый общий сценарий
нужно ещё реально пройти; наличие кода ffmpeg/ffprobe не доказывает, что
MP4 получен и вручную проверен. Ошибка конвертации прерывает команду; финальная
приёмка должна отдельно проверить MP4/ffprobe/кадры, как указано в SCENARIO.

## Фактическая проверка этого reviewer

- `uv run --no-sync python day32/test_scenarios.py`:39 PASS,18.170с.
  Включает локальный Git, concurrent budget/dedupe,100 seeded invariant checks,
  создание9 SIMULATED fault cases и отсутствие network call в их проверке.
- `uv run --no-sync python day32/video/test_run_demo.py`:6 PASS,0.009с,
  включая final cleanup failure и terminate-timeout/kill tests.
- `git diff --check`: PASS.
- Canonical live SQLite открыт только через mode=ro:1 complete,
  reported actual и accounted sum $0.006884. Это прежний readiness probe;
  reviewer новых платных вызовов не делал.

17 прежних core tests ранее проверены в основном ревью и сообщены родителем
как свежо пройденные; в этой проверке неизменённые17 не перезапускались.
Ни push, ни GitHub mutation, ни paid/live вызовы, ни запись браузера reviewer
не запускал. Usage/cost reviewer не предоставлены и не выдумывались.
