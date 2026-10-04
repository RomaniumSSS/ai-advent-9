# HANDOFF — Day25 после финального run07

Обновлено 04.10.2026. Старый Day24-контекст сохранён в [истории](docs/handoffs/day24-history-before-day25-2026-10-04.md).

## Точная точка остановки

[Day25 код/docs/video](day25/README.md) подготовлены; T1–T4 PASS, T5 **открыта**: run07 A1 NOT PROVEN, A2–A6 PASS. [Результат](day25/RESULT.md):24calls/$0.0142782304/unknown-retries0; независимый Astra22PASS/0FAIL/2NOT PROVEN (all4 retrieval miss, all5 attribution_not_cited). Human acceptance NOT PROVEN. Private raw/матрица — day25/private/live-run-07; старые run01–06 не изменены.

Новое [public-видео1:39](day25/video/README.md) записано во время12 настоящих ask:2segments вокруг реального restart,0allIDs/extraasks; MP4 privacy/provenance gate PASS. Дополнительный playback GET-only/ledger unchanged. Сервера8053/8054 после run остановлены; Day24 не затронут. User запросил selective repository commit авторизованных артефактов; это не означает разрешение на включение private или несвязанных изменений. Push/publication не разрешены автоматически.

## Следующий шаг

1. Проверить Git/worktree/status и короткий текущий todo перед продолжением; checkout `/Users/ramanpazharytski/orca/workspaces/ai-advent-9/study`, ветка `RomaniumSSS/study`, много прежних user changes. Не включать несвязанные Day24/private raw в selective commit.
2. Selective commit авторизованных Day25 артефактов и current-status docs запрошен. Передать пользователю код/видео с явными ограничениями; не отмечать T5 PASS или human acceptance по агентской матрице.
3. После передачи пользователю — остановиться. Если потребуется ещё paid run, согласовать новый лимит и сделать новые dirs/ledgers/hashes/preflight; run07 caps не переиспользовать. Сценарии являются regression, не новым holdout.

## Решения и границы

- Run01–05 — исторические FAIL, run06/run07 — A1 NOT PROVEN; raw и оценки не менять. [Run06](day25/T5-REGRESSION-06-MECHANICAL.md):$0.014535388; [run07](day25/T5-REGRESSION-07-MECHANICAL.md):$0.0142782304; по24calls, unknown/retries0. Public-видео подготовлено локально, не опубликовано.
- Prompt-only исправления не устранили сравнение стабильно; поэтому ввели типизированный контракт. `insufficient_context` — отдельный неуспешный исход, чтобы не выдумывать вторую сторону. Старые сохранённые результаты читаются без перезаписи; public-only privacy и terminal/read guards проверены офлайн.
- Последний offline repair после run06:45app+15validation PASS. Run07 уже проверил этот runtime, новые paid calls после него0. All4 всё ещё не нашёл нужное обсуждение; all5 заблокирован attribution_not_cited. Не ослаблять роли/цитаты ради закрытия приёмки и не запускать восьмой run без отдельного решения.
- Роли команды ранее согласованы: executor Sol 6.1 low, независимый validator Astra. После каждого завершённого этапа — сверка со SPEC/планом. Никаких commit/push/deploy/публикаций без отдельного запроса.
