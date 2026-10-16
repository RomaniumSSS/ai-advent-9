# Day32 — задачи

Разработка начата от main0883264 в ветке `day32-pr-review`.
Учебный PR направлен в неё из `day32-demo-limit10`; commit с кодом/видео — в results/publication.json.
Day31 закрыт; требования Day32 — [SPEC](SPEC.md).

- [x] Проверены main/worktree/инструкции и gh read-only доступ; окружение установлено.
- [x] Сохранены SPEC и сценарий; отсутствие PR проверялось только при подготовке.
- [x] Перед clear обновлён контекст; Astra read-only сверила концепцию с заданием32.
- [x] Сохранены локальные черновики (/tmp/day32-pre-base-20261016T204703Z), база fast-forward до 0883264.
- [x] Закреплён дефект: limit=10 отклоняется вопреки документации. Спека подтверждена.
- [x] Реализованы режимы diff/files/rag и сохранение точного контекста.
- [x] Закреплены интерфейсы модулей в IMPLEMENTATION.md.
- [x] Qwen/Alibaba профиль и общий потолок $0.50 подтверждены пользователем.
- [x] Sol: PR adapter, snapshot/diff, docs+code retrieval, reviewer, ledger и UI.
- [x] Проверены fixtures: mocked PR adapter, настоящий локальный Git, новый SHA, dedupe, ограничения, ошибки.
- [x] Browser: desktop/tablet/mobile, diff/docs+code/prompt, сохранение раскрытых секций; results/browser-check.json.
- [x] Независимые Luna → исправления Sol → Astra → исправления/повторная Astra: APPROVED offline; свежие 17 tests PASS.
- [x] Учебный diff подготовлен; пользователь разрешил baseline/regression commits+push+PR.
- [x] Настоящий PR-trigger/5новых SHA/7новых ответов записи и dedupe проверены; качество оценено отдельно.
- [x] Dry/живое видео11:34, ffprobe/9извлечённых кадров; RESULT/RELEASE_NOTES.
- [x] По просьбе пользователя ожидания ×6: версия 8:39, 10 кадров проверены, исходник сохранён.
- [x] Commit/push 9249205 и remote video blob/size сверены; Drive Anyone/Viewer, anonymous HTTP200.
- [x] Один комментарий с кодом/видео в AG132: наличие подтверждено пользователем 17.10.2026; агентское чтение после reload не доказано.
- [x] Пользователь принял Day32; состояние SPEC и сдачи обновлено.
- [x] Финальные60+8=68тестов PASS, отдельно100generated checks/9SIMULATEDcases.

## Контракт и границы

`PrSnapshot={repository,number,base_sha,head_sha,merge_base,changed_files,diff}`.
`SourceChunk={id,path,start_line,end_line,text,sha256,kind=docs|code}`.
`ReviewReport={status,pr_snapshot,findings[],source_ids[],trace_id}`.
`Finding={category,path,line,evidence,suggestion}`; строки проверяются по нужной версии.
Фиксированный repo и allowlist источников/расширений, ограничения размера/контекста.
Данные PR — недоверенный текст. Код из PR и инструкции внутри него не исполняются.
Отчёт от старого head не выдаётся за новый. Пограничные случаи diff/rename/deletion
не должны превращаться в ложные ссылки. Состояние watcher хранится между перезапусками.
Резерв расходов создаётся до вызова; неизвестная стоимость/неоднозначный сбой
не запускают повтор. Точные сигнатуры фиксируются до параллельных зависимых модулей.

## Порядок

Day31 уже закрыт; повторять его прогоны не нужно. Теперь Day32: событие → снимок →
контекст → ревью → проверяемый отчёт. Подготовку независимых файлов можно делегировать,
но реальные модельные прогоны и видео идут последовательно. Моки/replay не live proof.
Изменения зависимостей/общих инструкций объединяет один координатор.
