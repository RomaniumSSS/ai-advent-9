# Day30 — independent Astra CODE review, profile07

**CODE: APPROVED, baseline07.** Существенных дефектов в этой правке не обнаружено. Actual07 runtime PASS1, delivered semantic FAIL1; gate07 FAIL. Исторические failures01–06 не переоцениваются и не отменяются.

Baseline `results/code-baseline-07.json`:32 independently checked hashes, base b3e607e, расхождений нет. Frozen SPEC `results/review-history/SPEC-profile07.md`, SHA `69bca5bdce93628bb30d99732f519f20987b571957ae20b753fc24d6e2fab9be`, также совпал. Рабочая редакция производна согласованному результату; отдельное человеческое утверждение SPEC не заявляется.

Изменение ограничено stage options и их передачей в provider/budget/trace. Selection получает прежний dict num_ctx8192,num_predict1024,temperature0. Synthesis получает независимую копию с temperature0.7,top_p0.8. Local.chat копирует explicit/default options; общие defaults и caller dict не мутируются. Остальные model defaults не выдаются за явно переданные поля. Model/digest, think=false, no retry, protocol06, template512 и provider absolute deadline300s прежние.

Независимая inverse hash проверка: удаление только нового options plumbing и metadata полностью восстанавливает точные local.py и service.py hashes baseline06. Тем самым prompts, selection/retrieval, validators/provenance/M/renderer и остальная логика не переписаны. Protocol/evidence/tokenizer/server/UI/deploy hashes неизменны. Все8 изменённых прежних test files также дают точные baseline06 hashes после удаления options signature/forwarding и одного budget-test argument: прежние assertions не ослаблены.

Service создаёт options отдельно для каждой стадии до budget loop; один и тот же набор проходит fit_prompt/check_budget, actual client.chat и parse_response. Budget включает копию полного явно переданного dict. Observed count gate использует stage num_ctx/num_predict плюс прежний reserve512. Whole-unit pruning/projection/schema rebuilding не изменены. Независимый wire fixture проверяет HTTP body на обеих стадиях, а не только вызов mock API.

Private generation_attempt_parameters создаётся при попытке. generation_parameters и schema order появляются после successful return или transport failure на headers/body, когда отправка известна. Pre-send timeout не выдаётся за known-sent стадию; не начатый synthesis не получает фиктивной metadata. Все структуры копируются, failure raw/budgets сохраняются приватно; public_receipt исключает trace/query.

Reviewer `/usr/bin/python3` CLT3.9.6:
`PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile07 test_ordering05 test_protocol06 -v` — **21 PASS за3.587s**, exit0. Fake models/ephemeral loopback HTTP, без реального inference и общего live flock. Прочитаны Sol profile07-green6 PASS1.540s и linked79 PASS7.756s. Прежний full102 относится к baseline06; новый full suite не заявляется и reviewer его не дублировал.

Код готов к controlled restart и первому предусмотренному вопросу07. Максимум3 неизменённых private cases; root ожидает независимый semantic verdict перед следующим API submit, first runtime/semantic FAIL останавливает ещё не принятые случаи. Один удачный ответ не доказывает causal sampling benefit или общую надёжность. Итоговая conformance, video/public delivery, второе физическое устройство и человеческая приёмка этим CODE заключением не закрываются.

## Actual07 semantic follow-up

Первый done/partial ответ:2 completed chat/220.125s,3 sources. Все3 original spans/metadata independently exact; API/internal answers совпали. Показанный prose искажает временной план и отношение между альтернативами, теряет конкретную исходную проблему; conclusion усиливает обсуждение до неподтверждённых трудностей внедрения. Это delivered semantic FAIL по A3; точный provenance/partial его не исправляет.

Stage trace/budgets подтверждают selection0/synthesis0.7+top_p0.8; prompts/schemas совпадают с corresponding previous known-case inputs. Все32 hashes повторно совпали. Restart07 сохранил15 старых state files, CA/hostname verified, no replay. Следующие2 cases не submitted, public шаги остановлены. CODE approval сохраняется отдельно от SPEC FAIL. Подробнее только private/semantic-review-07.md; безопасный aggregate semantic-summary.json. Новая гипотеза этим аудитом не одобрена.
