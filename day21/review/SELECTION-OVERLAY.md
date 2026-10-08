# Corrected proposal overlay

```sh
python3 day21/review/test_reviewed_selection_overlay.py
python3 day21/review/build_reviewed_selection_overlay.py
```

Immutable private `selection-reviewed-proposals-v1`:rows.json,groups.json,diff-summary.json,manifest.json. SHA `3ecf96d1f103bff0b7cd0975d4703b80535fd088d21303f45d44b2c9ed43c7c0`. Sourceproposalv3/rootsemanticreview SHA pinned;acceptedguards/sourceartifacts before/after unchanged. No newfullpreview,onlyref кsourcepreview. API/raw/source/acceptedmutation0.

3573ID exactlyonce:1467candidateinclude,806exclude,805semanticreview,388invalidmodelreview,82unreadmedia,24acceptedassignments,1transportunresolved.10statuschanges=7review/3exclude;root_review_proposal не approval. Modeldecision/reason/flags и rawmodelgroups сохранены;source_grouprefs/reviewoverlay отдельно. Groups потерявшиеmembers removed/rebuilt;7новых reviewgroups отдельны от validmodelgroups. Replacement1→5,13members;continuation3579 толькоref,не promoted. Group totals733include/738review;dependencies/directreplyrefs/statuses recomputed,81groupsс direct/explicit спорными dependencies.

Synthetictests+pycompilePASS:coverage/dedup,changedstatus/rootrevieworigin,rawgroupsimmutable,continuationrefonly,provenancedrift refusal,immutable/repeat/privacy. Realrepeat:все4artifactSHA совпали,manifesthashesvalid,0700/0600. Нет заявлений о fullcorpusready/семантической приемке. Directdependencies не покрывают всеancestor risks;root separately отметил103candidate groups для внимания поancestor обходу,это неsemanticerror и не расширяет текущийoverlay. Root review дальше;код/artifacts заморожены.

## Final v2 correctness fix

v1 не принят rootreview:explicitimagecontext1895 был потерян и QA3591/3592разделена. Finaloutput `selection-reviewed-proposals-v2`,manifestSHA `615d53241afc38a2a17cf27ba2c93919febfc9a5a6c62aa634748806543d7392`. v1 сохранён как промежуточный,не использовать. Теперь всеmovedreviewmembers per sourcegroup остаются вместе,исходные explicitcontextrefs сохраняются,source directreply refs достраиваются;остальные members исходной ветки не добавляются целиком вcontext.6новыхreviewgroups;итого733include/737reviewgroups. Статусы и10changes unchanged. Tests+realrepeatPASS:пара3591/3592вместе,1902→explicit1895сохранён,rawmodelgroupunchanged;все4artifacthashes repeatidentical. API/acceptedmutation0. Финальнаяv2 заморожена дляrootreview.
