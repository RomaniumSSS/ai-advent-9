"""День 10: архив, facts, ветки и журнал расхода в SQLite.

Схема v4 заменяет summary дня 9 на память «ключ-значение» и таблицу веток.
Ветка — это обычная сессия в том же файле, а не новая сущность: изоляция сессий
уже есть и уже переживает перезапуск, а вторая система для того же разъезжалась
бы с первой. База дня 10 самостоятельна; ход пишется одной транзакцией."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "history.db"
DEFAULT_SESSION = "main"

# Версия схемы. Читается и пишется в PRAGMA user_version — счётчик, который
# SQLite держит в самом файле специально для этого. Смысл в отказе: база,
# написанная более новой версией кода, до нас не разберётся, и упасть на ней
# честнее, чем прочитать половину полей и молча потерять остальные.
SCHEMA_VERSION = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session    TEXT    NOT NULL,
    role       TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    model      TEXT,
    elapsed    REAL,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    cost       REAL
);

CREATE INDEX IF NOT EXISTS messages_by_session ON messages (session, id);

CREATE TABLE IF NOT EXISTS sessions (
    name          TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    model         TEXT NOT NULL,
    system_prompt TEXT NOT NULL
);

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
CREATE INDEX IF NOT EXISTS calls_by_session ON calls (session, id);
CREATE TABLE IF NOT EXISTS web_requests (
    session TEXT NOT NULL, request_id TEXT NOT NULL, question TEXT NOT NULL,
    response TEXT, PRIMARY KEY(session, request_id)
);
CREATE TABLE IF NOT EXISTS facts (
    session    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (session, key)
);

CREATE TABLE IF NOT EXISTS branches (
    session    TEXT PRIMARY KEY,
    parent     TEXT NOT NULL,
    checkpoint INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

"""


def now() -> str:
    """Время в UTC с явной зоной. Локальное время в базе — заявка на путаницу
    при первом же переезде или переводе часов."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SqliteStore:
    """Память агента между запусками. Один файл, много именованных сессий.

    Сессия — это отдельный разговор внутри одного файла. Разные сессии не видят
    друг друга так же, как в дне 6 не видели друг друга два агента в процессе;
    только теперь граница переживает выключение.
    """

    def __init__(self, path=DEFAULT_DB, session: str = DEFAULT_SESSION):
        session = session.strip()
        if not session:
            raise ValueError("имя сессии не может быть пустым")
        self.path = Path(path)
        self.session = session
        self._prepare()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5.0)
        try:
            # WAL: терминал и панель — два процесса на одном файле. Без него
            # читатель и писатель блокируют друг друга, и «база занята» прилетает
            # в момент, когда ответ модели уже получен и оплачен.
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
            with connection:
                # Блокировка до чтения версии не даёт двум процессам перенести
                # одни и те же старые замеры дважды.
                connection.executescript("BEGIN IMMEDIATE;\n" + SCHEMA)
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > SCHEMA_VERSION:
                    raise RuntimeError(
                        f"база {self.path} написана схемой версии {version}, "
                        f"этот код знает только {SCHEMA_VERSION}"
                    )
                if version < 2:
                    connection.execute(
                        "INSERT INTO calls (session, created_at, model, prompt_tokens, "
                        "completion_tokens, cost) SELECT session, created_at, "
                        "COALESCE(model, 'unknown'), prompt_tokens, completion_tokens, cost "
                        "FROM messages WHERE role = 'assistant' ORDER BY id"
                    )
                if version < 3:
                    connection.execute(
                        "ALTER TABLE calls ADD COLUMN kind TEXT NOT NULL DEFAULT 'chat'"
                    )
                # Отдельного шага для v4 нет, и это не упущение: facts и branches
                # заводятся самой схемой, а summary дня 9 сюда не переезжает —
                # переносить из v3 нечего.
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def load(self) -> list[dict]:
        """История сессии в том виде, в каком она уедет в модель.

        Наружу отдаются только `role` и `content`: всё остальное в таблице —
        для человека и для отчёта, и отправлять это модели значило бы платить
        за собственную бухгалтерию токенами.
        """
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT role, content FROM messages WHERE session = ? ORDER BY id",
                (self.session,),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def append_turn(self, question: str, reply) -> None:
        """Один завершённый ход: вопрос и ответ, одной транзакцией.

        `reply` — объект `Reply` из `agent.py`. Хранилище берёт из него замеры,
        но не решает, класть ли ход: неудачные ходы сюда просто не доходят.
        """
        stamp = now()
        with self._connect() as connection:
            with connection:  # commit при выходе, rollback при исключении
                connection.execute(
                    "INSERT INTO messages (session, role, content, created_at) "
                    "VALUES (?, 'user', ?, ?)",
                    (self.session, question, stamp),
                )
                connection.execute(
                    "INSERT INTO messages (session, role, content, created_at, model, "
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
                    "UPDATE sessions SET updated_at = ? WHERE name = ?",
                    (stamp, self.session),
                )

    def append_call(self, reply, kind="chat") -> None:
        """Замер ответа API, в том числе пустого, до записи переписки.

        Отдельная транзакция сохраняет расход даже при сбое записи сообщений.
        Локальный отказ и ошибки без usage сюда не попадают.
        """
        with self._connect() as connection:
            with connection:
                connection.execute(
                    "INSERT INTO calls (session, created_at, model, prompt_tokens, "
                    "completion_tokens, cost, cost_reported, empty, kind) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        self.session,
                        now(),
                        reply.model,
                        reply.prompt_tokens,
                        reply.completion_tokens,
                        reply.cost,
                        reply.cost_reported,
                        reply.empty,
                        kind,
                    ),
                )

    def remember_config(self, model: str, system_prompt: str) -> None:
        """Роль и модель сессии — в отдельной таблице, а не в списке сообщений.

        Системный промпт не реплика: в дне 6 он сознательно не кладётся в историю,
        иначе после `reset()` агент терял бы роль. Но запомнить его всё же нужно —
        только затем, чтобы при следующем запуске заметить, что история снята под
        другой ролью, и сказать это вслух, а не делать вид, что разговор тот же.
        """
        stamp = now()
        with self._connect() as connection:
            with connection:
                connection.execute(
                    "INSERT INTO sessions (name, created_at, updated_at, model, "
                    "system_prompt) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(name) DO UPDATE SET updated_at = excluded.updated_at, "
                    "model = excluded.model, system_prompt = excluded.system_prompt",
                    (self.session, stamp, stamp, model, system_prompt),
                )

    def config_of_record(self) -> dict | None:
        """С какой моделью и ролью сессия писалась в прошлый раз. None — новая."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT model, system_prompt, created_at, updated_at "
                "FROM sessions WHERE name = ?",
                (self.session,),
            ).fetchone()
        return dict(row) if row else None

    def stats(self) -> dict:
        """Переписка и расход имеют разные источники: messages и calls.

        SUM в SQLite пропускает NULL. Неполную сумму нельзя выдавать за итог:
        если хотя бы один замер отсутствует, итог этого показателя неизвестен.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FILTER (WHERE role = 'user') AS turns, "
                "COUNT(*) AS messages, MIN(created_at) AS first_at, "
                "MAX(created_at) AS last_at FROM messages WHERE session = ?",
                (self.session,),
            ).fetchone()
        calls = self.growth()
        result = {"session": self.session, **dict(row), "calls": len(calls)}
        for key in ("prompt_tokens", "completion_tokens", "cost", "cost_reported"):
            values = [call[key] for call in calls]
            result[key] = (
                sum(values)
                if values and all(value is not None for value in values)
                else None
            )
        return result

    def growth(self) -> list[dict]:
        """Статистика каждого ответа API, включая пустые, в порядке вызовов."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT created_at, model, prompt_tokens, completion_tokens, cost, "
                "cost_reported, empty, kind FROM calls WHERE session = ? ORDER BY id",
                (self.session,),
            ).fetchall()
        return [dict(row) for row in rows]

    def sessions(self) -> list[dict]:
        """Все разговоры в файле, свежие сверху. Считаются по сообщениям, а не
        по таблице `sessions`: та могла не завестись, если базу писал другой код."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT session, COUNT(*) FILTER (WHERE role = 'user') AS turns, "
                "MAX(created_at) AS last_at FROM messages "
                "GROUP BY session ORDER BY last_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def clear(self) -> None:
        """Забыть эту сессию — и в базе тоже.

        Без последней строки `/reset` очищал бы только память процесса, а
        следующий запуск воскрешал бы «забытое». Рассинхрон памяти и диска —
        самый тихий сорт поломки: всё работает, просто агент помнит не то.
        """
        with self._connect() as connection:
            with connection:
                connection.execute(
                    "DELETE FROM messages WHERE session = ?", (self.session,)
                )
                connection.execute(
                    "DELETE FROM sessions WHERE name = ?", (self.session,)
                )
                connection.execute(
                    "DELETE FROM calls WHERE session = ?", (self.session,)
                )
                connection.execute(
                    "DELETE FROM facts WHERE session = ?", (self.session,)
                )
                connection.execute(
                    "DELETE FROM branches WHERE session = ?", (self.session,)
                )
                connection.execute(
                    "DELETE FROM web_requests WHERE session = ?", (self.session,)
                )

    def load_facts(self) -> dict:
        """Память «ключ-значение» этой сессии. Пустой словарь — её просто нет."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key, value FROM facts WHERE session = ? ORDER BY key",
                (self.session,),
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def save_facts(self, values: dict) -> None:
        """Записать память целиком, одной транзакцией.

        Ключи, которых в `values` нет, из базы НЕ удаляются: стирание памяти —
        не побочный эффект записи. Единственное место, где facts исчезают, —
        `clear()`, и туда приходят по явной команде человека.
        """
        stamp = now()
        with self._connect() as connection:
            with connection:
                connection.executemany(
                    "INSERT INTO facts VALUES (?, ?, ?, ?) ON CONFLICT(session, key) "
                    "DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                    [
                        (self.session, key, value, stamp)
                        for key, value in values.items()
                    ],
                )

    def fork(self, new_session: str, checkpoint: int) -> None:
        """Ветка от точки `checkpoint`: копия первых N сообщений и текущих facts.

        Копия, а не ссылка на общий префикс. Ссылка была бы экономнее, но тогда
        ветка перестала бы быть обычной сессией: всякий читатель истории должен
        был бы знать про склейку, а `clear()` одной ветки уносил бы начало другой.

        Граница считается в сообщениях, а не в ходах, и проверяется по факту
        сохранённой истории: checkpoint из головы вызывающего кода мог быть снят
        до того, как в базу лёг последний ход.
        """
        new_session = new_session.strip()
        if not new_session:
            raise ValueError("имя ветки не может быть пустым")
        if new_session == self.session:
            raise ValueError("ветка не может совпадать с исходной сессией")
        if type(checkpoint) is not int or checkpoint < 0:
            raise ValueError("checkpoint должен быть неотрицательным целым")
        stamp = now()
        with self._connect() as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT 1 FROM messages WHERE session = ? LIMIT 1", (new_session,)
                ).fetchone():
                    raise ValueError(f"сессия {new_session!r} уже существует")
                rows = connection.execute(
                    "SELECT role, content, created_at, model, elapsed, prompt_tokens, "
                    "completion_tokens, cost FROM messages WHERE session = ? "
                    "ORDER BY id LIMIT ?",
                    (self.session, checkpoint),
                ).fetchall()
                if len(rows) < checkpoint:
                    raise ValueError(
                        f"в сессии {self.session!r} только {len(rows)} сообщений, "
                        f"граница {checkpoint} вне истории"
                    )
                connection.executemany(
                    "INSERT INTO messages (session, role, content, created_at, model, "
                    "elapsed, prompt_tokens, completion_tokens, cost) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [(new_session, *tuple(row)) for row in rows],
                )
                connection.execute(
                    "INSERT INTO facts SELECT ?, key, value, ? FROM facts WHERE session = ?",
                    (new_session, stamp, self.session),
                )
                connection.execute(
                    "INSERT INTO sessions SELECT ?, ?, ?, model, system_prompt "
                    "FROM sessions WHERE name = ?",
                    (new_session, stamp, stamp, self.session),
                )
                connection.execute(
                    "INSERT INTO branches VALUES (?, ?, ?, ?)",
                    (new_session, self.session, checkpoint, stamp),
                )

    def branches(self) -> list[dict]:
        """Все ветки файла с их происхождением. Исходной сессии здесь нет."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT session, parent, checkpoint, created_at FROM branches "
                "ORDER BY created_at, session"
            ).fetchall()
        return [dict(row) for row in rows]

    def usage_by_kind(self):
        calls = self.growth()
        result = {}
        for kind in ("chat", "facts", "total"):
            selected = [c for c in calls if kind == "total" or c["kind"] == kind]
            entry = {"calls": len(selected)}
            for key in ("prompt_tokens", "completion_tokens", "cost_reported"):
                values = [c[key] for c in selected]
                entry[key] = sum(values) if all(v is not None for v in values) else None
            entry["tokens"] = (
                entry["prompt_tokens"] + entry["completion_tokens"]
                if entry["prompt_tokens"] is not None
                and entry["completion_tokens"] is not None
                else None
            )
            result[kind] = entry
        return result

    def begin_request(self, request_id, question):
        """После обрыва HTTP повтор не должен ещё раз тратить токены."""
        with self._connect() as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT question, response FROM web_requests WHERE session=? AND request_id=?",
                    (self.session, request_id),
                ).fetchone()
                if row:
                    if row["question"] != question:
                        raise ValueError(
                            "request_id уже использован для другого вопроса"
                        )
                    if row["response"] is None:
                        raise RuntimeError(
                            "запрос ещё выполняется или прерван; проверьте историю перед новым запросом"
                        )
                    return json.loads(row["response"])
                connection.execute(
                    "INSERT INTO web_requests VALUES (?, ?, ?, NULL)",
                    (self.session, request_id, question),
                )
        return None

    def finish_request(self, request_id, response):
        with self._connect() as connection:
            with connection:
                connection.execute(
                    "UPDATE web_requests SET response=? WHERE session=? AND request_id=?",
                    (
                        json.dumps(response, ensure_ascii=False),
                        self.session,
                        request_id,
                    ),
                )
