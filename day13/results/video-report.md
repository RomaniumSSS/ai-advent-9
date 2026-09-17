# Проверка видео

Файл: `day13/demo/day13-task-state.webm`.

- контейнер WebM, видео VP8, 1280×800, 25 кадров/с;
- длительность 49,68 с, размер 2 782 909 байт;
- аудиодорожки нет;
- полное декодирование через ffmpeg прошло без ошибок;
- контактный лист ключевых кадров просмотрен вручную.

В кадрах видны: online-badge DeepSeek/OpenRouter, настоящий planning proposal,
пауза и новый экземпляр агента с сохранённой границей, затем подтверждённые
пользователем `planning → execution → validation → done` и полный журнал событий.
В отдельной чистой БД зафиксирован ровно один provider call: 518 input + 610
output tokens, reported cost `$0.0000852`; итоговая FSM — `done`, версия 6.
Ошибок JavaScript и `pageerror` нет.

SHA-256 видео:
`52b0b96030d18062512b8a8ce9d87d43dfc1aeb6be8ffbe94fb7ccd9435c9fb0`.
