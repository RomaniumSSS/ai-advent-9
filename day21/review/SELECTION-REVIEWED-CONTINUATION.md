# Reviewed continuation helper

`resume_selection_reviewed.py` не меняет frozen runner/requests/raw. Defaultdry. Root пишет private review JSON:

```json
{"acknowledgment":{"request_manifest_sha256":"CURRENT_REQUEST_MANIFEST_SHA","audit_sha256":"CURRENT_AUDIT_SHA","case_id":"p-0194e3fa84cc0eeef94a","raw_sha256":"FAILED_RAW_SHA","disposition":"review_required","acknowledge":"output_validation"}}
```

```sh
python3 day21/review/test_selection_resume.py
python3 day21/review/resume_selection_reviewed.py --phase pilot --review /absolute/private/review.json
# Root после review:
python3 day21/review/resume_selection_reviewed.py --phase pilot --review /absolute/private/review.json --live
```

Проверяется единственная exact context error included_reply_unread_parent:4123, HTTP200/stop/provider/model, strict schema и structural coverage. Любой другой error/pending/hash mismatch запрещён. Ledger meta и frozenrunner SHA сверяются; shared flock и cap9 сохраняются. Failed attempt остаётся error,modelvalid не подделывается,его reserve/cost не сбрасывается,он не повторяется. Live перед новымиcalls записывает event UTC/helperSHA/reviewSHA/priorstop/reason/no_retry. Defaultdry state не изменяет. Newerror вновь останавливает.

Full требует review JSON с дополнительным `full_gate`: approved=true, request_manifest_sha256, pilot_evidence_sha256 (`prep.digest` sorted JSON mapping всех12caseIDs→rawSHA), quarantined_case_id, quarantined_disposition=review_required, audit_sha256. Все12raw обязаны существовать;11complete+известныйerror. Это отдельный rootqualitygate. Успех continuation не запускаетfull.

Offline tests PASS: exactack и каждый tampered field, unreviewed HTTP/length/pending rejects, remaining5, failedID skip, исходные statuses/costs/ledger неизменны, sharedbudget, synthetic all12fullgate и fakePASS rejects. py_compilePASS. API разработчиком0. Stop в текущем ledger не сброшен. Helper готов и заморожен для review.
