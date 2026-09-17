# Валидация terminal prompt и третьей live campaign

Проверки выполнены в отдельной временной копии `day13/` с чистыми временными
SQLite-базами. Продуктовые файлы на этапе VALIDATION не изменялись.

Успешно выполнены:

- `test_task_state.py`: формальные переходы, pause/resume на каждом stage,
  restart без истории, один снимок state и optimistic locking;
- regression для `done`: terminal prompt не содержит команды продолжать,
  запрещает выдумывать новый state и сообщает об отсутствии действия;
- `test_web.py`: API/UI, pause → clear → restart → resume → continue;
- `test_live_eval.py`: 64 terminal situations, 60 model paths, 4 pause guards,
  12 restart cases, at-most-once после provider uncertainty и tamper detection;
- policy `day13-live-03`: SHA-256 и собственная стоимость ledger live-02
  проверяются отдельно, накопительная стоимость live-01 + live-02 равна
  `$0.00082234`, дополнительный лимит `$0.01917766`, общий лимит `$0.02`;
- JavaScript syntax check и Python byte compilation.

Реальный provider на этом этапе не вызывался. Следующий разрешённый шаг —
LIVE_VALIDATION новой campaign `day13-live-03`; прошлые ledgers не изменяются и
ни один их case не отправляется повторно.
