# Independent Luna review: recorder benchmark state projection

**Verdict: APPROVED (scoped recorder-only fix).** The validation now matches the public state shape emitted by the frozen benchmark app, while still comparing the complete expected profile map. I found no defect in this targeted correction.

## Snapshot reviewed

- `day29/video/run_full_demo.py` SHA-256: `38b6e7761b65fead5d9d606a674590f841588033f7745a75d5fdec4dccf7e24d`
- `day29/app.py` SHA-256: `5548e4febe572bbaac0432d38ffd0e6026acdb955e0b27e7501ed63c69cf8ef9`
- `day29/tests/test_full_demo.py` SHA-256: `2796383e04e9c06242857d210efde06a01cb35502750e5fe1aa8704b0d1801b2`
- `day29/tests/full-demo-state-evidence.json` SHA-256: `7373fc4376d9814e0fb32432ff5b5c1190fa8ef7eea67b99252ae5a0c6f86e12`

`day29/app.py` emits each of the six public profile entries as exactly `options`, `quantization`, and `model`. `validate_state` constructs that exact projection from frozen profiles and checks map equality, alongside the app model/run ID, scope, embedding model, and index identity. Receipt validation remains unchanged, so profile hash, model/digests, generation options, and payload checks still operate on the richer per-request receipts.

The new synthetic tests verify the served schema and reject changes to options, model, quantization, missing profile IDs, and unexpected IDs. The evidence file records one saved read-only API state validation as PASS, 0 generation calls, 0 embedding calls, and 18 recorder tests. I reviewed those evidence fields but did not make the API request myself.

## Verification and limits

- Ran `python3 -m unittest discover -s day29/tests -p 'test_full_demo.py' -v`: **18 passed**.
- No browser, HTTP, provider, Ollama, embedding, or server requests were made by this review.
- This establishes the frozen source contract and synthetic recorder behavior; it does not replace the fresh dry run or Astra review. Root should perform the fresh recorder dry run only after the mandatory Astra follow-up.
