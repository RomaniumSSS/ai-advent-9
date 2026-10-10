# Независимое Astra review: exact-day source и recorder IDs

**Финальный verdict: APPROVED.** Фактический reviewer — gpt-6-astra. Обязательное сильное ревью после Luna выполнено самостоятельно; обнаруженный A1 исправлен и закрыт. Это одобрение ограниченного изменения кода и подготовки диагностического запуска. Human SPEC approval/acceptance не заявляется.

## Финальный снимок

| Файл | SHA-256 |
|---|---|
| full_chat_core.py | `f1b62d97909f391462a0a6396ebb23e91e352d6a83cb5378514abc62314c9e12` |
| video/run_full_demo.py | `73df411fd637b3efbf3e4211f6102be5ad729fbee8351216dd9c8c3c513841b6` |
| tests/test_full_chat_day_anchor.py | `f81ff10631790238e45ad37da2ad2650229030d0b32e6081d9aeeb209d0e6d20` |
| tests/full-chat-day-anchor-evidence.json | `97c80c25d735b84b24d9b50e0cdbe70f726a6800edbe59adc29404f43c624e93` |
| QUALITY_EVAL_SPEC.md | `7f28fd6e2807544dfd9dc94d44cae0fc74962c08efa5e98c8185ad7c988495d6` |
| review-day-parser-luna.md | `c7614654e934d9fc87f8bc3b7539c17619a5011c6e0135160f6b0281fad28b5d` |

Исходные snapshots: full core `98e6725d1e9246d1f1335d81726db4b43dfb3e5b3ddfe2e17981c9ed8bcaccc6`; recorder `c25e57930cbee56068da8e949fb24a5028bd7d2c4d8b86c6572250d0987e6eee`. Public core остаётся `ffd03a0c5bc659e50783416c469c72d8f79f7d02a7d9a1309208c74875b2e24d`, quality runner — `329a11f5442cd02ac2a87f3bdaeb438c89e2c10e4f011af381895f4d191cb89c`.

## A1 — WARNING, CLOSED

В промежуточном core `5a6acf57194d13e621f69e1bf022f1c18b34b91456fdd63178e5a3257e1ab20c`, `full_chat_core.py:86/119`, reservation доверял старому parser без границ слова/полного числа. Независимое воспроизведение на выдуманном corpus: «Как устроен каталог в Day130?» и «Сегодня 13 записей о каталоге.» оба давали explicit_days=[13] и mandatory a13. Новый guard делал прежнее permissive совпадение причиной внедрения постороннего источника.

Финальное исправление `full_chat_core.py:86–90` извлекает полные tokens и числовые последовательности локально, затем фильтрует диапазон1..31; public core не менялся. Повторены исходные воспроизведения и 7 targeted tests: отрицательные Day130/Day13suffix/midDay13/Сегодня13/Day130/140; положительные Day13/дне13/дня13 и списки через и, запятую, slash. В смешанном списке out-of-range число не превращается в префикс; допустимый сосед сохраняется. A1 устранён без списка тем или gold-дней.

## Независимая проверка контракта

| Требование | Verdict / evidence |
|---|---|
| Границы изменений | PASS: AST final core равен исходному после удаления только retrieve_all; recorder — только validate_full. |
| Scoring и scope | PASS: каждый из724 chunks получает прежние cosine/lexical/boost; threshold/topK прежние. Reservation следует после scoring; полный корпус не фильтруется по дню/source. |
| Exact-day и negatives | PASS: полный day token, существующий assignment exact day; неизвестный день не выдумывается; pure explicit discussion не получает forced anchor. |
| Mixed-source diversity | PASS: сохраняются near-requested discussion/note; возможный assignment anchor защищён от замены, без изменения model/options/system. |
| Budget | PASS: anchor имеет приоритет порядка; build_context удаляет целые chunks с конца после истории. Общий бюджет сохраняется; слишком большой anchor не обещается вместить любой ценой. |
| Initial3 регрессия | PASS: reviewer сам загрузил immutable DB724 и сохранённые embedding responses H05/H12/H20; final/old selected до budget, original selected после budget, query/messages/payload совпали точно. |
| Full recorder ID | PASS: assignment:NN и именно нужный день; проверки chunk/document/text/request связи, identity и privacy не ослаблены. Legacy benchmark assignmentNN неизменён. |
| Реальная metadata shape | PASS: настоящий assignment:16 metadata из immutable DB помещён в synthetic envelope; canonical принят, legacy/wrong-day/private IDs отвергнуты. Это не live recording. |
| Offline | PASS: независимо42full +34quality +16recorder на первом snapshot; после единственного parser изменения —7targeted, финальный AST и all724 saved-vector replay. Sol final44full/34quality/16recorder сверены по evidence/log hashes; их полный финальный rerun не приписан reviewer. |
| Derived source matrix | PASS: cases-v4 differs от исходного v1 только baseline_hashes/full_chat_core.py, установлен точно final SHA. Весь остальной JSON, включая cases/gold/evidence/profile, равен. |
| H06 live на final code | NOT PROVEN: известный diagnostic retest и независимая source оценка ещё впереди. |
| Новый qualified dry/MP4 | NOT PROVEN: root-owned fresh runtime/запись/проверки ещё впереди. |

Среда: Python3.14.0/macOSarm64. В широком offline прогоне Ollama.request запрещён; socket разрешал только ephemeral synthetic localhost, отвергал8069/8070/11434. Получилось16 synthetic HTTP connections, active-app/Ollama0. В final targeted/replay запрещена вся сеть.

Сохранённые RED проверены содержательно: три anchor failures показывают пропуск источника; четвёртый старый no-day expected-rank assertion был ошибкой теста и не считается дефектом реализации. Canonical recorder RED воспроизводит отказ на действительном ID. Parser RED содержит предметные false-anchor failures; final log hashes совпадают evidence.

Initial3 неизменные payload SHA: H05 `e7f40799fc5cb346a2358f7e2480ca86a1f3f3729da9a7cea8d781887da6ce77`; H12 `ae49426de0d0452f83fd729e34dbc2021d2d0816e77ecb33b939b28a7abd9da4`; H20 `e7a62357377df38e168eef96bd2673d6c3f4f41c98016fe6b5e9f3fc6e98aaeb`. DB SHA `9894d937c4bcbae653459a6fe758f231992571e436622a0cd33fcda7f707f11b`.

## Разрешённый следующий шаг и предел заключения

Root может вывести новый source-audit sidecar с parent provenance для metadata-only `cases-v4-day-anchor-diagnostic.json`, SHA `df49148c565d228c62ee5fb6bd28de98da53eeea8347d7be2dc32b193e1640bb`, затем подготовить **только известный H06** в новом run. Это производная версия ранее проверенного gold с новым baseline hash, не новый source truth audit и не новая holdout выборка. Исходные inputs/receipts/assessment и неиспользованный draft сохраняются.

Первоначальные blind оценки не переписываются. Diagnostic2 остаётся2/5 covered +1partial, paired0. Качество нового ответа и repair benefit из offline PASS не следуют. Reviewer не выполнял inference/embedding, restart, изменения реализации, commits или публикацию. Открытых blocking/warning findings для данного bounded изменения нет.
