"""Настоящий локальный HTTP и SQLite, подставная модель.

Проверяется то, что в панели легко сломать незаметно: переключение стратегии,
ветвление и повтор запроса после обрыва HTTP.
"""

import json
import sqlite3
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parent))

import web  # noqa: E402
from test_agent_strategies import FakeClient  # noqa: E402

failures = []


def check(condition, message):
    if condition:
        print(f"ok  {message}")
    else:
        failures.append(message)
        print(f"FAIL {message}")


def main():
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "web.db"
        web.build_panel(database, "main")
        client = FakeClient(["ответ модели", '{"цель": "сайт записи"}'])
        web.STATE["agent"].client = client

        server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        root = f"http://127.0.0.1:{server.server_port}"

        def post(path, payload, origin=None):
            headers = {"Content-Type": "application/json"}
            if origin:
                headers["Origin"] = origin
            request = Request(
                root + path, data=json.dumps(payload).encode(), headers=headers
            )
            try:
                with urlopen(request) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                return error.code, json.load(error)

        def get(path):
            with urlopen(root + path) as response:
                return json.load(response)

        try:
            message = {"text": "Планируем сайт записи", "request_id": "req-1"}
            code, first = post("/api/chat", message)
            check(code == 200 and first["state"]["turns"] == 1, "ход прошёл и записан")

            code, again = post("/api/chat", message)
            check(
                code == 200 and again["text"] == first["text"],
                "повтор с тем же request_id вернул сохранённый ответ",
            )
            check(
                len(client.requests) == 1, "повтор HTTP не стоил нового вызова модели"
            )

            check(
                post("/api/chat", {**message, "text": "другой"})[0] == 409,
                "тот же id с другим текстом отвергается",
            )
            check(
                post("/api/chat", {**message, "request_id": None})[0] == 400,
                "запрос без request_id отвергается",
            )
            check(
                post("/api/chat", {**message, "text": "\ud800"})[0] == 400,
                "некорректный Unicode отвергается",
            )
            check(
                post(
                    "/api/chat", {**message, "request_id": "r2"}, "https://example.com"
                )[0]
                == 403,
                "чужой Origin отвергается",
            )

            code, switched = post("/api/strategy", {"name": "facts"})
            check(
                code == 200 and switched["strategy"] == "facts",
                "стратегия переключилась",
            )
            check(switched["turns"] == 1, "переключение не тронуло историю")
            check(
                post("/api/strategy", {"name": "magic"})[0] == 400,
                "несуществующая стратегия отвергается",
            )
            check(
                post("/api/strategy", {"name": "sliding", "recent_messages": 0})[0]
                == 400,
                "недопустимое окно отвергается",
            )

            code, sliding = post(
                "/api/strategy", {"name": "sliding", "recent_messages": 2}
            )
            check(
                code == 200 and sliding["sent_messages"] <= 2,
                "в модель уедет только хвост, хотя архив полный",
            )
            check(sliding["archived_messages"] == 2, "архив остался целым")

            code, branched = post("/api/branch", {"name": "a"})
            check(code == 200 and branched["created"] == "main/a", "ветка создана")
            check(branched["session"] == "main", "создание ветки не переносит в неё")
            check(
                post("/api/branch", {"name": "a"})[0] == 400,
                "повторное имя отвергается",
            )
            check(
                post("/api/branch", {"name": 5})[0] == 400, "имя не-строка отвергается"
            )
            check(
                post("/api/branch", {"name": "b", "checkpoint": 99})[0] == 400,
                "граница вне истории отвергается",
            )

            code, moved = post("/api/switch", {"session": "main/a"})
            check(code == 200 and moved["session"] == "main/a", "переключились в ветку")
            check(moved["turns"] == 1, "ветка унаследовала разговор до точки")
            check(
                post("/api/switch", {"session": "main/zzz"})[0] == 400,
                "переход в несуществующую ветку отвергается",
            )

            client.replies = ["ответ в ветке"]
            code, in_branch = post(
                "/api/chat", {"text": "только в ветке", "request_id": "req-b"}
            )
            check(
                code == 200 and in_branch["state"]["turns"] == 2, "ход записан в ветку"
            )
            post("/api/switch", {"session": "main"})
            contents = [m["content"] for m in get("/api/state")["panel"]["history"]]
            check(
                "только в ветке" not in contents,
                "исходный разговор не увидел ход ветки",
            )

            web._lock.acquire()
            try:
                check(
                    post("/api/chat", {**message, "request_id": "busy"})[0] == 409,
                    "занятая панель отвечает 409, а не ждёт молча",
                )
            finally:
                web._lock.release()

            store = web.STATE["agent"].store
            with patch.object(
                store,
                "begin_request",
                side_effect=sqlite3.OperationalError("disk unavailable"),
            ):
                check(
                    post("/api/chat", {**message, "request_id": "disk"})[0] == 409,
                    "сбой базы не роняет сервер",
                )

            before = web.STATE["agent"].history
            with patch.object(
                store, "clear", side_effect=sqlite3.OperationalError("disk unavailable")
            ):
                check(
                    post("/api/reset", {})[0] == 503, "неудачная очистка отвечает 503"
                )
            check(
                web.STATE["agent"].history == before,
                "после неудачной очистки история цела",
            )

            code, cleared = post("/api/reset", {})
            check(code == 200 and cleared["turns"] == 0, "очистка убрала историю")
            check(
                cleared["branches"]
                == [
                    {
                        "session": "main",
                        "parent": None,
                        "checkpoint": None,
                        "created_at": None,
                        "active": True,
                    }
                ],
                "очистка унесла ветки вместе с разговором",
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    if failures:
        print(f"\nПРОВАЛЕНО {len(failures)}:")
        for item in failures:
            print(f"  - {item}")
        raise SystemExit(1)
    print("\nвсе проверки прошли")


if __name__ == "__main__":
    main()
