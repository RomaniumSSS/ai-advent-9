# Protocol06 offline evidence

Environment: `/usr/bin/python3`, Python3.9.6; stdlib unittest, fake model and ephemeral
loopback HTTP/TLS fixtures. No real Ollama inference, weights/service changes or deployment.

Final contract: points contain only `aspect_ids,evidence_id,text`; both model projections
pass full original text once plus essential metadata. No anchor partition/IDs. Backend
preserves immutable units and derives full point source quotes/spans. Missing is derived
in code; optional doubts contain only effective-full aspect IDs. Public API is unchanged.

RED history is preserved rather than rewritten:

- `protocol06-anchor-draft-red.log`: first 9 checks on the previous05 implementation;
  failures/errors reflect unavailable projection/bookkeeping APIs and the then-proposed
  anchor contract. The anchor design was cancelled by root before freeze.
- `protocol06-red.log`: revised final-contract 10 checks while implementation was an
  incomplete cancelled anchor draft; 10 errors from the abandoned missing helper.
  This is a recorded intermediate failure, not evidence of 10 distinct legacy05 bugs.

Actual successful checks on the final runtime code:

- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_protocol06 -v`:
  10 PASS,0.017s, `protocol06-green.log`.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_protocol03 test_selection03 test_ordering05 test_profile04 test_review_regressions test_extended.ExtendedCore test_service.CoreTests -q`:
  63 PASS,6.212s, `protocol06-linked.log`.
- `/usr/bin/python3 -m unittest discover -s day30/tests -q`:
  102 PASS,20.294s, `protocol06-full.log`.

New checks cover byte-exact full Unicode/whitespace text, nullable metadata, stage-local
context refs, private full-unit spans, wrong/removed/background/cross-aspect proof IDs,
rejection of model quote/anchor/offset fields, mandatory partial/none/unrepresented
missing, conservative full doubts, dynamic schema and real sent-body budgets.
Related fixtures retain duplicate JSON key, conclusion refs, unknown, output limits,
provider deadline/cancellation, model identity, two-call/no-retry and private-error negatives.
Real HTTP wire tests assert selection/root/point/conclusion property order after pruning.

Old receipts and semantic/runtime FAIL were not modified or re-rendered as success.
Valid structure/provenance does not establish semantic support. Parent owns independent
review, new baseline and bounded real-provider/semantic gate.
