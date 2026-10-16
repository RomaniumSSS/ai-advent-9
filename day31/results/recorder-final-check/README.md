# Проверка финального recorder — только офлайн

Изменены только recorder/run_demo.py и docs/run.md; runtime/provider/retrieval
не менялись. Проверка использует отдельный temporary server на свободном порту,
настоящий stdio MCP текущего Git-root и явный длинный контрольный текст без LLM.
8071 не затрагивался; OpenRouter client и платный ledger не создавались.

Команда из корня проекта:

```bash
PYTHONPATH=. .venv/bin/python day31/results/recorder-final-check/check.py
```

Артефакты уже существуют: повторная команда честно откажется перезаписывать их.
Для нового прогона нужны новые имена каталогов в копии проверочного скрипта.

- [Обычный dry-run](normal-dry/manifest.json): 3 новых offline ответа, effective hold=0.
- [Контрольная запись](long-offline-record/manifest.json): 3 новых offline ответа,
  два длинных ответа по 80 нумерованных строк, каждый показан на 3 экранах с
  перекрытием; actual hold=1 s выбран только для короткой проверки обвязки.
  По умолчанию финальная запись удерживает каждый экран 6 s.
- [Отчёт](report.json): ветка и HEAD видимы в том же MCP JSON для всех 3 ответов,
  внутренний scrollTop=146; полный JSON сверяется с API.
- [Видео](long-offline-record/Day31-offline.mp4), [ffprobe](long-offline-record/ffprobe.json):
  H264 1280×1000, 25 fps, 19.92 s, 1 602 017 bytes.
- Просмотрены [первый экран](long-offline-record/01-answer.png),
  [конечный экран](long-offline-record/01-answer-03.png) с видимой последней
  строкой и [MCP result](long-offline-record/01-mcp-result.png) с branch/head.

Полный trace/исходный текст — NN-answer.json, screenshot каждого экрана и
координаты прокрутки — events.jsonl. Настоящее ожидание API не менялось.
Это проверка видимости и записи, не реальная генерация и не финальное видео.
