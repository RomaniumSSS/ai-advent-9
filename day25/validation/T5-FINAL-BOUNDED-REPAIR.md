# Последний ограниченный цикл после run07

04.10.2026. Пользовательский stop condition: при корпусном пробеле дальнейшие платные прогоны остановить. Нового live run нет. Run07 A1 NOT PROVEN и human acceptance NOT PROVEN сохраняются; готовность артефактов к сдаче не означает формальный PASS.

## All4: фактический read-only audit

Два read-only SSH обращения к frozen Structure SQLite (mode=ro), без embedding/generator/provider calls. Exact identity SHA `6c3672a133e01288a7c8b1b59d5f017183f7a14402a000c9b5290b4f7a25f6bb`, generation5d5502c69976163325ad6c35, полный охват724 чанков/694 discussion-чанков.

- Discussion с буквальными `чанк|chunk`:0.
- Cooccurrence темы с размером/длиной и расширенные fragment/segment/разбиение markers:0.
- Дополнительные синонимы кусок/нарезка/разбивка и размер/длина/токены/контекст:7 совпадений. Фокусный просмотр — другие темы (multihead, код, skills, usage, задачи), не RAG chunk-size discussion. Независимый просмотр подтвердил эту классификацию.

Это bounded lexical audit всего frozen index, **не исчерпывающее доказательство смыслового отсутствия**. Поддерживающий материал для all4 не выявлен; новый ranking/детерминированный ответ не добавлен. All4 остаётся NOT PROVEN; утверждать мнения участников по отсутствующему материалу нельзя. Raw/скрипты аудита только private/final-repair-audit; приватный текст не опубликован.

## All5: контракт цитирования участников

Saved all5 содержит3 typed references участников одного чанка; глобальная цитата этого чанка подтверждает лишь одного. Две другие привязки правильно отклоняются `attribution_not_cited`.

Изменён только generation contract в structured_evidence.model_contract: каждая привязка требует своей точной цитаты **того же message_id member**, цитата соседнего участника не подходит. Добавлены максимум2 paired examples attribution/source/quote, построенные из уже переданных single-member discussion частей, excerpt≤90characters, проверенные тем же resolver. Public assignment-only контекст не получает participant examples. Неиспользуемые привязки нужно не выводить; фабрикация цитат запрещена.

Строгий check_response/citation/role validator не изменён. Автоматической правки ответа нет. Старый all5/raw остаётся unverified. Реальное соблюдение нового prompt и смысл ответа **NOT PROVEN**.

## Офлайн evidence

46 app tests PASS (4.791s),15 validation PASS; независимый запуск46+15 с ResourceWarning aserror PASS. Адресная saved all5 проверка: исходный full fake Service rejected; синтетический ответ с двумя точными member quotes verified; повтор цитаты соседнего member rejected. Это structural exercise, не новый live ответ. Проверены actual final messages≤24000bytes и пустые examples для public контекста. Другие T1–T4 regressions сохранены.

Независимые hashes JSON raw06/raw07 совпали с baseline; новые paid calls0, caps не менялись. Python compile/diff-check PASS. Текущий видеофайл run07 не менялся: он показывает выполненный тогда runtime, не новый prompt.

## Остановка

Implementation/local gate PASS; formal A1 и human acceptance NOT PROVEN. Артефакты готовы к передаче с явными all4/all5 ограничениями. Дополнительный paid run не планируется. Публикация не выполнялась.
