# Narrow context review policy

Новый `run_selection_context_review.py`, defaultdry. Frozenrunner/helpers/requests/raw/gates/audit12 не изменены. Root создаёт policy JSON с ровно четырьмя полями: `allowed_context_error:"included_reply_unread_parent"`, `cap:9.0`, `request_manifest_sha256`, `root_full_gate_sha256`.

```sh
python3 day21/review/test_selection_context_review.py
python3 day21/review/run_selection_context_review.py --policy /absolute/private/policy.json
# Root после review:
python3 day21/review/run_selection_context_review.py --policy /absolute/private/policy.json --live
```

Все20attempts/расходы сохраняются. Startup проверяет original meta/runnerSHA, fullgate hash, audit12 hash и pilot evidence; классифицирует каждый raw отдельно. Только HTTP200/correctprovider/model/finishstop/JSON/strictschema/coveragePASS и известный unread-parent context error допустимы в review. Остальные ошибки/pending безraw/budgetfatal запрещают continuation независимо от порядкаattempts.

Whole-case queue `selection-run-v1/context-review-queue.json` содержит disposition review_required,rawSHA/requestSHA,ownedIDs,errorcodes. Attempts остаются error, modeloutput/flags не меняются. Queue не означает принятие корпуса. Existing queue не может относиться к complete case. Live adoption event сохраняет time/helperSHA/policySHA/oldledgerSHA/priorstop, затем разрешает новыеcalls. Reservation до отправки; exact compactUTF8 bytes;raw доparse;newresponse только incrementalreconciliation;unknowncost reserve сохраняется;no retries/fallback. Future API/length/schema/coverage/unknowncontext/budgeterror stop. Derivedreferences будут подготовлены позднее offline, audit12 сейчас frozen.

Offline tests PASS:2eligiblecontext cases,20unchanged paidstatuses/costs,1698remaining,no repeats;HTTP/length/schema/duplicates/unknowncontext/pending fatal;fatalfirst/last не маскируется context;costoverreserve;rawresponse recovery;stalequeue rejects. py_compilePASS. API разработчиком0. Policy/live запускает root после review. Код заморожен.

## Новая явно разрешённая general output review policy

Предыдущая narrow policy заменена новым поручением пользователя. Snapshot старого runner: `run_selection_context_review.snapshot-1e42da23dc46.py`, SHA256 `1e42da23dc46958dab6e325b86bcd86b14bb8a608e48372c31fe3e9fc37a1ae8`. Frozen helpers/request/raw/audit12/gates не изменены. Exact structural exception artifact не используется.

Root policy теперь ровно: `allowed_error_category:"model_output_errors"`, cap9,request_manifest_sha256,root_full_gate_sha256,prior_policy_sha256 (исходный queue.policy_sha256). Policy adoption требует прежний hash,queue policy_history записывает миграцию;ledger event сохраняет oldledgerSHA/priorstop/helperSHA/oldnew policy hashes. Defaultdry не записывает state.

HTTP200 с правильными model/provider и usable envelope/usage: model parse/schema/coverage/groups/context/length/refusal → whole-case review_required,attempt остаётся error,model output не меняется. Precise reason codes в queue. HTTP/API/auth/transport/provider/envelope/usage/nonfinitecost/source/integrity/pending/overreserve/cap продолжают останавливать. Ошибка вывода не повторяется и не становится accepted. Снятие прежнего structuralstop возможно лишь после классификации всехexisting attempts безfatal. Derivedrefs/offlineaudit пока не запускаются.

Текущие offline агрегаты:81paid,76complete+5error,5review packets,1637remaining. Прежние4queueentries сохранены без изменений. Tests `test_selection_output_review.py` и py_compile PASS: все категории outputreview;fatal HTTP401/429,model/provider,envelope/usage/nonfinitecost,pending/rawidentity,overreserve;fatalfirst/lastне маскируется review;paidledgerunchanged,no repeats. Старый `test_selection_context_review.py` относится к superseded narrow policy; текущий targettest указан выше. API разработчиком0. Root проверяет и запускаетlive; код заморожен после readiness.
