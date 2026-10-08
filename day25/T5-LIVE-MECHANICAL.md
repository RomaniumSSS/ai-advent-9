# T5: реальный механический прогон, смысловая приёмка ожидается

04.10.2026. Пользователь разрешил два отдельных cap$0.06, public assignment:18 и all frozen corpus. Independent pre-live Astra gate PASS; scenario SHA `13cc7c6fb48c1beaf358cf96c4f386815027a4d28e5ff568fbe630513c63800f`, frozen SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`. T5 PASS здесь не утверждается.

## Факты

| Scope | Ходы / поиски | Provider calls | Статусы | Измеренный расход | Tokens prompt / completion / total |
| --- | --- | --- | --- | --- | --- |
| public |12 /12|11|10 verified,1 no_context,1 unverified|$0.0032485936|15950 /3908 /19858|
| all |12 /12|12|9 verified,3 model_refusal|$0.0084438648|38532 /9247 /47779|
| всего |24 /24|23|см. выше|$0.0116924584|54482 /13155 /67637|

Стоимость взята из actual provider usage и совпадает с суммой ledger charge; unknown0, retries0, provider DeepInfra/model deepseek/deepseek-v4.1-flash. Остатки public$0.0567514064/all$0.0515561352 не означают разрешение на дополнительные экспериментальные вызовы.

Runner preflight обоих серверов проверил exact SHA/scope/budget до POST. Checkpoint после public6: exit2, реальный SIGINT/start public8054 с тем же data-dir, PID6420→7045, шесть request IDs и task state сохранены; --resume exit0 MECHANICAL_RUN_COMPLETE. Refresh не отправлял POST, archive views не добавляли вызовов. Day24 не трогали.

Raw answers/queries/context/usage all остаются только `day25/private/live-run-01`; `USAGE-SUMMARY.json` содержит расчёты, `semantic-review.csv` содержит критерии по каждому ходу с NOT_REVIEWED. Ключ читался сервером из существующего env-file; значения не выводились и не копировались. Новые ledgers отдельные, cap$0.06 каждый.

## Ограничения и оценка

Public5: no_context, без генерации. Public8: unverified, validation source_not_in_context; неподтверждённая ссылка не показана как verified. All5/11/12: model_refusal с пустыми источниками/цитатами. Не выполнено повторных запросов или автоматического исправления. Сохранённый terminal результат проверяем отдельно от смысловой успешности; mechanical completion не доказывает выполнение A1/удержание цели. Содержимое private ответов сюда не переносится.

Оценщик root/Astra должен проверить смысл всех24 ходов, особенно позднюю память и отказы, по актуальной рубрике и реально переданным источникам; human review пока PENDING. Любые исправления/повторные эксперименты определяются отдельно, не закрывают текущие провалы задним числом.

## Видео

`day25/private/live-video-01/saved-public.webm`,2PNG, RECORDING.json: настоящий public-only UI, сохранённые12 результатов, толькоGET; new searches/provider calls0, public ledger$0.0032485936 до=после, DOM guard PASS. Publication NOT_APPROVED. Это просмотр сохранённых результатов; fresh_search_demonstrated=false, не доказательство качества all.

Остановка: live run завершён; независимая смысловая оценка ожидается. Commit/push/deploy/publication не выполнялись.
