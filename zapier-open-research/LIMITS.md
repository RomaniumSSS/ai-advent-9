# Limits and verification boundary

- Интеграция private и не публиковалась в Zapier App Directory.
- API и PostgreSQL развёрнуты на личном VPS; версия integration `1.0.0` загружена в
  Zapier как private, адрес HTTPS API задан через version environment.
- В Zapier account не создавались connections или Zaps; скриншотов live run пока нет.
- Метаданные публикаций реальные и получаются из OpenAlex CC0. Saved works, notes,
  review scores и API account — демонстрационные данные.
- Automatic score — прозрачный приоритет для чтения по title match, возрасту,
  открытому доступу и citation count. Он не измеряет научное качество, истинность,
  peer-review status или соответствие конкретному исследовательскому протоколу.
- Локально проверены API contract-сценарии и Zapier harness-сценарии; точное число
  выводится тест-раннером. Это не проверка сетевых сбоев, конкуренции, больших объёмов
  или поведения Zapier.
- Через deployed HTTPS API проверены health, auth и стабильность трёх OpenAlex ID между
  двумя последовательными запросами. Это ещё не проверка scheduler/deduplication Zapier.
- `zapier-platform validate` проверяет структуру. Оставшиеся advisory warnings про
  dynamic dropdown у ID-полей сознательно приняты: эти значения должны маппиться из
  trigger, а не выбираться из потенциально огромного списка. Warning для API key остаётся,
  потому что private demo не имеет публичной страницы управления ключами.
- `npm audit --omit=dev` сообщает GHSA-hmw2-7cc7-3qxx в транзитивном
  `form-data@4.0.5`, который жёстко зафиксирован текущим Zapier Core 19.1.0.
  Интеграция не создаёт multipart forms и не передаёт пользовательские filenames,
  то есть известный уязвимый путь здесь не используется. Автоматический fix не
  применён: npm предлагает несовместимый downgrade Zapier Core до 10.2.0.
- Zapier Free: 100 tasks/month, polling раз в 15 минут, Zaps только trigger + action.
- Private integration на Free/Professional ограничена 100 вызовами за 60 секунд
  суммарно по пользователям владельца.
- Polling возвращает только первую страницу (до 100 новейших записей), как требует
  модель deduplication Zapier. Если между poll появится более 100 совпадающих works,
  часть событий может быть пропущена.
- Volume, concurrency, webhook redelivery и multiple-instance delivery не проверены.
- Webhook delivery сейчас best-effort: неуспешный target не откатывает идемпотентный
  upsert. Durable delivery queue не реализована.
- Резервное копирование PostgreSQL на VPS пока не настроено. Для synthetic demo это
  допустимо, но потеря volume уничтожит сохранённые demo works и review ledger.
- OpenAlex — внешний сервис со своими лимитами и изменяемой доступностью.
