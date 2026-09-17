# Валидация структурного state-envelope

Проверки выполнены в отдельной временной копии `day13/` с чистыми SQLite-базами;
продуктовые файлы на этапе VALIDATION не изменялись.

- Полный test-double campaign: 64/64 terminal cases, 60 model paths, 4 pause
  guards, 12 restart/resume.
- Канонические `stage/current_step/expected_action/objective` формирует
  приложение из снимка до вызова; после вызова снимок совпадает побайтово.
- Модель возвращает только `decision` и `answer`; намеренно неверный decision
  получает `quality_fail`, но не может изменить канонический state-envelope.
- Provider uncertainty по-прежнему останавливает campaign без retry; tamper
  checkpoint обнаруживает изменение ledger.
- Live-04 связан с SHA-256 ledger live-03, его собственной стоимостью
  `$0.00081272` и накопительной стоимостью `$0.00163506`; дополнительный лимит
  `$0.01836494`, общий `$0.02`.
- FSM/web тесты, JavaScript syntax и Python compilation прошли.

Реальная сеть на этом этапе не использовалась.
