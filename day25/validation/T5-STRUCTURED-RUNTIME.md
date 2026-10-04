# Structured runtime integration — offline evidence

Implementation integrated after run04; no fifth live run, provider or SSH calls.

## Runtime contract

- `typed-evidence-v1` adds optional typed attributions and structured comparison rows to the existing answer/sources/quotes envelope. Ordinary non-comparison answers retain the existing flow.
- An explicit request to compare requirements with discussions requires two typed quoted sides, or the separate `insufficient_context` branch. Comparing assignment days alone does not require a discussion source.
- Source/day/message bindings and quotes resolve against the actual transmitted snapshot and the same validated single-member part. References must also appear in validated sources/quotes. Free explicit machine IDs are rejected in displayed narrative fields, including aspect, analysis, reason and quote.
- `insufficient_context` is terminal but not successful: validation.valid=false, structure_valid=true. It cannot be upgraded to verified by changing status. No automatic retry.
- Terminal and read guards check confirmed transmission and exact attempted/transmitted IDs. New UI metadata is reconstructed from validated raw response and snapshots rather than trusting persisted display metadata.
- Old Day25 v1 results remain readable and are labelled as using the previous contract. They are not retroactively certified or rewritten.
- UI uses text nodes for metadata, narrative and quotes. Public-only filtering covers transmitted snapshots as well as retrieval/archive material.

## Evidence

Environment: macOS, Python 3.14, Node 24.11.1; Chromium 153 through temporary Playwright venv/cache.

- `python3 -m unittest discover -s day25/app -q`: **39 PASS** (4.467 s). Includes 33 existing regressions, five structured runtime tests and one HTTP test.
- `python3 -m unittest discover -s day25/validation -q`: **15 PASS** (0.015 s): eight preparation checks and seven isolated prototype checks.
- `node --check day25/app/app.js`: PASS.
- `check_structured_ui.py`: actual DOM renderer in offline Chromium, desktop 1280 and mobile 390; no horizontal overflow, injected HTML rendered as text, no script execution; insufficient branch labelled unfinished. No API requests. Screenshots/report stay in `day25/private/structured-runtime-ui`.
- Saved all7/all10 are read only: all7 false textual ID and wrong typed binding rejected; correct day22→4154 accepted. all10 missing structured comparison rejected; synthetic two-sided quoted comparison accepted structurally. These positive outputs are synthetic, not semantic provider acceptance.
- HTTP verifies derived metadata, no extra generation on archive refresh, and denial of a record containing a private transmitted snapshot. Legacy record byte content remains unchanged.

## Remaining limits

**Semantic analysis NOT PROVEN.** Typed evidence proves attribution, quote membership and presence of both sides, not that prose accurately interprets or meaningfully compares them. Explicit-ID recognition is a bounded syntax check, not complete linguistic fact detection. A provider must emit the revised schema correctly; no revised provider run has occurred. Existing live01–04 verdicts and raw evidence remain unchanged.
