# Profile08 P2 positive-shape repair

Independent Astra found that a short reasoning-key denylist allowed arbitrary parseable
analysis objects into private error snapshots. Initial08 baseline/review/logs are preserved;
no real08 inference or service restart occurred during this fix.

Only runtime change: `local.safe_final_shape` accepts a positive persistence shape:
selection evidence/coverage with typed ID mappings/statuses, or synthesis points/doubtful
IDs/conclusion with exact nested keys and expected types. Unknown fields/arbitrary nested
payloads become opaque bytecount/SHA, regardless of their names. This replaces the denylist.
It does not edit/reconstruct the model response or change any strict validator, enums,
semantic gate, ref proof, two calls, wire, prompt/schema/options or limits. Raw remains in
RAM for validation. Safely shaped invalid-ref final JSON stays byte-exact in diagnostics.

Meaningful tests on `/usr/bin/python3`3.9.6:

- Before fix: `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_privacy_shape08 -v`:
  4 tests,10 subtest failures,0.146s, `profile08-shape-red.log`.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_privacy_shape08 test_profile08 -v`:
  14 PASS,2.770s, `profile08-shape-green.log`.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_privacy_shape08 test_profile08 test_profile07 test_protocol06 test_protocol03 test_selection03 test_ordering05 test_profile04 test_review_regressions test_extended.ExtendedCore test_service.CoreTests -q`:
  93 PASS,10.495s, `profile08-shape-linked.log`.
- `/usr/bin/python3 -m unittest discover -s day30/tests -q`:
  122 PASS,24.423s, `profile08-shape-full.log`.

New fake-model tests execute actual Application→Store with a temporary directory and fake
lock. They check error request+conversation files, public receipt and logs for analysis-only,
extra analysis, nested unknown point/conclusion properties, incorrect nested types, selection
extra/nested payloads and provider response_data. No reasoning sentinel appears anywhere.
They assert error/no-retry counts and opaque metadata while a shaped invalid-ref final is
preserved exactly and still rejected as invalid_point_reference.
Existing two parsed provider-error fixtures now use a legitimate evidence/coverage body,
retaining final-preservation/message.thinking-removal/body-hash assertions; their prior
arbitrary diagnostic/final objects are no longer considered safe final. Initial tests/logs
are not silently regraded.

No prompt/protocol/options/model/index/UI/API/deadline changes. No actual generation,
deployment or old-history mutation. Independent CODE regate and real per-case semantic gate remain parent-owned and NOT PROVEN
by these mocks. Root separately confirmed provider INFO/debug/trace-off preflight PASS in
`results/provider-logging-preflight.json`; no08 model calls have occurred yet.
