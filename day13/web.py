"""Локальная накопительная панель дня 13: возможности дня 12 плюс FSM."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

from agent import Agent, AgentCapabilities, AgentConfig
from offline import OfflineClient
from profile import DEMO_PROFILES, UserProfile
from store import DEFAULT_DB, SqliteStore

ROOT = Path(__file__).parent
WEB = ROOT / "web"
MAX_BODY_BYTES = 64 * 1024


class BusyError(RuntimeError):
    """Изменяющая операция уже выполняется; запрос не должен ждать."""


class Runtime:
    def __init__(
        self,
        db: Path,
        *,
        session: str = "main",
        task: str = "project",
        user: str = "roman",
        recent_turns: int = 6,
        max_tokens: int = 8_000,
        offline: bool = True,
    ):
        self.db = db
        self.recent_turns = recent_turns
        self.max_tokens = max_tokens
        self.offline = offline
        self.generation = 0
        self.lock = threading.Lock()
        self.agent = self._new_agent(session, task, user)

    def _build_agent(self, session: str, task: str, user: str) -> Agent:
        return Agent(
            name="Агент дня 13",
            config=AgentConfig(max_tokens=self.max_tokens),
            store=SqliteStore(self.db, session=session, task_id=task, user_id=user),
            capabilities=AgentCapabilities(recent_history_turns=self.recent_turns),
            client=OfflineClient() if self.offline else None,
        )

    def _new_agent(self, session: str, task: str, user: str) -> Agent:
        agent = self._build_agent(session, task, user)
        self.generation += 1
        return agent

    def switch_scope(self, session: str, task: str, user: str) -> None:
        candidate = self._build_agent(session, task, user)
        # AICODE-NOTE: сначала полностью читаем новую область. При ошибке
        # активный агент остаётся прежним, и UI возвращается к источнику правды.
        self.state(candidate)
        self.generation += 1
        self.agent = candidate

    def restart(self) -> None:
        scope = self.agent.store
        self.agent = self._new_agent(scope.session, scope.task_id, scope.user_id)

    def state(self, agent: Agent | None = None) -> dict:
        agent = agent or self.agent
        snapshot = agent.memory_state()
        snapshot.update({
            "generation": self.generation,
            "history": agent.history,
            "turns": agent.turns,
            "recent_turns": agent.recent_turns,
            "model": agent.config.model,
            "max_tokens": agent.config.max_tokens,
            "profile": agent.store.load_profile().to_dict(),
            "offline": self.offline,
        })
        return snapshot


def require_text(body: dict, key: str, limit: int) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"поле {key} должно быть непустой строкой")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"поле {key} длиннее {limit} символов")
    return value


class Handler(BaseHTTPRequestHandler):
    runtime: Runtime

    def valid_host(self) -> bool:
        return self.headers.get_all("Host", []) in [
            [f"127.0.0.1:{self.server.server_port}"],
            [f"localhost:{self.server.server_port}"],
        ]

    def log_message(self, *_args):
        # Тексты чата и заметок не должны попадать в системный лог.
        return

    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._json(404, {"error": "не найдено"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.valid_host():
            self._json(403, {"error": "неверный Host"})
            return
        path = urlsplit(self.path).path
        if path == "/":
            self._file(WEB / "index.html", "text/html; charset=utf-8")
        elif path == "/app.js":
            self._file(WEB / "app.js", "text/javascript; charset=utf-8")
        elif path == "/api/state":
            try:
                self._json(200, {"state": self.runtime.state(), "read_only": False})
            except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
                self._json(500, {"error": f"ошибка хранилища: {error}"})
        else:
            self._json(404, {"error": "не найдено"})

    def do_POST(self):
        if not self.valid_host():
            self._json(403, {"error": "неверный Host"})
            return
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if origin is not None and self.headers.get_all("Origin") != [f"http://{host}"]:
            self._json(403, {"error": "чужой Origin"})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self._json(415, {"error": "нужен JSON"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY_BYTES:
                raise ValueError("неверный размер запроса")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("JSON должен быть объектом")
            self._json(200, self._run(urlsplit(self.path).path, body))
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error), "state": self.runtime.state()})
        except BusyError as error:
            self._json(409, {"error": str(error)})
        except (RuntimeError, sqlite3.Error, OSError) as error:
            self._json(500, {"error": str(error)})

    def _run(self, path: str, body: dict) -> dict:
        # Pause — единственная команда, которая должна пройти параллельно с
        # model turn: следующий commit увидит новую version и отбросит ответ.
        if path in {"/api/task/pause", "/api/pause"}:
            return self._dispatch(path, body)
        if not self.runtime.lock.acquire(blocking=False):
            raise BusyError("агент уже выполняет другую операцию")
        try:
            return self._dispatch(path, body)
        finally:
            self.runtime.lock.release()

    def _dispatch(self, path: str, body: dict) -> dict:
        agent = self.runtime.agent

        # Возможности накопительного агента дня 12.
        if path == "/api/profile":
            agent.store.save_profile(UserProfile.from_dict(body))
            return {"state": self.runtime.state(), "message": "Профиль сохранён; применяется автоматически"}
        if path == "/api/demo-user":
            user = require_text(body, "user", 80)
            if user not in DEMO_PROFILES:
                raise ValueError("неизвестный демонстрационный пользователь")
            candidate = self.runtime._build_agent(f"demo-{user}", "demo", user)
            candidate.store.save_profile(DEMO_PROFILES[user], if_missing=True)
            self.runtime.state(candidate)
            self.runtime.generation += 1
            self.runtime.agent = candidate
            return {"state": self.runtime.state(), "message": "Демонстрационный профиль открыт"}
        if path == "/api/save":
            layer = require_text(body, "layer", 20)
            agent.save(
                layer,
                require_text(body, "key", 80),
                require_text(body, "value", 2000),
            )
            return {"state": self.runtime.state(), "message": f"Запись сохранена в {layer}"}
        if path == "/api/forget":
            layer = require_text(body, "layer", 20)
            removed = agent.forget(layer, require_text(body, "key", 80))
            message = "Запись удалена" if removed else "Запись не найдена"
            return {"state": self.runtime.state(), "message": message}
        if path == "/api/scope":
            self.runtime.switch_scope(
                require_text(body, "session", 80),
                require_text(body, "task", 80),
                require_text(body, "user", 80),
            )
            return {"state": self.runtime.state(), "message": "Область открыта"}
        if path in {"/api/reset", "/api/clear"}:
            agent.reset()
            return {"state": self.runtime.state(), "message": "Диалог очищен; состояние задачи сохранено"}
        if path == "/api/chat":
            return Handler._chat(self, require_text(body, "text", 20_000))

        # Формализованное состояние задачи дня 13.
        if path in {"/api/task/start", "/api/demo-reset"}:
            objective = (
                require_text(body, "objective", 2000)
                if path == "/api/task/start"
                else "Подготовить план безопасного релиза мобильного приложения"
            )
            agent.store.delete_task_state()
            agent.start_task(objective)
            return {"state": self.runtime.state(), "message": "Новая задача создана на этапе planning"}
        if path in {"/api/task/action", "/api/action"}:
            state = agent.task_state()
            if state is None:
                raise ValueError("сначала создайте задачу")
            action = str(body.get("action") or state.expected_action or "")
            result = require_text(body, "result", 20_000)
            agent.apply_task(action, result)
            return {"state": self.runtime.state(), "message": f"Событие {action} сохранено"}
        if path in {"/api/task/pause", "/api/pause"}:
            agent.pause_task()
            return {"state": self.runtime.state(), "message": "Пауза сохранена в SQLite"}
        if path in {"/api/task/resume", "/api/resume"}:
            agent.resume_task()
            return {"state": self.runtime.state(), "message": "Продолжение — с того же шага"}
        if path in {"/api/task/restart", "/api/restart"}:
            self.runtime.restart()
            return {
                "state": self.runtime.state(),
                "message": f"Создан новый экземпляр агента №{self.runtime.generation}",
            }
        if path == "/api/workflow/run":
            loop = agent.run_to_boundary(int(body.get("max_model_turns", 4)))
            return {
                "state": self.runtime.state(),
                "loop": loop.to_dict(),
                "message": f"Workflow остановлен: {loop.reason}",
            }
        if path == "/api/workflow/approve":
            loop = agent.approve_workflow(int(body.get("max_model_turns", 4)))
            return {
                "state": self.runtime.state(),
                "loop": loop.to_dict(),
                "message": f"Решение принято; workflow: {loop.reason}",
            }
        if path == "/api/workflow/revise":
            loop = agent.revise_workflow(
                require_text(body, "feedback", 20_000),
                int(body.get("max_model_turns", 4)),
            )
            return {
                "state": self.runtime.state(),
                "loop": loop.to_dict(),
                "message": f"Замечание сохранено; workflow: {loop.reason}",
            }
        if path == "/api/continue":
            result = Handler._chat(self, "Продолжай")
            result["reply"] = result["message"]
            result["message"] = (
                "Модель получила сохранённый task state"
                if result["model_called"]
                else "Приложение ответило без вызова модели"
            )
            return result
        raise ValueError("неизвестная команда")

    def _chat(self, text: str) -> dict:
        agent = self.runtime.agent
        requests = getattr(agent.client, "requests", None)
        requests_before = len(requests) if requests is not None else None
        reply = agent.ask(text)
        model_called = (
            len(requests) > requests_before
            if requests_before is not None
            else reply.finish_reason != "local_state" and not reply.overflow
        )
        state_error = None
        try:
            current = self.runtime.state()
        except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
            current = None
            state_error = f"Не удалось обновить состояние: {error}"
        return {
            "state": current,
            "state_error": state_error,
            "store_error": reply.store_error,
            "message": "Пустой ответ" if reply.empty else reply.text or reply.error,
            "context": (
                requests[-1]["messages"]
                if requests is not None and model_called and not reply.overflow
                else None
            ),
            "model_called": model_called,
            "ok": reply.ok and not reply.empty,
            "saved": reply.saved,
            "usage": {
                "prompt_tokens": reply.prompt_tokens,
                "completion_tokens": reply.completion_tokens,
                "cost_reported": reply.cost_reported,
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--session", default="main")
    parser.add_argument("--task", default="project")
    parser.add_argument("--user", default="roman")
    parser.add_argument("--recent-turns", type=int, default=6)
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8_000,
        help="максимум токенов ответа модели (по умолчанию: 8000)",
    )
    parser.add_argument("--port", type=int, default=8043)
    parser.add_argument(
        "--env-file",
        type=Path,
        help="включить реальную модель и загрузить OPENROUTER_API_KEY из файла",
    )
    args = parser.parse_args()
    if args.env_file:
        if not args.env_file.is_file():
            parser.error("--env-file не существует")
        load_dotenv(args.env_file)
        if not os.environ.get("OPENROUTER_API_KEY"):
            parser.error("в --env-file отсутствует OPENROUTER_API_KEY")
    runtime = Runtime(
        args.db,
        session=args.session,
        task=args.task,
        user=args.user,
        recent_turns=args.recent_turns,
        max_tokens=args.max_tokens,
        offline=args.env_file is None,
    )
    Handler.runtime = runtime
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
