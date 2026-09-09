"""День 8: хранилище истории на SQLite. Модуль дня 7 плюс две суммы по токенам.

Схема не менялась: `prompt_tokens` и `completion_tokens` лежали в таблице с дня 7,
их просто никто не складывал. Дописаны `stats()` (суммы токенов рядом с деньгами)
и `growth()` — таблица роста ход за ходом, ради которой день 8 и затевался.

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
SCHEMA_VERSION = 1

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
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"база {self.path} написана схемой версии {version}, "
                    f"этот код знает только {SCHEMA_VERSION}"
                )
            connection.executescript(SCHEMA)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()

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
        """Сводка по сессии. Ходы и деньги считает база, а не счётчик в процессе.

        Счётчик в процессе обнулялся бы при каждом запуске — и «за сессию: $0.0001»
        после часа разговора выглядело бы правдоподобно, что хуже, чем ошибка,
        которая бросается в глаза.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FILTER (WHERE role = 'user')  AS turns, "
                "       COUNT(*)                               AS messages, "
                "       SUM(cost)                              AS cost, "
                "       SUM(prompt_tokens)                     AS prompt_tokens, "
                "       SUM(completion_tokens)                 AS completion_tokens, "
                "       MIN(created_at)                        AS first_at, "
                "       MAX(created_at)                        AS last_at "
                "FROM messages WHERE session = ?",
                (self.session,),
            ).fetchone()
        return {
            "session": self.session,
            "turns": row["turns"] or 0,
            "messages": row["messages"] or 0,
            "cost": row["cost"],
            # Суммы токенов, а не только денег. Деньги зависят от прайса и от
            # модели и после переезда на другую становятся несравнимыми; токены
            # — то, что разговор весит на самом деле, и они сравнимы всегда.
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "first_at": row["first_at"],
            "last_at": row["last_at"],
        }

    def growth(self) -> list[dict]:
        """Ход за ходом: сколько ушло на вход, сколько вернулось, сколько стоило.

        Ради этой таблицы день 8 и затевался. Одна строка ничего не показывает;
        весь смысл в столбце `prompt_tokens` сверху вниз — он растёт, потому что
        история уезжает в модель целиком на каждом ходу, и растёт быстрее, чем
        длина разговора, потому что растут обе стороны переписки сразу.

        Берутся строки ассистента: замеры лежат на них. Строки пользователя —
        та же половина хода, но без цифр, и включать их значило бы получить
        таблицу, наполовину состоящую из прочерков.
        """
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT created_at, model, prompt_tokens, completion_tokens, cost "
                "FROM messages WHERE session = ? AND role = 'assistant' ORDER BY id",
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
