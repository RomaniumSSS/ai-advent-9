# Local risk-based review preparation

```sh
python3 day21/review/test_selection_review.py
python3 day21/review/prepare_selection_review.py
```

Final immutable generation: `day21/private/selection-review-v3/` (после замечаний root к промежуточным v1/v2; те сохранены, не использовать как final). Files:inventory.json,cases.json,selected-message-ids.json,manifest.json. Seed210124,sourceproposalmanifestSHA `076f2962bd221b659da1492691b4e1a8b85488c1aa6ba0e1327ee1fb588eb85a`. FinalmanifestSHA `7eec066255962ecb6ec7d4a363563607ee7c2bb13b650f97a8d205468750f7b7`.

Inventory всех85candidate groups со спорными dependencies содержит только refs/provenance/status/lengths, не текст переписки. Выбрано20wholecases:10dependency groups,5candidateinclude без спорных dependencies,5candidateexclude. Dependency coverage:exclude/review/unread/outside;mixedflag отсутствует среди dependency groups, но выбран1cleaninclude case с таким modelflag. Всего6cases имеют needs_fact_check samplinglabel. Include/exclude включают no_reply,длинные и короткие по memberlength;exclude есть2modelreason-botmarker cases. Marker — только строка в объяснении модели для выбора разнообразия, не доказанная идентичность бота или правильность exclude.

Sample57уникальных canonical IDs,11223Unicode chars (≤120IDs/60000chars);casechars с повторами11223. No budgetrejections в реальной выборке. Кейсы не усечены:members+direct/explicitcanonicalcontext полные originaltext;внешний недоступный contextID сохранён отдельно. Contextне promoted. Privatecase record содержит provenance/version/textsha,reply/media/source_role,modeldecision proposal reason/flags,status;group modelreason сохранён отдельно как предложение. selected-message-ids.json — deduplicated members+доступныйcontext,не весь85inventory. Privacy/cloud authorization покаfalse: новаяподборка не передана в API и не выведена в coding-agent контекст.

Проверки PASS:deterministicseed20strata/categorycoverage,Unicodeexacttext,refs-onlyinventory,contextboundary,sourceidentitydrift refusal,oversizedwholecase skip withouttruncation,modelreason/flags,private0700/0600. Реальная сборка+repeat:все4hashes совпали,manifestartifactSHA валидны,source/acceptedguards совпали before/after;py_compilePASS. API/modelcalls/acceptedmutations0. Sourceselection-proposals-v3/canonical/accepted/MCP/todo/PLAN не менялись.

Это risk-basedinspection, не статистическая оценка accuracy. Будущие reviewer criteria:course relevance/неботпересказ;самостоятельный вопрос+ответ;недостающий context/media явно;смешанное содержимое и provenance;claims участников не выдавать за verifiedfacts. Future result shape:case_id,verdict keep|propose_change|defer,reason,sourceIDs. Сейчас смысловых решений нет. Проверка20sample не подтверждает остальные85groups и798semanticreview+388invalid+82unread+1transport. Следующийgate:явное разрешение пользователя на чтение новойподборки родителем;до него остановка,безAPI/UI/новых моделей.

Root independent preparation review PASS:artifact/sourceguard/preparer hashes,каждый selectedtext/version точно canonical,20cases/57IDs/11223chars/85inventory,0600;synthetic tests повторены PASS. `coverage.mixed_flag=not_available` относится только к dependency stratum;в cleaninclude sample1mixedcase присутствует. Новые фрагменты здесь не читались;ожидается решение пользователя.

## Последующее разрешение и проверка

После подготовки пользователь ответил «продолжай» на запрос о чтении новой подборки текущей моделью OpenAI. Родитель прочитал только указанные 20 кейсов / 57 ID. Поле `cloud_authorized:false` в неизменяемом манифесте отражает состояние на момент подготовки; исходный файл не переписан. [Результат смысловой проверки](SELECTION-SEMANTIC-REVIEW.md). Разрешение не распространялось автоматически на новые кейсы или весь корпус.
