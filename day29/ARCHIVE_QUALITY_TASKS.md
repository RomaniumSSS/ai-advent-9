# Выполнение ARCHIVE_QUALITY

Требования: [SPEC](ARCHIVE_QUALITY_SPEC.md), порядок: [PLAN](ARCHIVE_QUALITY_PLAN.md).
Здесь подробный checklist; todo.md — только краткий текущий результат.

- [x] AQ1: записаны границы, замороженная база и точечное supersession full_chat.
- [x] AQ1: root snapshot protected hashes/index/history/runtime перед изменениями.
      `private/full-chat/quality-rework-20261011/initial-state.json`; 249 trackedfiles/18 conversations, index SHA confirmed.
- [x] AQ5: независимый private holdout 10 тем / 18 ходов, 23 facts, source-audit;
      SHA256 `9566ed19dba4252d4156fe69b650f205ad2246ce869a5683346b75acad3f3443`.
      Root independent sourcecheck: 0errors. Первый blind18 выполнен без раскрытия Sol;
      затем independent Astra13 PASS/1 PARTIAL/4 FAIL. После раскрытия — regression.
- [x] AQ2: RED→GREEN generic resolver, collective/author/local subject/follow-up/ack/switch.
      Synthetic tests GREEN; actual final33 отдельно ниже, не считать API quality доказанной.
- [x] AQ3: RED→GREEN author/topic coverage и real-source regression fixtures.
      Fictional public fixtures + private immutable original-source eval;
      current-refinement17 tests и actual targeted-v10 five/5PASS.
- [x] AQ3: полный безопасный budget, пригодные exact spans/history, честный trace.
      InstalledQwen2BPE, messages/schema/template512/output1024 guard;
      independent largest-five6045+1024<=8192; actual selected-source scores retained.
- [x] AQ4: faithful attribution/negation/action/status, partial/unknown, source rendering.
      Typed immutable units/exact author spans; targeted-v10 Luna→Astra5PASS;
      live semantic_support=NOT_CHECKED, completeness caveats are not a verifier.
- [x] AQ1–4: прежние tests GREEN; private/security/store/identity invariants сохранены.
      Root264offlinePASS + Luna→freshAstra CODE approved5acc34;
      actual Host/Origin403, before-restart86 conversation hashes preserved.
- [x] AQ5: реальный baseline-regression after, независимый source grading.
      V2 Astra8 PASS/1 PARTIAL/6 FAIL из15; улучшение не означает приёмку.
- [x] AQ5: первый замороженный holdout через API, отдельный source grading.
      V2 Astra13 PASS/1 PARTIAL/4 FAIL из18; combined21/33 не проходит AQ5.
- [x] AQ5: fixes при FAIL, targeted reruns без перезаписи before/after.
      V3 targeted13:5 PASS/4 PARTIAL/4 FAIL; V4:12 PASS/1 PARTIAL;
      V5 targeted6:6 PASS. Новые generic3:0 PASS/2 PARTIAL/1 FAIL.
      V6–V9 reviews/fixes retained in private journal. V9 official33=32PASS1FAIL;
      known current-question AQ3 bug corrected after fresh boundedplan/CODE gates.
      V10 targeted S08two+ordinaryGthree:5PASS,5GEN5EMBED30calls0errors,
      median103.605s; firstS08PARTIAL reassessment explicit, oldprefix unchanged.
- [ ] AQ5: финальный combined run: >=80% all и answerable; zero fabricated participant
      claims; unsupported корректны; per-suite/scenario/latency/technical отчёт.
      ОСТАНОВЛЕНО по явному поручению пользователя; новый полный33 отменён.
      V10 native73778 exit130:14 ранее принятых запросов завершились,0errors;
      13 reviewed Luna=12PASS1PARTIAL,10 reviewed SECOND Astra=9PASS1PARTIAL.
      Это не результат полного33. Dataset86dd942b…f86f821/core5acc34 сохранены.
- [ ] AQ5: browser/API dialogue, six service calls/объяснённые exits, reload/sources.
      Выполнены actualnewCID/ACK(noGEN)/reload/RAGfollow/MCPsourcepanels,
      desktop/mobile/localresources; 14queryaudit84servicecalls0errors.
      Дополнительные unknown/newtopic UI проверки отменены пользователем.
- [ ] AQ5: Luna independent review → Sol fixes → обязательное Astra independent review.
      CODE264tests и targeted5 полностью Luna→Astra APPROVED/PASS;
      новый combined33 SECOND неполон, дальнейшие проверки отменены пользователем.
- [x] AQ1: protected hashes/history/index после работы, локальный runtime актуален.
      wrapup-user-stop.json:249trackedfiles only5allowedchanged,initial18 +
      before-final90conversationsSHA preserved,Day01–28 diff empty,8070idle.
- [x] AQ5: результат/ограничения, короткие todo/HANDOFF; human acceptance отдельно.
      Пользователь считает улучшение достаточным и отменил дальнейшие тесты;
      полного нового33 результата и ручной приёмки всех сценариев не заявляем.
      Report8072 разделяет historical33,target5 и остановленный новый набор.

Planning/source assembly: фактическая модель роли `gpt-6-astra` (orchestrator);
usage/cost не предоставлены. Галочки проверок ставить только по фактическому evidence.
