# HANDOFF — Day25 после новых2×15

Обновлено04.10.2026. [Исторический Day24](docs/handoffs/day24-history-before-day25-2026-10-04.md).

## Точная точка остановки

Новые [два живых разговора по15](day25/T5-SESSION15-MECHANICAL.md) завершены через обычный UI:30search/20calls/$0.0108725232/unknown-retries0. Независимый gate14PASS/12FAIL/4NP,A1FAIL,A2–A6structuralPASS,humanNP; T5 открыта. [Видео2:58](day25/video/README.md) толькоpublic15IDs/all0/noextraasks, privacy/provenancePASS. Raw/private session15-live-01, старые run01–07 неизменны.

Public8056 остановлен/authorization revoked, all8057 остановлен. Общий user cap.10: public$.0040298888; all cap$.0959701112/charged$.0068426344. Fresh «Мой чат» в **том же** `day25/private/session15-live-01/all` ledger, остаток послеавтоматики **$.0891274768**. Root остановил прежний preview PID81473 и запустил настоящий full web.py на8053 с тем же all data-dir/ledger; GET подтверждает enabled/all и новый «Мой чат». Ledger/cap не сбрасывать: последующие ручные вызовы уменьшают общий остаток.

Executed runtimee1561e73… сохраняется в snapshot; root post-run repair исправил учебный dayrange→calendar и shortfollowups. Независимо50app+21validation/10savedcontext replayPASS, новыеmodelsemanticsNP. Никаких дополнительных платных повторов; liveFAILнеподменятьофлайнPASS.

## Следующий шаг

Проверить Git/worktree/status перед продолжением. Передать код/docs/новое видео с явными ошибками; selective commit выполняется только по отдельному пользовательскому разрешению. Root ведёт ручной сервер на том же ledger. Не включать private raw, ключи и несвязанные Day24 изменения. Для дальнейшей оценки не считать текущий A1 или human acceptance пройденными.

## Решения и границы

- Run01–05 — исторические FAIL, run06/run07 — A1 NOT PROVEN; raw и оценки не менять. [Run06](day25/T5-REGRESSION-06-MECHANICAL.md):$0.014535388; [run07](day25/T5-REGRESSION-07-MECHANICAL.md):$0.0142782304; по24calls, unknown/retries0. Public-видео подготовлено локально, не опубликовано.
- Prompt-only исправления не устранили сравнение стабильно; поэтому ввели типизированный контракт. `insufficient_context` — отдельный неуспешный исход, чтобы не выдумывать вторую сторону. Старые сохранённые результаты читаются без перезаписи; public-only privacy и terminal/read guards проверены офлайн.
- Последний offline repair после run06:45app+15validation PASS. Run07 проверил этот runtime; на той исторической границе новых paid calls было0. All4 всё ещё не нашёл нужное обсуждение; all5 заблокирован attribution_not_cited. Не ослаблять роли/цитаты ради закрытия приёмки и новые live сценарии выполняются только по отдельному решению и бюджету.
- Роли команды ранее согласованы: executor Sol 6.1 low, независимый validator Astra. После каждого завершённого этапа — сверка со SPEC/планом. Никаких commit/push/deploy/публикаций без отдельного запроса.
