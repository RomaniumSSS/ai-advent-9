# Profile09 offline evidence

Python3.9.6 `/usr/bin/python3`; stdlib fake model, ephemeral loopback, mocked launchd and
poll/browser wait. No actual model inference, service restart, real plist rewrite or weights.

Only synthesis changes: num_predict1408 and absolute transport cap600s. Selection remains
1024/300s; embedding/default provider routes300s. Context8192/template512,08 think/format,
ordered embedded schema counted once, privacy positive shape and protocol06 gates remain.
The shared limits module computes provider sum1200, worker join1210, launchd1220 and CLI/
video poll1230. These are provider/lifecycle bounds, not a full-request SLA for local overhead.
Existing plists keep their own ExitTimeOut until root regenerates main/demo with prepare.

Actual stage deadline passes to the synchronous transport, outside Ollama options. TIMEOUT
is now a maximum600 ceiling; default routes still clamp300, and existing short fixture
TIMEOUT patches still shorten any stage. Trace attempt/known-sent and budget carry actual
deadline_seconds; embedding has provider deadline evidence too. Socket closes before return
and before Application finally releases its lock. No reader/background retry is added.

Actual checks:

- Before implementation: `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile09 -v`:
  7 tests,2 failures/6 errors,2.051s, `profile09-red.log`.
- First targeted attempt: two errors because the old stalled fixture only supported GET,
  while new synthesis transport check uses POST. Preserved `profile09-targeted-initial-failure.log`;
  added POST body consumption and reused its existing slow-byte/cancellation behavior.
- Same targeted command: 7 PASS,2.555s, `profile09-green.log`.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile09 test_privacy_shape08 test_profile08 test_profile07 test_protocol06 test_protocol03 test_selection03 test_ordering05 test_profile04 test_review_regressions test_extended.ExtendedCore test_service.CoreTests test_deploy_lifecycle -q`:
  107 PASS,13.061s, `profile09-linked.log`.
- Added focused invariant check after linked run (runtime code unchanged):
  `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile09.Profile09Tests.test_timeout_closes_transport_before_application_releases_lock -v`:
  1 PASS,0.527s, `profile09-cancel-before-unlock.log`.

Actual Ollama.request loopback bodies show selection1024 vs synthesis1408, think/format08
unchanged and no deadline option leak. Captured DeadlineConnection bounds are300/600;
default route remains300 and monkeypatched TIMEOUT.2 still produces.2. Budget fixture gives
input6738+output1408=8146; observed prompt6272 fits exactly with512 reserve and6273 fails.
Slow fragmented headers/body prove absolute short caps and cancellation. Actual Application
error path observes closed fd at fake lock release. Mock join and generated temporary plist
assert1210/1220; old plist910 still uses915 shutdown helper. CLI accepts completion at1229,
and async video terminal wait passes1230000ms with unchanged status condition.

Historical test logs/baselines remain unchanged. Related fixtures only forward stage
deadlines and update current normative output/lifecycle assertions. No broad full rerun:
107 affected/linked checks plus focused cancellation cover this bounded change; unrelated
HTTP/UI/security behavior is untouched. Real09 latency/output/semantic quality remain
NOT PROVEN; parent owns independent review, baseline, controlled restart and bounded gate.
