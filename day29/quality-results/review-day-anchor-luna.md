# Independent Luna review: explicit-day retrieval anchor and recorder ID

**Verdict: APPROVED (scoped code review).** I found no correctness or contract defect in the two reviewed changes. The exact-day reservation is a selection guard after all chunks have been scored; it does not change cosine/lexical scores or turn retrieval into a day/source filter. The recorder now accepts the full-chat canonical `assignment:NN` document ID while leaving legacy benchmark `assignmentNN` validation unchanged.

## Reviewed snapshot

- `day29/full_chat_core.py` SHA-256: `5a6acf57194d13e621f69e1bf022f1c18b34b91456fdd63178e5a3257e1ab20c`
- `day29/video/run_full_demo.py` SHA-256: `73df411fd637b3efbf3e4211f6102be5ad729fbee8351216dd9c8c3c513841b6`
- `day29/tests/test_full_chat_day_anchor.py` SHA-256: `4c832ab9541090c4e1fa884b6d16d1e718fcfa6b01705683669ec0b8552dcd19`
- `day29/tests/test_full_demo.py` SHA-256: `dac2cd5185e4e3c554845b3dc6d8ed70db0c94cab8e9f1313506114d58455d4c`
- `day29/tests/full-chat-day-anchor-evidence.json` SHA-256: `22d6732c37b6a7efed723b545f1afa01010be28f58ccca9bda81cf3793a68ccb`

## Review observations

- `retrieve_all` still computes semantic and lexical scores for every chunk (724 in the frozen index), applies the existing threshold/top-K, and retains cross-source diversity. The new reservation only considers exact parsed day values present in ranked assignment chunks; it cannot invent an absent day. Pure explicit-discussion requests are excluded from reservation, while mixed requests can retain the assignment anchor alongside requested discussion/note sources. `build_context` receives the anchor first and its whole-source budget removal drops lower-ranked optional sources before that anchor.
- Synthetic coverage checks a low-score exact day anchor, mixed discussion/note retention, no forced assignment for pure discussion, unchanged ranking without a day, absent-day behavior, and survival under the serialized-context budget. The tests also assert all chunks remain eligible and scope remains `all`.
- `validate_full` requires canonical `assignment:<digits>` for full-chat citations, checks each citation against the selected receipt’s chunk ID, document ID and exact text, and requires the assignment document for the scenario’s requested day. Benchmark validation retains its separate legacy `assignmentNN` convention. Wrong metadata and wrong-day references are rejected by synthetic tests.
- The evidence JSON records unchanged AST outside both modified functions and exact equality of recomputed saved-vector initial-three ranking/payload hashes before and after the guard. I checked only its metadata/hashes, not private question or source text.

## Verification and limits

- `python3 -m unittest discover -s day29/tests -p 'test_full_chat_day_anchor.py' -v`: 5 passed.
- `python3 -m unittest discover -s day29/tests -p 'test_full_demo.py' -v`: 16 passed.
- These checks are offline and synthetic. I made no provider, Ollama, embedding, browser, or HTTP calls and did not restart a server. This review does not independently establish live runtime behavior, actual answer support, video quality, or human acceptance; those remain with the root-owned run and required Astra review.
