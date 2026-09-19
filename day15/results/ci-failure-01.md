# Первый GitHub Actions run — отказ установки

- Run: https://github.com/RomaniumSSS/ai-advent-9/actions/runs/35450727531
- Commit SHA: `e1108e82acc3d7f1a636a2554753a6a211e73580`
- Результат: `failure` на шаге `Install project dependencies`; тесты не запускались.
- Причина: `pip install -e .` запускает автоматическое обнаружение Python-пакетов,
  а в плоском учебном репозитории есть несколько `dayNN/`. Setuptools отказался
  собирать их как один пакет.
- Исправление: CI устанавливает `uv`, применяет `uv.lock` через
  `uv sync --no-dev --locked` и запускает проверки из созданной среды.

Это ошибка CI-окружения, не свидетельство падения тестов Дня 15.
