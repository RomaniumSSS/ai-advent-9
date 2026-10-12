# Day30 — видео

Живая assignment-only демонстрация: **PASS — ffprobe/кадры/воспроизведение/privacy**.
Видео: [Day30-live.mp4](https://drive.google.com/file/d/1qZXTzqn9nUa3OL_yNYksOahMt_RivTZY/view?usp=sharing). Новый MP4:517.0 сс,1280×1000,H264/yuv420p,
без аудио и ускорения. Evidence записанного прогона:[Record3](results/assignment-record.json).
Проверены ffprobe, кадры начала/ответов/конца и воспроизведение:[Video check](results/assignment-video-check.json).

Один [сценарий](SCENARIO.md) в `dry` и `record`: Day21,продолжение в том же
разговоре,Day24 в новом; каждый accepted request ID наблюдается в браузере
и сверяется с API/private receipt. Видны реальное ожидание,ответы,метрики,
раскрытие оригиналов и отдельно обозначенные настоящие API проверки401/400/409.
Проверки429,Host/Origin и restart относятся к отдельным evidence в RESULT.

Команды из корня репозитория для заранее подготовленного assignment env.
Ollama и assignment service уже должны работать; запись их не перезапускает:

```sh
/usr/bin/python3 day30/deploy.py status --env day30/private/demo.env \
  --label org.ai-advent.day30.demo
uv run --offline --no-project --with playwright python day30/video/run_demo.py \
  --mode dry --env day30/private/demo.env \
  --base-url https://192.168.0.100:8081 --cafile day30/private/server.crt \
  --output day30/private/video/dry-20261012-01
uv run --offline --no-project --with playwright python day30/video/run_demo.py \
  --mode record --env day30/private/demo.env \
  --base-url https://192.168.0.100:8081 --cafile day30/private/server.crt \
  --output day30/private/video/record-20261012-01
```

Каждый запуск требует новый каталог и создаёт три новых inference; повторный
dry+record расходует ещё шесть принятых запросов. Для online установки Playwright
нужны установленные Chromium и ffmpeg; флаг `--offline` подходит для уже готовой
среды. Каталог/env/cert paths относятся к настроенному локальному серверу;
на другой машине оператор задаёт собственные пути и LAN IP.

Токен только в password-поле, немедленно очищается. Chromium доверяет SPKI
указанного сертификата после Python CA+hostname preflight. Контекст закрывается
в `finally`; raw WebM сохраняется даже при runtime ошибке. Unknown/error/timeout,
неоткрытый оригинал или неподтверждённый budget останавливают сценарий.

Raw video,полные receipts/traces/screenshots остаются private; публикуется
проверенный MP4 и ограниченная сводка после privacy review. Запись новых ответов
не является проверкой смысловой полноты. Старый private semantic FAIL сохранён;
фактические ограничения — в [RESULT](../RESULT.md).
