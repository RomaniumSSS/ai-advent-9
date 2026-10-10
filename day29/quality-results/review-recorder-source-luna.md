# Independent Luna review: benchmark canonical source IDs

**Verdict: APPROVED (scoped `validate_benchmark` correction).** The recorder now expects the exact canonical source IDs produced by the frozen materializer, while retaining the prior strict receipt, profile, model, index, privacy, and exact-quote checks. I found no defect in this targeted change.

## Snapshot reviewed

- `day29/video/run_full_demo.py` SHA-256: `947477a172d8744b3396e7aa79d0b4a6b178f4ab8a9db2d60458c9495bbd8dc8`
- `day29/core.py` SHA-256: `ffd03a0c5bc659e50783416c469c72d8f79f7d02a7d9a1309208c74875b2e24d`
- `day29/tests/test_full_demo.py` SHA-256: `466ebfd9bc263fde4ea0b604f54b1cba6a7fa2d080e93318917cb3b76670961f`
- `day29/tests/full-demo-benchmark-source-evidence.json` SHA-256: `f3495cf9312ae50a8cb28d816748dffe778a45a234579bb9945def1606d77049`

`core.materialize_references` emits each citation's `source` from the selected chunk's canonical `document_id`; the recorder now requires both `assignment:19` and `assignment:20` for this frozen benchmark scenario. `core.validate_answer` then verifies every source ID against the selected chunk and every quote as an exact substring of that chunk. The validator also retains the public selected-source gate and all prior model/digest/profile/options/index checks. The change is limited to `validate_benchmark` according to the reviewed evidence.

## Checks and evidence limits

- Ran `python3 -m unittest discover -s day29/tests -p 'test_full_demo.py' -v`: **19 passed**.
- New synthetic cases accept canonical source IDs and reject legacy `assignment19`, wrong-day and private source IDs, missing source/quote, wrong chunk, and changed quote.
- The evidence JSON reports the saved actual benchmark receipt reproduces the canonical output and passes `validate_benchmark`; I did not read private receipt/source text or make any request. It also records zero generation and embedding calls.
- No provider, Ollama, embedding, browser, HTTP, or server mutation was made during this review. Synthetic browser evidence is fixture-only and is not live-model validation. A fresh full recorder dry run and mandatory Astra review remain separate gates.
