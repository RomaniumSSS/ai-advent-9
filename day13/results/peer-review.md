# Контекст дня 13 и проверка чужих реализаций

Дата проверки: 17.09.2026. Рассматривались только задание 13 и указанные Романом
участники. Таблица Challenge выгружена как CSV; репозитории проверены по их
актуальным публичным веткам.

| Участник | Результат |
| --- | --- |
| Артём Томилов (`duplesh`) | ветка `day13`, типизированная FSM и перебор переходов |
| Виталий Гуков (`vitaly_gukov`) | JSON persistence, CLI, task state в prompt |
| Vladimir Stroganov (`vlastro`) | публичного day13 в проверенных ветках нет |
| Илья (`ilushkius`) | отдельные model/store/manager, unit/integration/e2e tests |
| Petr (`hm_petr`) | C# FSM, схемы state, тесты и отчёт |
| Роман (`roma_minsk`) | ветка `task-state-machine`, stage/status раздельны, blocked и completed steps |
| Юля (`novikova_yuliya`) | публичной ветки/папки day13 нет |
| Игорь Седой (`arnyigor`) | SQLite, optimistic version, audit events, restart test |
| Иван Щитов (`ivanshchitov`) | очередь задач, сохранение перед операцией, pause boundary |
| Roman Sokk (`resokk`) | Telegram bot, SQLite state/todo/summary и tool-driven transition |
| Xenia (`XeniaXS`) | FSM в working memory, controlled transitions, clear/restart acceptance |

Выводы, перенесённые в нашу реализацию:

1. Этап и пауза — ортогональные поля.
2. Код, а не LLM, владеет таблицей переходов.
3. Для «без повторных объяснений» недостаточно prompt: нужен durable state и
   проверка новым экземпляром агента с пустой историей.
4. State должен содержать не только имя этапа, но и точный шаг, ожидаемое
   событие и уже полученные артефакты.
5. Журнал и версия делают ошибки переходов наблюдаемыми и защищают от stale
   write — это добавлено поверх общего минимума сдач.
