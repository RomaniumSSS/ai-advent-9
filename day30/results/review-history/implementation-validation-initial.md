# Day30 — independent implementation validation (initial baseline)

**Вердикт: SPEC NOT SATISFIED.** Это сохранённый первоначальный аудит до исправлений fresh Astra, не финальная приёмка. Полная финальная матрица требует новых baseline/evidence после исправлений. Не трактовать review как разрешение публикации или человеческую приёмку.

## Baseline и evidence

Рабочий контракт SPEC от11.10.2026 выведен из разрешённого результата HANDOFF; отдельное человеческое утверждение SPEC не заявляется. Base `b3e607e`, implementation —20 файлов `results/code-baseline-final.json`; reviewer сверил все20 SHA-256, mismatches0. SPEC SHA-256 `cf6387f952e12f2660da4927e391cb653256578830a1f1cccd24e9d38119a2cf`.

Самостоятельно прочитан полный SPEC и runtime/UI/video/test surface; static evidence далее обозначено CODE. OFF49 — сохранённый `results/offline-green.log` (49 PASS, Python3.14, mock inference); контендированный system-Python run не GREEN. REV11 — reviewer command `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_connections test_deploy_lifecycle -v`, exit0, 11 PASS,3.707s, CLT Python3.9.6; 4 real TCP/HTTP +7 mocked launchd. UI — `results/browser-offline.json` с mock inference. LAN — `results/deployment-initial.json`, настоящий CA-verified LAN TLS/API на одном Mac. PRIVATE — исходные приватные receipts и независимое чтение immutable DB spans/metadata, подробности только `private/semantic-review.md`. Публичный агрегат — `results/semantic-summary.json`.

Failure model: mock может не отражать реальную генерацию; допустимый ref не доказывает смысл; loopback не доказывает LAN, а запрос с одного Mac не доказывает второе устройство; atomically saved fixture не доказывает actual launchd restart; код video runner не доказывает записанные кадры; stale hashes не доказывают текущую реализацию. Поэтому evidence classes разделены. Исторические FAIL не заменяются pending при последующем исправлении.

## Нормативный инвентарь полного SPEC

Каждая строка объединяет только связанные наблюдаемые требования; A1–A10 сохранены как исходные IDs. Строки G и Z покрывают нормативные границы и раздел «Завершение» вне таблицы SPEC.

| SPEC item | Наблюдаемый контракт | Evidence | Статус | Граница доказательства |
|---|---|---|---|---|
| G1 | Самостоятельный Day30, API+чат, M2/16GiB, runtime imports только своего дня | CODE, LAN, environment report | PASS | Не доказательство качества ответов |
| G2 | Read-only frozen generation/DB724chunks663docs и source counts | local/archive, deployed startup identity | PASS | DB только ro+immutable, hash verification before reads |
| G3 | Frozen Qwen8B Q4+embedding/options, local loopback, no proxy/redirect/cloud/retry | local.py, OFF49, live metrics | PASS | Никаких provider failovers |
| G4 | Day29/index/history/tests не изменены; нет нового framework/FSM/весов/VPS/public exposure | bounded diff, runtime imports, launchd configuration | PASS | В пределах обозримой Day30 работы |
| A1.a | Отдельный process Day30, API question+optional conversation, IDs/status/answer/error | server/service, OFF49, LAN | PASS | Actual live ответ и конкретный error наблюдались |
| A1.b | UI new conversation/follow-up/original details | app.js, UI | PASS | UI mock; semantic follow-up отдельно A8.b |
| A1.c | question1–500, body≤64KiB, invalid before inference | OFF49, handler checks | PASS | Negative HTTP contracts |
| A2.a | Fresh retrieval весь private snapshot; assignment scope отделён | catalogs/retrieve, OFF49, PRIVATE | PASS | Не означает поиск всегда семантически полон |
| A2.b | Два sequential calls same Qwen think=false, selection IDs→originals→synthesis; embedding separately | local/service, OFF49, completed live receipt | PASS | Unknown/error разрешено закончить раньше |
| A2.c | No hidden retry/critic; invalid/empty stops | exhaustive calls in CODE, OFF49 | PASS | Фактический error не повторён автоматически |
| A3.a | Source-grounded пересказ/вывод, uncertainty, no unsupported attribution/action/result | PRIVATE independent semantic audit | FAIL | Первый live summary+conclusion искажают отношение из оригинала |
| A3.b | JSON/done/refs validation; shown immutable original metadata; no automatic semantic PASS | parse_response/validators/source_units, OFF49, DB comparison | PASS | Не переносить этот PASS на A3.a |
| A3.c | Unknown disclosed, no free out-of-corpus answer; recommendation labelled Вывод | validators/prompts, OFF49 | PASS | Гарантия кода о формате; реальная смысловая поддержка A3.a |
| A4.a | Separate full prompt/schema/template512/output1024 ≤8192 before both calls,temperature0 | fit_prompt/check_budget, OFF49, private budgets | PASS | BPE или явная conservative byte fallback |
| A4.b | ≤3 user history questions, no assistant factual evidence; oldest history then complete low-ranked units, current question intact | resolve_query/fit_prompt, OFF49 | PASS | Dialogue focus defect отдельно review; сами budget/history правила соблюдены |
| A4.c | Synthesis receives only final retained originals/refs | rebuilt schema/coverage, OFF49 | PASS | Final selected IDs constrained |
| A5.a | One chain, shared existing flock, busy409/no queue, release on errors | generation_lock/Application, OFF49 | PASS | Mock error release; real model quality отдельно |
| A5.b | Sliding credential6/60s,429+Retry-After before inference | OFF49, accepted deque | PASS | Process-local rate state, documented reset at restart |
| A5.c | ≤300s total provider call, no infinite wait/retry | independent slow-response fixture | FAIL | timeout0.08s request lasted0.474s; socket idle timeout is not absolute deadline |
| A6.a | TLS explicit private LAN IPv4/free port, no public bind/tunnel; SAN actual IP+localhost,key0600 | LAN, server bind check, file modes | PASS | Другой физический device не тестировался |
| A6.b | API/private bearer, constant compare; env0600/gitignored; UI token memory only | guards/load_env/UI, OFF49, file modes+gitignore | PASS | Credential values не читались в public audit |
| A6.c | Host/Origin allowlist, absent Origin CLI allowed, foreign forbidden,no wildcard CORS | OFF49+LAN | PASS | Real auth401/Host403/Origin403 |
| A6.d | Static contains no private data; safe textContent/no remote scripts | static CODE+UI hostile-text test | PASS | Public publication scan ещё Z2/A10.c |
| A7.a | Own private dir0700/files0600, atomic store, namespaces/new conversations isolated | save_private/Store, OFF49,file modes | PASS | Trace on model error loses diagnostic detail: review finding |
| A7.b | Restart preserves completed conversations; unfinished interrupted, no regeneration | OFF49 mocked store restart | NOT PROVEN | Actual controlled restart root pending |
| A7.c | Sanitized ID/status/duration/counters logs; private full evidence | code/log inspection, OFF49 | PASS | No raw data in public error; missing failure trace flagged review |
| A7.d | Own launchd supervision/start/stop, old apps untouched | deploy CODE, REV11,LAN running distinct jobs | NOT PROVEN | Actual controlled lifecycle observation pending |
| A8.a | Offline auth/Host/Origin/body/JSON/rate/busy/both budgets/invalid model/timeout/unlock/history/demo | OFF49+REV11 | PASS | Fresh quiet system-Python broad suite pending; no inference mocks count as live |
| A8.b | ≥3 successive real content responses incl private discussion+follow-up | initial PRIVATE receipts | FAIL | Initial follow-up returned invalid_model_response; only1 completed content response so far |
| A8.c | Recovery after controlled restart | pending root | NOT PROVEN | Need before/after PID and preserved receipts via CA-verified API |
| A8.d | Independent semantic reading checks completeness/author/date/numbers/plan-v-result | PRIVATE audit | PASS | Audit performed; outcome FAIL in A3.a, not semantic acceptance |
| A9.a | Actual HTTPS LAN CA verification,no -k,auth/errors through API | LAN | PASS | One physical host only, exactly specified limitation |
| A9.b | README exact CA client command and supervision state | README commands+deployment report | PASS | Final state still needs root readback before delivery |
| A10.a | Explicit server assignment scope before retrieval/prompt,separate history,only assignment originals | CODE+OFF49+LAN demo scope | PASS | Server-side boundary, not UI-only selector |
| A10.b | Live silent MP4 ≥2 questions/input/wait/answer/conclusion/opened original, no token/private/staging | video runner only | NOT PROVEN | Need actual MP4/rendered frames/fresh receipts/ffprobe |
| A10.c | Public code/reports contain no private text/raw traces/keys | current bounded code review/gitignore | NOT PROVEN | Final publication inventory/content scan required |
| Z1 | Luna independent review→fixes→mandatory fresh Astra, no invented human acceptance | review-luna/review-astra | NOT PROVEN | Luna fixes verified; fresh Astra findings unresolved |
| Z2 | Authorized deploy+commit/push, GitHub day01–30 ordered, old days preserved | pending root | NOT PROVEN | No commit/push executed by reviewer |
| Z3 | MP4 existing Drive folder, viewer link/playback checked | pending root | NOT PROVEN | Publication evidence absent |
| Z4 | Verify Day30 header+row132, two URLs, reload/readback | pending root | NOT PROVEN | Actual external mutation/readback absent |
| Z5 | All unverified explicit pending; no substituted human acceptance/public purchase | TASKS and audit limitations | PASS | Human acceptance pending |

## Условные и ненормативные положения

Второе физическое устройство явно недоступно по A9; это исключённый optional check, **NOT PROVEN** как ограничение среды, не новый блокирующий requirement. «Обычно2–4»/«1–2» — целевой стиль, не самостоятельный абсолютный счётчик; поддержка смысла обязательна A3.a. Альтернативный VPS, новый framework/FSM, новые веса, публичный порт, Day29 benchmark вне scope; их не выполнять. Идентификатор AE132 ожидаемый: актуальный header должен подтвердить root до записи, сам reviewer его не проверял.

## Неуспехи и недостающие доказательства

FAIL: A3.a семантическое искажение; A5.c нет absolute provider deadline; A8.b live follow-up error. Code findings и проверяемые коррекции — `review-astra.md`, подробные факты корпуса только private. Остальные NOT PROVEN перечислены построчно: actual restart/lifecycle, video/privacy, fresh review after fixes и публикация. Эти исходные FAIL сохраняются при новом baseline; после исправления потребуется новая текущая матрица и точные rerun evidence.
