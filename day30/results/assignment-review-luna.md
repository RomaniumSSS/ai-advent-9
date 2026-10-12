# Day30 delivery review — Luna

**Overall: APPROVED (recording harness code review).** Fresh D3 endpoint evidence is present, and the source disclosure is now enforced before the runner can report a successful step. Live dry/record execution and human acceptance remain pending.

## Findings

- **[D3 resolved by fresh evidence]** `day30/results/assignment-delivery-preflight.json` — CA+hostname verification and actual checks are recorded for both main and assignment endpoints: missing/bad bearer `401 unauthorized`, overlength `400 invalid_request`, disallowed Host `403 forbidden_host`, and disallowed Origin `403 forbidden_origin`. Both endpoints report `active=false`; model is Qwen3 8B Q8. The artifact records the 151-test offline suite separately and states that it used mock/loopback without Ollama inference.

- **[D5 finding resolved]** `day30/video/run_demo.py:168-169` — after the click, the runner records `original_opened` and now raises `assignment_original_not_opened` if the disclosure is still closed. Confirmed in the current worktree. The screenshot is taken before this assertion, but a failed step propagates to run failure and no successful MP4/public summary is produced.

## Reviewed behavior

The runner captures the request ID and conversation ID from the exact accepted `/api/chat` response, rejects reused IDs, checks that the first/follow-up share a conversation and the third uses a new one, and validates terminal `done`, non-empty answer fields, assignment-only sources, actual generation call counts, observed context/output budgets, and API conversation readback. It reads the private receipt by the captured request ID, compares status/IDs/metrics with the public API response, and writes private artifacts under a fresh mode-0700 output directory using `save_private`.

The record path uses a new Playwright recording context, closes it in `finally`, converts the resulting video without audio or speed changes, and requires a single H.264 stream at 1280×1000 with positive duration. Credential entry is a password field, is cleared before requests continue, and is not placed in the visible API panel. Private traces are read only to derive allowlisted budget values and are saved only in the private output; the public summary omits prompts, source text, and trace. The semantic FAIL for the historical profile12 answer remains accurately disclosed as a known limitation, not treated as an assignment gate.

## Verification performed

- Read project `AGENTS.md`, current `todo.md` / `HANDOFF.md`, SPEC D1–D6 clarification, the full scenario and runner, and the local review skill.
- Inspected the worktree status. `day30/` is untracked in this worktree; the runner and scenario are the delivery harness under review. No repository files were changed.
- Ran bounded helper-level checks with the worktree Python: `observed_limits` accepted a valid synthetic pair of stage budgets and rejected an over-limit input. Then applied it to the exact profile12 receipt `day30/private/service/state/request-eec2af7ce9b5408a8cedf00a0f093499.json`; both stages passed. Selection: context 8192, max output 1024, upper bound 2382, observed prompt/output 1423/51. Synthesis: context 8192, max output 1024, upper bound 1663, observed prompt/output 880/239. The receipt has per-stage `options` entries. No inference, service request, browser run, or shared flock was used.
- The root-reported full offline suite result (151 tests, OK) was not rerun here. Fresh D3 endpoint checks were reviewed in `assignment-delivery-preflight.json`. Compiled the current `run_demo.py` source in memory: syntax OK. No dry or live recording was performed, so D2/D5 runtime outcomes remain pending.
