"""День 11: архив разговора и три отдельные области памяти в SQLite."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "history.db"
SCHEMA_VERSION = 1
LAYERS = ("short", "working", "long")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    model TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    model TEXT,
    elapsed REAL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost REAL
);
CREATE INDEX IF NOT EXISTS messages_by_session ON messages(session, id);
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    created_at TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost REAL,
    cost_reported REAL,
    empty INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS short_notes (
    session TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(session, key)
);
CREATE TABLE IF NOT EXISTS working_notes (
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, task_id, key)
);
CREATE TABLE IF NOT EXISTS long_notes (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, key)
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} не может быть пустым")
    result = value.strip()
    if len(result) > 80:
        raise ValueError(f"{label} длиннее 80 символов")
    return result


class SqliteStore:
    """Сессия, задача и пользователь задают разные границы видимости."""

    def __init__(
        self,
        path: str | Path = DEFAULT_DB,
        session: str = "main",
        task_id: str = "project",
        user_id: str = "roman",
    ):
        self.path = Path(path)
        self.session = identifier(session, "сессия")
        self.task_id = identifier(task_id, "задача")
        self.user_id = identifier(user_id, "пользователь")
        self._prepare()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5.0)
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.row_factory = sqlite3.Row
            yield connection
        finally:
            connection.close()

    def _prepare(self) -> None:
        if not self.path.parent.exists():
            raise FileNotFoundError(f"нет каталога {self.path.parent}")
        with self._connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            # AICODE-NOTE: база дня 11 самостоятельная. Открывать здесь файл
            # дня 10 означало бы смешать разные схемы и области памяти.
            if version not in (0, SCHEMA_VERSION):
                raise RuntimeError(f"несовместимая схема SQLite: версия {version}")
            connection.executescript(SCHEMA)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            row = connection.execute(
                "SELECT user_id, task_id FROM sessions WHERE session = ?",
                (self.session,),
            ).fetchone()
            if row and (row["user_id"], row["task_id"]) != (
                self.user_id,
                self.task_id,
            ):
                raise ValueError(
                    "эта сессия уже принадлежит другому пользователю или задаче; "
                    "задайте новое имя сессии"
                )
            connection.commit()

    def config_of_record(self) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT model, system_prompt, created_at, updated_at "
                "FROM sessions WHERE session = ?",
                (self.session,),
            ).fetchone()
        return dict(row) if row else None

    def remember_config(self, model: str, system_prompt: str) -> None:
        stamp = now()
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO sessions(session, user_id, task_id, model, system_prompt, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(session) DO UPDATE SET model = excluded.model, "
                "system_prompt = excluded.system_prompt, updated_at = excluded.updated_at",
                (
                    self.session,
                    self.user_id,
                    self.task_id,
                    model,
                    system_prompt,
                    stamp,
                    stamp,
                ),
            )

    def load(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT role, content FROM messages WHERE session = ? ORDER BY id",
                (self.session,),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def append_turn(self, question: str, reply) -> None:
        stamp = now()
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO messages(session, role, content, created_at) "
                "VALUES (?, 'user', ?, ?)",
                (self.session, question, stamp),
            )
            connection.execute(
                "INSERT INTO messages(session, role, content, created_at, model, "
                "elapsed, prompt_tokens, completion_tokens, cost) "
                "VALUES (?, 'assistant', ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.session,
                    reply.text,
                    stamp,
                    reply.model,
                    reply.elapsed,
                    reply.prompt_tokens,
                    reply.completion_tokens,
                    reply.cost,
                ),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session = ?",
                (stamp, self.session),
            )

    def append_call(self, reply) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO calls(session, created_at, model, prompt_tokens, "
                "completion_tokens, cost, cost_reported, empty) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.session,
                    now(),
                    reply.model,
                    reply.prompt_tokens,
                    reply.completion_tokens,
                    reply.cost,
                    reply.cost_reported,
                    int(reply.empty),
                ),
            )

    def _scope(self, layer: str) -> tuple[str, tuple[str, ...]]:
        if layer == "short":
            return "short_notes", (self.session,)
        if layer == "working":
            return "working_notes", (self.user_id, self.task_id)
        if layer == "long":
            return "long_notes", (self.user_id,)
        raise ValueError(f"слой должен быть одним из: {', '.join(LAYERS)}")

    def load_notes(self, layer: str) -> dict[str, str]:
        table, scope = self._scope(layer)
        columns = {
            "short": "session",
            "working": "user_id = ? AND task_id",
            "long": "user_id",
        }[layer]
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT key, value FROM {table} WHERE {columns} = ? ORDER BY key",
                scope,
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def notes(self) -> dict[str, dict[str, str]]:
        return {layer: self.load_notes(layer) for layer in LAYERS}

    def save_note(self, layer: str, key: str, value: str) -> None:
        table, scope = self._scope(layer)
        key = identifier(key, "ключ")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("значение не может быть пустым")
        value = value.strip()
        if len(value) > 2000:
            raise ValueError("значение длиннее 2000 символов")
        fields = {
            "short": "session, key, value, updated_at",
            "working": "user_id, task_id, key, value, updated_at",
            "long": "user_id, key, value, updated_at",
        }[layer]
        placeholders = ", ".join("?" for _ in range(len(scope) + 3))
        with self._connect() as connection, connection:
            connection.execute(
                f"INSERT INTO {table}({fields}) VALUES ({placeholders}) "
                "ON CONFLICT DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (*scope, key, value, now()),
            )

    def forget_note(self, layer: str, key: str) -> bool:
        table, scope = self._scope(layer)
        key = identifier(key, "ключ")
        columns = {
            "short": "session",
            "working": "user_id = ? AND task_id",
            "long": "user_id",
        }[layer]
        with self._connect() as connection, connection:
            cursor = connection.execute(
                f"DELETE FROM {table} WHERE {columns} = ? AND key = ?",
                (*scope, key),
            )
        return cursor.rowcount > 0

    def clear(self) -> None:
        """Новая беседа очищает короткий слой, сохраняя задачу и пользователя."""
        with self._connect() as connection, connection:
            for table in ("messages", "calls", "short_notes"):
                connection.execute(
                    f"DELETE FROM {table} WHERE session = ?",
                    (self.session,),
                )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session = ?",
                (now(), self.session),
            )

    def stats(self) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FILTER (WHERE role = 'user') AS turns, "
                "COUNT(*) AS messages FROM messages WHERE session = ?",
                (self.session,),
            ).fetchone()
            calls = connection.execute(
                "SELECT COUNT(*) FROM calls WHERE session = ?",
                (self.session,),
            ).fetchone()[0]
        return {"session": self.session, "task_id": self.task_id,
                "user_id": self.user_id, **dict(row), "calls": calls}
