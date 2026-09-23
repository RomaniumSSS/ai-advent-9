"""День 15: память, инварианты и состояние задачи в SQLite."""

import sqlite3
import json
from profile import UserProfile
from task_state import Stage, Status, TaskState
from invariants import Invariant
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "history.db"
SCHEMA_VERSION = 7
LAYERS = ("short", "working", "long")

SCHEMA = """
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
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
CREATE TABLE IF NOT EXISTS task_states (
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step TEXT NOT NULL,
    expected_action TEXT,
    version INTEGER NOT NULL,
    artifacts_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, task_id)
);
CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event TEXT NOT NULL,
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    version INTEGER NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS task_events_by_task
ON task_events(user_id, task_id, id);
CREATE TABLE IF NOT EXISTS transition_denials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    version INTEGER NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS transition_denials_by_task
ON transition_denials(user_id, task_id, id);
CREATE TABLE IF NOT EXISTS workflow_proposals (
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    action TEXT NOT NULL,
    result TEXT NOT NULL,
    based_on_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(user_id, task_id)
);
CREATE TABLE IF NOT EXISTS invariants (
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    invariant_id TEXT NOT NULL,
    category TEXT NOT NULL,
    rule TEXT NOT NULL,
    rationale TEXT NOT NULL,
    deny_patterns_json TEXT NOT NULL,
    active INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, task_id, invariant_id)
);
CREATE TABLE IF NOT EXISTS invariant_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    session TEXT NOT NULL,
    phase TEXT NOT NULL,
    decision TEXT NOT NULL,
    invariant_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS invariant_checks_by_task
ON invariant_checks(user_id, task_id, id);
CREATE TABLE IF NOT EXISTS chat_turns (
    turn_id TEXT PRIMARY KEY,
    session TEXT NOT NULL,
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    state_stage TEXT,
    state_status TEXT,
    state_version INTEGER,
    status TEXT NOT NULL,
    error_type TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chat_turns_by_session
ON chat_turns(session, created_at);
CREATE TABLE IF NOT EXISTS chat_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    role TEXT,
    tool_call_id TEXT,
    tool_name TEXT,
    arguments_json TEXT,
    result_json TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost REAL,
    cost_reported REAL,
    created_at TEXT NOT NULL,
    UNIQUE(turn_id, sequence)
);
CREATE INDEX IF NOT EXISTS chat_events_by_turn
ON chat_events(turn_id, sequence);
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
            # AICODE-NOTE: база дня 12 самостоятельная. Открывать здесь файл
            # дня 10 означало бы смешать разные схемы и области памяти.
            if version not in (0, 1, 2, 3, 4, 5, 6, SCHEMA_VERSION):
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

    def load_profile(self) -> UserProfile:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT profile_json FROM user_profiles WHERE user_id = ?",
                (self.user_id,),
            ).fetchone()
        return UserProfile() if row is None else UserProfile.from_dict(json.loads(row[0]))

    def save_profile(self, profile: UserProfile, *, if_missing: bool = False) -> None:
        validated = UserProfile.from_dict(profile.to_dict())
        conflict = ("DO NOTHING" if if_missing else
                    "DO UPDATE SET profile_json=excluded.profile_json, updated_at=excluded.updated_at")
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO user_profiles VALUES (?, ?, ?) ON CONFLICT(user_id) " + conflict,
                (self.user_id, json.dumps(validated.to_dict(), ensure_ascii=False), now()),
            )

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

    @staticmethod
    def _chat_sequence(connection, turn_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM chat_events WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()
        return int(row[0])

    def start_chat_turn(self, turn_id: str, state: TaskState | None) -> None:
        stamp = now()
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO chat_turns(turn_id, session, user_id, task_id, state_stage, "
                "state_status, state_version, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)",
                (
                    identifier(turn_id, "turn_id"), self.session, self.user_id, self.task_id,
                    None if state is None else state.stage.value,
                    None if state is None else state.status.value,
                    None if state is None else state.version,
                    stamp, stamp,
                ),
            )

    def record_chat_event(
        self,
        turn_id: str,
        *,
        kind: str,
        status: str,
        role: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        arguments: object = None,
        result: object = None,
    ) -> None:
        with self._connect() as connection, connection:
            sequence = self._chat_sequence(connection, turn_id)
            connection.execute(
                "INSERT INTO chat_events(turn_id, sequence, kind, status, role, "
                "tool_call_id, tool_name, arguments_json, result_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    turn_id, sequence, kind, status, role, tool_call_id, tool_name,
                    None if arguments is None else json.dumps(arguments, ensure_ascii=False, sort_keys=True),
                    None if result is None else json.dumps(result, ensure_ascii=False, sort_keys=True),
                    now(),
                ),
            )

    def record_provider_event(self, turn_id: str, kind: str, reply) -> None:
        """Provider audit и legacy usage ledger фиксируются одной transaction."""

        with self._connect() as connection, connection:
            sequence = self._chat_sequence(connection, turn_id)
            status = "error" if not reply.ok or reply.empty or reply.truncated else "success"
            connection.execute(
                "INSERT INTO chat_events(turn_id, sequence, kind, status, role, result_json, "
                "prompt_tokens, completion_tokens, cost, cost_reported, created_at) "
                "VALUES (?, ?, ?, ?, 'provider', ?, ?, ?, ?, ?, ?)",
                (
                    turn_id, sequence, kind, status,
                    json.dumps({
                        "finish_reason": reply.finish_reason,
                        "error": reply.error,
                        "tool_request_count": len(reply.tool_requests),
                    }, ensure_ascii=False, sort_keys=True),
                    reply.prompt_tokens, reply.completion_tokens, reply.cost,
                    reply.cost_reported, now(),
                ),
            )
            connection.execute(
                "INSERT INTO calls(session, created_at, model, prompt_tokens, "
                "completion_tokens, cost, cost_reported, empty) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.session, now(), reply.model, reply.prompt_tokens,
                    reply.completion_tokens, reply.cost, reply.cost_reported,
                    int(reply.empty),
                ),
            )

    @staticmethod
    def _state_matches_row(row, expected: TaskState | None) -> bool:
        if expected is None:
            return row is None
        return row is not None and (
            row["stage"], row["status"], row["version"]
        ) == (expected.stage.value, expected.status.value, expected.version)

    def chat_state_matches(self, expected: TaskState | None) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT stage, status, version FROM task_states "
                "WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            ).fetchone()
        return self._state_matches_row(row, expected)

    def finish_chat_turn(self, turn_id: str, status: str, error_type: str | None = None) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE chat_turns SET status = ?, error_type = ?, updated_at = ? "
                "WHERE turn_id = ?",
                (status, error_type, now(), turn_id),
            )

    def finalize_chat_turn(
        self,
        turn_id: str,
        question: str,
        reply,
        expected_state: TaskState | None,
    ) -> bool:
        """FSM compare и conversation commit в одной write transaction."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT stage, status, version FROM task_states "
                    "WHERE user_id = ? AND task_id = ?",
                    (self.user_id, self.task_id),
                ).fetchone()
                if not self._state_matches_row(row, expected_state):
                    connection.execute(
                        "UPDATE chat_turns SET status='invalidated', error_type='fsm_changed', "
                        "updated_at=? WHERE turn_id=?",
                        (now(), turn_id),
                    )
                    connection.commit()
                    return False
                stamp = now()
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
                        self.session, reply.text, stamp, reply.model, reply.elapsed,
                        reply.prompt_tokens, reply.completion_tokens, reply.cost,
                    ),
                )
                connection.execute(
                    "UPDATE sessions SET updated_at = ? WHERE session = ?",
                    (stamp, self.session),
                )
                connection.execute(
                    "UPDATE chat_turns SET status='completed', error_type=NULL, updated_at=? "
                    "WHERE turn_id=?",
                    (stamp, turn_id),
                )
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

    def chat_turn(self, turn_id: str) -> dict | None:
        with self._connect() as connection:
            turn = connection.execute(
                "SELECT turn_id, status, error_type, created_at, updated_at FROM chat_turns "
                "WHERE turn_id = ? AND session = ?",
                (turn_id, self.session),
            ).fetchone()
            if turn is None:
                return None
            events = connection.execute(
                "SELECT sequence, kind, status, role, tool_call_id, tool_name, "
                "arguments_json, result_json, prompt_tokens, completion_tokens, cost, "
                "cost_reported, created_at FROM chat_events WHERE turn_id = ? ORDER BY sequence",
                (turn_id,),
            ).fetchall()
        result = dict(turn)
        result["events"] = []
        for event in events:
            item = dict(event)
            item["arguments"] = (
                None if item.pop("arguments_json") is None
                else json.loads(event["arguments_json"])
            )
            item["result"] = (
                None if item.pop("result_json") is None
                else json.loads(event["result_json"])
            )
            result["events"].append(item)
        return result

    def save_invariant(self, invariant: Invariant, *, if_missing: bool = False) -> None:
        validated = Invariant.from_dict(invariant.to_dict())
        conflict = ("DO NOTHING" if if_missing else
                    "DO UPDATE SET category=excluded.category, rule=excluded.rule, "
                    "rationale=excluded.rationale, deny_patterns_json=excluded.deny_patterns_json, "
                    "active=excluded.active, updated_at=excluded.updated_at")
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO invariants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, task_id, invariant_id) " + conflict,
                (
                    self.user_id, self.task_id, validated.invariant_id,
                    validated.category.value, validated.rule, validated.rationale,
                    json.dumps({
                        "request_patterns": list(validated.deny_patterns),
                        "forbidden_terms": list(validated.forbidden_terms),
                        "response_patterns": list(validated.response_patterns),
                        "request_allow_patterns": list(validated.request_allow_patterns),
                        "response_allow_patterns": list(validated.response_allow_patterns),
                    }, ensure_ascii=False),
                    int(validated.active), now(),
                ),
            )

    def load_invariants(self) -> tuple[Invariant, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT invariant_id, category, rule, rationale, deny_patterns_json, active "
                "FROM invariants WHERE user_id = ? AND task_id = ? ORDER BY invariant_id",
                (self.user_id, self.task_id),
            ).fetchall()
        def decode_policy(raw: str) -> dict:
            value = json.loads(raw)
            if isinstance(value, list):
                return {"request_patterns": value}
            if not isinstance(value, dict):
                raise ValueError("policy инварианта должен быть объектом")
            return value

        result = []
        for row in rows:
            policy = decode_policy(row["deny_patterns_json"])
            result.append(Invariant.from_dict({
            "invariant_id": row["invariant_id"],
            "category": row["category"],
            "rule": row["rule"],
            "rationale": row["rationale"],
            "deny_patterns": policy.get("request_patterns", []),
            "forbidden_terms": policy.get("forbidden_terms", []),
            "response_patterns": policy.get("response_patterns", []),
            "request_allow_patterns": policy.get("request_allow_patterns", []),
            "response_allow_patterns": policy.get("response_allow_patterns", []),
            "active": bool(row["active"]),
            }))
        return tuple(result)

    def record_invariant_check(self, phase: str, decision: str, ids: tuple[str, ...]) -> None:
        if phase not in {"request", "response"} or decision not in {"allow", "deny", "explain"}:
            raise ValueError("некорректный результат проверки инвариантов")
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO invariant_checks(user_id, task_id, session, phase, decision, "
                "invariant_ids_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.user_id, self.task_id, self.session, phase, decision,
                 json.dumps(list(ids), ensure_ascii=False), now()),
            )

    def invariant_checks(self, limit: int = 20) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT phase, decision, invariant_ids_json, created_at FROM invariant_checks "
                "WHERE user_id = ? AND task_id = ? ORDER BY id DESC LIMIT ?",
                (self.user_id, self.task_id, limit),
            ).fetchall()
        return [{
            "phase": row["phase"], "decision": row["decision"],
            "invariant_ids": json.loads(row["invariant_ids_json"]),
            "created_at": row["created_at"],
        } for row in rows]

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

    def load_task_state(self) -> TaskState | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT objective, stage, status, current_step, expected_action, "
                "version, artifacts_json FROM task_states "
                "WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            ).fetchone()
        if row is None:
            return None
        return TaskState(
            objective=row["objective"],
            stage=Stage(row["stage"]),
            status=Status(row["status"]),
            current_step=row["current_step"],
            expected_action=row["expected_action"],
            version=row["version"],
            artifacts=json.loads(row["artifacts_json"]),
        )

    @staticmethod
    def _state_from_row(row) -> TaskState:
        return TaskState(
            objective=row["objective"],
            stage=Stage(row["stage"]),
            status=Status(row["status"]),
            current_step=row["current_step"],
            expected_action=row["expected_action"],
            version=row["version"],
            artifacts=json.loads(row["artifacts_json"]),
        )

    def load_workflow_proposal(self) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT action, result, based_on_version, created_at "
                "FROM workflow_proposals WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            ).fetchone()
        return None if row is None else dict(row)

    def save_workflow_proposal(
        self, state: TaskState, action: str, result: str
    ) -> dict:
        if action != state.expected_action:
            raise ValueError("предложение не совпадает с ожидаемым действием FSM")
        stamp = now()
        with self._connect() as connection, connection:
            current = connection.execute(
                "SELECT version, status FROM task_states "
                "WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            ).fetchone()
            if (
                current is None
                or current["version"] != state.version
                or current["status"] != Status.ACTIVE.value
            ):
                raise RuntimeError("состояние изменилось; предложение модели отброшено")
            connection.execute(
                "INSERT INTO workflow_proposals VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, task_id) DO UPDATE SET "
                "action=excluded.action, result=excluded.result, "
                "based_on_version=excluded.based_on_version, created_at=excluded.created_at",
                (self.user_id, self.task_id, action, result, state.version, stamp),
            )
        return self.load_workflow_proposal()

    def apply_workflow_proposal(self) -> TaskState:
        with self._connect() as connection, connection:
            row = connection.execute(
                "SELECT objective, stage, status, current_step, expected_action, "
                "version, artifacts_json FROM task_states "
                "WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            ).fetchone()
            proposal = connection.execute(
                "SELECT action, result, based_on_version FROM workflow_proposals "
                "WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            ).fetchone()
            if row is None or proposal is None:
                raise ValueError("нет предложения, ожидающего решения")
            state = self._state_from_row(row)
            if proposal["based_on_version"] != state.version:
                raise RuntimeError("предложение устарело относительно FSM")
            updated = state.apply(proposal["action"], proposal["result"])
            self._update_task_row(connection, updated, state.version)
            connection.execute(
                "DELETE FROM workflow_proposals WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            )
            self._append_task_event(
                connection, proposal["action"], state.stage, updated, proposal["result"]
            )
        return updated

    def reject_workflow_proposal(self, feedback: str) -> TaskState:
        feedback = feedback.strip()
        if not feedback:
            raise ValueError("замечание не может быть пустым")
        with self._connect() as connection, connection:
            row = connection.execute(
                "SELECT objective, stage, status, current_step, expected_action, "
                "version, artifacts_json FROM task_states "
                "WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            ).fetchone()
            proposal = connection.execute(
                "SELECT based_on_version FROM workflow_proposals "
                "WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            ).fetchone()
            if row is None or proposal is None:
                raise ValueError("нет предложения, ожидающего решения")
            state = self._state_from_row(row)
            if proposal["based_on_version"] != state.version:
                raise RuntimeError("предложение устарело относительно FSM")
            connection.execute(
                "DELETE FROM workflow_proposals WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            )
            if state.stage is Stage.VALIDATION:
                updated = state.apply("request_changes", feedback)
                self._update_task_row(connection, updated, state.version)
                self._append_task_event(
                    connection, "request_changes", state.stage, updated, feedback
                )
            elif state.stage is Stage.PLANNING:
                updated = state
                self._append_task_event(
                    connection, "proposal_rejected", state.stage, state, feedback
                )
            else:
                raise ValueError("пересмотр предложения здесь недоступен")
        return updated

    def request_task_changes(self, feedback: str) -> TaskState:
        """Вернуть проверку на доработку атомарно с записью причины."""
        feedback = feedback.strip()
        if not feedback:
            raise ValueError("замечание не может быть пустым")
        with self._connect() as connection, connection:
            row = connection.execute(
                "SELECT objective, stage, status, current_step, expected_action, "
                "version, artifacts_json FROM task_states "
                "WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            ).fetchone()
            if row is None:
                raise ValueError("сначала создайте состояние задачи")
            state = self._state_from_row(row)
            if state.stage is not Stage.VALIDATION:
                raise ValueError("замечания принимаются только на этапе validation")
            updated = state.apply("request_changes", feedback)
            self._update_task_row(connection, updated, state.version)
            connection.execute(
                "DELETE FROM workflow_proposals WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            )
            self._append_task_event(
                connection, "request_changes", state.stage, updated, feedback
            )
        return updated

    def latest_workflow_feedback(self, version: int) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT details FROM task_events WHERE user_id = ? AND task_id = ? "
                "AND version = ? AND event = 'proposal_rejected' ORDER BY id DESC LIMIT 1",
                (self.user_id, self.task_id, version),
            ).fetchone()
        return "" if row is None else row["details"]

    def create_task_state(self, objective: str) -> TaskState:
        state = TaskState.create(objective)
        stamp = now()
        with self._connect() as connection, connection:
            try:
                connection.execute(
                    "INSERT INTO task_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    self._task_values(state, stamp),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("у этой задачи уже есть состояние") from error
            self._append_task_event(connection, "created", None, state, "")
        return state

    def save_task_state(
        self,
        state: TaskState,
        *,
        previous_version: int,
        event: str,
        details: str = "",
        from_stage: Stage | None = None,
    ) -> TaskState:
        """Снимок и событие фиксируются вместе; версия не даёт затереть гонку."""
        stamp = now()
        with self._connect() as connection, connection:
            self._update_task_row(connection, state, previous_version, stamp)
            if event in {"pause", "resume"}:
                connection.execute(
                    "UPDATE workflow_proposals SET based_on_version = ? "
                    "WHERE user_id = ? AND task_id = ? AND based_on_version = ?",
                    (state.version, self.user_id, self.task_id, previous_version),
                )
            else:
                connection.execute(
                    "DELETE FROM workflow_proposals WHERE user_id = ? AND task_id = ?",
                    (self.user_id, self.task_id),
                )
            self._append_task_event(
                connection,
                event,
                from_stage or state.stage,
                state,
                details,
            )
        return state

    def _update_task_row(
        self, connection, state: TaskState, previous_version: int, stamp: str | None = None
    ) -> None:
        cursor = connection.execute(
            "UPDATE task_states SET objective=?, stage=?, status=?, current_step=?, "
            "expected_action=?, version=?, artifacts_json=?, updated_at=? "
            "WHERE user_id=? AND task_id=? AND version=?",
            (
                state.objective, state.stage.value, state.status.value,
                state.current_step, state.expected_action, state.version,
                json.dumps(state.artifacts, ensure_ascii=False, sort_keys=True),
                stamp or now(), self.user_id, self.task_id, previous_version,
            ),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("состояние уже изменилось; перечитайте задачу")

    def task_events(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event, from_stage, to_stage, version, details, created_at "
                "FROM task_events WHERE user_id = ? AND task_id = ? ORDER BY id",
                (self.user_id, self.task_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_transition_denial(
        self, action: str, stage: Stage, version: int, reason: str
    ) -> None:
        # AICODE-NOTE: отказ отдельно от task_events, чтобы журнал успешных
        # переходов не выглядел как изменившаяся FSM.
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO transition_denials(user_id, task_id, stage, version, "
                "action, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.user_id, self.task_id, stage.value, version,
                 action[:100], reason[:1000], now()),
            )

    def transition_denials(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT stage, version, action, reason, created_at "
                "FROM transition_denials WHERE user_id = ? AND task_id = ? "
                "ORDER BY id DESC LIMIT 20",
                (self.user_id, self.task_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_task_state(self) -> None:
        """Удалить только FSM текущей задачи; память и профиль не затрагиваются."""
        with self._connect() as connection, connection:
            connection.execute(
                "DELETE FROM transition_denials WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            )
            connection.execute(
                "DELETE FROM workflow_proposals WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            )
            connection.execute(
                "DELETE FROM task_events WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            )
            connection.execute(
                "DELETE FROM task_states WHERE user_id = ? AND task_id = ?",
                (self.user_id, self.task_id),
            )

    def _task_values(self, state: TaskState, stamp: str) -> tuple:
        return (
            self.user_id,
            self.task_id,
            state.objective,
            state.stage.value,
            state.status.value,
            state.current_step,
            state.expected_action,
            state.version,
            json.dumps(state.artifacts, ensure_ascii=False, sort_keys=True),
            stamp,
        )

    def _append_task_event(
        self,
        connection,
        event: str,
        from_stage: Stage | None,
        state: TaskState,
        details: str,
    ) -> None:
        connection.execute(
            "INSERT INTO task_events(user_id, task_id, event, from_stage, to_stage, "
            "version, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.user_id,
                self.task_id,
                event,
                None if from_stage is None else from_stage.value,
                state.stage.value,
                state.version,
                details,
                now(),
            ),
        )

    def clear(self) -> None:
        """Новая беседа очищает короткий слой, сохраняя задачу и пользователя."""
        with self._connect() as connection, connection:
            self.clear_in_transaction(connection, self.session)

    @staticmethod
    def clear_in_transaction(connection, session: str) -> None:
        """Тот же reset внутри атомарного campaign fixture."""
        connection.execute(
            "DELETE FROM chat_events WHERE turn_id IN "
            "(SELECT turn_id FROM chat_turns WHERE session = ?)",
            (session,),
        )
        connection.execute("DELETE FROM chat_turns WHERE session = ?", (session,))
        for table in ("messages", "calls", "short_notes"):
            connection.execute(f"DELETE FROM {table} WHERE session = ?", (session,))
        connection.execute("UPDATE sessions SET updated_at = ? WHERE session = ?", (now(), session))

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
