# Двухэтапный runner proposals

`run_selection_requests.py` читает только immutable selection-requests-v2 и повторно сверяет исходную ownership/provenance, accepted hashes, parser, body/hash/bytes. Рубрика и bodies не меняются. Default dry, API вызовов при проверке:0.

```sh
python3 day21/review/test_selection_runner.py
python3 day21/review/run_selection_requests.py --phase pilot
# Только root после code/provider review:
python3 day21/review/run_selection_requests.py --phase pilot --live
# Только отдельное решение root после смыслового review pilot:
python3 day21/review/run_selection_requests.py --phase full --approval /absolute/private/approval.json --live
```

Pilot детерминирован: обе транспортные части двух крупнейших split branches (roots4217/3559), крупнейший unsplit, обычные reply/singleton/media-context. Всего12calls, reserve upper$0.0773576. Full исходный upper$8.5699684, общий cap$9 включает pilot; уже attempted requests не повторяются. Успех pilot не запускает full автоматически.

Private state `day21/private/selection-run-v1/`: ledger.json и один raw response JSON на request,0700/0600; exclusive flock. Reservation сохраняется до HTTP. Unknown/timeout стоимость остаётся reserve. Сохранённый raw envelope содержит usage до parse; startup reconciliation восстанавливает результат после interruption без повторного вызова. Pending без raw блокирует продолжение, failed attempt не повторяется. Stop на HTTP/transport/provider/model/length/parse/schema/context errors и cost выше reserve. Никакого fallback/retry или принятия корпуса.

Full approval JSON обязан точно содержать `approved:true`, `request_manifest_sha256` текущего manifest и `pilot_evidence_sha256`: `prep.digest({case_id:sha256(private_raw_result_file) for case_id in pilot_ids})`. Это отдельный root review gate, а не автоматическая оценка качества. При неполном/ошибочном pilot full отвергается.

Runtime jsonschema сейчас отсутствует: используется проверяющий точный subset schema (types без bool-as-int, required/additionalProperties, enum, min/max items/length), затем adapted validate_selection_output и отдельный unread-media reply guard, включая context-only parent. При доступном jsonschema вызывается его validate. Родитель самостоятельно оценивает смысловой результат; structural PASS не равен semantic acceptance.

Проверено stdlib mocked/offline: deterministic pilot IDs; cap/reserve; malformed/duplicate JSON keys и types/minima; context-only unread parent; durable429/unknown reserve; duplicate attempts; interruption after saved response; no repeat; length/provider rejection; exact отправляемые compactUTF8 bytes/digest/length; TLS CA включён. py_compile PASS. Реальный provider run ещё не выполнялся разработчиком. Raw тексты/ключи не печатаются; APIkey безопасный прежний reader, requests+certifi без установки. Код заморожен для root review.
