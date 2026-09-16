"""Локальная панель дня 11: три кнопки записи и видимые границы памяти."""

import argparse
import json
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, AgentConfig  # noqa: E402
from store import DEFAULT_DB, SqliteStore  # noqa: E402

PAGE = Path(__file__).parent / "web" / "index.html"
SCRIPT = Path(__file__).parent / "web" / "app.js"
MAX_BODY_BYTES = 64 * 1024
STATE: dict = {}
ACTION_LOCK = threading.Lock()


class BusyError(RuntimeError):
    """Изменяющая операция уже выполняется; запрос не должен ждать сеть."""


def make_agent(session: str, task: str, user: str) -> Agent:
    return Agent(
        name="Агент дня 11",
        config=STATE["config"],
        store=SqliteStore(STATE["db"], session, task, user),
        recent_turns=STATE["recent_turns"],
    )


def state() -> dict:
    agent = STATE["agent"]
    memory = agent.memory_state()
    return {
        **memory,
        "history": agent.history,
        "turns": agent.turns,
        "recent_turns": agent.recent_turns,
        "model": agent.config.model,
    }


def require_text(body: dict, key: str, limit: int) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"поле {key} должно быть непустой строкой")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"поле {key} длиннее {limit} символов")
    return value


def act(path: str, body: dict) -> dict:
    if not ACTION_LOCK.acquire(blocking=False):
        raise BusyError("агент уже выполняет другую операцию")
    try:
        agent = STATE["agent"]
        if path == "/api/save":
            layer = require_text(body, "layer", 20)
            agent.save(layer, require_text(body, "key", 80),
                       require_text(body, "value", 2000))
            return {"state": state(), "message": f"Запись сохранена в {layer}"}
        if path == "/api/forget":
            layer = require_text(body, "layer", 20)
            removed = agent.forget(layer, require_text(body, "key", 80))
            return {"state": state(), "message": "Запись удалена" if removed else "Запись не найдена"}
        if path == "/api/scope":
            session = require_text(body, "session", 80)
            task = require_text(body, "task", 80)
            user = require_text(body, "user", 80)
            STATE["agent"] = make_agent(session, task, user)
            return {"state": state(), "message": "Область открыта"}
        if path == "/api/reset":
            agent.reset()
            return {"state": state(), "message": "Текущий разговор очищен"}
        if path == "/api/chat":
            text = require_text(body, "text", 20_000)
            reply = agent.ask(text)
            return {
                "state": state(),
                "message": reply.text or reply.error or "Пустой ответ",
                "ok": reply.ok and not reply.empty,
                "saved": reply.saved,
                "usage": {
                    "prompt_tokens": reply.prompt_tokens,
                    "completion_tokens": reply.completion_tokens,
                    "cost_reported": reply.cost_reported,
                },
            }
        raise ValueError("неизвестная команда")
    finally:
        ACTION_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def valid_host(self) -> bool:
        host = self.headers.get("Host", "")
        try:
            parsed = urlsplit(f"http://{host}")
            return (
                parsed.hostname in {"127.0.0.1", "localhost"}
                and parsed.port == self.server.server_port
            )
        except ValueError:
            return False

    def send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, result: dict, status: int = 200) -> None:
        self.send_bytes(
            json.dumps(result, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def do_GET(self) -> None:
        if not self.valid_host():
            self.send_json({"error": "неверный Host"}, 403)
            return
        path = urlsplit(self.path).path
        if path == "/":
            self.send_bytes(PAGE.read_bytes(), "text/html; charset=utf-8")
        elif path == "/app.js":
            self.send_bytes(SCRIPT.read_bytes(), "text/javascript; charset=utf-8")
        elif path == "/api/state":
            try:
                # Чтение остаётся доступным, пока модель отвечает. Изменения
                # агента публикуются только после завершения одного шага.
                self.send_json({"state": state()})
            except (sqlite3.Error, OSError) as error:
                self.send_json({"error": f"ошибка хранилища: {error}"}, 500)
        else:
            self.send_json({"error": "не найдено"}, 404)

    def do_POST(self) -> None:
        if not self.valid_host():
            self.send_json({"error": "неверный Host"}, 403)
            return
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if origin and urlsplit(origin).netloc != host:
            self.send_json({"error": "чужой Origin"}, 403)
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.send_json({"error": "нужен JSON"}, 415)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY_BYTES:
                raise ValueError("неверный размер запроса")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("JSON должен быть объектом")
            self.send_json(act(urlsplit(self.path).path, body))
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)
        except BusyError as error:
            self.send_json({"error": str(error)}, 409)
        except (RuntimeError, sqlite3.Error, OSError) as error:
            self.send_json({"error": str(error)}, 500)

    def log_message(self, format_string: str, *args) -> None:
        # В системный лог не попадают тексты чата и заметок.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--session", default="main")
    parser.add_argument("--task", default="project")
    parser.add_argument("--user", default="roman")
    parser.add_argument("--recent-turns", type=int, default=6)
    parser.add_argument("--port", type=int, default=8041)
    args = parser.parse_args()
    if args.env_file:
        if not args.env_file.is_file():
            raise FileNotFoundError(f"нет env-файла {args.env_file}")
        load_dotenv(args.env_file)
    STATE.update({
        "db": args.db,
        "config": AgentConfig(),
        "recent_turns": args.recent_turns,
    })
    STATE["agent"] = make_agent(args.session, args.task, args.user)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Панель дня 11: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Панель остановлена")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
