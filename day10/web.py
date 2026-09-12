"""День 10: панель с переключателем стратегий и ветвлением.

Одна панель вместо двух панелей дня 9, и это не упрощение ради экономии. День 9
сравнивал два режима на одном вопросе, поэтому ему нужны были две независимые
истории рядом. Здесь сравниваются три стратегии на одном и том же разговоре:
показать это можно только переключателем, который историю не трогает.

Запуск: uv run day10/web.py (127.0.0.1:8040)."""

import argparse
import json
import re
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).parent))

from agent import DEFAULT_SYSTEM_PROMPT, Agent, AgentConfig, StrategyConfig  # noqa: E402
from branches import branch_list, checkpoint, fork, switch  # noqa: E402
from models import DEFAULT_MODEL, MAX_TOKENS, MODELS  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402
from store import DEFAULT_DB, SqliteStore  # noqa: E402
from strategies import STRATEGIES, STRATEGY_LABELS  # noqa: E402

PAGE = Path(__file__).parent / "web" / "index.html"
MAX_BODY_BYTES = 64 * 1024
MAX_MESSAGE_CHARS = 20_000

# Агент живёт, пока живёт процесс. Замок один: панель тут одна, и два
# одновременных сообщения в неё испортили бы историю.
STATE: dict = {}
_lock = threading.Lock()


def build_panel(
    db_path,
    session: str,
    strategy: str = "full",
    recent_messages: int = 6,
    context_limit: int | None = None,
) -> None:
    STATE["agent"] = Agent(
        config=AgentConfig(
            model=DEFAULT_MODEL,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            context_limit=context_limit,
        ),
        name="Агент дня 10",
        strategy=StrategyConfig(name=strategy, recent_messages=recent_messages),
        store=SqliteStore(db_path, session),
    )
    STATE["root"] = session


def budget_json(budget) -> dict | None:
    """Бюджет в вид, который переживёт JSON. None остаётся None."""
    if budget is None:
        return None
    return {
        "system": budget.system,
        "history": budget.history,
        "question": budget.question,
        "overhead": budget.overhead,
        "prompt": budget.prompt,
        "reserved": budget.reserved,
        "total": budget.total,
        "limit": budget.limit,
        "free": budget.free,
        "fits": budget.fits,
        "history_share": budget.history_share,
        "line": budget.line(),
    }


def panel_state() -> dict:
    agent = STATE["agent"]
    return {
        "name": agent.name,
        "model": agent.config.model,
        "system_prompt": agent.config.system_prompt,
        "max_tokens": agent.config.max_tokens,
        "turns": agent.turns,
        "history": agent.history,
        "session": agent.store.session,
        "restored_turns": agent.restored_turns,
        "context_limit": agent.config.context_limit,
        "usage_summary": agent.store.stats(),
        "usage": agent.store.usage_by_kind(),
        "strategy": agent.strategy.name,
        "strategy_label": agent.strategy.label,
        "recent_messages": agent.strategy.recent_messages,
        "facts": agent.facts.values,
        "facts_revision": agent.facts.revision,
        "facts_event": agent.facts_event,
        "branches": branch_list(agent),
        "checkpoint": checkpoint(agent),
        # Сколько сообщений архива реально уедет в модель на следующем ходу.
        # Именно этим стратегии и отличаются: число ходов у них одинаковое.
        "sent_messages": len(agent.context_history()),
        "archived_messages": len(agent.history),
        "budget": budget_json(agent.budget("")),
    }


def state() -> dict:
    """Всё, что нужно странице при загрузке. Ни одного обращения к API."""
    with _lock:
        return {
            "models": {key: entry["params"] for key, entry in MODELS.items()},
            "max_tokens": MAX_TOKENS,
            "strategies": [
                {"name": name, "label": STRATEGY_LABELS[name]} for name in STRATEGIES
            ],
            "panel": panel_state(),
        }


def validate_chat(payload: dict) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "тело JSON должно быть объектом"
    text_value = payload.get("text")
    if not isinstance(text_value, str):
        return None, "сообщение должно быть строкой"
    try:
        text_value.encode("utf-8")
    except UnicodeEncodeError:
        return None, "сообщение содержит некорректный Unicode"
    text = text_value.strip()
    if not text:
        return None, "пустое сообщение"
    if len(text) > MAX_MESSAGE_CHARS:
        return None, f"сообщение длиннее {MAX_MESSAGE_CHARS} символов"
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not re.fullmatch(
        r"[a-zA-Z0-9-]{1,80}", request_id
    ):
        return None, "нужен уникальный request_id"
    return {"text": text, "request_id": request_id}, None


def same_origin(origin: str | None, host: str | None) -> bool:
    """CLI без Origin разрешён; браузер обязан обращаться к своему же Host."""
    if origin is None:
        return True
    if not host:
        return False
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == host.lower()


def is_loopback_host(host: str | None, port: int) -> bool:
    """Не даёт DNS rebinding выдать чужой домен за локальный endpoint."""
    if not host:
        return False
    return host.lower() in {f"127.0.0.1:{port}", f"localhost:{port}"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # тише в консоли
        pass

    def send_json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_file(PAGE, "text/html; charset=utf-8")
        elif self.path == "/app.js":
            self.send_file(
                PAGE.parent / "app.js", "application/javascript; charset=utf-8"
            )
        elif self.path == "/api/results":
            report = PAGE.parent.parent / "results" / "comparison.json"
            self.send_json(json.loads(report.read_text()) if report.exists() else [])
        elif self.path == "/api/scenarios":
            self.send_json(SCENARIOS)
        elif self.path == "/api/state":
            self.send_json(state())
        else:
            self.send_json({"error": "нет такого адреса"}, 404)

    def read_json(self) -> tuple[dict | None, str | None]:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            return None, "некорректный Content-Length"
        if length < 0 or length > MAX_BODY_BYTES:
            return None, f"тело запроса должно быть не больше {MAX_BODY_BYTES} байт"
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, "тело запроса не разобралось как JSON"
        return payload, None

    def guard(self) -> str | None:
        """Общая охрана endpoint-ов, меняющих состояние."""
        if self.headers.get_content_type() != "application/json":
            return "нужен Content-Type: application/json"
        if not is_loopback_host(self.headers.get("Host"), self.server.server_port):
            return "панель доступна только через localhost"
        if not same_origin(self.headers.get("Origin"), self.headers.get("Host")):
            return "запрос с чужого Origin запрещён"
        return None

    def do_POST(self) -> None:
        routes = {
            "/api/chat": self.handle_chat,
            "/api/reset": self.handle_reset,
            "/api/strategy": self.handle_strategy,
            "/api/branch": self.handle_branch,
            "/api/switch": self.handle_switch,
        }
        handler = routes.get(self.path)
        if handler is None:
            self.send_json({"error": "нет такого адреса"}, 404)
            return

        refusal = self.guard()
        if refusal:
            self.send_json({"error": refusal}, 403)
            return

        payload, error = self.read_json()
        if error or payload is None:
            self.send_json({"error": error or "пустое тело"}, 400)
            return
        handler(payload)

    def handle_chat(self, payload: dict) -> None:
        args, error = validate_chat(payload)
        if error or args is None:
            self.send_json({"error": error or "не разобрали запрос"}, 400)
            return
        if not _lock.acquire(blocking=False):
            self.send_json({"error": "панель уже ждёт ответ"}, 409)
            return
        try:
            agent = STATE["agent"]
            cached = agent.store.begin_request(args["request_id"], args["text"])
            if cached is not None:
                result = {**cached, "state": panel_state()}
            else:
                reply = agent.ask(args["text"])
                result = {
                    "text": reply.text,
                    "elapsed": reply.elapsed,
                    "error": reply.error,
                    "empty": reply.empty,
                    "truncated": reply.truncated,
                    "store_error": reply.store_error,
                    "state": panel_state(),
                }
                agent.store.finish_request(args["request_id"], result)
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
            self.send_json({"error": str(error)}, 409)
            return
        finally:
            _lock.release()
        self.send_json(result)

    def handle_strategy(self, payload: dict) -> None:
        name = payload.get("name")
        recent = payload.get("recent_messages")
        if not _lock.acquire(blocking=False):
            self.send_json({"error": "панель ещё отвечает"}, 409)
            return
        try:
            STATE["agent"].switch_strategy(name, recent)
            result = panel_state()
        except (TypeError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)
            return
        finally:
            _lock.release()
        self.send_json(result)

    def handle_branch(self, payload: dict) -> None:
        name = payload.get("name")
        point = payload.get("checkpoint")
        if not isinstance(name, str):
            self.send_json({"error": "имя ветки должно быть строкой"}, 400)
            return
        if point is not None and (isinstance(point, bool) or type(point) is not int):
            self.send_json({"error": "checkpoint должен быть целым числом"}, 400)
            return
        if not _lock.acquire(blocking=False):
            self.send_json({"error": "панель ещё отвечает"}, 409)
            return
        try:
            session = fork(STATE["agent"], name, point)
            result = {"created": session, **panel_state()}
        except (ValueError, RuntimeError, sqlite3.Error) as error:
            self.send_json({"error": str(error)}, 400)
            return
        finally:
            _lock.release()
        self.send_json(result)

    def handle_switch(self, payload: dict) -> None:
        session = payload.get("session")
        if not isinstance(session, str):
            self.send_json({"error": "имя сессии должно быть строкой"}, 400)
            return
        known = {row["session"] for row in branch_list(STATE["agent"])}
        if session not in known:
            self.send_json({"error": "нет такой ветки"}, 400)
            return
        if not _lock.acquire(blocking=False):
            self.send_json({"error": "панель ещё отвечает"}, 409)
            return
        try:
            switch(STATE["agent"], session)
            result = panel_state()
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
            self.send_json({"error": str(error)}, 400)
            return
        finally:
            _lock.release()
        self.send_json(result)

    def handle_reset(self, payload: dict) -> None:
        if not _lock.acquire(blocking=False):
            self.send_json({"error": "панель ещё отвечает"}, 409)
            return
        try:
            agent = STATE["agent"]
            known = [row["session"] for row in branch_list(agent)]
            # Сначала вернуться в исходную сессию, потом чистить. Обратный
            # порядок оставил бы агента стоять в ветке, которую только что стёрли.
            if agent.store.session != STATE["root"]:
                switch(agent, STATE["root"])
            # Ветки — отдельные сессии, и сброс текущей их не касается. Чистим
            # весь эксперимент: иначе «новый эксперимент» оставил бы позади ветки
            # стёртого разговора, продолжающиеся с несуществующего места.
            for session in known:
                if session != agent.store.session:
                    SqliteStore(agent.store.path, session).clear()
            agent.reset()
            result = panel_state()
        except (OSError, sqlite3.Error) as error:
            self.send_json({"error": f"не удалось очистить историю: {error}"}, 503)
            return
        finally:
            _lock.release()
        self.send_json(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--budget", type=float, default=0.50)
    parser.add_argument("--port", type=int, default=8040)
    parser.add_argument("--db", default=DEFAULT_DB, help="файл базы с историей")
    parser.add_argument("--session", default="main", help="сессия панели")
    parser.add_argument("--strategy", default="full", choices=STRATEGIES)
    parser.add_argument(
        "--recent",
        type=int,
        default=6,
        help="сколько последних сообщений держать в контексте",
    )
    parser.add_argument(
        "--context-limit",
        type=int,
        default=None,
        help="окно модели в токенах: вход и ответ вместе",
    )
    args = parser.parse_args()

    from dotenv import load_dotenv
    from experiment import BudgetLedger, MeasuredClient, real_client, DEFAULT_LEDGER

    load_dotenv(args.env_file) if args.env_file else load_dotenv()
    ledger = BudgetLedger(args.ledger or DEFAULT_LEDGER, args.budget)
    build_panel(args.db, args.session, args.strategy, args.recent, args.context_limit)
    STATE["agent"].client = MeasuredClient(real_client(), ledger, "panel")

    agent = STATE["agent"]
    restored = agent.restored_turns
    note = f"восстановлено ходов: {restored}" if restored else "новый разговор"
    print(f"сессия {agent.store.session!r} — {note}, стратегия {agent.strategy.label}")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"история: {args.db}")
    print(f"панель: http://127.0.0.1:{args.port}   (Ctrl+C чтобы остановить)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
