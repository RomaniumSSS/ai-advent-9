# Profile12 offline evidence

Среда: `/usr/bin/python3` 3.9.6, stdlib unittest; synthetic provider responses, actual ephemeral loopback, fake lifecycle. Никакого inference/load/pull/restart/global settings изменения. Один разрешённый read-only `/api/show` verbose сохранён в private/q8-show-profile12.json0600; публичны лишь агрегаты/SHA.

MODEL=qwen3:8b-q8_0 и frozen digest по SPEC12. Native/think=false1024/300 обеих стадий, selection0/synthesis.7/.8,8192/512,quantity11 и P2 неизменны. Canonical builders возвращают schema плюс actual alias wire_schema до каждого budget. Actual wire/order/raw и model/digest trace отдельно от canonical schema/response. Alias roots/conclusion нормализуются лишь после duplicate-key strict JSON; unknown/mixed/missing rejected invalid_wire_shape. Safe raw final сохраняет original alias content; malformed/reasoning/unknown payload opaque.

Фактические checks:

- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile12 -v`: [RED4](profile12-red.log),2 failures/2 errors,1.035с; [initial4 PASS](profile12-green-initial.log),1.033с.
- `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile12 test_profile11 test_profile10 test_profile09 test_privacy_shape08 test_profile08 test_profile07 test_protocol06 test_protocol03 test_selection03 test_ordering05 test_profile04 test_review_regressions test_extended.ExtendedCore test_service.CoreTests test_deploy_lifecycle -q`: [127 PASS](profile12-linked-initial.log),16.659с.
- Добавлены focused alias duplicate/previous9B rejection tests (runtime неизменён): `PYTHONPATH=day30:day30/tests /usr/bin/python3 -m unittest test_profile12 test_privacy_shape08 test_ordering05 -v`: [final15 PASS](profile12-green-final.log),3.221с.
- [Actual installed metadata preflight](profile12-tokenizer-preflight.json): existing Qwen2Tokenizer принял preqwen2/151936tokens/151387merges; Unicode/числа/whitespace synthetic counts и fake Engine.real оба BPE budgets проверены до provider, source character span неизменён. Нет live model token-count/semantic измерения. [Provider preflight](profile12-provider-preflight.json) отдельно подготовлен root.

Actual loopback format и simulated Go alphabetic decode сохраняют selection grounds→coverage и synthesis points→doubts→conclusion/text→refs. Raw alias final byte-exact; text/IDs не replace. Native schema budget once, dynamic per-prune alias enum/oneOf/maps, quantity/background/unknown/source gates и positive-shape Application/Store error checks PASS. Связанные fixtures обновляют wire field names/model identity, сохраняя прежние negative assertions. Широкий HTTP/UI suite не повторялся: UI поменяла только badge модели; current baseline/review принадлежат root.

Actual11 semantic FAIL и прежние failures не regrade. Model/defaults/BPE/retained context изменяются вместе; precision-only effect не доказан. Независимый CODE review, restart12, real completion/latency/semantic gates и внешняя доставка pending.
