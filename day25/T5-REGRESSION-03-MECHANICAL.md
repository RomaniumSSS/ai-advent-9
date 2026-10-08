# T5: третий regression — механический результат

04.10.2026. Пользователь разрешил третью проверку2×12, новые отдельные cap$0.06/public и$0.06/all, max24calls/retries0. Это regression на прежних вопросах, не независимый holdout. Старые live01/live02 raw/оценки не изменены; их FAIL не переписан. T5 PASS здесь не утверждается.

## Preflight

32 app tests PASS3.750с и8 preparation tests PASS0.005с. Runtime SHA `57f0931d0c5032b5b296fc6bc6b56cad6b5ba672143b2443bce6ce0d1ce0b48b`; scenarioSHA `2438f66008ce72ccb2f2e3c27b5e33ff86eacfbd5c049b04cf5a1a84ae650430`; frozenSHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`. Новые private/live-public-03 и live-all-03, отдельные пустые ledgers/single scopes, public только assignment:18. Расчёт maxreserve24≤$0.10816512,12scope≤$0.05408256. Actual calls ниже обоихcap$0.06. Runner GET-preflight обоих dedicated servers SHA/scope/budget доPOST PASS. Ключи не копировались/выводились.

## Выполнение

Public12/all12 через обычный UI; послеpublic6 checkpoint exit2, реальный SIGINT/start8054 с тем жеdata-dir, PID64904→65641, сохранённые6IDs/task-state проверены, resume exit0 MECHANICAL_RUN_COMPLETE. Refresh/archive не добавляли запросов. Day24 не трогали.

| Scope | Ходы/поиски | Provider calls | Статусы | Actual cost | Prompt/completion/total tokens |
| --- | --- | --- | --- | --- | --- |
| public |12/12|12|12verified|$0.0033395432|21843/4064/25907|
| all |12/12|12|10verified,2model_refusal|$0.0086173584|41388/10198/51586|
| всего |24/24|24|22verified,2model_refusal|$0.0119569016|63231/14262/77493|

Provider DeepInfra/model deepseek-v4.1-flash. Actual provider cost совпадает с ledger charged. Unknown0/retries0, cap не превышен; дополнительных экспериментов нет. Отказы all2 (короткое продолжение) иall11 (SLA), их приемлемость определяет смысловая оценка. Ответы не переписывались; citation/format checks действовали.

## Evidence и остановка

Rawall остаются только private/live-run-03, рядом USAGE-SUMMARY.json/CODE-SNAPSHOT.json/semantic-review.csv с NOT_REVIEWED. Новый private/recheck-setup-03.json фиксирует runtime/scenario/frozen/scope/caps.

private/live-video-03/saved-public.webm +2PNG/RECORDING.json: GET-only public saved playback exit0,0 новых searches/providercalls, ledger$0.0033395432 до=после, DOMguardPASS; publication NOT_APPROVED, fresh_search_demonstrated=false. Это не доказательство поиска/качестваall.

Точка остановки — independent Astra semantic gate всех24 ходов, особенно выбранногоSQLite/returned-tool-result/краткости и отказаall2. Verified не означает правильный смысл. Согласованные24calls исчерпаны как количество; остаток бюджета не разрешает новые эксперименты. Commit/push/deploy/publication не выполнялись.

## Independent gate после прогона

Astra full gate: A1 FAIL — all10 ошибочно ограничил сравнение с обсуждениями, хотя релевантный day22 фрагмент передан. Public9/all2/all4 NOT PROVEN. Это механический отчёт, не PASS. Запись завершена; собственные8053/8054 остановлены SIGINT послеGET-only video, Day24 не трогали. Новых live попыток не планируется.
