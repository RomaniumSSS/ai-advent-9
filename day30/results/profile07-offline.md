# Profile07 offline evidence

Python3.9.6 `/usr/bin/python3`, stdlib fake model + ephemeral loopback provider fixtures.
No real Ollama inference, weights/service/deployment changes, new seed or third call.

Explicit wire options are independent full dicts:

- selection `{num_ctx:8192,num_predict:1024,temperature:0}`;
- synthesis `{num_ctx:8192,num_predict:1024,temperature:0.7,top_p:0.8}`.

Model9B/digest, think=false, protocol06/prompts/schema/projection/retrieval/index/UI/API,
context8192/output1024/reserve512 and absolute provider deadline300s remain unchanged.
Package defaults are documented separately; they are not included as explicitly sent values.

`generation_attempt_parameters` records attempted call model/think/options. Known-sent
`generation_parameters` records the same full parameters only after response or transport
headers/body evidence, alongside schema wire order. A pre-send failure does not prove send;
no unused synthesis parameters are manufactured. Private budgets include actual stage
options; observed-count validation uses actual num_ctx/num_predict. Public receipt drops trace.

Actual checks:

- Before implementation: `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile07 -v`,
  6 RED (errors),1.035s, `profile07-red.log`. Missing options API/private metadata caused failures.
- Same targeted command: 6 PASS,1.540s, `profile07-green.log`.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile07 test_protocol06 test_protocol03 test_selection03 test_ordering05 test_profile04 test_review_regressions test_extended.ExtendedCore test_service.CoreTests -q`:
  79 PASS,7.756s, `profile07-linked.log`.

Checks capture actual Ollama.request body for both Engine generation stages, verify the
matching private model/think/options and budget, and ensure request mutation cannot alter
explicit options or defaults. Synthetic varying output/context limits verify budgeting and
observed-count validation use supplied values rather than old hardcoded constants.
Completed invalid selection/synthesis and sent transport parse failures preserve only the
appropriate stage parameters. Unproven pre-send failure records an attempt separately.
Fixtures forward options without weakening existing model/protocol/negative assertions.

Full102 baseline06 suite was not repeated for this bounded change; related core/provider/
identity/budget/provenance/no-retry/deadline checks passed. Real profile07 semantic support
is NOT PROVEN. Earlier rejected receipts and semantic FAIL remain unchanged; parent owns
independent review, baseline and bounded new live gate.
