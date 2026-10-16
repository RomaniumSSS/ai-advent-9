# План и интерфейсы

Исполнитель: gpt-6.1-sol. Один последовательный read-only pipeline без исполнения PR.
`review.py`: GitSnapshot.build(repo,number,base,head), retrieve(snapshot),
validate(answer,snapshot,sources), Store.claim/finish, Runner.run.
`cli.py`: fixture, local, watch, serve. `web.py`: только GET, localhost8072.
SQLite хранит уникальный repository/PR/base/head/mode/provider, резерв до запроса,
терминальный отчёт и точные артефакты. Незавершённая claim после падения не повторяется.
Снимки содержат merge-base diff, bounded blobs из object database, docs/code chunks.
RAG — отдельный SQLite FTS5/BM25, без embeddings или старых dayNN imports.
Live только с --live и положительным --budget; один urllib запрос без retry/fallback.
Fixture создаёт отдельный учебный Git и статический явно обозначенный ответ.
Проверки: настоящий локальный Git, FTS5, persistent dedupe/reserve, schema/link guards,
ошибки, rename/delete, ограничение корпуса и недоверенные инструкции; затем UI review.
