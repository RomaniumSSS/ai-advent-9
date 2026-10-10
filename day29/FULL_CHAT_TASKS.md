# Full local chat — задачи

Статус 10.10.2026: полный локальный чат завершён, обязательное Astra ревью —
**APPROVED / SPEC SATISFIED, 25 PASS**. Человеческая приёмка не проводилась.
[SPEC](FULL_CHAT_SPEC.md) задаёт приёмку; [результат](FULL_CHAT_RESULT.md) содержит evidence и ограничения.

- [x] **F1 / Sol:** зафиксировать public artifact hashes и immutable identity; проверить
  доступность Q4/embedding. RED для retrieval/provenance/history/budget/boundaries.
- [x] **F2 / Sol:** full loader + semantic/lexical all retrieval + attributed source
  context + guarded local generation; GREEN для SPEC 1, 3–5.
- [x] **F3 / Sol:** отдельные /8070 API/UI, durable private conversations, new/reset,
  pending/errors/restart recovery; GREEN для SPEC 2, 4–5.
- [x] **F4 / Sol/root:** прежние offline tests, browser/API checks, bounded real local smoke
  по новым корпусным вопросам; agent semantic check по original sources. Private
  receipts сохраняют модель/digest/index, запрос/anchor, selected IDs, actual payload,
  ответ/status, время и причину остановки; mock и real evidence разделены.
- [x] **F5 / Luna:** независимое первое ревью SPEC/code/tests/evidence; записать findings.
- [x] **F6 / Sol → Astra:** исправления и targeted checks, обязательное второе независимое
  ревью; новые исправления перепроверены. При недоступности Astra не ставить DONE.
- [x] **F7 / Sol/root:** unchanged public artifacts/index подтверждены; README/краткий
  full-chat result/action journal/todo/HANDOFF обновлены, /8070 проверен и доступен.
  Итог отдельно указывает код, offline, live, browser, смысловую и человеческую приёмку.

Для закрытия F4 корпусный пробел не заменяется выдуманным PASS: зафиксировать unknown
и подобрать поддержанный новый кейс того же типа, сохранив исходное наблюдение.
Публикация, новый ZIP/видео и benchmark переоценка в этот checklist не входят.

## Implementation evidence — Sol high

Реализованы `full_chat_core.py`, `full_chat.py`, `full_chat_static/`,
[запуск/API/лимиты](FULL_CHAT_README.md), synthetic tests и browser helper.
Применённые core/Ollama/lock/save helpers заимствованы из того же Day29;
public Engine/benchmark и Day01–28 не менялись. Child preservation проверил
46 исходных benchmark файлов без mismatches; root имеет более широкий снимок99.
Root отдельно подтвердил immutable full loader724/663 и старые45 compatibility.

RED→GREEN: all retrieval/attribution/followup/budget, HTTP Host/busy, storage
atomic failures, independent new subject/topic switch, commonellipses.
[28 focused GREEN](tests/full-chat-offline-green.txt),
[команды/hashes/evidence](tests/full-chat-offline-evidence.json). Тесты используют
только synthetic fixtures/tempdirs/mocks, приватные тексты корпуса в public
fixtures не копировались. Model/generation calls исполнителя:0.

Luna warnings исправлены: new/reset/switch синхронно инвалидируют view token;
cid/version/sequence проверяются после await до DOM/state updates. Chromium
[delayed UI RED](tests/full-chat-tdd-ui-race-red.txt) →
[GREEN](tests/full-chat-tdd-ui-race-green.txt); controlled bootstrap GET500 после
newChat дал [RED](tests/full-chat-tdd-bootstrap-red.txt) →
[GREEN](tests/full-chat-tdd-bootstrap-green.txt). Elliptical continuations
«А почему?», «А почему так?», «Что дальше?», «А что дальше?» получают user anchor.
[Source diff](tests/full-chat-review-fixes.patch) и old snapshots сохранены.

Synthetic browser desktop1280×800/tablet768×1024/mobile375×812: reload, source
text/attribution, XSS text-only, pending/errors/unknown, new/reset late response
isolation и delayed send/poll races PASS. Последний exception-only bootstrap fix
проверен отдельным Chromium кейсом. API/CSP не ослаблялись; реальный8070 executor
не поднимал и моделью не пользовался. Root owns server/actual UI/three livecases,
проверку сохранения после restart, public-safe live report/journal/rootdocs.

Три root livecases source support PASS; исходный discussion PARTIAL2/3,
follow-up/personal_note complete по выбранным требованиям. Смысловая поддержка
оценена агентом по оригиналам, общей точности и human approval не заявляется.
[Root live summary](full-chat-results/live-summary.json). Mandatory Astra и
полные F4/F5/F6/F7 checkbox statuses закрывает root на собственных evidence.


## Итоговая проверка — root / Astra

28 новых offline PASS, 45 прежних compatibility PASS, synthetic UI RED/GREEN
и actual post-restart source panels на трёх viewport. Три новые local generation
через UI — [safe summary](full-chat-results/live-summary.json), source support 3 PASS;
D01 completeness PARTIAL 2/3, остальные два PASS. Общий hallucination rate не измерен.

[Restart persistence](full-chat-results/restart-persistence.json),
[точное совпадение payload после fixes](full-chat-results/fix-payload-equivalence.json),
[final UI](full-chat-results/final-browser.json).
[Luna](full-chat-results/review-luna.md) findings и bootstrap race исправлены Sol;
[Astra](full-chat-results/review-astra.md) независимо проверила code/tests/real sources,
[матрица 25 PASS](full-chat-results/implementation-validation.md).
99 protected файлов и индекс SHA сохранены; приватные тексты не опубликованы.


## Порученная публикация Day29 — 11.10.2026

Пять random вопросов вместо всех24; свежая живая запись, orderedmain/day29,
Drive Anyone with link/Viewer и отдельные video/code URLs в Лист1!AD132.
Подробные source experiment задачи/negative results остаются в QUALITY_EVAL_TASKS.

- [x] D1: исходные пять, known resolver2/source1 retests, независимые оценки, safe summary.
- [x] D2: general resolver/source fixes и Luna→Astra,139offline PASS; индекс/старыеreceipts сохранены.
- [x] D3: recorder actual API profile projection RED/GREEN, Luna→Astra; faileddry0calls сохранён.
- [x] D4: новый real3-request dry, source-backed visible claims и readable/privacy frames.
- [x] D5: новый отдельный real3-request record, MP4 ffprobe/decode/frames/receipts checks.
- [x] D6: final independent Astra delivery validation against actual artifacts/state.
- [ ] D7: commit/mainff/push, remoteSHA/tree order/day01–28 preservation.
- [ ] D8: Drive owner/folder/Anyonewithlink Viewer/public read verification.
- [ ] D9: own two-URL comment AD132, AD1/A132 correct, complete reload readback.
