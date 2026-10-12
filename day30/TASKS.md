# Day30 — задачи и доказательства

## Сдача по исходному условию — 12.10.2026

Приоритет: последние требования пользователя, SPEC D1–D6. Historical A3 semantic FAIL сохранён как ограничение архивного пересказа; он не блокирует сдачу локального сервиса. Нижний checklist — история разработки, его semantic-gate не применяется к текущей сдаче.

- [x] D1/D3: fresh main/assignment LAN HTTPS, модель/profile12, auth/Host/Origin.
- [x] D4: targeted offline rate429/Retry-After, busy409, оба context budgets; реальные negative API probes до inference.
- [x] D2: dry3, новые done-ответы, первый + follow-up в одном разговоре, третий в новом; API readback.
- [x] D5: record3 новых live-ответов, MP4/ffprobe/кадры/privacy/playback.
- [x] Независимые Luna → Astra review текущей сдачи и затронутой обвязки.
- [ ] D6: GitHub main/day30, remote SHA/content readback; старые дни неизменны.
- [ ] D6: Drive existing folder, Anyone with link / Viewer, playback.
- [ ] D6: Day30/AE132 header + row owner, две ссылки в комментарии, Saved/reload/readback.
- [ ] Краткие RESULT/DELIVERY/RELEASE_NOTES/todo/HANDOFF отражают факты; human acceptance отдельно.

## Исторические этапы разработки

Требования: [SPEC](SPEC.md). Порядок: [PLAN](PLAN.md).
Статус: LAN HTTPS/CA/auth на системном Python3.9.6; службы исполняют profile12.
**SPEC NOT SATISFIED:** последний [smoke12](results/live-private-12.json) runtime1 PASS,
semantic1 FAIL; следующие2 не отправлены. Всего15 completed private queries,
старые FAIL сохранены. [Smoke07](results/live-private-07.json): runtime1 PASS/semantic1 FAIL.
CODE07/32 hashes: Sol6+79 linked и independent21 targeted PASS.
Fixed08 CODE approved/34 hashes: Sol14 targeted/93 linked/full122 PASS;
Astra14 targeted+originalP2 regate PASS, provider actual INFO/replayoff checked.
[Restart08](results/restart-08.json) сохранил17 old states. [Smoke08](results/live-private-08.json):
selection завершён78.3с, synthesis timeout300.003с при headers/0bytes; total380.269с,
attempted2/completed1 generation, финального ответа нет (semantic NOT PROVEN).
Следующие2 не запущены; всего11 completed private queries. Astra аудирует08;
CODE09 APPROVED/36 hashes: Sol7 targeted+1 focused/107 linked PASS; Astra8+19 PASS.
Synth1408/deadline600с, ctx8192; restart09 сохранил19 old states. G01T1 завершён error/length без final; session75144 closed1.
Inherited P2 исправлен в10: global CODE APPROVED/37 hashes; Sol11 final targeted/111 linked
и Astra25 targeted + actual09 reconstruction PASS. Synth1920/900; restart21 old states unchanged.
G01T1 завершён FAIL length1920/empty-final; session8455 closed1. CODE10 approved.
SPEC/PLAN11 готовы: native nonthinking1024/300, explicitONE current-question1/1,
ordinary8/4; CODE11 fixed APPROVED/38 hashes, independent12+27 PASS.
Restart23 old states unchanged; G01T1 done/supported/122.387с,1source/1point/2chatcomplete.
Всего14 completed private queries; semantic11 FAIL, next2 not run.
SPEC/PLAN12 готовы: установленная8B Q8, строгие wire aliases, прежние gates/quantity/P2;
CODE12 APPROVED/39 hashes: Sol127 linked/15 final, independent37 affected/15 final PASS.
Restart25 old states unchanged; G01T1 done/partial163.639с/1source/2generation,
independent semantic12 FAIL;15 completed private queries; следующие2 не отправлены.
Completed restart12:27 old states unchanged, latest receipt/metrics/conversation1turn
CA-verified API readback PASS; no inference replay. Semantic verdict остаётсяFAIL.
Model/parameter loop stopped; async user format choice pending. До ответа только
независимые проверки/документация, без dependent code/inference/video/publication. Reasoning не сохраняется. Видео/публикаций нет,
human acceptance pending.
Второе физическое устройство NOT PROVEN.

- [x] Проверены root/ветка/base `b3e607e`, проектные AGENTS/CLAUDE, верх todo/HANDOFF.
- [x] Изучены используемые Day29 функции и AICODE-заметки; определены самостоятельные копии.
- [x] Astra подготовила SPEC/PLAN: домашний Mac, TLS+auth, два вызова Qwen, отдельные budgets,
      public-safe demo/private functional evidence. Исходный stop снят новым запросом.
- [x] **A1–A4 offline:** RED→GREEN core: selection→synthesis, свежие источники, атрибуция,
      history/context на каждом вызове, ошибки/unknown без retry.
      Evidence: `results/offline-red.log`, `results/offline-first-implementation.log`,
      `results/offline-green.log` (49 model-core/HTTP/TLS PASS Python3.14; mock модель).
      A3 semantic/live остаётся отдельным незавершённым пунктом.
- [x] **A1,A5–A7 offline:** RED→GREEN API: auth/Host/Origin/body,429/Retry-After,409/busy,
      освобождение lock, history/restart/interrupted, безопасный UI.
      Evidence: `results/offline-green.log`, `results/browser-offline.json`,
      `results/ui-mock-*.png`. TLS stalled TCP regression: `results/tls-stalled-red.log`
      → GREEN; независимый valid TLS запрос с CA прошёл при stalled клиенте.
      Это временный loopback test-cert, не доказательство deployment на LAN.
      Luna NEEDS CHANGES (bounded workers/absolute deadline) исправлено:
      `results/connections-red.log` (3 поведенческих FAIL) → `results/connections-green.log`
      (4 PASS); общие49 PASS и обновлённый Playwright mock PASS.
      Launchd bootstrap race: `results/deploy-lifecycle-red.log` →
      `results/deploy-lifecycle-green.log` (7 mocked lifecycle PASS CLT Python3.9.6),
      `results/deploy-lifecycle-python314.log` (7 PASS Python3.14). Helper ждёт
      unregister + prior PID gone до bootstrap, ограничение ExitTimeOut+5с.
      Read-only реальный launchd state/PID разобран; actual controlled restart
      выполняет root отдельно. Новая broad56 попытка CLT встретила shared flock busy
      (`results/offline-system-python-contended.log`: 14 errors/failures из-за lock/409);
      она не является GREEN и не повторяется параллельно live inference. Fresh Astra review и live evidence остаются pending.
- [x] **Astra P2 offline fixes:** Day30 evidence-ID focus по immutable spans (S-renumbering,
      adjacent-author exclusion, legacy-only fallback); private partial error snapshot до
      model parsing (raw response/budgets/prompts/last phase/attempted+completed counts);
      synchronous absolute provider deadline с закрытием физического fd до возврата.
      Evidence: `results/astra-fixes-red.log` (8 tests, 10 failures с subtests) →
      `results/astra-fixes-green.log` (12 targeted PASS CLT Python3.9.6),
      `results/astra-fixes-python314.log` (12 targeted PASS Python3.14),
      `results/offline-astra-fixed.log` (68 quiet PASS CLT Python3.9.6).
      Generic synthesis instructions сохраняют субъект/объект/направление действия,
      конкретные альтернативы/числа/отрицания, без corpus-specific facts.
      Baseline02 CODE approved; новый live pair всё ещё FAIL, оба результата сохранены.
- [x] **A6,A9:** private TLS deployment, конкретный LAN bind/сертификат/CA,
      launchd start/stop/restart; HTTPS API на LAN IP без `-k`.
      LAN/CA/auth/Host/Origin: `results/deployment-initial.json` PASS; interpreter
      choice: `results/network-diagnosis.json`. Actual controlled restart/history/
      external flock409: `results/restart-and-lock.json` PASS. Второй device NOT PROVEN.
- [x] **Repair03 offline/CODE:** keyed selection, strict JSON на обоих ответах,
      отдельное coverage запроса предложения/результата, points с exact anchor и refs,
      старый API/UI; pruning пересобирает maps/schema и сохраняет полные счётчики.
      `results/protocol03-red.log` → `protocol03-green.log` (10 PASS);
      `protocol03-regression.log` (81 quiet PASS CLT); independent Astra13 targeted
      PASS, baseline26 hash совпали. `results/restart-03.json`: шесть old state hashes
      неизменны. Live/semantic этого протокола пока отдельно pending.
- [x] **Protocol06 offline/CODE:** компактные projections с exact full text один раз,
      point IDs без quote copying; code-derived provenance/M и conservative full-only doubts.
      [Offline](results/protocol06-offline.md): Sol10targeted/63linked/full102 PASS;
      independent Astra28targeted PASS +12 temporary legacy copies; [baseline31](results/code-baseline-06.json).
      [Restart06](results/restart-06.json):12old states неизменны, оба CA endpoints/новые PID.
      Real semantic остаётся отдельным pending gate, старые FAIL сохранены.
- [ ] **A8:** короткий live smoke ≥3 успешных последовательных содержательных запросов,
      private discussion+follow-up; восстановление после рестарта. Evidence: pending.
- [ ] **A3,A8:** независимое смысловое чтение originals против пересказа/вывода,
      атрибуции, чисел, полноты и план/результат. Начальный FAIL:
      `results/semantic-summary.json`, `private/semantic-review.md`; repair + rerun pending.
- [ ] Независимое Luna review → Sol fixes → обязательное fresh Astra review;
      затронутые regression checks после исправлений. Первые отчёты:
      `results/review-luna.md`, `results/review-astra.md`, `results/implementation-validation.md`.
      Post-Astra focus/error-trace/total-deadline/semantic fixes и regate pending.
- [ ] **A10:** server-side assignment demo scope, отдельная история, ≥2 живых вопроса,
      MP4 без аудио, проигрывание и проверка отсутствия private/credential. Evidence: pending.
- [ ] README/RESULT/DELIVERY и минимальный журнал: реальные environment/метрики,
      разделены mock/live/semantic; доступ со второго устройства **NOT PROVEN**.
- [ ] Private service финально запущен; путь к credential и CA указан без значений секретов.
- [ ] Разрешённые commit/push, GitHub day01–30 по порядку; удалённый SHA/URL проверены.
- [ ] Видео загружено в прежнюю Drive-папку; anyone-with-link/viewer и воспроизведение проверены.
- [ ] Проверен заголовок Day30/строка132 (ожидается AE132), записаны две отдельные ссылки,
      выполнены reload/readback; обновлены короткие todo/HANDOFF.

Человеческая приёмка: pending. Покупка VPS/публичный порт не входят в разрешение.
