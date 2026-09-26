# Day 18 G2 — первый реальный DeepSeek V4.1 Flash turn

Дата: 26.09.2026. Диагностический `manual no-send` для последнего завершённого
слота 25.09.2026. Run ID: `199d7a07-5f3a-4aae-83ab-e9a047fed89d`.
Локальная БД: `/private/tmp/day18-g2-v41-20260926.sqlite3` (`0600`).
Ключ и Telegram token не записаны в этот файл или БД. Пользователь явно выбрал
ключ **без внешнего лимита** после проверки `GET /api/v1/key` (`limit=null`);
scope оставался один run, максимум два model calls, без resume/Telegram.

## Сохранённый trace

| Фаза | Итог | Evidence |
| --- | --- | --- |
| Model call 1, `tool_choice=auto` | OK, модель предложила `collect_habr_agent_cases` | 716 input, 259 output, reasoning 0, `usage.cost=$0.00020902` |
| MCP | accepted, 1 execution, batch committed | feed_seen 100; in_period 15; eligible 15; omitted 5; invalid_entries 51; coverage `partial`, feed_limit_hit |
| Model call 2 | API OK, ответ не прошёл локальную draft validation | 3740 input, 1548 output, reasoning 0, `usage.cost=$0.00117376` |
| Report / delivery | `FAILED_AFTER_DATA`, `invalid_draft_or_report`; 0 reports, 0 Telegram sends | `STARTED → MCP_PENDING → DATA_READY → REPORT_PENDING → FAILED_AFTER_DATA` |

Сумма по provider `usage.cost`: **$0.00138278**. Фактический tool choice и
отсутствие hidden reasoning подтверждены этим run; итоговая сводка и качество
классификации **не доказаны**. Сырой draft намеренно не сохранялся, поэтому
точную причину отказа валидатора после первого run восстановить нельзя.

## Разбор без повторного платного вызова

- В prompt второго вызова модель получала требование «JSON по контракту», но
  саму JSON Schema не получала. Это вероятная причина отказа, не доказанный
  разбор конкретного ответа. В код добавлены схема и правила для каждой записи,
  а также сохранение только безопасного кода ошибки в будущем; сырой текст
  ответа по-прежнему не пишется в БД.
- Read-only проверка того же фиксированного RSS URL показала HTTP 200 и
  `Content-Type: text/xml`. Дополнительный снимок 100 ссылок: 49
  `/ru/articles/...`, 32 `/ru/companies/.../articles/...`, 19 news. Старый
  парсер отверг 32 статьи компаний вместе с 19 news. Он исправлен так, чтобы
  обе формы article URL давали один canonical article ID. На сохранённом
  снимке новый парсер принимает 81 статью и отвергает 19 news; coverage
  остаётся `partial` из-за `feed_limit_hit`.
- После исправлений локально: **47/47** тестов на macOS/Python 3.12,
  `git diff --check` — OK. Новый реальный model turn пока не выполнялся.

Следующий платный turn будет **отдельным** запуском после решения пользователя:
этот run уже израсходовал оба предусмотренных model calls, автоматического
`resume` не было.
