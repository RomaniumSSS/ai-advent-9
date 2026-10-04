# Run05 bounded offline repair

No provider/SSH calls. Historical run01–05 raw and verdicts unchanged. New model behavior and semantic correctness remain NOT PROVEN.

## Changes

- Ordinary assignment-only comparison omits the typed discussion-comparison template. Requirements-vs-discussions retains strict two-sided typed evidence or insufficient_context. Public4 saved response replay, with only its invalid optional comparison field removed in memory, passes full fake Service; the original response remains rejected and unchanged.
- all1/all5/all10 each finish_reason=length and completion_tokens=2048. Partial JSON lengths5975/5312/6045 characters; all10 contains6 typed-side quote fields plus global quotes. Contract now requests at most2 aspects, short exact excerpts, no redundant typed attributions and no full-document quotes. This reduces requested duplication without changing schema/citation validators or 2048 token ceiling. Reduction in actual provider output is NOT PROVEN.
- Active maximum-points constraint now requires an explicit numbered/bulleted answer list within the limit. Saved all7 fails; synthetic three-point grouping passes, four-point list fails. Exact source-free model refusal remains a short paragraph under its existing strict prefix/clarification contract; offline full Service refusal passes.
- public12 prompt explicitly distinguishes stored input data, returned tool result and completed project. No heuristic semantic fact validator was added: output meaning needs independent evaluation.
- public9 query already anchored the immediately preceding quote correctly. Prompt now requires clarification or conditional alternatives when a pronoun has multiple plausible referents; this is guidance, not semantic proof.
- all4 diagnosed old task days contaminating a complete named discussion-topic query: selected four assignments and personal note, while15 discussion candidates existed. Named requests such as “Найди обсуждения курса о размере…” now search their own current question; they do not inherit old day21–24 from a local “этот тезис”. Exact current day/date precedence retained. No live retrieval verification occurred, so recovered relevant discussion is NOT PROVEN.
- New persisted results use day25-chat-v3. Existing v1/v2 answers stay readable as historical contract results, without current revalidation or disk mutation. UI labels historical contract and omits recertified structured view. Guards apply to new v3 only.

## Offline evidence

macOS/Python3.14/Node24.11.1, temporary Playwright Chromium153.

- 43 app tests PASS: saved failure replay, full Service ordinary comparison and refusal, point-limit negatives/positive, actual generation envelope, exact named discussion query and current day override, v2 archived bytes unchanged, prior T1–T4/structured tests. Independent gate also found and verified two narrow fixes: an explicit reference to the current goal keeps task state in the dependent query; a date followed by a sentence-ending period has priority over old task context, while six malformed partial dates are rejected.
- 15 validation tests PASS (0.015s).
- Node syntax and git diff-check PASS.
- Actual renderer Chromium desktop/mobile PASS, script injection rendered as text; API/provider requests0.

Changed runtime: task_contract.py, structured_evidence.py, conversation.py, service.py, app.js. Compatibility in scenario_runner.py and check_structured_ui.py; targeted test_structured_runtime.py. No caps/budget/provider changes. Independent local gate PASS; no new live execution is implied.
