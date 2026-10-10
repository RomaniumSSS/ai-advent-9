# Quality eval — задачи

11.10.2026: [контракт](QUALITY_EVAL_SPEC.md) и [план](QUALITY_EVAL_PLAN.md).
Private matrix: 24 кейса / 50 gold-групп / exact original spans. Source audit
Astra APPROVED, root отдельно подтвердил 50 spans; dataset bytes неизменны.
Пользователь поручил **пять случайных новых вопросов**, выборка frozen до inference:
H05, H12, H20, H06, H11. Остальные 15 holdout и четыре pilot сейчас не запускаются.
Общего walltime/call cap нет; один repair — фиксированный протокол сравнения.

- [x] **Q1 / root+Astra:** 24 private cases, originals/gold/offsets checked; group split
  4 pilot/20 holdout, dependencies и порядок frozen. Безопасный manifest; profiles,
  source/index hashes и baseline artifact preservation зафиксированы.
- [x] **Q2 / Sol:** additive runner, paired shared draft, bounded critic→optional one
  repair→recheck, strict errors, stage metrics; существенные RED→GREEN.
- [x] **Q3 / Sol:** mock dry-run, privacy, source/history/gold boundaries, полный учёт calls/time,
  atomic checkpoints, interrupted-unknown no replay, dependency/partial resume.
- [x] **Q4 / Luna → Sol → Astra:** независимые reviews и targeted fixes/tests; live
  readiness подтверждена без изменения full-chat core/API/UI.
- [x] **Q5 / root:** source audit, seeded selection пяти и final code/protocol
  hashes входят в свежий prepare manifest после mandatory Astra review.
- [x] **Q6 / root:** выбранные пять без общего cap, private receipts каждого stage,
  все ошибки/паузы/pending сохранены. При ошибках продолжать независимые кейсы после проверки безопасного idle.
- [x] **Q7 / independent assessor+Astra:** source-backed A/B scoring и аудит gold,
  separate retrieval/support/correctness/completeness; NOT PROVEN не превращены в PASS.
- [x] **Q8 / root:** безопасный отчёт, partial/full coverage и tradeoff времени,
  checksum preservation, короткий journal/todo/HANDOFF; live auto-correction не включена.

Модели ролей задаются фактическими параметрами делегирования по AGENTS.md;
использованные модели/доступный usage записываются без выдуманной стоимости.
Текущий эксперимент завершится независимой оценкой выбранных пяти и честным
partial отчётом. Полный набор остаётся подготовленным для будущего поручения;
победа B и человеческая приёмка не гарантируются.

## Implementation evidence — Sol

Additive `quality_eval.py` и два focused test modules: 24 synthetic unittest PASS.
[RED/GREEN и hashes](tests/quality-evidence.json), [GREEN](tests/quality-offline-green.txt),
[README/CLI](QUALITY_EVAL_README.md). Initial executable protocol skeleton RED:
accept/issues/refs, shared draft и бюджет; отдельные RED для nullable metrics и
конкурирующих controllers. Atomic dispatch checkpoints, interruption/no replay,
baseline-only prefixes, source/history identity, no gold prompt и один repair
проверены tempdirs/FakeClient, без настоящего корпуса в публичных fixtures.

Полный synthetic24: 23 completed model pairs +1 local clarification, 46 mock chat,
23 mock embed, 184 mock service calls, real network 0. `prepare` настоящего private
matrix также network0; старые manifests оставлены неизменными после code changes.
Реального preflight/pilot/embedding/generation не выполнялось. Full-chat core/API/UI
не редактировались; root владеет source audit, preservation99, Luna/Astra review
и будущим запуском. Условная оценка 31–79 минут, новые стадии пока не измерены.

### Явный subset — 11.10.2026

Пользователь выбрал реальный прогон пяти новых holdout после reviews. Additive
selection-file/repeatable case-id frozen в prepare с dataset/source/selection SHA;
resume проверяет identity subset, missing dependency отвергается без auto closure.
[Subset RED](tests/quality-subset-red.txt): игнорирование selection давало 38 mock
chat вместо 10, пропускало missing dependency и mutation. GREEN 28 tests;
summary показывает selected5/pending_unselected15 и partial_selected_subset.
Root владеет seededrandom выбранными пятью группами и реальным запуском;
исполнитель не делал новых model calls.

### Luna finding repair refs — 11.10.2026

[RED](tests/quality-uncited-red.txt): repair factual answer с empty refs + recheck accept
ошибочно давал accepted_by_recheck. B теперь использует `core.validate_answer`
unknown guard baseline, invalid repair → unavailable, recheck не dispatch.
Корректный explicit unknown с empty refs допускается, quality остаётся NOT_CHECKED.
30 focused tests GREEN; no actual calls. Final evidence/source hashes обновлены.

### Astra finding resumed latency — 11.10.2026

[RED](tests/quality-resume-latency-red.txt): A2s + savedcritic10s ошибочно давали
B≈2.014s; три saved stages22s давали≈2.000s вместо lower bound24s.
Сохранённые durations теперь входят отдельно в observed lower bound, без double count.
Lost orchestration не угадывается: resumed headline B_latency/pair_observed_seconds
null, incomplete timing flags/missing timings явные. Crash прежних continuous flags
не считается доказательством полного resumed walltime. 34 tests GREEN; actual calls0.

## Реальный прогон пяти — root

Fresh prepare после final code APPROVED: run `405d5a5a7bac4e0da30aafccb6f600b7`.
Frozen H05/H12/H20/H06/H11; dispatch последовательный, без общих deadline/budget.
[Финальное ревью подготовки](quality-results/review-astra.md). Initial5 завершён:
6 generation / 3 embedding, HTTP errors0; B completed0. Независимая blind оценка
— [initial-five-semantic.json](quality-results/initial-five-semantic.json): 15 supported
claims, completeness4/12, two false clarification. Q7/Q8 закроются после retest.

- [x] **Q9 / Sol → Luna → Astra → root:** bounded resolver fix, synthetic RED/GREEN,
  initial3 payload equivalence, approved versioned diagnostic H06/H11 retest,
  independent source scoring. Исходные пять/источники/gold/протокол не переписывать.


- [x] **Q10 / Sol → Luna → Astra → root:** general exact-day assignment reservation,
  42 full/34 quality/16 recorder offline PASS, saved-vector initial3 payload equivalence;
  независимые reviews, versioned known H06-only retest и blind source grading.
  Canonical recorder DocID fix проверяется вместе; без новых random cases.

Resolver retest run5c2b89978dd64feeb73e99eede037f0d завершён: 4 generation/2 embedding,
HTTP errors0, B completed0. Blind diagnostic grading: H11 полнота2/3+1partial,
5 supported claims; H06 контекстный unknown, оба gold groups отсутствовали в prompt.
Источники/gold и исходные пять неизменны.
