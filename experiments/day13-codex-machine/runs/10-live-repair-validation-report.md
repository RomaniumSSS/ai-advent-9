# Валидация repair-контракта live-eval

В scratch-копии повторно прошли `test_live_eval.py`, FSM/web тесты, JavaScript
syntax check и Python compilation.

Новый regression predicate проверяет, что pinned request содержит
`extra_body.reasoning = {"effort": "none"}`. Policy `day13-live-02` содержит
неизменяемую ссылку на failed ledger `day13-live-01`, его SHA-256 и расход
$0.00002707. Дополнительный бюджет $0.01997293 не позволяет суммарному расходу
двух кампаний превысить $0.02.

Автоматические повторы по-прежнему запрещены; новый campaign ID не переписывает
и не маскирует первый failed run.
