# Visual report

Локальная офлайн-панель проверена 17.09.2026 через Python Playwright, потому что
общая MCP Chrome-сессия была занята другим процессом.

| Viewport | document width | Переполнение | Артефакт |
| --- | ---: | --- | --- |
| 1280×800 | 1280 | нет | `viewport-1280.png` |
| 768×1024 | 768 | нет | `viewport-768.png` |
| 375×812 | 375 | нет | `viewport-375.png` |

Вручную просмотрены все три full-page screenshot, конфликтный отказ, безопасное
объяснение и состояние после pause → restart → resume. Иерархия читается,
кнопка отказа заметна, ID и причина не обрезаны, audit показывает `deny` и
`explain`, горизонтального overflow и console/page errors нет.
