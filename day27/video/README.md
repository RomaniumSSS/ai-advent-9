# Day27 — живая запись

Для сдачи: [Day27-live.mp4](Day27-live.mp4), 42.88 с, 1280×1000, H.264, без звука.
[Видео на Google Drive](https://drive.google.com/file/d/1xa1AKj_OgkX1O-xQU495QIgVuvs3UFLM/view?usp=sharing)
загружено в папку AI Advent; основной владелец и доступ Viewer по ссылке проверены.
Это копия проверенного [record-1/live.mp4](runs/record-1/live.mp4).
Исходный [WebM](runs/record-1/live.webm) сохранён без ускорения.

Ролик записывает viewport изолированного Chromium во время трёх новых запросов
к приложению → Ollama → `qwen3:8b`. Личные окна и профиль Chrome не использовались.
Сухой прогон и браузерные фикстуры в ролик не включены.

Порядок: три шага создания чата → вопрос о названии «Маяк» из предыдущего
сообщения → «Новый чат» → 17 + 25. Все ответы и метрики видны.
Первый ответ описывает обычный чат и не упоминает интеграцию LLM;
это свойство реального ответа, текст не редактировался.

Скрипт и команды: [run_demo.py](run_demo.py), [основной README](../README.md).
Сценарий: [SCENARIO.md](SCENARIO.md).
Метрики и фактические payloads: [results.json](runs/record-1/results.json).
Подтверждение загрузки: [drive-upload.json](../results/drive-upload.json).
Проверка файла: [ffprobe.json](runs/record-1/ffprobe.json),
[декодирование и просмотр кадров](runs/record-1/video-checks.json).
Новая запись всегда создаёт новый каталог; старые дубли не перезаписываются.
