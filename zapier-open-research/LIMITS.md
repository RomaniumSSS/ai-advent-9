# Limits and verification boundary

- Интеграция private и не публиковалась в Zapier App Directory.
- API и PostgreSQL развёрнуты на личном VPS; версия integration `1.0.0` загружена в
  Zapier как private, адрес HTTPS API задан через version environment.
- В Zapier account создана API-key connection и два опубликованных двухшаговых Zap:
  polling → upsert и REST hook → ledger action. Скриншоты Zap и успешных live runs
  сохранены. Zap с Email/Slack-уведомлением пока не создан: адресат не выбран.
- Polling Zap v1 выполнил реальные задачи, но дал нерелевантные результаты с 0/40
  title relevance; API исправлен. Опубликованный v2 Zap сейчас выключен: Zapier HTTP
  logs показали GET `/v1/works` с `per_page=325` и статусом 422. В editor при
  включении отображался «partner issue», ручной Run — «Cannot test a paused Zap».
  Настройку Results Per Poll нужно исправить на ровно `3` и перепубликовать.
- Метаданные публикаций реальные и получаются из OpenAlex CC0. Saved works, notes,
  review scores и API account — демонстрационные данные.
- Automatic score — прозрачный приоритет для чтения по title match, возрасту,
  открытому доступу и citation count. Он не измеряет научное качество, истинность,
  peer-review status или соответствие конкретному исследовательскому протоколу.
- Локально проверены API contract-сценарии и Zapier harness-сценарии; точное число
  выводится тест-раннером. Это не проверка сетевых сбоев, конкуренции, больших объёмов
  или поведения Zapier.
- Через deployed HTTPS API проверены health, auth и одинаковые три OpenAlex ID между
  двумя последовательными запросами после фильтра. Первая версия polling Zap выполнила
  один фактический пакет запусков; две автоматические итерации scheduler после правки
  не проверены, поэтому live deduplication нельзя считать доказанной.
- REST-hook Zap получил настоящий webhook и выполнил action. Replay этого Zap сохранил
  один ledger entry для исходного Event ID; повторный результат показал `replayed: true`.
  Это проверка replay через Zapier runtime, но не сетевых автоповторов при сбое.
- `zapier-platform validate` проверяет структуру. Оставшиеся advisory warnings про
  dynamic dropdown у ID-полей сознательно приняты: эти значения должны маппиться из
  trigger, а не выбираться из потенциально огромного списка. Warning для API key остаётся,
  потому что private demo не имеет публичной страницы управления ключами.
- `npm audit --omit=dev` сообщает GHSA-hmw2-7cc7-3qxx в транзитивном
  `form-data@4.0.5`, который жёстко зафиксирован текущим Zapier Core 19.1.0.
  Интеграция не создаёт multipart forms и не передаёт пользовательские filenames,
  то есть известный уязвимый путь здесь не используется. Автоматический fix не
  применён: npm предлагает несовместимый downgrade Zapier Core до 10.2.0.
- [Zapier Free](https://help.zapier.com/hc/en-us/articles/32337438839565-What-s-included-in-Zapier-s-Free-plan):
  100 tasks/month, polling раз в 15 минут, Zaps только trigger + action.
  Task Usage на 15.09 показывал 24 задачи: 22 polling и 2 hook.
- [Private integration](https://docs.zapier.com/integrations/quickstart/private-vs-public-integrations)
  на Free/Professional ограничена 100 вызовами за 60 секунд суммарно по
  пользователям владельца.
- Polling просматривает первую страницу (100 новейших OpenAlex works), а при query
  пропускает только заголовки с title relevance ≥20/40. Если между poll появится более
  100 совпадающих works, часть событий может быть пропущена.
- Volume, concurrency, webhook redelivery и multiple-instance delivery не проверены.
- Webhook delivery сейчас best-effort: неуспешный target не откатывает идемпотентный
  upsert. Durable delivery queue не реализована.
- Резервное копирование PostgreSQL на VPS пока не настроено. Для synthetic demo это
  допустимо, но потеря volume уничтожит сохранённые demo works и review ledger.
- OpenAlex — внешний сервис со своими лимитами и изменяемой доступностью.
