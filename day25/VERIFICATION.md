# Day25 — проверки

04.10.2026, macOS, Python3.14/Node24.11.1; Chromium153 через временный Playwright venv/cache.

## Прогоны goal-exec, 06.10.2026

Офлайн-гейт перед оплатой: **72 app + 21 validation PASS**, `node --check day25/app/app.js` без
ошибок, `validate_scenarios` принимает новый файл сценариев. Живьём: два прогона 24/24/24,
$0.0195184696 и $0.0189338296, unknown и retries 0, `no_context` 0. Остаток общего cap
$0.0506751776. Доказательства — в ignored `day25/private/goal-exec-live-01` и `-02`.

Проверено отдельно, до второго платного прогона: токенный критерий покрытия на пяти настоящих
предложениях первого прогона давал Jaccard 0.08–0.21 при пороге 0.75, то есть не менял ничего.
Поэтому guard переведён в непрозрачно-мягкий режим (пометка вместо скрытия), а не докручен
порогом. Реплей сохранённых ходов через новый код выполнен без обращения к провайдеру.

Границы: `verified` не доказывает смысл и не доказывает атрибуцию выбора пользователя;
независимая смысловая матрица на эти два прогона не снималась. Разброс наборов ошибок между
прогонами сопоставим с эффектом правок — на одном прогоне вывод о качестве не строится.

## Исторический запуск2×15

46 app +21 validation офлайн PASS с ResourceWarning aserror; scoped synthetic30 сообщений/restart/isolation/sequential global controller/provider0. Live:30search/20provider calls/$0.0108725232/unknown-retries0. Независимо14PASS/12FAIL/4NP; A1FAIL,A2–A6PASS (A5faults толькоофлайн), humanNP. Видео178.16sec/public15uniqueIDs/all0/extraasks0; privacy/provenancePASS. [Отчёт](T5-SESSION15-MECHANICAL.md).

Executed runtime `e1561e73de7db647bf4ebf1792c5a7b18ac6213a247a68d2b59358d23da268f7`, runner `ea05cfad9a6d8ff30855495bd5e5010c80bfab049cca609bbc4b24eb5b1bfad8`, scenario `d7eb245f0c299d328b4907217563b0658da7560f3dd8f6cc5f13e0270f7722bd`; exact frozen SHA прежний. Локальные post-run исправления root не проверены на провайдере; live FAIL не заменён тестами.

## Историческая проверка run07

| Проверка | Результат | Граница |
| --- | --- | --- |
| App tests |46 PASS|Офлайн fake search/generator; isolation/privacy/restart/ledger/format/citations/typed evidence|
| Validation/prototype tests |15 PASS|Preflight/path guards/budget и типизированный resolver|
| Полный synthetic video run |24 mock calls,2 public segments,12 unique public IDs|0 provider/SSH; настоящий restart; all IDs в записи0|
| Live run07 UI |24 searches/24 provider calls|Fresh isolated caps.06/.06, retries0,unknown0|
| Independent semantic review |22 PASS/0 FAIL/2 NOT PROVEN|A1 NOT PROVEN; all4 retrieval и all5 hidden answer|
| A2–A6 |PASS|A5 fault injection только офлайн; A6 public-only video|
| Human acceptance |NOT PROVEN|Агентская оценка не заменяет пользователя|

Команды из корня:

```bash
python3 -m unittest discover -s day25/app -q
python3 -m unittest discover -s day25/validation -q
node --check day25/app/app.js
```

Последний ограниченный repair:46 app tests4.791s +15 validation; независимые gate с ResourceWarning aserror PASS. Run07 preflight использовал45+15 (его исторический runtime/video не переписываются). [Аудит и границы последнего repair](validation/T5-FINAL-BOUNDED-REPAIR.md):2 read-only SSH проверки frozen корпуса,0 embedding/provider calls; смысловое отсутствие all4 и новая генерация all5 NOT PROVEN. Дополнительно py_compile/diff-check и desktop/mobile DOM checks PASS. Невалидные цитаты/источники, unknown spend, foreign chat/scope и приватная переданная трасса блокируются. Новый exact refusal не извлекается из произвольного пункта списка; старая raw all11 не переписывается.

Runtime SHA `c542a8a1190a73aab8cbc06cca70fa8e562d804e05e72a2cab9b208331d86776`; runner SHA `de8e20d907b9da9e9378305671e3c03ab9a55a99657a6b07ffe0f42913d34614`; scenario SHA `2438f66008ce72ccb2f2e3c27b5e33ff86eacfbd5c049b04cf5a1a84ae650430`; frozen SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`. Это runtime snapshot run07; последующие doc edits не меняют снимок выполненного кода.

Подробные raw/матрица/ledger находятся только в ignored day25/private; в публичных docs — агрегаты и ограничения. [Run07](T5-REGRESSION-07-MECHANICAL.md), [video provenance](video/README.md). Нет автоматического commit/push/deploy/publication или новых paid calls.

## Локальный repair после нового запуска

Root исправил распознавание диапазона учебных дней и коротких продолжений. Независимый offline gate: **50 app +21 validation PASS**,10 saved-context replay cases PASS (7 all календарных ошибок +3 public продолжения), сохранены независимые новые темы и explicit day/date precedence. Это pure replay/офлайн-проверка; новое поведение модели NOT PROVEN, историческая live матрица14/12/4 и A1FAIL не меняются. Дополнительных provider calls нет.
