"""Проверка API панели без HTTP и внешнего провайдера."""
import socket
import io
import json
from email.message import Message
from types import SimpleNamespace
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import base_agent
import web
from agent import AgentConfig
from profile import DEMO_PROFILES


def http_post(path, body):
    # Тот же Handler, но вход/выход в памяти: sandbox не разрешает bind.
    handler = object.__new__(web.Handler)
    data = json.dumps(body).encode()
    handler.path = path
    handler.server = SimpleNamespace(server_port=8042)
    handler.headers = Message()
    handler.headers["Host"] = "127.0.0.1:8042"
    handler.headers["Content-Type"] = "application/json"
    handler.headers["Content-Length"] = str(len(data))
    handler.rfile = io.BytesIO(data)
    result = []
    handler.send_json = lambda body, status=200: result.append((status, body))
    handler.do_POST()
    return result[0]


def main():
    with tempfile.TemporaryDirectory() as directory, patch.object(base_agent, "get_client", side_effect=AssertionError("live запрещён")), patch.object(socket.socket, "connect", side_effect=AssertionError("сеть запрещена")):
        web.STATE.update(db=Path(directory)/"web.db", config=AgentConfig(), recent_turns=2, offline=True)
        web.STATE["agent"] = web.make_agent("main", "task", "a")
        for user in ["brief", "detail", "brief"]:
            result = web.act("/api/demo-user", {"user":user})
            assert result["state"]["scope"]["user"] == user
            assert result["state"]["profile"] == DEMO_PROFILES[user].to_dict()
            assert result["state"]["offline"]
        agent = web.STATE["agent"]
        result = web.act("/api/chat", {"text":"вопрос"})
        assert result["ok"] and result["saved"] and "ОФЛАЙН" in result["message"]
        try:
            web.act("/api/scope", {"user":"detail", "session":"demo-brief", "task":"demo"})
        except ValueError:
            pass
        else:
            raise AssertionError("сессия переназначена")
        assert web.STATE["agent"] is agent
        changed = {**DEMO_PROFILES["brief"].to_dict(), "style":"Мой стиль"}
        web.act("/api/profile", changed)
        assert web.act("/api/demo-user", {"user":"brief"})["state"]["profile"] == changed
        agent = web.STATE["agent"]
        for question, expected in [("/empty", "Пустой ответ"), ("/error", "Демонстрационная ошибка")]:
            result = web.act("/api/chat", {"text":question})
            assert not result["ok"] and expected in result["message"]
        with patch.object(agent.store, "append_turn", side_effect=sqlite3.OperationalError("write failure")), patch.object(web, "state", side_effect=sqlite3.OperationalError("read failure")):
            result = web.act("/api/chat", {"text":"ответ не потерять"})
        assert result["ok"] and not result["saved"]
        assert "ОФЛАЙН" in result["message"]
        assert "write failure" in result["store_error"]
        assert "read failure" in result["state_error"] and result["state"] is None
        # Пробелы в content тоже должны давать явную ошибку.
        with patch.object(agent, "_call", return_value=base_agent.Reply(text="   ", model="deepseek", elapsed=0)):
            result = web.act("/api/chat", {"text":"пусто"})
            assert result["message"] == "Пустой ответ" and not result["ok"]
        count = len(agent.client.requests)
        with patch.object(agent.store, "load_profile", side_effect=sqlite3.OperationalError("read failure")):
            try:
                web.act("/api/chat", {"text":"не отправлять"})
            except sqlite3.Error as error:
                assert "read failure" in str(error)
            else:
                raise AssertionError("ошибка скрыта")
            code, data = http_post("/api/chat", {"text":"не отправлять"})
            assert code == 500 and "read failure" in data["error"]
        assert len(agent.client.requests) == count
        with patch.object(agent.store, "save_profile", side_effect=sqlite3.OperationalError("write failure")):
            try:
                web.act("/api/profile", changed)
            except sqlite3.Error:
                pass
            else:
                raise AssertionError("ошибка скрыта")
            code, data = http_post("/api/profile", changed)
            assert code == 500 and "write failure" in data["error"]
        previous = web.STATE["agent"]
        with patch.object(web, "state", side_effect=sqlite3.OperationalError("candidate read failure")):
            code, data = http_post("/api/scope", {"session":"candidate", "task":"other", "user":"other"})
            assert code == 500 and "candidate read failure" in data["error"]
            assert web.STATE["agent"] is previous
        web.ACTION_LOCK.acquire()
        try:
            try:
                web.act("/api/reset", {})
            except web.BusyError:
                pass
            else:
                raise AssertionError("занятая операция не отклонена")
        finally:
            web.ACTION_LOCK.release()
        print("ok  API: переключение, сохранение, пустой ответ, ошибка провайдера, ошибки БД, ответ не потерян, busy")


if __name__ == "__main__":
    main()
