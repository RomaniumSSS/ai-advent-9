# Day 18 — локальная проверка P0–P7

Дата: 26.09.2026. Рабочая ветка: `RomaniumSSS/day18-background-scheduler`;
базовый HEAD: `e1ad49df8815db94589327c1deb766346db399ce`. Коммита Day 18 нет.

## Контракт и проверенная сборка

- Утверждённый пользователем SHA-256 плана:
  `3e6e5a28e6538a0e3c5389ca9f9695dd59d56489bebc845ff73599c041d2cfa7`.
- SHA-256 SPEC:
  `09ad05e7273d0ef3aa85148cfa4d2ad6238d4fb71061b9c753de1927ed12c85a`.
- SHA-256 исходной сборки P0–P7 до смены модели:
  `a8bcc2dbb4faf385e86ba88dfc7c18d69206e3d19251f24d2d399d848da2b1aa`.
  Это SHA-256 конкатенации отсортированных относительных имён 21 файла `day18/`
  вне `results/`, NUL и SHA-256 содержимого каждого файла; включены `.py`,
  `.json`, `.md`, `.example`.
- Среда: macOS 15.6.1 arm64, Python 3.12.12, локальный SQLite и настоящий
  локальный stdio MCP protocol. Модель и Telegram в тестах подменены fake
  adapters; RSS подан из fixtures. Внешние сервисы не вызывались.

Команды и результат:

```text
uv run python -m unittest day18.test_architecture day18.test_offline -q
Ran 44 tests in 5.602s — OK
uv run python -m compileall -q day18 — OK
git diff --check — OK
git diff --name-only -- day17 — пусто
```

## Аудит нормативных критериев SPEC

`PASS local` относится только к проверенной локальной части. `NOT PROVEN`
означает, что обязательное реальное доказательство отсутствует, а не что
поведение опровергнуто.

| ID | Вердикт | Локальное доказательство и предел |
| --- | --- | --- |
| A01 | NOT PROVEN | `test_concurrent_slot_and_dst`, `test_migration_backup_and_gap_status`, `test_manual_identity_separate` проверяют зону, повтор и gap; VPS cron и его timestamp отсутствуют. |
| A02 | PASS local | `test_scheduled_identity_and_batch_replay`, `test_concurrent_slot_and_dst`, `test_one_run_lease`, `test_agent_process_lock_prevents_second_model_turn`, `test_two_dispatchers_cannot_send_same_report`. |
| A03 | NOT PROVEN | `test_fake_model_through_real_local_mcp` проверяет схему model→MCP→model с fake provider; выбора tool реальной моделью нет. |
| A04 | PASS local | `test_invalid_and_multiple_calls_never_reach_mcp`, `test_second_model_call_cannot_execute_another_tool`, `test_agent_linked_result_and_two_article_cap`: unknown name/extra args/multiple/late calls отклонены и linked results сохранены. |
| A05 | NOT PROVEN | `test_phase_reservation_survives_reopen`, `test_old_ready_queue_does_not_charge_generation_budget`, `test_presend_retry_uses_same_payload_and_cap`, `test_model_sees_only_preflight_selected_candidates`, `test_oversized_provider_request_stops_before_attempt` проверяют ключевые счётчики и входной byte cap; нет реальной паузы >960 секунд, provider tokenizer и live timeout. |
| A06 | PASS local | `test_batch_failure_rolls_back_articles_observations_and_coverage`, `test_committed_batch_reconciles_pending_tool_after_crash`, `test_repeated_article_in_next_period_is_not_new`. |
| A07 | PASS local | `test_unknown_date_kept_as_partial`, `test_invalid_link_does_not_hide_valid_sibling`, `test_no_matching_and_feed_limit_are_distinct`, `test_rss_outage_malformed_and_oversize_have_distinct_evidence`, `test_forty_guides_do_not_starve_new_case`; охват настоящего RSS пока неизвестен. |
| A08 | NOT PROVEN | Узкая input schema, неподставляемый URL/recipient, очистка XML и secret scan проверены локально; полного adversarial eval с реальной моделью и RSS нет. |
| A09 | PASS local | `test_fsm_requires_evidence`, `test_report_commit_rolls_back_dispositions_claims_and_state`, `test_ready_report_recovered_without_model`, `test_unknown_queues_later_empty_report_then_quarantine`. |
| A10 | PASS local | `test_unknown_blocks_and_does_not_retry`, `test_unknown_verified_receipt_or_negative_proof`, `test_old_ready_queue_does_not_charge_generation_budget`, `test_unknown_queues_later_empty_report_then_quarantine`, `test_crash_after_request_marker_becomes_unknown`; время >960 секунд моделируется старой датой записи. |
| A11 | NOT PROVEN | `test_confirmed_cases_come_before_possible`, `test_third_article_link_in_intro_rejected`, `test_truncated_draft_never_becomes_ready_report`, `test_forty_guides_do_not_starve_new_case`, `test_two_queued_reports_can_send_same_day_each_with_own_cap` проверяют renderer/grounding/backlog. Не проверены tokenizer закреплённого провайдера и качество real-model классификации. |
| A12 | NOT PROVEN | `test_telegram_http_adapter_classifies_receipt_rejection_and_uncertainty`, `test_presend_retry_uses_same_payload_and_cap`, `test_definitive_rejection_requires_explicit_retry_with_global_cap`, `test_unknown_verified_receipt_or_negative_proof` покрывают fake/HTTP adapter; настоящего Bot API `message_id` нет. |
| A13 | PASS | AST проверка `test_day18_isolation` и пустой `git diff --name-only -- day17`. |
| A14 | NOT PROVEN | Реальная Telegram доставка, VPS расписание и видео не выполнялись. |
| A15 | PASS local | `test_retired_old_report_releases_only_to_future_unfrozen_report`, `test_two_queued_reports_can_send_same_day_each_with_own_cap`, `test_presend_retry_uses_same_payload_and_cap`, `test_unknown_blocks_and_does_not_retry`. |

Итог по локальному этапу: P0–P7 реализованы и 44/44 проверки проходят; в
локальной проверке нет выявленного `FAIL`. Итог по полной SPEC: **NOT PROVEN**,
поскольку P8 содержит обязательные реальные проверки и видео. Это не verdict
о готовой сдаче Day 18. `SPEC_REVIEW.md` не найден; исходные независимые reviews
SPEC/плана дали 0 BLOCKER и 2 NOT PROVEN по live gate и этому файлу.

## Следующий gate P8

Отдельно согласовать стоимость и реальные обращения к провайдеру/RSS, проверить
официальный RSS URL и tokenizer/visible budget, затем получить реальный
model→MCP→model trace. После настройки защищённых Telegram credentials нужны
Bot API receipt, установка cron на VPS, timestamp 18:00 `Europe/Warsaw` и видео.
До этих доказательств автоматическая сводка по расписанию остаётся локально
реализованной, но не подтверждённой в эксплуатации. Никаких live вызовов,
установки cron, commit или push в P0–P7 не было.

## Дополнение 26.09: DeepSeek V4.1 Flash

По новому запросу пользователя модель переключена с V4 Flash 0731 на
`deepseek/deepseek-v4.1-flash` при сохранении provider `deepinfra`. Адаптер
явно посылает `reasoning.effort=none` и `require_parameters=true`.
SHA-256 21 файла `day18/` вне `results/` на момент этого дополнения:
`0ca0543b07ff5f91860c4fcdaf3daa877041a777d6635ca596c9c400d2cb7390`.
Метод: для каждого отсортированного пути `day18/...` в общий SHA-256 поданы
UTF-8 путь, NUL и hex SHA-256 содержимого; учитываются `.py`, `.json`, `.md`,
`.example`.

Локально: `.venv/bin/python -B -m unittest day18.test_architecture
day18.test_offline -q` — **45/45 OK** (macOS/Python 3.12), `compileall -q day18`
и `git diff --check` — OK. Новый тест проверяет форму запроса к провайдеру
через mock; реального ответа V4.1, RSS и Telegram всё ещё нет.
Позже добавлен явный `--env-file` в CLI и cron template; повторно 45/45 OK,
локальный `init-db` с пустой `.env` прошёл. Сам файл `.env` не входит в hash и
игнорируется Git.

После [первого G2 run](g2-v41-first-run.md) модель получает JSON Schema,
парсер принимает ссылки статей компаний, а ошибка draft записывается безопасным
кодом. Повторно **47/47** offline tests — OK; сохранённый снимок живого RSS
перепарсен без сети: 81 article и 19 news rejection вместо 49 article и 51
rejection. SHA выше отражает эти исправления. Новый live draft ещё не проверен.

## Дополнение после одного повторного G2 run

[Повторный run](g2-v41-repeat.md) вернул `draft_invalid_json` после успешных
model→MCP→model, без отчёта и отправки. Для следующего разрешённого запуска
только второй вызов провайдера запрашивает `response_format=json_schema` с
`strict=true`; схема провайдера задаёт форму, полный `DRAFT_SCHEMA` и
grounding остаются в локальном валидаторе. Локальный mock проверяет тело
запроса обоих вызовов. `47/47` тестов на macOS/Python 3.12, `git diff --check`
и проверка отсутствия изменений в `day17/` — OK. SHA-256 21 файла `day18/`
вне `results/` после этой правки:
`32217d86186ee99dafec8902f2ee1f3dc1be0f9405005e1af25bb675b06fb7f5`.
Результат строгого режима у реальной модели пока не проверен.

## Дополнение после live G2/G3

[Live trace](live-20260926.md) содержит real-model/MCP, прямой Telegram
test, receipt полного backfill, ручные resume и human check. После него
локально закрыты обнаруженные границы: `possible_case` требует бизнес-контекст
в RSS, manual resume не зависит от Telegram recipient, draft получает короткие
summary/metric fields и безопасный код типа schema failure, partial intro не
может объявлять отсутствие кейсов за все сутки. Проверки на macOS/Python 3.12:
**51/51 OK** с fixture RSS/fake model/Telegram и настоящим локальным MCP;
`git diff --check` — OK. SHA-256 21 файла `day18/` вне `results/` на момент
этого дополнения:
`6a691d05585fef37d7d8613831faef3ec0cb9e569d93f8951415f6f331cc6fd0`.
Проверенный live выпуск классифицировал 6/29 материалов, поэтому вопрос
увеличения охвата остаётся открытым.

После [отдельного положительного теста](positive-case-test-20260926.md)
ежедневный алгоритм не менялся; поправлена только документация. Текущий
SHA-256 тех же 21 файла `day18/` вне `results/`:
`1f48e659c9d1a68d1f8b8f269cb952409b031cd884b39fadc8446ad6402ba8a3`.

## Дополнение 27.09: 20 статей, VPS и видео

По следующему прямому запросу пользователя лимит анализа поднят до 20,
при сохранении двух ссылок на отчёт. Проверка `test_capacity_twenty` покрывает
конструктивный максимальный draft; тесты также проверяют доли 15 новых/5
старых и признаки личного применения. На macOS/Python 3.12:
`.venv/bin/python -B -m unittest day18.test_architecture day18.test_offline -q`
— **55/55 OK**. Те же 55/55 прошли на VPS под пользователем `day18`.
Реальный запуск cron, provider, MCP и Telegram описан отдельно в
[VPS evidence](vps-live-20260927.md). Предыдущие вердикты этой страницы
относятся к более ранним сборкам и не заменяют новую итоговую сверку SPEC.
