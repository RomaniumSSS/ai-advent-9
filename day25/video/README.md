# Day25 — видео

## Новая запись2×15

[Day25-session15.mp4](Day25-session15.mp4), **2:58 (178.16sec)**,1280×900,H.264,без аудио. Настоящие15 public сообщений нового сценария: поиск/генерация, цель и ограничения, источники/цитаты, refresh, настоящий restart после6 и отдельный пустой чат. Два public-only сегмента187sec склеены с равномерным ускорением1.05×; вставленных действий/ответов и дополнительных ask нет.15 уникальных public IDs/0all IDs. Независимый privacy/provenance gate PASS, sampled frames и финальный завершённый ответ проверены. SHA256 `9ef07f5c5f93de977a5fa12e0fd6a5a363dde7cc503933f2d427803f88086fab`.

Исходники/manifest/receipts только `day25/private/session15-live-01/fresh-video`. Видео показывает функциональность и реальные ошибки, не доказывает качество полного корпуса: текущий A1FAIL, независимая матрица14PASS/12FAIL/4NP; humanNP. Публикация не выполнена.

## Прежнее видео run07

[Day25-chat.mp4](Day25-chat.mp4),1:39,1280×900,H.264,без озвучки.

Запись настоящего public UI пути run07: создание чата/память задачи,12 новых вопросов со свежим поиском/генерацией, источники и цитаты, refresh; два public-сегмента разделены реальным restart после шестого вопроса. MP4 склеен из этих двух сегментов без новых ask. Это разрешённый public assignment18, не весь корпус.

Optional `scenario_runner.py --public-video-dir <day25/private/...>` записывает только отдельный public-only context, закрывает его доall и при checkpoint. Private output guard, public-only API и origin allowlist сохранены. Default runner не записывает видео. Полный offline dry-run и independent gate проверили2segments/12unique public IDs/0all IDs/extraasks0. Run07 receipt повторил эти результаты; независимый просмотр sampled frames подтверждает свежий search и завершённые ответы.

Исходные сегменты/concat manifest/receipts остаются private/live-fresh-video-07 и private/live-run-07; raw all в видео не входят. Дополнительный saved playback использовал толькоGET,0search/provider и неизменныйledger. Это отдельное доказательство чтения архива.

Видео показывает public пример, не доказывает A1 полного корпуса. Исторический gate run07: A1 NOT PROVEN, A2–A6 PASS, human acceptance NOT PROVEN. Публикация не выполнена.
