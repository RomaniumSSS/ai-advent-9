# Day32 — точечное ревью tree scope

**Вердикт: APPROVED для offline-исправления; live-исправление ещё не подтверждено.**

Прочитаны изменения `GitSnapshot.build()` и новые scope-тесты. Связанная офлайн-проверка прошла: `uv run --no-sync python -m unittest test_scenarios.ScenarioTests.test_scope_bounds_git_tree_before_read_limit_and_keeps_outside_change test_scenarios.ScenarioTests.test_scoped_tree_paths_are_literal_including_magic_prefix test_review.ReviewTests.test_large_tree_and_manifest_persist_limited -v` — **3 PASS**.

Чтение дерева теперь ограничивается самим Git вызовом: при scope передаются буквальный pathspec каталога и точные pathspec изменённых файлов, а `--literal-pathspecs` защищает имена с `[]` и `:(glob)` от интерпретации как magic. Неизменённое дерево вне scope больше не может исчерпать cap до Python-фильтра; изменённые файлы вне scope при этом остаются в выборке. Новые тесты проверяют дерево >200 KB, docs+code retrieval, изменённый файл вне scope и буквальные pathspec.

Новых дефектов в просмотренном fix не обнаружил. Указанный родителем фактический PR-снимок с base tree 213 957 bytes и 3 scoped chunks здесь повторно не строил; GitHub и платные вызовы не запускались. Поэтому вывод подтверждает реализацию и офлайн-регрессию, но не заменяет новый `--dry-run` на реальном PR.
