# Day 17 implementation validation

Дата: 23.09.2026. Итог: **SPEC SATISFIED**.

## Baseline

- SPEC SHA-256: `50d920e7696f798e8a9a97af0dd569dac68434373f6718157707887eb2b63340`.
- Проверенный HEAD baseline: `b37d97b38618d4699e03e337e7390a35430831d6` плюс рабочий Day 17 diff.
- Manifest SHA-256 проверенного implementation state (до добавления этого отчёта):
  `886ce675e8b5df9b1462b83e3374552b29789591314ca88886570fe06a041036`.
- Среда: macOS arm64, Python 3.12.12, MCP SDK 2.2.0, OpenAI SDK 3.6.0,
  jsonschema 4.26.0, Node 24.11.1.

## Evidence

- **T17:** все `day17/test_*.py`, 50 итоговых assertions, exit 0.
- **T15/T16:** исходные suites, 34/43 assertions, оба exit 0; директории без diff.
- **P:** настоящий MCP SDK discovery + `tools/call` сверены с независимым Git oracle.
- **L:** real-provider [probe](live-probe-01/report.json): auto tool choice, trace 2/1,
  exact Git IDs, grounded final, unchanged Git.
- **C:** real-provider [comparison](comparative-evaluation-01/report.json): direct,
  success и injected execution error, exact audit counts, false success отсутствует.
- **V:** browser 1280×800, 768×1024, 375×812; 0 console errors/warnings;
  [live video](../demo/day17-mcp-tool-calling.mp4), 35,56 с, пять проверенных кадров.
- **S:** exhaustive source/config inspection: bounded orchestration, validation,
  workflow isolation, transactional finalization, safe audit summaries.
- **Q:** JS syntax, JSON parsing, diff check, secret scan и no-pycache check прошли.

## Evidence failure model

Ложный green мог возникнуть из mock-only tool selection, сравнения MCP result с тем же
кодом вместо независимого Git oracle, подсчёта audit вместо фактических calls, записи
сырого LLM2 текста после error, TOCTOU между FSM check и commit, неполного Git snapshot
либо проверки Day 17 вместо исходных Day 15/16. Поэтому real provider/MCP evidence,
независимый `git log`, execution spies, fault injection, transactional race, refs/index/
full-worktree snapshot и оригинальные regression suites проверены раздельно.

## Normative matrix

| SPEC item | Observable claim | Evidence | Status |
| --- | --- | --- | --- |
| Goal | Полная user→LLM1→validation→MCP→observation→LLM2 цепочка наблюдаема | L, P | PASS |
| Scope 1 | Tools только в обычном chat | S, T17 | PASS |
| Scope 2–3 | Один собственный read-only Git tool без repo override | P, T17 | PASS |
| Scope 4–5 | Bounded input schema и ordered commit metadata | P, T17 | PASS |
| Scope 6 | Model schema происходит из discovery | T17, S | PASS |
| Scope 7 | Discovery отделён от execution и snapshot reusable | T17, S | PASS |
| Scope 8–9 | ≤2 provider calls и ≤1 MCP execution | L, C, T17 | PASS |
| Scope 10 | Общий ordered logical-turn audit | L, T17 | PASS |
| RB1 | Успешный discovered snapshot предшествует model-visible schema | T17, S | PASS |
| RB2 | Модель выбирает direct final либо tool request | L, C | PASS |
| RB3 | Direct final даёт 1 provider/0 MCP | C, T17 | PASS |
| RB4 | Name/object/schema/local-limit/execution-limit проверены до call | T17, S | PASS |
| RB5 | FSM freshness проверена непосредственно перед MCP | T17 | PASS |
| RB6 | Полный non-empty bounded observation contract | T17, P | PASS |
| RB7 | Linked observation и ровно один LLM2 после result/error | T17, C | PASS |
| RB8 | Повторный LLM2 request denied, без execution/LLM3 | T17 | PASS |
| RB9 | FSM freshness до persistence и atomic compare-and-commit | T17, S | PASS |
| RB10 | Existing response invariants применены к final | T17 | PASS |
| RB11 | Conversation содержит только user/final pair | T17 | PASS |
| RB12 | Audit различает calls/tool/args/status/result и per-call usage | L, T17 | PASS |
| INV1 | Model request не исполняется без harness validation | T17, S | PASS |
| INV2 | Turn limits 1 MCP/2 provider соблюдены | L, C, T17 | PASS |
| INV3 | Tool не меняет Git/files/app/memory/FSM | P, L, T17 | PASS |
| INV4 | Workflow не получает schema/observations/MCP | S, T15/T16, T17 | PASS |
| INV5 | Модель не меняет FSM | T17, T15/T16 | PASS |
| INV6 | paused/done guards во всех четырёх checkpoints | T17, S | PASS |
| INV7 | Изменившийся FSM инвалидирует дальнейшее применение | T17 | PASS |
| INV8 | Текст модели не доказывает внешнее действие | S, T17 | PASS |
| INV9 | MCP observation доказывает только возвращённые Git-данные | S, L | PASS |
| INV10 | Denial/error/timeout/is_error не становятся success | T17, C | PASS |
| INV11 | Каждый LLM1/LLM2 request получает linked result/denial | T17 | PASS |
| INV12 | MCP content трактуется как untrusted data | S, T17 | PASS |
| INV13 | Existing request/terminal/transition/final guards сохранены | T17, T15/T16 | PASS |
| FB1 | Discovery failure: ordinary fallback/Git unavailable, 0 MCP | T17 | PASS |
| FB2 | First provider failure: no MCP/conversation, audit retained | T17 | PASS |
| FB3 | Unknown/malformed/schema/multiple: 0 MCP + linked LLM2 error | T17 | PASS |
| FB4 | Multiple requests получают individual denials | T17 | PASS |
| FB5 | MCP failures дают error observation и safe final | T17, C, S | PASS |
| FB6 | Repeated final request: denial, no LLM3/conversation | T17 | PASS |
| FB7 | Final provider failure не сохраняет conversation | T17 | PASS |
| FB8 | FSM race останавливает остаток turn | T17 | PASS |
| FB9 | Нарушающий final заменяется safe local refusal | T17 | PASS |
| FB10 | Audit failure останавливает следующий шаг и виден caller | T17, S | PASS |
| AC1 | Discovered schema provenance и allowlisted model set | P, T17 | PASS |
| AC2 | Snapshot reuse и обе discovery-failure ветки | T17, S | PASS |
| AC3 | Non-Git direct path 1/0 | C, T17 | PASS |
| AC4 | Successful ordered trace provider→MCP→provider | L, T17 | PASS |
| AC5 | Реальная модель + own MCP + independent Git + grounded LLM2 | L | PASS |
| AC6 | Full result/error contract | P, T17, S | PASS |
| AC7 | Final использует actual observation, unknown IDs blocked | L, T17 | PASS |
| AC8 | Exact ordered audit, per-call usage/cost/counts | L, C, T17 | PASS |
| AC9 | Unknown/invalid gives 0 MCP, linked error, one LLM2 | T17 | PASS |
| AC10 | Multiple requests: 0 MCP, every denial, ≤1 LLM2 | T17 | PASS |
| AC11 | LLM2 repeat: denial/application error/no LLM3/history | T17 | PASS |
| AC12 | MCP error visible, no false Git success | C, T17 | PASS |
| AC13 | First/final provider failure exact counts/no conversation | T17 | PASS |
| AC14 | Durable history has exact user/final pair | T17 | PASS |
| AC15 | Initial terminal and three mid-turn FSM races fail closed | T17, S | PASS |
| AC16 | Real E2E refs/index/full worktree unchanged | L, P, T17 | PASS |
| AC17 | Metadata cannot alter policy, execute another tool/action | S, T17 | PASS |
| AC18 | Audit faults after LLM1/MCP/LLM2 fail closed | T17 | PASS |
| AC19 | Workflow tool-disabled and regressions preserved | T17, T15/T16, S | PASS |
| AC20 | Forbidden final excluded from history/task audit/proposal | T17, T15/T16 | PASS |
| AC21 | Original Day 15/16 guarantees remain green | T15/T16 | PASS |

## Excluded/non-normative scope

Parallel/sequential multi-tool loops, side effects, approval flow, multiple servers,
dynamic installation, workflow tools and FSM graph/model-turn changes are explicitly
out of scope and were not implemented. GitHub Actions and human submission acceptance
were not claimed; absence of remote CI does not weaken the locally required AC21 run.

## Verdict

No applicable item is `FAIL` or `NOT PROVEN`: **SPEC SATISFIED**.
