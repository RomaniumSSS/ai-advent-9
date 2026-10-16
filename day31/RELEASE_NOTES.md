# Day31 — DevHelper

16.10.2026. Подготовлены работающий код и новая живая запись; независимая
проверка видео координатором PASS. Git-публикация — у координатора.

- Браузер и CLI `/help` используют один обработчик: FTS5 по README/docs →
  настоящий read-only stdio MCP → один ответ DeepSeek V4.1 Flash/DeepInfra.
- Видны источники со строками/хешем, текущая ветка/HEAD и фактические этапы.
  Полная локальная схема и проверки source IDs сохранены; wire-схема совместима
  с провайдером. Fallback/retry/автовыбора модели нет, неизвестная стоимость — null.
- **44/44 офлайн PASS**; финальная конфигурация одобрена Luna → Astra.
  [Живой core](results/deepseek-final-core-20261016/summary.json): 7 ответов без
  runtime errors. Q2 PARTIAL из-за `.run(stdin)`; JSON-пример T3 — псевдо-JSON.
  Source guards не заменяют смысловую проверку; 6/6 gold PASS не заявляется.
- Новые [dry-run](results/deepseek-live-dry-20261016/manifest.json) и
  [record](results/deepseek-live-record-20261016/manifest.json): `ok/ok/unknown`,
  разные trace/receipt, настоящий Git и источники, JS errors=0.
- [Видео 1:17.44](video/Day31-live.mp4), H264 1280×1000/25 fps, 2 794 853 bytes.
  Полное декодирование без ошибок; просмотрены 6 кадров из самого видео, включая
  источник и MCP branch/head. Координатор независимо подтвердил читаемость всех
  6 кадров и конец на 76.5 s без чёрного кадра. Canonical/original SHA совпали.
- Сравнение недоступных ответов не даёт рейтинга: GLM5.3 length/HTTP429;
  Qwen первоначально HTTP404 с подтверждённым ZDR guardrail. После явного
  разрешения пользователя отключён только ZDR «All other models»: проверены
  [доступность](results/qwen-availability-after-zdr.json) и
  [успешный API probe](results/qwen-after-zdr-probe.json). Один provenance-чанк
  дал честный unknown; качество Qwen **NOT PROVEN**, это не парное сравнение.
  Исторические неудачные попытки сохранены.

По актуальному [финальному snapshot](results/budget-final.json), сверённому
read-only с ledger: известно $0.0163579524, неизвестные расходы удерживают
$0.45713269; общий учёт $0.4734906424 из $0.50, остаток $0.0265093576.
Dry+record добавили $0.0006702528, новый Qwen probe — $0.003622 известного usage.cost.
Неизвестные резервы не считались бесплатными и не освобождались.
Подробности, доказательства и ограничения — [RESULT](RESULT.md).
