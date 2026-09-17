# Video report

Файл: `day14/demo/day14-invariants.webm`.

- 13,16 с, WebM/VP8, 1280×800.
- Аудиодорожки нет.
- Сценарий: видны три отдельные записи правил; конфликт SQLite → PostgreSQL;
  локальный `ОТКАЗ` с `INV-STACK-001`, правилом и причиной; audit `request: deny`;
  безопасный вопрос «Почему нельзя…» с локальным explanation вместо refusal;
  затем создание задачи и сохранение planning после pause → новый Agent → resume.
- `video-contact-sheet.png` и `safe-explanation.png` просмотрены: начальный
  экран, отказ, explanation, paused FSM и resumed FSM присутствуют; layout не
  перекрыт.

Видео использует офлайн-клиент, но отказ проходит настоящий кодовый preflight и
не вызывает даже fake provider. Это демонстрация harness, не real-provider eval.
