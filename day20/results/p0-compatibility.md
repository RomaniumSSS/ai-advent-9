# Day 20 — P0: прямой GitHub MCP probe

28.09.2026, macOS arm64, worktree `scylla`, HEAD `8c3aac3`.

- Исходная регрессия: `uv run python -m unittest day19.test_offline
  day19.test_report_evidence -q` → **15 tests, OK** (46,480 с). Day 19 не менялся.
- Python MCP SDK из общего `uv.lock`: **2.2.0**.
- Официальный GitHub MCP: релиз **v1.12.2**, бинарник Darwin arm64, версия
  коммита `85598ba6e1256f7ebf4867b95d63b833c4549264`.
  SHA-256 архива `7e6c5aec43f26b82d3580e77a4ee26872bcd34b48c9a08d0eaef48b5d0563904`
  совпал с файлом checksums того же релиза. Бинарник лежит только в `/tmp`,
  в репозиторий не добавлялся.
- Stdio запуск с `--read-only` и точным набором
  `get_file_contents,get_latest_release,list_issues,search_repositories`.
  `tools/list` возвратил только эти четыре схемы, write tools отсутствовали.
- Через настоящий `call_tool` получен публичный README
  `github/github-mcp-server`. `is_error=false`, `structured_content=None`,
  ответ содержит `TextContent` (81 символ) и `EmbeddedResource` с
  `text/plain; charset=utf-8` (113183 символа).
  SHA-256 текста ресурса:
  `0686b41067fd437abbde4b473c394fe2365e5ad2ae81c21b9f988735359c9666`.
  Дополнительно проверено чтение малого публичного README `octocat/Hello-World`
  через будущий двухсерверный router: текстовый ресурс 13 символов.

Токен GitHub взят из системного хранилища `gh` только в окружение дочернего
процесса MCP; его значение, логи сервера и личные данные в evidence не входят.
Это подтверждает совместимость **выбранного релиза с текущим SDK для этих
вызовов**, но не качество Qwen и не работоспособность Telegram-чата.
