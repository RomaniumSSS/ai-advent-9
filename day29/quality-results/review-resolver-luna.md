# Independent Luna review: full-chat resolver

**Verdict: NEEDS CHANGES** for the resolver contract. The reviewed fix correctly recognizes the covered local nominal-definition and numbered-object examples, and the focused synthetic suite passes. Two neighboring dialogue cases remain incorrect.

Reviewed `day29/full_chat_core.py` SHA-256: `ffb2a15c1f3af4630fa86a403e23dbe8924e17f0f289a9451a93bcfa170c4721`. The SPEC contract says follow-ups retain prior user-topic context, explicit new topics take priority, and ambiguous continuations ask for clarification (`day29/FULL_CHAT_SPEC.md`, “Диалог”).

## Findings

### 🟡 WARNING — plural participant references bypass ambiguity clarification

[day29/full_chat_core.py](/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day29-full-chat/day29/full_chat_core.py:154)

The follow-up detector accepts `они` and `их` (line 149), but the multi-author ambiguity guard only checks `он|она|его|её` (line 154). With a prior completed turn whose cited excerpts have two distinct authors, synthetic `Что они предложили?` returns `followup` anchored to the previous topic instead of `clarification`. `Что из них применили?` is not recognized as a follow-up at all and becomes a standalone `new_topic`. This can attach an under-specified participant question to the wrong author or discard its topic context.

**Suggested fix:** handle plural participant anaphora consistently with singular forms: recognize the relevant `они/их/них` constructions and ask for clarification when cited authors are multiple and no unique participant is named. Keep non-participant plural uses from triggering that guard indiscriminately. Add synthetic tests for both forms with zero, one, and multiple cited authors.

### 🟡 WARNING — common demonstrative inflections lose conversational anchor

[day29/full_chat_core.py](/Users/ramanpazharytski/Projects/ai-advent-9-worktrees/day29-full-chat/day29/full_chat_core.py:149)

The new local-antecedent rule handles `этот/эта/этого/...`, but the general follow-up detector does not include inflections such as `том/той/таком`. With a prior completed question about a section, synthetic `А что в том разделе?` returns `new_topic` with no anchor; it is a natural elliptical reference to the earlier section and should retain that user-topic context (or clarify if context cannot resolve it). The same class includes `А что в той части?`.

**Suggested fix:** cover common demonstrative inflections as anaphoric forms in the follow-up resolver, while preserving the current local-antecedent precedence for self-contained questions. Add contrastive synthetic coverage for a demonstrative that refers to prior history and a separately introduced local object.

## Checks and boundaries

- `python3 -m unittest discover -s day29/tests -p 'test_full_chat_antecedents.py' -v`: 4 passed.
- `python3 -m unittest discover -s day29/tests -p 'test_full_chat_contract.py' -v`: 6 passed.
- Additional probes used fabricated turns/questions only; no corpus text, private actual questions, provider calls, Ollama calls, embedding calls, or network requests were used.
- The focused tests validate the new examples but do not cover the two findings above. I did not rerun the broader suite or use the live server.
- Synthetic test file SHA-256: `d1d1dee7beb2b6a2d2080aa74d6b7a5385e6bbdfd5f11047eeda767fdd69b755`; antecedent evidence JSON SHA-256: `37af697e9164a26b3954041e97c50c687c861bc23dd1783f607122c6720b944f`.
