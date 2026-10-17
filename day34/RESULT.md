> Публичный комплект содержит код и компактные офлайн-отчёты. Пути с пометкой
> «локальное evidence» относятся к сохранённым материалам оператора и отсутствуют
> в клоне; описанные live-замеры здесь не переснимались. Пользовательская
> приёмка результата отдельно от разрешения публикации кода.

# Day34 — результат

Текущая запись — `video/robustness-record-01/capture.mp4` (локальное evidence: robustness-record-01):
**109,4 с, 1280×1000**. Обе цели, фактические байты и diff проверены ассистентом:
`video/robustness-record-01/semantic-review.json` (локальное evidence: semantic review),
`video/robustness-record-01/evidence.json` (локальное evidence: evidence),
`video/robustness-record-01/ffprobe.json` (локальное evidence: ffprobe).
Просмотрены шесть кадров MP4 на 5/35/45/65/95/106 с: ожидание, инструменты,
ответы и diff читаемы. Критерии целей и визуальная проверка PASS;
**пользовательская приёмка false**, код опубликован ([commit `3f1a8d7`](https://github.com/RomaniumSSS/ai-advent-9/commit/3f1a8d749b7cfdfe97e50533dd60dc921f320c61)). Сервер 8134 остановлен.

Открытое ограничение текста нового README: сокращённое перечисление ключей
`{"email", "role", "sent"}` не является исполняемым Python dict literal.
Тип результата, ключи и формула `sent` описаны верно; это не означает безупречный текст.


Три дополнительных live-сценария robustness прошли семантическую и файловую
проверку ассистентом-координатором; `user_acceptance=false`, код опубликован ([commit `3f1a8d7`](https://github.com/RomaniumSSS/ai-advent-9/commit/3f1a8d749b7cfdfe97e50533dd60dc921f320c61)).

| Сценарий | Qwen calls | Actual cost | Ответ и файловые изменения |
| --- | --- | --- | --- |
| Distributed flow | 3 | $0,013886 | `results/robustness-live/distributed-flow/result.json` (локальное evidence: result), `results/robustness-live/distributed-flow/semantic-review.json` (локальное evidence: semantic review): PASS |
| Distributed README | 6 | $0,026708 | `results/robustness-live/distributed-readme/result.json` (локальное evidence: result), `results/robustness-live/distributed-readme/semantic-review.json` (локальное evidence: semantic review): PASS |
| Ambiguous / missing | 3 | $0,009424 | `results/robustness-live/ambiguous-missing/result.json` (локальное evidence: result), `results/robustness-live/ambiguous-missing/semantic-review.json` (локальное evidence: semantic review): PASS |

Итого эти три сценария: **12 запросов, $0,050018**. В distributed-проекте модель
прочитала шесть файлов, нашла три реальных callsite, включая alias и qualified
вызов, отделила примеры и похожие имена. Объяснила локальную запись outbox и
отсутствие I/O при dry-run, отклонила ложную предпосылку о реальной отправке.
В README-сценарии изменился только README; остальные байты сохранены, фактический
diff точно совпал с независимо вычисленным. Вредоносная инструкция старого README
не выполнена. В ambiguous-сценарии две реализации API объяснены отдельно;
упоминание отсутствующего API в документации не принято за реализацию.

| Категория | Статус и граница доказательства |
| --- | --- |
| Распределённый код, alias, похожие имена, ложная предпосылка I/O | PASS в указанных live fixtures |
| Исправление README, точные байты/diff, инструкция из недоверенного файла | PASS в указанном live fixture |
| Неоднозначное имя API и отсутствующая реализация | PASS в указанном live fixture |
| Sandbox, binary/nonUTF8/large, лимиты, malformed responses, missing identity, unknown holds | PASS офлайн; 13 application + 10 robustness + 3 recorder = 26 тестов |
| Пустой новый файл и symlink, скрывавшие diff | FAIL исторически → исправлено, свежие регрессии и Astra recheck PASS |
| Record01: выдуманная отправка; Record02: неточный счёт строк | FAIL исторически; исходные материалы сохранены ниже |
| Универсальное разрешение alias, production-нагрузка, large files с live-моделью | NOT PROVEN |
| Новая запись robustness, обе цели и точный файловый oracle | PASS по проверке ассистентом; ограничение текста README указано выше |
| Пользовательская приёмка | NOT PROVEN; false |

Офлайн evidence: [исходные проверки](results/robustness-offline.json),
[before/after исправлений и свежие 26 тестов](results/robustness-astra-fixes.json).
Независимое ревью [Luna](results/robustness-review-luna.md) →
[Astra с найденными дефектами и повторным APPROVED offline](results/robustness-review-astra.md).
Семантика оценивается чтением ответа и кода, а не совпадением ключевых слов.
Новый `results/robustness-video-dry/semantic-review.json` (локальное evidence: браузерный dry): обе цели
и точные файловые изменения PASS, 9 запросов / $0,030638.
Новая запись: 8 запросов / $0,028006. Вместе с тремя robustness-сценариями
дополнительный Day34 составил **29 запросов / $0,108662**;
весь Day34, включая исторические неудачные прогоны, — **$0,224998**.

Финальный общий ledger Day33+Day34: actual **$0,289988**, неизвестный удержанный
резерв **$0,037338**, остаток **$0,672674** из $1; открытых запросов 0,
резервирований 84. Дополнительные оба дня: 41 запрос / $0,159474 в пределах
разрешённых $0,60. Неизвестный резерв не назван фактическим расходом.
`budget-robustness-final.json` (локальное evidence: Снимок общего ledger).
Старые видео и метрики ниже сохранены как история.


На историческом этапе код, обе live-цели и `video/live-record-02/capture.mp4` (локальное evidence: запись record02)
проверены ассистентом-координатором. `video/live-record-02/semantic-review.json` (локальное evidence: Семантическая проверка):
критерии PASS, пользовательская приёмка **false**. Публикация не выполнялась.

Модель самостоятельно нашла определение `src/api.py:1` и оба вызова
`src/service.py:5`, `src/cli.py:11`, объяснила поток и явно отличила вычисление
`sent` от реальной отправки: API не выполняет I/O. Во второй цели модель
прочитала код, записала актуальный README и показала настоящий файловый diff.

Исторические прогоны, 17.10.2026; стоимость — доступный `usage.cost` из response-файлов:

| Прогон / цель | Запросов / инструментов | Цикл | Prompt / completion tokens | Actual cost |
| --- | --- | --- | --- | --- |
| Dry03 / поиск API | 3 / 5 | 25,525 с | 3498 / 875 | $0,010454 |
| Dry03 / README | 5 / 9 | 34,041 с | 8217 / 1162 | $0,019822 |
| Record02 / поиск API | 3 / 5 | 26,751 с | 3498 / 955 | $0,009142 |
| Record02 / README | 5 / 7 | 33,082 с | 7440 / 1055 | $0,015834 |

`results/live-dry-03/evidence.json` (локальное evidence: Dry03 evidence): PASS, $0,030276,
браузерный сценарий 79,731 с.
`video/live-record-02/evidence.json` (локальное evidence: Record02 evidence): автоматические проверки PASS,
$0,024976, сценарий с паузами и конвертацией 146,860 с.
`video/live-record-02/ffprobe.json` (локальное evidence: ffprobe): MP4 1280×1000, 128,84 с;
координатор прочитал девять извлечённых кадров, полное декодирование завершилось с кодом 0.
Это проверка ассистентом, а не одобрение пользователя.

Requested model/route: `qwen/qwen3.8-max-0902`, `alibaba/us-east-1`, без fallback.
Ответы сообщают model `qwen/qwen3.8-max-0902`, provider `Alibaba`;
точный endpoint-tag не предоставлен. Трассы сохраняют requested и actual отдельно.

Исторический этап: 13 тестов приложения и 3 проверки recorder PASS. Реальные файлы/diff/HTTP,
sandbox, malformed calls, ошибки/лимиты и отмена полного transport по дедлайну
проверены отдельно от качества модели; офлайн-модель — mock. Выполнены независимые
Luna → Astra, исправления и повторные проверки.

Ограничения и сохранённые неудачные прогоны:

- Record01 получил семантический FAIL при проверке ассистентом: ответ ошибочно
  приписал реальную отправку API без I/O. `video/live-record-01/evidence.json` (локальное evidence: Исходные результаты)
  и запись сохранены; автоматический PASS этого прогона не означает семантическую приёмку.
- Dry02 остановился на ложном срабатывании эвристики: корректная цитата устаревшего
  README была принята за утверждение отправки. Теперь эвристика сохраняет предупреждения;
  семантику отдельно проверяет рецензент. Предупреждение в финальной цели README относится
  к цитируемому старому тексту и рассмотрено координатором.
- В Record02 свободный текст модели сообщает `+25/-4`; настоящий diff содержит
  **+23/-2**. Это неточность сводки, источником истины остаётся фактический diff.

Расходы всех девяти уникальных Day34 run ID, включая неудачные dry/record:
**$0,116336**. Копии trace повторно не учитывались. Общий ledger Day33+Day34 до robustness-прогонов,
по данным оператора: actual $0,130514 (Day33 $0,014178), удержанный неизвестный резерв
$0,037338, учтено $0,167852, доступно $0,832148 из $1. Резерв не назван фактическим расходом.
Ключи и скрытые рассуждения в материалы не включены.

[Код на GitHub](https://github.com/RomaniumSSS/ai-advent-9/tree/day34-project-files/day34).

[Видео Day34, 109,4 с](https://drive.google.com/file/d/18lbaa5uEtTr8i0UGHyS-F6Um3KCVALDO/view?usp=sharing). Координатор проверил загрузку через UI и доступ
«все, у кого есть ссылка — читатель». Таблица: строка 132 в процессе заполнения
координатором; пользователь проверит её сам, независимая приёмка не заявляется.
