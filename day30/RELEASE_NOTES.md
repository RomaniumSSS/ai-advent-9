# Day30 — release notes

Домашняя локальная LLM доступна через защищённый HTTP API и браузерный чат.
Новый вопрос создаёт request/conversation IDs; клиент видит фазы работы,
ответ, времена и токены. Исходные документы раскрываются отдельно.

Сервис на Mac M2/16 GiB использует profile12 Qwen3 8B Q8 и существующий индекс:
две стадии generation,think=false,context8192,max output1024 каждая, без retry.
TLS, bearer,Host/Origin allowlist; максимум500 символов вопроса,6 принятых запросов
за60с, один активный inference с409 busy. Оба context budget проверяются до
вызова, фактический prompt token count — после; история хранится приватно.

Выполнено:151 offline тест/OK30.887с на `/usr/bin/python3`3.9.6;
реальные main/demo LAN HTTPS,auth401,invalid token401,501chars400,Host/Origin403.
Dry/record: **PASS/PASS**, 3/3
новых assignment-ответов, включая follow-up. Новое видео без аудио/ускорения:
**PASS — ffprobe/кадры/воспроизведение/privacy**,1280×1000,517.0 сс.
Числа и evidence — [RESULT](RESULT.md); доставка — [DELIVERY](DELIVERY.md).

Дополнительный архивный пересказ имеет сохранённый profile12 semantic FAIL.
Его точность/полнота не объявляются исправленными; это ограничение исключено
из gate исходного задания уточнением пользователя. Доступ со второго физического
устройства NOT PROVEN;429 проверен offline, не нагрузочным live-прогоном.
Код требует локально настроенных моделей, источников/индекса, TLS и env;
веса, private корпус, ключи и полные traces в публичный пакет не входят.
