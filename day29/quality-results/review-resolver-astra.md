# Resolver — независимое Astra review и триаж Luna

**Final verdict: APPROVED — resolver fix.** Final SHA `98e6725d1e9246d1f1335d81726db4b43dfb3e5b3ddfe2e17981c9ed8bcaccc6`. Reviewer — gpt-6-astra/xhigh. Подтверждённые bounded R1/R2 на прежнем ffb2a15c… устранены и независимо перепроверены. Реальные вызовы reviewer0. Исторический триаж ниже сохранён: механически принимать оба предложения Luna было бы ошибкой.

## Триаж замечаний Luna

**Luna1 — частично отклонено.** Само наличие нескольких авторов не делает plural «они/их» неоднозначным: коллективный antecedent может обозначать всех названных участников, а «из них» может относиться к предметам. Автоматический plural+authors>1 guard создаст false clarification. Синтетический anchor о предложениях двух явно названных участников → «Что они предложили?» уже правильно сохраняется; это не дефект. Число авторов нельзя использовать вместо смысловой проверки referent.

**R1 / WARNING — подтверждён ограниченный пробел**, `full_chat_core.py:149`: «Что из них применили?» не распознаётся как follow-up; с историей возвращает new_topic и теряет anchor, без истории тоже new_topic вместо уточнения. Добавить bounded plural anaphora, сохраняя group/object follow-ups независимо от0/1/2 авторов. Реально неоднозначный singular при двух возможных авторах и без именованного выбора должен по-прежнему уточняться.

**R2 / WARNING — подтверждено**, `full_chat_core.py:139–149`: «А что в том разделе?», «А что в той части?», «А что в таком разделе?» получают new_topic вместо сохранения предыдущей пользовательской темы. Новые формы должны согласованно работать в follow-up и local-antecedent правилах. Самостоятельно названный локальный раздел с номером/меткой должен остаться new_topic. Не превращать существительное «том» или условную частицу «то» в универсальный сигнал follow-up.

## Acceptance для ограниченного исправления

- Явная коллективная тема + они/их/них сохраняет user-topic anchor, в том числе при двух авторах.
- Тема о нескольких предметах + «из них» сохраняет anchor независимо от attribution источников.
- Plural/deictic ellipsis без подходящей истории просит уточнение.
- Singular participant reference с двумя возможными авторами и без единственного named anchor по-прежнему просит уточнение.
- Указательные формы том/той/таком с подходящим antecedent в истории сохраняют anchor; локальный именованный/нумерованный antecedent текущего вопроса имеет приоритет.
- Контрольная самостоятельная фраза «Сколько страниц содержит том 3?» остаётся new_topic; unrelated number не превращает неясную ссылку в локальный antecedent.
- Никакого topic/day/model словаря; AST вне resolve_query неизменен; прежние3 actual inputs остаются эквивалентны.

Прочитаны full resolve_query, FULL_CHAT_SPEC/PLAN dialogue contract, antecedent/contract/runtime tests и evidence. Независимые pure probes воспроизвели R1/R2 и подтвердили корректность коллективного plural и истинно неоднозначного singular. Core/API/UI не редактировались; реальные HTTP/embedding/generation не выполнялись. Initial-five blind assessment сохранён до этого review и не переоценивается по знанию причины ошибки.

## Финальная проверка исправления

R1 закрыт: добавлены plural forms них/им/ним/ими/ними без blanket multi-author guard. Collective и object anchors сохраняются при0/1/2 авторах; без истории требуется уточнение. Существующее истинно неоднозначное singular обращение по-прежнему уточняется.

R2 закрыт: distal demonstratives ограничены конструкцией с последующим словом и согласованно используются для определения follow-up, проверки самостоятельного subject и local antecedent. Синтетические «том 3» и conditional «то» не стали ложными ссылками на историю. Именованная/нумерованная локальная тема сохраняет new_topic. Обобщения сделаны грамматически, без словаря тем/номеров учебных заданий/названий моделей. Legacy proximal формы не расширены произвольно; это не попытка полного морфологического парсинга русского языка.

Независимо выполнены `unittest.defaultTestLoader.discover('day29/tests', pattern='test_full_chat*.py')` и затем `pattern='test_quality_eval*.py'`: **37 full-chat PASS +34 quality PASS**, failures0/errors0, exit0, Python3.14.0/macOS arm64. Real core.Ollama.request запрещён patch; socket.create_connection допускает только ephemeral loopback tests и отклоняет8069/8070/11434/внешние хосты. Синтетический HTTP API выполнил16 соединений с собственными temporary fake-engine servers. Работающие приложения/Ollama не вызывались и не перезапускались.

Независимый AST comparison со snapshot baseline6e887f… подтвердил идентичность всего модуля вне resolve_query. Дополнительно на сохранённых actual H05/H12/H20 заново вычислены query и build_context/profile_payload без модели: **query/messages/payload побайтно эквивалентны исходным receipts для всех3**. Их payload SHA:

- H05: `e7f40799fc5cb346a2358f7e2480ca86a1f3f3729da9a7cea8d781887da6ce77`;
- H12: `ae49426de0d0452f83fd729e34dbc2021d2d0816e77ecb33b939b28a7abd9da4`;
- H20: `e7a62357377df38e168eef96bd2673d6c3f4f41c98016fe6b5e9f3fc6e98aaeb`.

Для H06/H11 pure resolve_query теперь new_topic вместо прежнего clarification. Это доказывает исправление маршрутизации вопроса, но не будущие retrieval/answer quality или latency; разрешённый диагностический retest этих двух ещё предстоит. Предыдущая blind оценка initial five и последующий отдельный critic audit сохраняются неизменными.

## Версионирование диагностического retest

Допустим новый manifest/matrix version с изменённой только baseline code metadata и явной ссылкой на прежний снимок. До prepare root должен подтвердить неизменность cases/questions/gold/evidence/profile и назначить source-audit sidecar новому cases-file SHA; прежний файл не переписывать. Это согласование metadata-only versioning, не аттестация ещё не созданного файла. Повторяются только уже известные H06/H11; это2 diagnostic retests, не новые holdout и не замена результата initial5. Повтор всего набора и изменения retrieval/prompt/critic/profile этим review не поручаются.

Открытых BLOCKER/WARNING в проверенном bounded scope нет. Нельзя выводить из37 synthetic tests универсальное разрешение любых неоднозначностей естественного языка. Final own-idle app restart и actual2 receipts/semantic assessment выполняет root после этого code approval.

## Финальные SHA-256

- `full_chat_core.py`: `98e6725d1e9246d1f1335d81726db4b43dfb3e5b3ddfe2e17981c9ed8bcaccc6`
- `full_chat.py`: `d970f21c3f14f5b8a258c23f8eeb12ee475c0e16a07dc55382139576892b9878`
- `full_chat_static/app.js`: `3625298ddf5e3ecb7b9cc68f034d346899b5ea1c551cd41d8750318b1e05c87e`
- `quality_eval.py`: `329a11f5442cd02ac2a87f3bdaeb438c89e2c10e4f011af381895f4d191cb89c`
- `video/run_full_demo.py`: `c25e57930cbee56068da8e949fb24a5028bd7d2c4d8b86c6572250d0987e6eee`
- `tests/test_full_chat_antecedents.py`: `b693450f02cb33c5d6867f72bccf53a7892d09829aa6a04b9e09b2cea93fb489`
- `tests/full-chat-local-antecedent-evidence.json`: `cd3948eef4f073e27d9b79fbd3c1ffbfc8069ddde750a03a0d710dbddb9e2a6d`
