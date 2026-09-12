"""День 10: ветки диалога поверх сессий хранилища.

Ветвление не стратегия обрезки и намеренно живёт отдельно от `strategies.py`.
Те решают, сколько истории отправить; эта — какая это история. Свести их в один
переключатель значило бы предложить выбор между литрами и цветом.

Ветка здесь не новая сущность, а обычная сессия в том же файле базы. Причина
простая: изоляция сессий уже есть и уже переживает перезапуск. Вторая система
для того же самого рано или поздно разъехалась бы с первой — и разъезд заметили
бы не сразу, а когда в одной ветке всплыла бы реплика из другой.
"""

from strategies import FactsState
from store import SqliteStore


def checkpoint(agent) -> int:
    """Точка ветвления — граница в сообщениях, а не в ходах.

    Считается по тому, что уже лежит на диске, а не по памяти процесса: ход,
    не доехавший до базы, не должен попасть в ветку, которую потом поднимут
    заново и не досчитаются половины.
    """
    if agent.store is None:
        raise RuntimeError("ветвление требует хранилища: ветка — это сессия в базе")
    return len(agent.store.load())


def fork(agent, name: str, point: int | None = None) -> str:
    """Создать ветку от точки `point` и вернуть имя её сессии.

    Имя составное: `main/a` — видно, от кого ветка произошла, даже если строку
    из `branches` кто-то потеряет.

    Агент остаётся в исходной сессии. Автоматический переход в новую ветку
    выглядел бы удобным ровно до первого раза, когда человек создаёт две ветки
    подряд и вторая оказывается веткой от первой.
    """
    if agent.store is None:
        raise RuntimeError("ветвление требует хранилища: ветка — это сессия в базе")
    name = name.strip()
    if not name:
        raise ValueError("имя ветки не может быть пустым")
    if "/" in name:
        raise ValueError("имя ветки задаётся без косой черты: она добавится сама")
    session = f"{agent.store.session}/{name}"
    agent.store.fork(session, checkpoint(agent) if point is None else point)
    return session


def switch(agent, session: str) -> None:
    """Перевести агента в другую сессию: история и память перечитываются с диска.

    Именно перечитываются, а не переносятся. Ветка — отдельный разговор, и её
    facts могли разойтись с теми, что агент держал в памяти минуту назад.
    """
    if agent.store is None:
        raise RuntimeError("ветвление требует хранилища: ветка — это сессия в базе")
    session = session.strip()
    if not session:
        raise ValueError("имя сессии не может быть пустым")
    store = SqliteStore(agent.store.path, session)
    agent.store = store
    agent._history = store.load()
    agent.restored_turns = agent.turns
    agent.facts = FactsState(values=store.load_facts())
    agent.facts_event = None
    store.remember_config(agent.config.model, agent.config.system_prompt)


def branch_list(agent) -> list[dict]:
    """Ветки файла с пометкой, в какой из них агент сейчас находится.

    Текущая сессия попадает в список всегда, даже когда веток нет вовсе. Иначе
    разговор без ветвления показывался бы совсем без кнопки «где я», а после
    первого `fork` в интерфейсе разом появлялись бы сразу две.
    """
    if agent.store is None:
        return []
    current = agent.store.session
    rows = [
        dict(row, active=row["session"] == current) for row in agent.store.branches()
    ]
    known = {row["session"] for row in rows}
    roots = sorted(({row["parent"] for row in rows} | {current}) - known)
    return [
        {
            "session": root,
            "parent": None,
            "checkpoint": None,
            "created_at": None,
            "active": root == current,
        }
        for root in roots
    ] + rows
