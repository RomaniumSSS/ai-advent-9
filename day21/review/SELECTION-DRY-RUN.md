# Конкретный dry-run смыслового отбора

01.10.2026. Подготовлены локальные тела будущих запросов, **отправлено 0**.
Live sender, новые оценки моделей, API/сеть и бюджетный ledger не создавались.
Весь экспорт облаку не разрешён; прежний бюджет $1 относился только к тестовой выборке.

```text
python3 day21/review/prepare_selection_requests.py
python3 day21/review/test_selection_requests.py
```

`--run-name` задаёт отдельную immutable generation внутри private.
Вход — `selection-packets-v1`; проверены pinned approved manifest SHA, payload
hashes, версии/hash каждого record/text, parser SHA и неизменность accepted store.
Frozen rubric v3 не изменена; отдельный adapter instruction имеет собственный SHA.

Выход: `day21/private/selection-requests-v1/`, каталог 0700, файлы 0600:
`identity.json`, `requests.jsonl`, `manifest.json`. Тела находятся в `body`,
местные owned/context provenance и числовая оценка рядом, в API body не входят.
Manifest хранит объяснение учёта каждого из 3573 eligible ID и SHA payload.
Publication atomic по файлам под flock, manifest последний; changed generation
не перезаписывается. Повтор сохранил все три SHA, занял 1.409 с.

## Owned и контекст

- 24 уже принятых условия не классифицируются повторно; остаются доступными
  как нужный читаемый контекст. Accepted corpus не изменяется.
- 82 пустых сообщения с подтверждённым непрочитанным медиа получают локальное
  предложение review/incomplete_context. Их содержание не загружалось;
  они остаются доступными как контекст. Это отложенная проверка, не принятие.
- Решения API предназначены только 3467 owned ID; каждый принадлежит одному request.
  Context-only ID не входит в schema decisions и member ownership групп.
- Context-only сообщения доступны через context_messages. Родитель без canonical
  текста учитывается в missing_references; readable context не объявляется missing.
- Происхождение будущих групп восстанавливается по их owned ID из local
  owned_provenance/version/text SHA и исходного canonical record. Контекстные ссылки
  имеют отдельное происхождение; их наличие не даёт права принять весь контекст.

Модель получает только ID, неизменённый text, reply_to, source_role и media metadata.
Имена/даты/пути из metadata исключены. **Исходный text может содержать персональные
данные, имена и ссылки: это не анонимизация.** Текст не редактировался/не усекался.
Raw переписка и request bodies не выводились в контекст или stdout.

## Зафиксированная форма будущего запроса

DeepSeek `deepseek/deepseek-v4.1-flash`, only[`deepinfra/fp8`], fallback false,
require_parameters true, data_collection deny; reasoning enabled=false,
temperature0, stream=false, strict JSON Schema. Provider max_price:
input $0.20/M, output $0.60/M. Это настройки подготовленного объекта, не API-запуск.

Рубрика v3 плюс adapter задают решения только owned ID, read-only context и
proposals only. Форматные ограничения: причины до 80 Unicode символов,
notes до 160; массивы ограничены числом owned/context/missing ID. Output cap
рассчитан из компактной максимальной формы JSON, включая обе группы и худшие
surrogate escapes, с запасом 256 токенов и floor2048. Это консервативный запас
для <=16 owned, а не ожидаемая длина ответа. Нельзя гарантировать произвольное
whitespace/поведение модели; length в будущем должен считаться ошибкой без hidden retry.
Допустимость больших caps у конкретного endpoint нужно подтвердить перед live.

## Реальные агрегаты подготовки

| Показатель | Значение |
| --- | ---: |
| Исходные пакеты | 1784 |
| Будущие calls | 1718 |
| API-owned ID | 3467 |
| Accepted preserved / local unread review | 24 / 82 |
| Unique context ID / context occurrences | 71 / 122 |
| Full serialized UTF-8 request bytes, сумма | 22654627 |
| Full request bytes, максимум | 26627 |
| System prompt + schema bytes, сумма | 19973419 |
| Прочий overhead вместе с prompt/schema и JSON escaping | 21883345 |
| Conservative input token bound | 36728483 |
| Output caps, сумма | 14907589 |
| Output cap min / max | 5395 / 56860 |
| Отправленные requests / measured model usage | 0 / нет |

Input bound = serialized full request UTF-8 bytes + 8192 на каждый call.
Это консервативная byte-based оценка с запасом, не замер tokenizer/provider usage.
Максимум 26627 байтов уже включает owned, материализованный context, rubric,
adapter, schema, JSON framing/escaping и provider параметры.
Малые исходные пакеты не объединялись новым batching.

## Оценка бюджета для решения

По enforced max_price и указанным консервативным input/output bounds:
**upper $16.29025**. По сохранённому snapshot DeepInfra fp8
(input $0.00000014/token, output $0.00000042/token):
**estimate $11.403175** при тех же bounds/caps.

Это **estimate, not actual**, не ожидаемый средний счёт и не бюджетное разрешение.
Cache discount не предполагался; свежий pricing/endpoint metadata не запрашивался.
Новый расход отсутствует. 1718 calls и повторяемый prompt/schema дают существенный
bound; дальнейшее решение о batching/caps/методе отбора принадлежит родителю и
пользователю. Preparer самостоятельно не оптимизировал состав пакетов.

## Проверки и точка остановки

Stdlib synthetic test и py_compile прошли: schema строго only-owned; readonly
context нельзя превратить в decision/group member; readable/missing context
различается; accepted/media-only skip без потери учёта; Unicode text неизменён;
metadata минимизированы; bound/cap/price проверены; repeat/changed-generation и
0700/0600; pinned source/hash corruption отвергается. Адаптированный
validate_selection_output принимает schema decisions object и отдельно учитывает
context-only ID, сохраняя owned coverage и запрещая ложный missing.

Request manifest SHA:
`0fa239399d85bf99d7b8dad0bea589e058bb9792445d83cd44e7baea0c9503fb`.
Adapter SHA:
`f243350555387bead4c7ac43354a1530cba1c18075f0cbb4b178701b83a827de`.
Исходные пакеты, rubric v3, accepted corpus и holdout artifacts не изменены.
Остановка перед parent review; live sender отсутствует.

## Локальная коррекция v2: операционный output cap

Текущий default — `selection-requests-v2`, preparer version 2. Команда:

```sh
python3 day21/review/test_selection_requests.py
python3 day21/review/prepare_selection_requests.py
```

v1 сохранена побайтно. Её прежний output upper строился по искусственному максимуму JSON с одновременно заполненными группами и Unicode escapes; это не подходящая рабочая политика бюджета. v2 использует `max(1024, 512 + 256 * N)` для 1–16 owned ID, максимум 4608. Это жёсткий операционный лимит расходов, **не гарантия достаточного ответа**. Будущий sender при `finish_reason=length` обязан сохранить incomplete, остановить для ручной проверки и не повторять запрос скрыто. Sender сейчас отсутствует; API не вызывались.

Рубрика/adapter, тексты, ownership, context, schema и routing сохранены. Сравнение всех request bodies v1/v2 подтвердило единственное изменение `max_tokens`; производные byte/hash поля пересчитаны. Все dispositions/provenance совпадают.

| Метрика v2 | Результат |
|---|---:|
| Исходные пакеты / requests | 1784 / 1718 |
| Owned / unique context / context occurrences | 3467 / 71 / 122 |
| Accepted preserved / unread-media review | 24 / 82 |
| Full UTF8 bytes total / max | 22654258 / 26626 |
| Prompt+schema bytes | 19973419 |
| Conservative input token upper | 36728114 |
| Output caps total / max | 2040576 / 4608 |
| Enforced `.20/.60` perM upper | $8.5699684 |
| Saved snapshot `.14/.42` perM estimate | $5.99897788 |
| Отправлено запросов | 0 |

Обе суммы — локальные estimates, не actual cost и не разрешение бюджета. Кэш не предполагается. v2 manifest SHA256: `9d70a53c5847793a0a4eb5ed8773c7d337dd03ac1c5f2a6300892e01d98b3b7b`. Артефакты: `day21/private/selection-requests-v2/{identity.json,requests.jsonl,manifest.json}`, права 0700/0600. Повтор дал тот же manifest SHA. Синтетические проверки: cap монотонный и ≤4608, budget использует точный runtime cap, прежние coverage/privacy/source integrity проверки PASS. Дополнительная локальная сверка: v1 три файла неизменны, данные bodies кроме max_tokens идентичны.

### Уже измеренный небольшой holdout

В сохранённом DeepSeek run20 кейсов/51 ID reported completion tokens: min123, max428, median160.5, sum3986. Максимальный кейс имел9 owned ID. Это эмпирика другой небольшой выборки, **не доказательство достаточности cap для полного16-ID пакета**, длинных текстов или сложных связей. Новые model calls не выполнялись.

### Возможная будущая упаковка независимых кейсов — только арифметика

Если ограничения полного payload позволят размещать до16 owned ID на вызов с сохранением независимых границ, 3467 ID арифметически требуют минимум217 вызовов вместо1718 (на1501 меньше). Это не подготовленные пакеты и не обещание реализуемости. Для иллюстрации, сохранив все остальные bytes/schema/context неизменными, удалив только1501 повтор system prompt (9619bytes) и safety overhead8192 и пересчитав caps гипотетических16-ID вызовов, upper уменьшился бы на$5.9720142 до$2.5979542. Реальный новый schema/context/payload и разрывы могут изменить оценку; savings не измерены. Batching не реализован. Следующий scope выбирает root после review; отправка полного корпуса требует отдельного согласования.
