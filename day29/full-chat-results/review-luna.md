# Full local chat — первое независимое ревью

**Вердикт: NEEDS CHANGES.** В офлайн-контракте нет найденного обхода полного scope, ссылок на контекст или защиты локального API. Есть два поведенческих пробела: частые короткие продолжения не привязываются к предыдущей теме, а асинхронные ответы UI могут пройти проверку устаревшей версии и перерисовать сброшенный/сменённый разговор.

## Замечания

🟡 **[WARNING]** `day29/full_chat_static/app.js:12-16` — версия вида проверяется до некоторых `await`, но не после них. В `poll` проверка проходит после получения job, затем `await api('/api/conversations/...')` может завершиться уже после reset или переключения и `render` безусловно покажет старый снимок. `send` имеет такой же разрыв между проверкой после `/api/ask` и рендером загруженного разговора. `reset`/`newChat` увеличивают версию только после ответа сервера (внутри последующего `open`), поэтому старый poll ещё валиден, пока операция ожидает ответ. При медленной сети это временно возвращает удалённые reset-ом сообщения или содержимое прежнего разговора в текущую панель. Инвалидировать версию синхронно при начале смены/reset/new; после каждого асинхронного чтения повторно проверить захваченные `conversation_id` и `viewVersion` до любых изменений DOM/state. Добавить контролируемый UI-тест с задержанным ответом conversation API и reset/switch.

🟡 **[WARNING]** `day29/full_chat_core.py:129-130` — follow-up распознаёт точное `почему?`, но не варианты `А почему?`, `А почему так?`, `Что дальше?` и `А что дальше?`. Для истории с темой «Что обсуждали о SQLite?» все четыре воспроизводимо получают `intent=new_topic`, `anchor=None`; поиск уходит по короткой фразе без контекста предыдущего вопроса. Расширить разбор эллиптических вопросительных продолжений или классифицировать такие короткие фразы как неоднозначные и запросить уточнение. Покрыть эти варианты вместе с явным самостоятельным переключением темы.

## Проверки и границы доказательств

Запущено `python -m unittest discover -s day29/tests -p 'test_full_chat*.py' -v`: **27 focused synthetic/offline tests PASS**. Дополнительно напрямую вызван `resolve_query` для четырёх коротких фраз выше; все четыре показали описанный сбой. TDD red/green и offline evidence-файлы присутствуют в `day29/tests/`.

Реальные embedding/LLM вызовы и браузерный runtime в этом ревью не запускались. Сообщённые координатором проверки loader, старой совместимости, трёх viewport и приватных сценариев не перепроверялись. Семантическая поддержка реальных ответов, фактическое время/timeout провайдера и human acceptance здесь не доказаны. Текст FULL_CHAT_SPEC рассматривается как рабочий пользовательский контракт; формальное одобрение SPEC не заявляется.

## Снимки прочитанных файлов

SHA-256 на момент окончания ревью; после фиксации перед вердиктом файлы сверены повторно.

```text
day29/FULL_CHAT_SPEC.md  6b2405fd91e48b9988cbd34d36431cfbef3da8150e2adaff0a5d35210c0d64d8
day29/full_chat_core.py  2e75e0fbdfddac31b8f99dce80e9a1ed7065d79f43b5377b3fb5becb73b599db
day29/full_chat.py  d970f21c3f14f5b8a258c23f8eeb12ee475c0e16a07dc55382139576892b9878
day29/full_chat_static/index.html  66f9ca194a045c23fc729312602796c94db482be8469faaae79d5aa1d72d0eb1
day29/full_chat_static/app.js  57ab6d8010f181cda6a3df61733eb243bd6ad22dc64fa2965298ba466efca9f6
day29/full_chat_static/style.css  022f9a303efdb5f1f987e85fda8ab92d3d6c17daa2209d5247e8718e650f27cc
day29/tests/test_full_chat_contract.py  0fcec6a3a7e8de9f1be1a52f074994281a54d261d37dc4230fd01c07ce632553
day29/tests/test_full_chat_http.py  d94d73bc5eb601a039c993bcd4a10694ae7bf13e062473cd1878f4aa52620f12
day29/tests/test_full_chat_runtime.py  b7357fe988f666c80d0ac810490bdeea8bb0a6566c40a972f4ee06801c5a2c44
day29/tests/test_full_chat_store.py  0812da00e4316071c2eea1058803620da2cad6d68fa4a68f9399a9cc131c0914
day29/tests/full-chat-tdd-contract-green.txt  30566ca25d77c032e0373d38efdaaa9308c982df8c5787b48a9dc54fe887a8f3
day29/tests/full-chat-offline-green.txt  866d19fa203c53533f19297e7cf44c947089b8a6efaa5ef322a1a8e00803b003
day29/tests/full-chat-tdd-topic-switch-red.txt  7f939faa2ca801e4441a86986162736fc6db7123e888235d494733403b22b9e0
day29/tests/full-chat-tdd-http-red.txt  a4c0f6dbfd84cc19f70b838ad3bce027f80031596f3d7872d8cfb4fe5880eeaf
day29/tests/full-chat-tdd-storage-red.txt  f0101dfe3492aa5fa6dc3e27dc1003635e65ef3a74cf9c2d924795e9111e5485
```
