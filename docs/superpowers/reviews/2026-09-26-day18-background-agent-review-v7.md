# Read-only review SPEC Day 18 — v7, 26.09.2026

## Объект и источники

Объект — [нормативная SPEC Day 18](../specs/2026-09-25-day18-background-agent.md), SHA-256 `09ad05e7273d0ef3aa85148cfa4d2ad6238d4fb71061b9c753de1927ed12c85a`, HEAD `e1ad49df8815db94589327c1deb766346db399ce`. Сравнение: текущий выбор пользователя «до двух статей в каждом ежедневном отчёте» → [требования](../../day18-requirements.md), SHA-256 `abaa518e382c475977fc27c3962e702761359c91a62181f469d295f828f3a28c` → SPEC; прежний [review v6](2026-09-25-day18-background-agent-review-v6.md) относится только к старому SHA `a4cbc925…` и не является вердиктом этой версии. Применён `artifact-review`/SPEC rubric и `agents-best-practices`; это отдельный read-only проход после authoring. Код/план/интеграции не проверяются этим review.

`SPEC_REVIEW.md` не найден в текущем checkout и локальном `main`; возможные дополнительные правила недоступны. Day 17 — архитектурный образец, не нормативный контракт. Ни модель, ни RSS, ни VPS/Telegram не запускались.

## Модель отказов

Проверены сценарии: лимит двух ошибочно обрезает RSS ingestion или число сохранённых observations; возможный кейс вытесняет подтверждённый бизнес-кейс; модельный `proposed_text` протаскивает третью ссылку; размерный лимит подменяет article-count guard; omitted исчезают после receipt или retry меняет состав; «за день» незаметно становится глобальной календарной квотой и блокирует очередь после восстановления.

## Findings и traceability

**BLOCKER: 0. SHOULD FIX: 0.** Доказанного противоречия нового ограничения с сохранением данных, классификацией, FSM или доставкой не найдено.

| Источник | Контракт SPEC / failure boundary | Evidence | Итог |
|---|---|---|---|
| До двух статей **в каждом** ежедневном Telegram-отчёте | цель, выбор payload и Telegram: `payload_displayed≤2`; не календарная квота на все sends, не лимит RSS/model candidates | A11 mixed 3+ case fixture, renderer/validator | OK |
| Приоритет реальных бизнес-применений | confirmed business-process/agent/deployment criteria уже в классификации; renderer сначала confirmed, possible только на свободных местах и с пометкой | A11 category ordering/label fixture | OK |
| Сохранность остальных публикаций | полный batch, `model_seen≤10`, immutable membership и `payload_omitted`; после receipt не показанные возвращаются backlog | A11/A15 restart/backlog/claims test | OK |
| Нельзя обойти лимит текстом модели или retry | third article reference из `proposed_text` отклоняется; persisted payload/hash при retry неизменен | A11 third-link, A15 retry fixture | OK |
| Existing agent→MCP, unknown delivery, recipient | исходные guards не ослаблены, A01–A10,A12–A14 сохранены | прежняя matrix плюс новые A11/A15 checks | OK; live N1 |

Уточнение затронуло только публикацию одного отчёта и не добавило новый RSS source, tool, модельную команду или delivery transport. Непокрытых upstream требований и material orphan requirement не выявлено. Отсутствие `SPEC_REVIEW.md` не трактуется как выполненная проверка.

**NOT PROVEN N1 (не gate для текста SPEC):** реальный RSS profile/coverage, model choice/tokenizer, VPS cron и Telegram receipt остаются будущими integration gates, не mock evidence. **NOT PROVEN N2 (не gate по доступным источникам):** дополнительные правила отсутствующего `SPEC_REVIEW.md` неизвестны; при его появлении нужна отдельная сверка.

## Verdict

**0 BLOCKER, 0 SHOULD FIX, 2 неблокирующих NOT PROVEN. SPEC готова как нормативный вход для обновления implementation plan.** Это не approval реализации и не доказательство, что будущий код уже ограничивает отчёт двумя статьями. Reviewer не редактировал SPEC.
