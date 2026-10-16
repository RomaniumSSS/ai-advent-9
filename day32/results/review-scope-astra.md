# Day32 — сильное независимое ревью scope и исторического сегмента

Reviewer: gpt-6-astra. **APPROVED — готовность к новому dry/record прогону.**
Существующий неудачный dry остаётся неудачным; исправленный live ещё не проверен.

Независимо прочитаны точечное изменение GitSnapshot.build(), два новых real-Git
теста, review-scope-luna.md, изменения history_row/recorder/SCENARIO и guard test.
Неизменённые части pipeline повторно целиком не пересматривались.

Исправление обосновано: scope и точные изменённые пути передаются в сам
ls-tree до bounded read200KB. --literal-pathspecs исключает интерпретацию
специальных имён. Изменённые текстовые файлы за пределами scope сохраняются;
удалённые по-прежнему читаются отдельно из merge-base. Без scope прежний
лимит полного дерева и limited/dedupe поведение сохраняются. Лимиты не повышены.

Самостоятельно построен snapshot из существующих локальных объектов:
base94badd1603080af39610d1312daa5ab9264e6790,
head2b5776af440f0844e32d3926a87c42ab8cebaa94, scope day32/target.
Полное дерево213957bytes; исправленный snapshot имеет limitations=[],
head:day32/target/git_tool.py и3 corpus files: git_tool.py, docs/contract.md,
docs/provenance.md. Retrieval возвращает docs и code. Это проверка конкретного
PR snapshot без GitHub fetch и без новой модели, а не доказательство нового live.

History helper использует SQLite mode=ro и параметризованный trace_id; требует
существующий error/limited report. Исходные response/report не переписываются.
Исторический сегмент явно подписан как предыдущий dry до исправления, вынесен
в manifest.history и не попадает в новые outcomes. Он не вызывает Runner и не
расходует бюджет. Generic history option предназначен здесь для выбранного
реального ошибочного trace; не считать произвольный offline trace live-доказательством.

Свежие проверки reviewer:

-3 связанных scope/large-tree tests PASS4.271с; включая прежний5000files cap.
-7 recorder guard tests PASS0.014с.
-Readonly past dry manifest: scenario_finished_with_errors; upper error,
 fix limited. Сохранённая история не замаскирована успешным исходом.
-Readonly canonical ledger:3runs, actual/accounted sum $0.014338; удержаний
 сверх reported actual нет.

Новых существенных ошибок в изменённой области не обнаружено. Полный58-test
прогон сообщён исполнителем; reviewer повторил только связанные проверки.
Платных вызовов, публикаций и изменений live ledger reviewer не делал.
Перед финальной приёмкой остаются новый настоящий dry, fresh record, сверка
manifest/calls/ledger и визуальный просмотр видео. Usage/cost ревью не сообщены.
