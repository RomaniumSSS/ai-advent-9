# Day 17 MCP tool calling — change contract

## Objective

Реализовать frozen SPEC через утверждённый Implementation Plan: обычный chat может
выполнить максимум один read-only MCP `get_recent_commits`, вернуть observation в LLM2
и сохранить только проверенный final response; FSM workflow остаётся tool-disabled.

## Authoritative inputs

- SPEC: `docs/superpowers/specs/2026-09-23-day17-mcp-tool-calling.md`
- PLAN: `docs/superpowers/plans/2026-09-23-day17-mcp-tool-calling.md`
- baseline: опубликованный `day16/` на текущем HEAD `b37d97b`

## Authorized scope

- создать самостоятельный `day17/` и Day 17 documentation/evidence;
- добавить собственный stdio Git MCP server, schema-aware client, chat-only tool loop,
  validation, observation normalization, audit schema/migration и приложение;
- добавить offline/protocol/application/regression/live-provider проверки;
- выполнить один bounded provider probe и comparative evaluation после offline green.

Не входят: изменения Day 15/16, SPEC, multi-tool loop, side effects, approvals,
deploy, commit, push и внешняя сдача.

## Execution stages and gates

1. **Foundation:** Day 17 baseline, Git MCP server, discovery/call boundary. Gate:
   real SDK protocol tests и независимый Git oracle.
2. **Harness:** provider parser, validation, one-tool loop, FSM guards, fail-closed final.
   Gate: deterministic success/failure/race matrix.
3. **Durability/application:** schema v7 audit, atomic finalization, Web/CLI trace. Gate:
   migration, fault injection, restart и HTTP integration.
4. **Regression:** полный Day 17 offline suite плюс исходные Day 15/16 suites,
   compile/JS/diff/secret checks.
5. **Provider probe:** реальная модель сама выбирает tool; собственный stdio server
   читает Git; result независимо сверяется; Git остаётся неизменным.
6. **Comparative evaluation:** сопоставить direct chat, tool success и tool failure по
   trace correctness, grounding, calls, usage, latency и false-success behavior.

Зависимый этап не начинается, пока его gate не подтверждён. Mock evidence не закрывает
provider probe. Платный probe не повторяется без конкретной технической/quality причины.

## Completion evidence

- executable offline reports и исходные regression suites зелёные;
- ordered audit подтверждает ≤2 provider calls и ≤1 `tools/call`;
- real-provider report доказывает model-selected tool и совпадение с Git oracle;
- comparative report отделяет измерения от выводов;
- README/VERIFICATION описывают фактически проверенную среду и ограничения.

## Stop conditions

Остановиться и запросить решение только если требуется новый scope, внешний side effect,
недоступны credentials для разрешённого probe либо фактический provider не поддерживает
необходимый tool-call protocol и безопасного in-scope обхода нет. Любой частичный успех
без обязательного audit не считается завершением.
