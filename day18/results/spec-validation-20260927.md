# Day 18 — итоговая сверка SPEC, 27.09.2026

## Baseline и доказательства

SPEC: `docs/superpowers/specs/2026-09-25-day18-background-agent.md`, SHA-256
`59397636f3196123c5094cd4e96a964c7bbf2ce1f7959c7aef1e08d074e09f3b`.
Runtime-код локально и на VPS: комбинированный SHA-256 вывода `sha256sum
day18/*.py day18/schemas/*.json day18/deploy/*.sh` —
`09bd0b36dc24c566abdbcd9823ac1f81631c75c901aa6ef04854c22b103c3962`.
Код Day 18 ещё не закоммичен. Проверено в рабочем дереве и на установленном
экземпляре `crm-agent`, а не на удалённом GitHub HEAD.

- macOS/Python 3.12: `.venv/bin/python -B -m unittest day18.test_architecture day18.test_offline -q` → **55/55 OK**; `compileall -q day18`, `git diff --check`, пустой `git diff --name-only -- day17` → OK.
- Ubuntu VPS/Python 3.12 под пользователем `day18`: те же 55/55 offline tests → OK. Локальный stdio MCP в тестах настоящий, но модель/RSS/Telegram там подменены.
- Real-provider/RSS на VPS: no-send `808102ec-e989-4f1f-bfae-444ba8aa5a71` → `REPORT_READY`, 2 model calls, 1 MCP, 12/12; real cron-backfill `6e5cdddf-fa3f-4a70-987e-a6bfa8dafb7e` → `DELIVERED`, model attempts `ok/ok`, tool attempt `collect_habr_agent_cases/accepted`, 12/12, 2 ссылки, Bot API `message_id=6`; пользователь подтвердил отображение. Детали: [VPS evidence](vps-live-20260927.md).
- Видео `day18/demo/day18-scheduled-agent.mp4`: 29 с, SHA-256 `1fcd9c12774011190536bc933034aa1f6176a3a1bdfb36bff1c7173ea0fcdb9c`; проверены воспроизведение и кадр. Это запись просмотра сохранённых фактов после cron-запуска.

Как доказательство могло бы обмануть: зелёный mock-тест не подтверждает поведение внешнего API; Bot API receipt сам по себе не означает видимость в чате; одноразовый cron-backfill не доказывает ежедневный trigger точно в 18:00; код на VPS может отличаться от локального (сверен дайджест); видео с фактами после события не является записью экрана в момент запуска. Эти границы учтены ниже.

## Матрица нормативных требований

Нормативные пункты разделов «Цель», «Расписание», «MCP», «SQLite», «Coverage»,
«FSM», «Telegram/security/observability», «Enforcement» и acceptance A01–A15
сгруппированы по проверяемому поведению. Ненормативные объяснения Day 17,
будущие Day 19/20 и исключённые из scope веб-интерфейс/полные статьи не
оцениваются. Условные ветви recovery применимы: реализация их содержит.

| SPEC item | Наблюдаемое требование | Доказательство | Статус | Предел |
| --- | --- | --- | --- | --- |
| A01 | Ежедневный cron в 18:00 Warsaw; DST, missed slot, backfill | cron config, `not_due`, cron-backfill 00:15, zone tests | NOT PROVEN | Первый реальный ежедневный trigger ещё не наступил; нужен timestamp 18:00 |
| A02 | Один run на slot и один sender при overlap | SQLite concurrency tests | PASS | Offline fault/concurrency |
| A03 | Реальная модель сама выбирает MCP, получает result и формирует draft | VPS `ok/accepted/ok`, 2 model calls/1 MCP, report | PASS | Один успешный live путь |
| A04 | Неизвестные/двойные/поздние вызовы блокируются с linked result | targeted local MCP/harness tests | PASS | Негативные пути offline |
| A05 | Счётчики model/tool/wall/size/retry сохраняются после crash и не обходятся | reservation, retry, capacity tests; provider request cap | NOT PROVEN | Нет реального длительного provider timeout/crash и независимой проверки всех provider token limits |
| A06 | Atomic batch и идемпотентный replay без дубликатов | SQLite rollback/reconcile/repeat tests | PASS | Offline fault injection |
| A07 | Empty/no-new/no-match/partial/outage разделены, плохие элементы не дают false empty | RSS parser и batch tests; VPS частичный RSS | PASS | Формально только фиксированный RSS profile |
| A08 | RSS/prompt injection, fake tool, recipient и секреты не меняют policy | schema/adversarial fixtures, adapter boundary, secret-value scan 40 файлов | NOT PROVEN | Нет полного real-model adversarial eval |
| A09 | FSM не переходит без batch/report; report commit и restart dispatch атомарны | transition/rollback/restart tests | PASS | Offline fault injection |
| A10 | Unknown delivery блокирует очередь и retry до доказанного resolution | timeout/unknown/checkpoint/queue tests | PASS | Негативные пути offline |
| A11 | Классификация, evidence, ≤2 ссылки, 15+5, ≤20, bounded draft | capacity fixture, mixed case tests, VPS payload с confirmed+possible | NOT PROVEN | Проверена консервативная byte/token граница и metadata provider; точный tokenizer провайдера и качество всех категорий live не доказаны |
| A12 | Receipt-only `DELIVERED`; retry/unknown guards | adapter fault matrix + реальный `message_id=6`, пользователь видит | PASS | Один реальный успешный send; ошибки offline |
| A13 | Нет изменений/импортов Day 17 | AST test, `git diff --name-only -- day17` пуст | PASS | Текущее рабочее дерево |
| A14 | Реальная Telegram-доставка и расписание показаны в видео | VPS cron, receipt, human chat confirmation, MP4 просмотрен | NOT PROVEN | Видео создано после запуска; ежедневный 18:00 ещё не наблюдался, пользователь видео ещё не просмотрел |
| A15 | Claims/backlog/retry/checkpoint не дублируют статьи | SQLite queue/retirement/restart tests, VPS 2 omitted | PASS | Будущий live backlog cycle ещё не наблюдался |
| N01: source profile | Фиксированный HTTPS Habr RSS, пределы чтения и сохранение coverage | код/config, real MCP batch, tests | NOT PROVEN | Нет независимого сохранённого доказательства `application/rss+xml` со страницы поиска и полного daily feed coverage |
| N02: operational security | Секреты вне repo/model/log/video; фиксированный recipient, no webhook/Telegram MCP | config/adapter inspection, права 0600, scan значений, live send | PASS | Скан известных ключа и токена, не универсальная гарантия отсутствия всех секретов |
| N03: observability/recovery | Durable transitions/usage/checkpoint; различимы ошибки и очереди | SQLite schema/tests, VPS run/receipt/checkpoint/usage | PASS | Алерты как отдельный канал SPEC не требует |

Противоречащих фактов (`FAIL`) не найдено. `NOT PROVEN` означает конкретный
пробел доказательства, а не установленный дефект.

**Вердикт: SPEC PARTIALLY SATISFIED.** Практический минимум задания — cron
запускает агента, тот сам вызывает MCP, сохраняет и присылает сводку —
показан реальным запуском. Строгие A01/A14 требуют наблюдения первого
ежедневного выпуска в 18:00 и пользовательского просмотра видео.
