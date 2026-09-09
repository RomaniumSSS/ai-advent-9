"""День 8: хранилище истории на SQLite. Модуль дня 7 плюс две суммы по токенам.

Замеры API хранятся в `calls` отдельно от переписки: пустой оплаченный ответ
не становится сообщением, но входит в расход. Схема v1 переносится в v2 при
открытии; восстановить расход старых несохранённых пустых ответов невозможно.

Отдельный модуль, а не метод агента, — по той же причине, по которой в дне 6
отдельной стала сама коробка: агент обязан знать, что у него есть память, и не
обязан знать, чем она сделана. Здесь единственное место в проекте, где написано
слово `sqlite3`; поменять его на файл, на Postgres или на чужой сервис можно,
не открывая `agent.py`.

Три решения, которые легко принять наоборот и потом долго ловить:

- **соединение открывается на каждую операцию, а не живёт в объекте.**
  Соединение sqlite3 привязано к потоку, в котором создано, а панель — сервер
  на потоках: одно долгоживущее соединение упало бы на первом же параллельном
  запросе с «SQLite objects created in a thread can only be used in that same
  thread». Плата — открытие файла на каждый ход, доли миллисекунды против
  секунд ожидания модели;
- **порядок сообщений берётся по `id`, а не по времени.** Время пишется для
  человека. Два сообщения одного хода попадают в одну и ту же секунду, и
  сортировка по времени переставила бы вопрос с ответом местами — то есть
  сломала бы ровно то единственное, ради чего история хранится;
- **ход пишется одной транзакцией.** Вопрос и ответ ложатся вместе или не
  ложатся вовсе. Это та же дыра, которую `Agent.ask` уже закрыл в памяти:
  вопрос без ответа в стеке модель прочитает как реплику, оставшуюся без
  реакции, и начнёт извиняться за то, чего не было.

Файл базы создаётся сам при первом обращении. Каталог — нет: несуществующий
каталог означает опечатку в пути, а не просьбу его завести.
"""

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
SCHEMA_VERSION = 2

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

    def append_call(self, reply) -> None:
        """Замер ответа API, в том числе пустого, до записи переписки.

        Отдельная транзакция сохраняет расход даже при сбое записи сообщений.
        Локальный отказ и ошибки без usage сюда не попадают.
        """
        with self._connect() as connection:
            with connection:
                connection.execute(
                    "INSERT INTO calls (session, created_at, model, prompt_tokens, "
                    "completion_tokens, cost, cost_reported, empty) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        self.session, now(), reply.model, reply.prompt_tokens,
                        reply.completion_tokens, reply.cost, reply.cost_reported, reply.empty,
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
                sum(values) if values and all(value is not None for value in values)
                else None
            )
        return result

    def growth(self) -> list[dict]:
        """Статистика каждого ответа API, включая пустые, в порядке вызовов."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT created_at, model, prompt_tokens, completion_tokens, cost, "
                "cost_reported, empty FROM calls WHERE session = ? ORDER BY id",
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
