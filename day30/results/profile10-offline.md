# Profile10 offline evidence

Среда: `/usr/bin/python3` 3.9.6; stdlib unittest, synthetic fixtures, ephemeral loopback и mocked lifecycle. Реального inference, restart, изменения secrets/weights/index не было.

Исправлен inherited P2: `fit_prompt` — единственный владелец pruning. Pure stage builder пересобирает schema/allowed IDs/focus/maps/effective coverage перед каждым render/budget, projection использует те же retained units. Synthesis coverage выводится из исходной validated selection coverage, не из предыдущего downgrade. Engine получает финальный согласованный context без позднего внешнего цикла. История также снимается до следующего актуального budget test.

Только synthesis capacity изменена до1920/900с; selection1024/300с, embedding/default300с. Shared limits автоматически дают1500/1510/1520/1530. Privacy08, two calls, no native synthesis format, schema once, options sampling и strict gates прежние.

Фактические проверки:

- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile10 -v`: [RED](profile10-red.log), 3 tests, 1 failure/3 errors,0.022с; capacity старая, builder ещё отсутствовал.
- Отдельный существующий Engine causal [RED](profile10-pruning-red.log): 1 FAIL,0.019с; budget последовательность `[5,4,3,3]` показывала поздний повторный rebuild вместо `[5,4,3]`.
- Первый targeted run сохранил [fixture failure](profile10-targeted-initial.log): synthetic units имели одинаковый immutable span, поэтому focus корректно совпал со всеми. Fixture получил разные chunk IDs; контракт focus не менялся.
- [Targeted GREEN](profile10-green.log): 3 PASS,0.023с. Обе стадии с настоящим ByteBound сохраняют earliest-fitting3, а контроль со stale schema/extra —2. Каждая попытка проверяет актуальные enums/maps/coverage/focus/context IDs после history/unit removal; исходные units/coverage неизменны.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile10 test_profile09 test_privacy_shape08 test_profile08 test_profile07 test_protocol06 test_protocol03 test_selection03 test_ordering05 test_profile04 test_review_regressions test_extended.ExtendedCore test_service.CoreTests test_deploy_lifecycle -q`: [111 PASS](profile10-linked.log),13.566с.
- Затем causal Engine fixture дополнен настоящим Ollama.request loopback capture. `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile10 test_profile09 -v`: [final11 PASS](profile10-green-final.log),4.105с. Actual wire равен final trace snapshot, native selection schema и embedded synthesis schema согласованы, synthesis format отсутствует, think=true/output1920. Runtime после linked не менялся.

Связанные проверки включают фактические900/300 transport bounds, короткий TIMEOUT ceiling, stalled headers/body и synchronous cancel-before-unlock, budget6240+1920=8160, strict observed overflow, join1510/temporary plist1520/CLI+video1530, privacy positive-shape и error-state persistence. Старые лог-файлы не переписывались; текущие нормативные ожидания fixtures обновлены без ослабления негативных gates.

Private08/09 reconstruction и сравнение конкретных retained evidence/wire выполняет независимый reviewer; private факты не переносились в публичные fixtures. Real10 completion/latency/semantics, controlled restart и доставка NOT PROVEN; parent отвечает за review/baseline/дальнейшие gates. Новый capacity не объявляется достаточным.
