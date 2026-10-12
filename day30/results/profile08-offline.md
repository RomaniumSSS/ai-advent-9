# Profile08 offline evidence

Environment: `/usr/bin/python3`3.9.6; stdlib fake model and ephemeral loopback fixtures.
No real model inference, deployment/service/weight changes or private-case replay.
Protocol06/schema/index/9B/digests/options07/UI/API remain unchanged.

Selection retains think=false and native format. Synthesis sends think=true and no format
key (neither null nor empty), preserving options07 and two system/user messages. Its user
content is canonical context JSON followed by newline and ordered dynamic schema JSON.
Budget counts actual messages with embedded schema once: separate synthesis schema_tokens0.
8192context/1024 combined reasoning+final output/512 reserve/300s absolute deadline stay fixed.
Format omission avoids the pinned Ollama native-format restart branch; this is a wire/source
contract, not a measured claim about real backend speed or semantic improvement.

Private known-sent parameters record model/think/options/format_mode and expected schema
property order. Synthesis schema order is an instruction; no grammar/output-order guarantee.
All strict final/duplicate-key/length/ref/provenance/missing gates remain. Raw provider values
stay in RAM for false-phase unexpected-thinking rejection. Persisted copies whitelist final
JSON and metadata, delete message.thinking and allow only a presence flag. Unsafe/partial/
malformed body or final content is opaque stage/bytecount/SHA256, without prefixes. Safely
parsed error response_data is sanitized too. Parseable but schema-invalid final JSON with
explicit thinking/reasoning fields is also opaque; valid-shaped invalid-ref final remains
available without reasoning. Local validation still sees original raw values; no content repair.

Recorded RED/failure history is preserved:

- Initial8 checks before implementation: 5 failures/3 errors,1.578s, `profile08-red.log`.
- First linked87 run: one fixture error,9.851s, `profile08-linked-initial-failure.log`.
  Its old duplicate-key assertion required preserving malformed final text. Replaced only
  that assertion with positive opaque bytecount/SHA plus absent content; duplicate rejection,
  error code and no-second-call assertions remain.
- Initial9 targeted/88 linked/117 full: PASS2.628s/10.345s/24.265s, original logs preserved.
- Extra privacy fixture found labelled reasoning inside parseable invalid final JSON:
  RED1,0.016s, `profile08-privacy-extra-red.log`; fixed persistence sanitizer, not validator.

Final checks on frozen runtime code:

- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile08 -v`:
  10 PASS,2.613s, `profile08-green-final.log`.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile08 test_profile07 test_protocol06 test_protocol03 test_selection03 test_ordering05 test_profile04 test_review_regressions test_extended.ExtendedCore test_service.CoreTests -q`:
  89 PASS,10.367s, `profile08-linked-final.log`.
- `/usr/bin/python3 -m unittest discover -s day30/tests -q`:
  118 PASS,24.544s, `profile08-full-final.log`.

Actual loopback bodies prove omitted synthesis format, actual think/options, two messages,
ordered schema suffix and unchanged schema content. Budget checks prove no separate schema
counting and unchanged reserves; existing pruning fixture checks final retained mapping and
order metadata. Privacy sentinel checks cover success, schema/ref failure, false-phase
thinking, empty/length/duplicate/tagged final, malformed outer JSON, parsed provider error,
legacy response_text/response_data and real partial timeout. Private atomic files, API and
logs contain no synthetic reasoning sentinel; peer observes synchronous socket cancellation.
No fixture log contains the sentinel value. Existing diagnostics/identity/no-retry/provenance/
HTTP/TLS/rate/worker/deployment/restart contracts pass the full suite.

Earlier real semantic FAIL and receipts remain unchanged. Profile08 runtime/semantic quality,
reasoning volume, latency and real cancellation delay remain NOT PROVEN; parent owns review,
baseline and per-case bounded real gate before any public recording/delivery.
