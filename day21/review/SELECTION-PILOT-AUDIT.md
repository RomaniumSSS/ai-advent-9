# Offline audit pilot proposals

Команды: `python3 day21/review/test_selection_audit.py`, затем `python3 day21/review/audit_selection_proposals.py`. API/повторы не выполняются. Frozen runner/helper/ledger/raw не меняются; текущий stop остаётся.

Private output: `day21/private/selection-pilot-audit-v1.json`,0600. Model output сохраняется отдельно без изменения decision/reason/flags. Derived context references добавляются отдельно для direct source.reply родителей вне members обеих разновидностей групп. Они содержат child/parent IDs, version/text hashes, canonical/missing state и доступное решение родителя, включая exclude/review. Derived ссылка не превращает родителя в include. Тексты и вложения не загружаются в stdout.

Реальный offline audit:7attempts =6complete+1error;7paid HTTP200responses,6modelvalid,6proposal_pending_manual_review+1review_required,19derived references. Paid success response не равен accepted proposal: принятых решений корпуса0. Ошибки strict/schema/structural/context дают review_required, не устраняются искусственным исправлением output. Fact flags/semantic noise автоматически не классифицируются; manual_notes оставлены отдельно для root. Последующие5pilot requests не отправлены,full gate не открыт.

Синтетические tests PASS: excluded/missing parent provenance, неизменность modeloutput, context failure и malformed output → review_required. py_compile PASS. Все7raw и ledger hashes до/после совпали и включены в private audit. Источники/requests проверены существующими offline loaders. Root выполняет смысловой review и отдельно решает продолжение.
