# Run06: three NOT PROVEN — bounded offline repair

No provider/SSH/budget changes; run01–06 raw/verdicts unchanged. Semantic success is NOT PROVEN.

## Refusal

Run06 all11 has empty sources/quotes and three numbered points, with exact refusal prefix only in point3. It stays unverified: searching for a prefix anywhere would incorrectly promote arbitrary preceding assertions. `refusal_text` accepts the existing exact prefix at the beginning of answer or first list point, requires clarification and source-free output. Citation/role/unknown-field validators remain strict. Prompt explicitly puts refusal prefix in the first point when using a list. Offline full Service rejects unchanged saved output and accepts a synthetic first-point refusal; sources invalidate this refusal path. No automatic rewriting or display recovery of old raw.

## Public9 referent

Separate bounded generation `continuation_reference` identifies the nearest same-task-version user request about a quotation, only for an actual demonstrative followup. It does not replace search query or sources, and tells the model to verify all claims against fresh RAG. Explicit current day/date disables the hint. Other scope, obsolete task version, and task-reference-only questions do not borrow a quotation referent. Public8→9 saved context/envelope tests confirm the intended nearest quotation rather than an older SQLite choice. Correct model interpretation remains NOT PROVEN.

## All4 retrieval

Saved top20 has no discussion containing `чанк|chunk`; reranking these candidates cannot recover the missing material. For explicit discussion + chunk-size/length questions, the existing single `retrieve` scans its already scored, temporally filtered frozen input for discussions containing both topic markers. At most5 lexical topic candidates are added/prioritized after explicit assignment matches. Existing score threshold, top5 selected limit, byte limits, supplied scope, and date filtering stay active; no extra embedding/provider call. Trace exposes topic_candidates/topic_reason.

Synthetic target below vector top20 is recovered; ordinary queries do not use this expansion; low-score target remains rejected, assignment source is not treated as discussion, excluded dates stay excluded. This proves bounded algorithm behavior, not that the actual frozen archive has suitable discussion or that its interpretation is correct. Real recall remains NOT PROVEN.

## Verification

macOS/Python3.14:45 app tests PASS (4.718s),15 validation PASS (0.015s); py_compile and diff-check PASS. Two new tests cover full Service refusal, saved contexts/envelope, isolation/version/date negatives, lexical retrieval and bounds. Runtime changes: task_contract.py, service.py, conversation.py, retrieval.py; test_structured_runtime.py. Current v3 archive statuses remain untouched; no retroactive acceptance of all11.

Private runtime snapshot: day25/private/run06-offline-repair/SNAPSHOT.json. Next step is independent local gate; no additional live authorization inferred.
