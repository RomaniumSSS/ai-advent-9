# Day30 delivery harness — independent Astra review

**Overall: APPROVED for one bounded dry3, then record3 only if dry succeeds.** No remaining blocker found in the reviewed capture harness. This is code approval, not live D2/D5 completion, semantic acceptance, or human acceptance.

## Scope and findings

Independently read the actual worktree AGENTS/CLAUDE, current HANDOFF/todo, SPEC D1–D6, full video scenario/runner, associated client/UI, private writer, public receipt/metric shapes and limits. Reviewed Luna's findings and fresh `day30/results/assignment-delivery-preflight.json`.

- Luna's original D3 evidence gap is closed by the fresh preflight artifact: authenticated state plus actual CA/hostname-verified negative auth, Host, Origin and overlength checks on both endpoints. These establish access from this Mac; another physical device remains NOT PROVEN and is not a new submission gate.
- Luna's source-disclosure finding was valid and is now closed in the worktree: immediately after recording `original_opened`, the runner raises `assignment_original_not_opened` if it is false. The earlier screenshot does not create false success: the run then fails and no successful public summary is emitted.
- The exact UI POST response supplies IDs; reuse is rejected against existing private receipts and current steps. The second request must share conversation ID; the third must differ. Terminal done, nonempty answer fields, assignment source labels, two attempted/completed generation calls, matching public/private receipt IDs/status/metrics, budget limits and conversation readback are enforced. The browser follows the existing live UI; no mock/replay response is injected. Busy probing remains a real rejected POST while the first request is active; any unexpected outcome stops the run.
- Python verifies the CA/hostname before the browser; Chromium exception is limited to the supplied certificate SPKI. Token entry is masked, cleared, excluded from the API panel and redacted from captured errors. State/metrics are numerical or controlled service fields in the reviewed runtime. Full receipts/traces/screenshots/raw video remain under a fresh private directory; `save_private` uses atomic mode-0600 writes. Public summary contains no questions, source texts, prompts or full trace. Publication still requires checking the actual artifact and video frames, as specified.
- Record creates a fresh recording context and closes it in finally, preserving raw video on a scenario failure. Successful conversion has no speed filter and removes audio; output must have a single H.264 stream at 1280×1000 and positive duration. Actual readability, visual privacy and playback remain post-record checks.
- Historical profile12 semantic FAIL is retained accurately. Relaxing that archival-summary requirement is the explicit D1–D6 scope clarification, not a model repair or a semantic PASS. No new quality tuning or second-device requirement is introduced.

## Verification and limits

Reviewer used `/usr/bin/python3` (local macOS, offline, no provider calls) to parse the runner and execute its exact `observed_limits` helper extracted by AST. Existing exact12 receipt `eec2af7ce9b5408a8cedf00a0f093499` passes: selection upper bound 2382, observed prompt/output 1423/51; synthesis upper bound 1663, prompt/output 880/239; both context8192/output1024/reserve512. Four synthetic mutations are rejected: missing budget, excessive output, estimated input overflow, observed prompt overflow. The final worktree source-open guard was structurally verified. An initial reviewer check used an imprecise error-string spelling supplied in a message and failed; direct code/AST verification confirms the correct `assignment_original_not_opened` guard.

Root reports and the fresh artifact records 151 offline tests, 30.887 s, OK, with mock/loopback and no Ollama inference; the reviewer did not rerun the full suite or live network checks. Root separately verifies unchanged runtime/index against profile12 baseline and the installed model digest. No repository edits, inference, shared locks, service mutations or live browser run were performed by this reviewer.

Pending execution evidence: dry3; new record3 only after successful dry; final receipt/conversation readback; ffprobe, frames, playback and privacy review; final public manifest/secret scan; GitHub remote readback, Drive sharing/playback and spreadsheet save/reload/readback. Run success remains bounded by the SPEC stop-on-first-runtime/protocol/privacy-failure rule, with six accepted requests total and no retry. Human acceptance remains pending.

Final reviewed `day30/video/run_demo.py` SHA256: `90403c939229097d1dffd78a2743549259eb9c6dc47d053756b7aa264ced0949`.
