# Unified selection proposals

Локальная сборка `build_selection_manifest.py`; API/модели/принятие корпуса:0. Root MCP/todo/PLAN и frozen paidraw/helpers/gates/audit12 не изменены.

```sh
python3 day21/review/test_selection_manifest.py
python3 day21/review/build_selection_manifest.py
```

Текущий immutable output `day21/private/selection-proposals-v3/`: rows.jsonl,groups.json,review-inventory.json,accepted-notes.json,preview.md,manifest.json. Промежуточные v1/v2 оставлены неизменными; v3 добавляет строгий transport acknowledgment и явные dependency statuses. Все артефакты0700/0600. Manifest SHA256 `076f2962bd221b659da1492691b4e1a8b85488c1aa6ba0e1327ee1fb588eb85a`. Реальный повтор: все6artifactSHA совпали.

## Coverage

| Proposed status | ID |
|---|---:|
| Accepted assignment preserved |24|
| Candidate include |1477|
| Candidate exclude |803|
| Semantic review |798|
| Invalid model whole-case review |388|
| Unread media review |82|
| Transport unresolved |1|
| Всего eligible Telegram ID |3573|

Каждый ID встречается ровно один раз в rows, сохраняет source/version/text/record hashes, provenance, origin,modeldecision при валидном output,effective proposedstatus,reasoncategory,packet/reply/media refs. Invalid packet полностью review, даже если rawmodel решил include; raw не изменяется. Modelvalid include/review группы:737/731, membercoverage/unique membership проверены. Draft IDs воспроизводимы по packet/group/memberversions. Sections указывают originaltextbyref; excluded текст не становится memberdraft. Explicit и derived source directreply refs отдельно, с provenance и effective parentstatus/media/parentstate; родитель не promoted автоматически.

Candidate original text:252101 Unicode chars/443279 UTF8 bytes. Review original text (semantic+invalid+unread+transport):83842 chars. Context отдельно deduplicated:284IDs/60278chars; его объём не прибавлен к candidate. Это не подтверждение30страниц и не acceptedкорпус.

85candidate groups имеют зависимости вне candidate_include/accepted_assignment. Это отдельная очередь проверки зависимостей, **не85доказанно плохих групп**. Context occurrences этих include drafts:exclude37,include162,assignment39,outside/missing3,semanticreview43,unreadmedia8. Preview содержит inert membertext и отдельно contextID/status/provenance/text, без activeHTML/links (принятый Sol inert_markdown, fence длиннее любого ряда backticks). Для смешанных сообщений только flags/review, автоматического extract нет.

Accepted Solsqlite открыт readonly:1active accepted note отдельно,0inactive noteversions/0acceptedhistory; заметка не Telegramproposal. Sourceaccepted hashes проверены с ожидаемым packet snapshot, затем before/after. Originaltext в приватных файлах может содержать персональные данные.

## Evidence and limitations

Root finalverification binds requests/ledger/queue hashes. Каждый1718raw перечитан локально и переклассифицирован;bodyhash,queue rawSHA,reservation,ownership/groups coverage проверены. Все1718текущие rawSHA сохраняются в generationidentity и сверяются before/after. Ранее отдельного baseline1718rawSHA в verification не было; такую проверку не утверждаем. Transportcase допускается только через exactledger.transport_deferrals acknowledgment сrawSHA/requestmanifestSHA/no_retry, unknowncost не заменяется0. Fullgate/audit12 не перезаписываются.

Синтетические stdlib tests PASS:coverage/dedup,excludeparent не promoted,missingparentprovenance,invalidwholepacketreview,Unicode/inertfence,bodyhash/reservation/drift refusal,immutable repeat/changedgeneration refusal/privatepermissions. py_compilePASS. Реальная сборка и повтор PASS;raw и acceptedstore неизменны. Семантическая приемка и спорные зависимости остаются rootreview; нового provider или вызовов нет. Код и v3 заморожены для независимой проверки.

Root independent review v3 PASS: всеartifactSHA/1718rawSHA/acceptedguards,coverage3573,unique include/review groupmembership,все source directreply dependencies,dependency statuses соответствуют rows,права0600;targettest повторён PASS. Это проверка целостности и подготовки proposals, не смысловая приемка.
