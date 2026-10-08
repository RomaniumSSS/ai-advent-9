# Локальная подготовка транспортных пакетов Day21

01.10.2026. Это механическая упаковка для будущих предложений отбора.
Смысловой отбор, extract, нарезка для эмбеддингов и применение к корпусу не выполнены.
API, модели, сеть и VPS не использовались; реальные тексты не выводились в контекст.

## Команда и артефакты

```text
python3 day21/review/prepare_selection_packets.py
python3 day21/review/test_selection_packets.py
```

Параметры: `--source-dir` — свежий экспорт из пяти частей; `--run-name` — имя
каталога внутри private; `--max-messages` (16) и `--max-bytes` (24000).
Источник разбирается существующим Sol `../day21-sol-high/day21/corpus.py`;
Luna importer не используется. Условия определяются только проверенными ID
`ASSIGNMENT_BY_ID`, без поиска ключевых слов. Период: 31.08–01.10.2026 включительно.

Результат: `day21/private/selection-packets-v1/` (0700), файлы 0600:

- `identity.json`: source/parser/preparer/metadata-preparer hashes, revision,
  параметры, версии записей и readonly accepted guard.
- `messages.jsonl`: полные canonical records eligible ID, разово, без усечения;
  source/line, text/record/version hashes, ссылки, reply, media metadata.
- `packets.jsonl`: уникальные owned IDs и отдельные повторяемые context references.
- `manifest.json`: полный учёт каждого входного ID, owner/status, агрегаты,
  SHA двух payload-файлов. Публикуется последним после проверки комплекта.

## Правила

Service и внепериодные ID имеют явные статусы без ownership. Все in-period
обычные ID получают один owner, включая пустой text при непрочитанном медиа.
Подготовка не меняет прежние accepted/include/exclude решения. Новая версия
принятого текста помечалась бы changed_proposal_only; автоматически не заменяется.

Reply образует структурные ветви: каждое проверенное условие отдельно;
его разные прямые вопросы не склеиваются в один документ. Эти ветви не объявлены
смысловыми документами. Порядок — дата/ID. Нетекстовый, вне eligible и физически
отсутствующий родитель различаются; циклы отмечаются явно.

Большая ветка делится только для транспорта: part index/count, previous/next
packet IDs и forced_transport_break сохраняют разрыв. Внешний parent/branch-root/
assignment-context остаётся reference с версией и происхождением. Owned IDs
не повторяются, context IDs могут повторяться. Огромное одиночное сообщение
полностью сохраняется со статусом needs_segmentation и не считается готовым
к отправке. Проверка этого случая выполнена синтетически.

Лимит байтов относится к сериализованным canonical owned records; контекстные
ссылки и будущие rubric/schema/request overhead в него не входят. Материализатор
будущего запроса должен отдельно проверять полный размер. Пакеты сейчас хранят
ссылки, не копии контекстных текстов; они не отправлялись классификатору.

Медиа: только классы HTML через Node existing parser; содержимое не загружается.
`media_status=unread`, `content_read=false`; пустое медиа имеет metadata_only payload.
Unknown отличается от подтверждённого отсутствия. Смешанное сообщение не обрезается:
предусмотрено mixed_content_proposal с hash исходного текста, Unicode codepoint
half-open offsets и proposed_ranges. Сейчас ranges пусты, not_evaluated,
requires_review=true, applied=false; будущие точные диапазоны требуют review.

## Реальная локальная проверка

| Учёт | Количество |
| --- | ---: |
| Входные numeric ID всех пяти частей | 4321 |
| Service / outside period | 203 / 545 |
| Eligible / уникальный ownership | 3573 / 3573 |
| Обычные ID всего снимка | 4118 |
| Проверенные условия | 24 |
| Структурные ветви / транспортные пакеты | 1778 / 1784 |
| Ветви с forced transport break | 6 |
| Огромные одиночные сообщения в реальном input | 0 |
| Eligible metadata-only, без текста | 82 |
| Photo / video / voice / file | 156 / 29 / 1 / 4 |
| Reply к unread media / outside eligible | 119 / 7 |
| Физически missing parents / циклы | 0 / 0 |
| Автоматические смысловые решения | 0 |

82 нетекстовых media-ID сохранены, поэтому eligible охват шире прежних 3491
текстовых кандидатов/условий. Это учёт данных, не увеличение принятого корпуса.
1127 пакетов содержат один ID; максимальный owned payload — 23612 UTF-8 байтов,
максимум 16 сообщений. Малые независимые ветви не уплотняются в общий пакет.
Параметры не оптимизированы для стоимости будущего классификатора.

24 версии условий совпадают с accepted store; 3549 eligible сообщений не приняты
в нём. Accepted SQLite и selection manifest Sol прочитаны только readonly,
их SHA до/после обоих запусков неизменны. Полный text и links равны исходным
record Sol; содержимое внешних URL и вложений не читалось.

Manifest SHA:
`0159dd0bf7285564682f2d19773eb59cad42c5295522538af6c62fc28451104f`.
Input SHA:
`add6d6a95901eff0d3467129ad53df356d2c9ac838a094234b50022493fe9ee9`.
Реальный повтор занял 1.776 с; SHA всех четырёх файлов совпали побайтно.
Changed input/configuration для занятого run-name отвергается, старые артефакты
сохраняются. Для новой версии нужны новое имя/явный следующий шаг.

## Целевые проверки и ограничения

Stdlib test прошёл: no-reply, orphan/outside parent, cycle, независимые вопросы
под условием, длинная ветка, огромное Unicode-сообщение без усечения, links,
metadata-only, детерминированный повтор, отказ changed input, восстановление
прерывания между payload-файлами и manifest, 0700/0600. py_compile прошёл.

Публикация атомарная по файлам под flock; незавершённый комплект не имеет manifest.
Повтор с той же identity восполняет недостающие файлы; отличающийся готовый файл
не перезаписывается. Исходники экспорта и accepted corpus не меняются.

Пакеты не доказывают полезность сообщений, качество смысловых границ или минимум
30 страниц. Личная заметка уже хранится отдельно в принятом store; текущий input
содержит только Telegram-export. Следующее — review preparer и отдельное решение
о способе смыслового отбора; облачная передача всего экспорта требует отдельного согласования.

Независимая проверка родителем: PASS для всех 3573 canonical records/text/links/
provenance/version/hash, coverage4321, unique ownership, reply references, packet IDs,
owned size/count, accepted hashes и прав 0700/0600. Лимит max-bytes не включает
материализованный context и prompt: будущий sender обязан считать полный payload.
