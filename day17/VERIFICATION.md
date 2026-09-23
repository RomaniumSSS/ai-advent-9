# Проверка Day 17

Дата: 23.09.2026. Baseline: `b37d97b38618d4699e03e337e7390a35430831d6`.
Frozen SPEC SHA-256:
`50d920e7696f798e8a9a97af0dd569dac68434373f6718157707887eb2b63340`.
Среда: macOS arm64, Python 3.12.12, MCP SDK 2.2.0, OpenAI SDK 3.6.0,
jsonschema 4.26.0, Node 24.11.1.

## Результат

- Все executable `day17/test_*.py` прошли, включая настоящий MCP SDK protocol,
  fault injection, FSM races, audit boundaries и read-only Git snapshot.
- Все исходные `day15/test_*.py` и `day16/test_*.py` повторно прошли; Day 15/16
  не изменялись.
- `node --check`, Python compile check, `git diff --check` и secret scan прошли.
- Desktop 1280×800, tablet 768×1024 и mobile 375×812 проверены в браузере;
  browser console: 0 errors, 0 warnings.
- Real-provider probe: `tool_choice=auto`, модель сама выбрала
  `get_recent_commits(limit=3)`, один реальный MCP execution совпал с независимым
  `git log`, LLM2 использовал observed IDs, Git snapshot не изменился.
- Видео: 35,56 с, 1440×900, H.264, без аудио; проверены пять кадров.

## Live evidence

Probe: [machine report](results/live-probe-01/report.json) и
[human summary](results/live-probe-01/report.md).

- trace: `provider_initial → mcp_execution → provider_final`;
- provider calls: 2; MCP executions: 1;
- prompt/completion: 3450/236 tokens;
- reported cost: $0.00024948;
- exact observed commit-ID sequence совпала с независимым Git oracle.

Comparative evaluation:
[machine report](results/comparative-evaluation-01/report.json) и
[human summary](results/comparative-evaluation-01/report.md).

| Scenario | Provider | MCP | Result |
| --- | ---: | ---: | --- |
| direct chat | 1 | 0 | direct final сохранён |
| tool success | 2 | 1 | grounded final сохранён |
| tool error | 2 | 1 | raw LLM2 text отброшен, сохранён canonical safe response |

## Acceptance evidence

| Требование | Доказательство | Итог |
| --- | --- | --- |
| Schema из discovery | captured provider payload и protocol test | pass |
| Model-selected request | live probe с `tool_choice=auto` | pass |
| Validation до execution | unknown/arguments/mixed/multiple/missing/duplicate-ID matrix, execution spy = 0 | pass |
| Полный successful observation | malformed/empty/error/identity/field/oracle checks | pass |
| Один bounded tool loop | ordered audit и exact call counts | pass |
| Repeated LLM2 request | linked denial, no execution/LLM3/history | pass |
| FSM freshness | checkpoints и transactional compare-and-commit race tests | pass |
| Mandatory audit | create/LLM1/MCP/LLM2 fault injection fail closed | pass |
| Read-only Git | refs, index и полный worktree до/после | pass |
| Workflow isolation | payload capture и Day 15/16 workflow regressions | pass |
| Реальный E2E | provider + own stdio MCP + independent Git oracle | pass |

## Ограничения evidence

Injected tool-error comparison использует реальную модель, но намеренно подменяет
только execution result после настоящего discovery; transport failure отдельно покрыт
offline boundary tests. GitHub Actions не запускался, потому что ветка не отправлялась
в remote. Human acceptance сдачи не заявляется.
