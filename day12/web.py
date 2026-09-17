"""Локальная панель дня 12: три кнопки записи и видимые границы памяти."""

import argparse
import json
import sqlite3
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

import base_agent
from live_budget import LiveBudget
from offline import OfflineClient
from profile import UserProfile, DEMO_PROFILES

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
        name="Агент дня 12",
        config=STATE["config"],
        store=SqliteStore(STATE["db"], session, task, user),
        recent_turns=STATE["recent_turns"],
        client=OfflineClient() if STATE.get("offline") else None,
    )


def state(agent=None) -> dict:
    agent = agent or STATE["agent"]
    memory = agent.memory_state()
    return {
        **memory,
        "history": agent.history,
        "turns": agent.turns,
        "recent_turns": agent.recent_turns,
        "model": agent.config.model,
        "profile": agent.store.load_profile().to_dict(),
        "offline": STATE.get("offline", False),
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
        if STATE.get("campaign"):
            campaign = STATE["campaign"]
            if path == "/api/campaign/dispatch":
                if set(body) != {"case_id"}:
                    raise ValueError("только manifest case_id")
                return campaign.dispatch(body["case_id"])
            if path == "/api/campaign/restart-prepare":
                return campaign.restart_prepare()
            if path == "/api/campaign/restart-verify":
                return campaign.restart_verify(body)
            raise ValueError("campaign mode: legacy mutations and paid entries disabled")
        agent = STATE["agent"]
        if path == "/api/resume":
            if base_agent._live_budget is None:
                raise ValueError('live ledger required')
            return base_agent._live_budget.authorize_resume(
                body['source_report'], body['approved_by'], body['reason'])
        if path == "/api/profile":
            agent.store.save_profile(UserProfile.from_dict(body))
            return {"state": state(), "message": "Профиль сохранён; применяется автоматически"}
        if path == "/api/demo-user":
            user = require_text(body, "user", 80)
            if user not in DEMO_PROFILES:
                raise ValueError("неизвестный демонстрационный пользователь")
            candidate = make_agent(f"demo-{user}", "demo", user)
            candidate.store.save_profile(DEMO_PROFILES[user], if_missing=True)
            result = state(candidate)
            STATE["agent"] = candidate
            return {"state": result, "message": "Демонстрационный профиль открыт"}
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
            candidate = make_agent(session, task, user)
            result = state(candidate)
            STATE["agent"] = candidate
            return {"state": result, "message": "Область открыта"}
        if path == "/api/reset":
            agent.reset()
            return {"state": state(), "message": "Текущий разговор очищен"}
        if path == "/api/chat":
            text = require_text(body, "text", 20_000)
            if base_agent._live_budget is not None:
                ledger = base_agent._live_budget.snapshot()
                if 'manual_resume' in ledger:
                    from repair_contract import require, RUN_ID
                    current = state()
                    label = 'B-resume' if len(ledger['attempts']) == 2 else 'B-repeat'
                    require(current['scope'] == {'session': f'{RUN_ID}-{label}',
                                                'task': RUN_ID, 'user': RUN_ID}
                            and not current['history'] and not any(current['notes'].values()),
                            'resume requires original user/task and a fresh empty session')
            reply = agent.ask(text)
            # AICODE-NOTE: сбой повторного чтения БД не должен уничтожить
            # уже полученный ответ, особенно если вызов был платным.
            state_error = None
            try:
                current = state()
            except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
                current = None
                state_error = f"Не удалось обновить состояние: {error}"
            return {
                "state": current,
                "state_error": state_error,
                "store_error": reply.store_error,
                "message": "Пустой ответ" if reply.empty else reply.text or reply.error,
                "context": (agent.client.requests[-1]["messages"]
                            if STATE.get("offline") and agent.client.requests and not reply.overflow else None),
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
    read_only = False

    def valid_host(self) -> bool:
        return self.headers.get_all("Host", []) in [
            [f"127.0.0.1:{self.server.server_port}"],
            [f"localhost:{self.server.server_port}"],
        ]

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
        elif path == "/api/campaign/evidence" and not self.read_only:
            if STATE.get("campaign"):
                self.send_json(STATE["campaign"].evidence())
            else:
                self.send_json({"error": "campaign not configured"}, 409)
        elif path == "/api/evidence" and not self.read_only:
            if base_agent._live_budget is None:
                self.send_json({"error": "live ledger not configured"}, 409)
            else:
                self.send_json(base_agent._live_budget.snapshot())
        elif path == "/api/state":
            try:
                # Чтение остаётся доступным, пока модель отвечает. Изменения
                # агента публикуются только после завершения одного шага.
                self.send_json({"state": state(), "read_only": self.read_only})
            except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
                self.send_json({"error": f"ошибка хранилища: {error}"}, 500)
        else:
            self.send_json({"error": "не найдено"}, 404)

    def do_POST(self) -> None:
        if not self.valid_host():
            self.send_json({"error": "неверный Host"}, 403)
            return
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if origin is not None and (
            self.headers.get_all("Origin") != [f"http://{host}"]
        ):
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


class ReadHandler(Handler):
    read_only = True

    def valid_host(self) -> bool:
        return True

    def do_POST(self) -> None:
        # AICODE-NOTE: отказ до чтения тела; Host не меняет права listener.
        self.send_json({"error": "публичная панель доступна только для чтения"}, 403)


def bind_servers(port=8042, read_port=None, run_port=None):
    servers = []
    try:
        if read_port is None:
            servers.append(ThreadingHTTPServer(("127.0.0.1", port), Handler))
        else:
            servers.append(ThreadingHTTPServer(("127.0.0.1", read_port), ReadHandler))
            servers.append(ThreadingHTTPServer(("127.0.0.1", run_port), Handler))
        return servers
    except BaseException:
        for server in servers:
            server.server_close()
        raise


def serve(servers):
    stopped = threading.Event()
    threads = []
    previous = {}

    def worker(server):
        try:
            server.serve_forever(poll_interval=0.1)
        finally:
            stopped.set()

    def stop(signum, frame):
        stopped.set()

    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, stop)
        for server in servers:
            thread = threading.Thread(target=worker, args=(server,), daemon=True)
            thread.start()
            threads.append(thread)
        stopped.wait()
        if any(not thread.is_alive() for thread in threads):
            raise RuntimeError("listener остановился неожиданно")
    finally:
        for server, thread in zip(servers, threads):
            if thread.is_alive():
                server.shutdown()
        for server in servers:
            server.server_close()
        for thread in threads:
            thread.join()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--session", default="main")
    parser.add_argument("--task", default="project")
    parser.add_argument("--user", default="roman")
    parser.add_argument("--recent-turns", type=int, default=6)
    parser.add_argument("--port", type=int, default=8042)
    parser.add_argument("--read-port", type=int)
    parser.add_argument("--run-port", type=int)
    parser.add_argument("--offline", action="store_true", help="демонстрация без сети и API")
    parser.add_argument("--live-policy", type=Path)
    parser.add_argument("--live-ledger", type=Path)
    parser.add_argument("--mass-policy", type=Path)
    parser.add_argument("--mass-ledger", type=Path)
    parser.add_argument("--mass-gate", type=Path)
    args = parser.parse_args()
    mass_args = (args.mass_policy, args.mass_ledger, args.mass_gate)
    if any(mass_args) and (not all(mass_args) or args.live_policy or args.live_ledger or args.offline):
        parser.error("mass mode requires policy/ledger/gate and excludes legacy/offline")
    if (args.read_port is None) != (args.run_port is None):
        parser.error("--read-port и --run-port задаются вместе")
    if args.offline and args.env_file:
        parser.error("--env-file несовместим с --offline")
    for port in (args.port, args.read_port, args.run_port):
        if port is not None and not 1 <= port <= 65535:
            parser.error("порт должен быть в диапазоне 1..65535")
    if args.env_file:
        if not args.env_file.is_file():
            raise FileNotFoundError(f"нет env-файла {args.env_file}")
        load_dotenv(args.env_file)
    if bool(args.live_policy) != bool(args.live_ledger):
        parser.error("--live-policy и --live-ledger задаются вместе")
    if args.offline and args.live_policy:
        parser.error("live budget несовместим с offline")
    base_agent._live_budget = LiveBudget(args.live_ledger, args.live_policy) if args.live_policy else None
    config = AgentConfig(max_tokens=base_agent._live_budget.policy["max_tokens"]) if base_agent._live_budget else AgentConfig()
    STATE.update({
        "db": args.db,
        "offline": args.offline,
        "config": config,
        "recent_turns": args.recent_turns,
    })
    STATE.pop("campaign", None)
    if args.mass_policy:
        from mass_live import Campaign
        STATE["campaign"] = Campaign(args.mass_ledger, args.mass_policy, args.db, args.mass_gate)
    STATE["agent"] = make_agent(args.session, args.task, args.user)
    servers = bind_servers(args.port, args.read_port, args.run_port)
    serve(servers)


if __name__ == "__main__":
    main()
