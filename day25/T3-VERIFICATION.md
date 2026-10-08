# T3 — доказательства исполнителя

Дата: 04.10.2026. Область: SPEC R4/R7/R8, PLAN P3. Независимый gate ещё не выполнен.

Файлы: `app/service.py`, новый `app/test_states.py`, обновлённая `app/README.md`. T1/T2 API/контекст и Day24 runtime не изменены.

Локальный macOS/Python 3.14: `cd day25/app && python3 -W error::ResourceWarning -m unittest -v test_chats test_context test_states` — 24 теста PASS, 0.825с. `git diff --check` — PASS. Включены 12 регрессий T1/T2, в том числе хеши Day24.

Проверки T3 используют настоящие Service, save/fsync и lock, временный локальный каталог, synthetic retrieve и fake generator из фикстуры T2. requests.Session.request запрещён. Ни SSH, ни платный провайдер не вызываются; ключ и usage/cost фиктивные, каталоги тестов удаляются.

- Успешный ход сохраняет distinct searching/selecting/generating/validating/terminal и transition events; на сохранённом validating ещё нет успешного answer. Терминальный verified возможен только после valid check_answer по подтверждённому снимку transmitted_chunks, совпадению attempted/transmitted IDs и результату проверки. Семантическая правильность не заявляется.
- Ledger entry/result link содержат request ID, chat_id, task_state_version, payload_sha256. Повтор ID и чтение после restart не выполняют поиск или генерацию.
- Недопустимый переход, прямой generate из terminal, поддельный verified с невалидным raw_answer не проходят и не вызывают провайдера.
- Невалидный JSON, неточная цитата, неизвестный chunk/source, кандидат вне переданного selected, скрытый текст вне transmitted message_parts и усечённый provider response не получают verified.
- Empty search создаёт локальный no_context, cost0, sources/quotes=[]; явный model_refusal остаётся отдельным исходом без источников. Ошибка search заканчивается error без ledger/генерации.
- Имитация PowerLoss (BaseException) на searching, selecting, generating до резерва и на сохранённом validating: restart завершает запрос interrupted; подтверждённый ответ не выдаётся как успешный, ID не повторяется. На saved validating ledger содержит известный completed расход; исход местного результата interrupted.
- PowerLoss после входа в fake provider оставляет pending/inflight; restart преобразует ledger в unknown и запрос в terminal unknown, убирает answer. Повтор того же ID не вызывает модель, новый ID блокируется explicit_recovery_required до pricing.
- Timeout имеет тот же запрет повторов. Неизвестный cost при известном валидном ответе сохраняет verified по цитатам, но резерв/cost_unknown блокируют новые платные вызовы: неизвестный расход не считается нулём.
- Ошибки initial save, reserve ledger save и pending result save не вызывают provider; сохранённый неопределённый резерв блокирует будущие вызовы. Ошибка terminal result save возвращает saved=false/unverified без успешного answer, повтор в том же процессе использует ephemeral, после restart остаётся interrupted. Ошибка итогового ledger save возвращает unknown без успешного answer; inflight блокирует новые вызовы.

Границы: восстановление консервативно завершает прерванный запрос и не продолжает его автоматически. Для новой попытки до платной границы нужен новый ID; после неизвестного расхода — отдельный разбор ledger. Протокол не является распределённой транзакцией с провайдером: неизвестные расходы сохраняют резерв. Настоящий провайдер, UI (T4), длительные сценарии/смысловая оценка (T5) здесь не проверялись.
