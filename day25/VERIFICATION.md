# Day25 — проверки

04.10.2026, macOS, Python3.14/Node24.11.1; Chromium153 через временный Playwright venv/cache.

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
