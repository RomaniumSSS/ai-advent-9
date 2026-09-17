# Integration report — capability matrix

Локальный runtime прогнан на временной SQLite-базе с `FakeClient`; сеть и
реальный provider не использовались.

| Конфигурация | Наблюдаемый контекст |
|---|---|
| default | profile + FSM + short + working + long |
| stateless | только system + user question |
| profile_only | profile, без FSM/memory/history |
| task_working | FSM + working, без profile/short/long/history |
| history_only | system + последняя user/assistant пара + новый вопрос |

Все 5/5 конфигураций сформировали ожидаемый фактический payload fake provider.
