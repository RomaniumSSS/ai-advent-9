"""День 9: два режима диалога рядом на локальном HTTP-сервере.

Один вопрос отправляется в независимые сессии полной и сжатой истории.
Запуск: uv run day09/web.py (127.0.0.1:8039)."""

import argparse
import json
import sys
import threading
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).parent))

from agent import DEFAULT_SYSTEM_PROMPT, Agent, AgentConfig, CompressionConfig  # noqa: E402
from models import DEFAULT_MODEL, MAX_TOKENS, MODELS  # noqa: E402
from scenarios import SCENARIOS
from store import DEFAULT_DB, SqliteStore  # noqa: E402

PAGE = Path(__file__).parent / "web" / "index.html"
MAX_BODY_BYTES = 64 * 1024
MAX_MESSAGE_CHARS = 20_000

# Два агента живут, пока живёт процесс. Замок у каждого свой: два одновременных
# сообщения в одну панель испортили бы историю, а замок на обе панели сразу мешал
# бы им работать параллельно — то есть скрывал бы главное, что панель показывает.
#
# В отличие от дня 6, словарь наполняется не при импорте, а в main(): агентам
# теперь нужен путь к базе, а он приходит из аргументов командной строки. Поднять
# их раньше разбора аргументов означало бы прочитать не тот файл и узнать об этом
# по пустой истории.
PANELS: dict[str, Agent] = {}
_locks: dict[str, threading.Lock] = {}


def build_panels(
    db_path, sessions: dict[str, str], context_limit: int | None = None
) -> None:
    titles = {"left": "Полная история", "right": "Со сжатием"}
    PANELS.clear()
    _locks.clear()
    for side, session in sessions.items():
        PANELS[side] = Agent(
            config=AgentConfig(
                model=DEFAULT_MODEL,
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                context_limit=context_limit,
            ),
            name=titles[side],
            compression=CompressionConfig(enabled=side == "right"),
            store=SqliteStore(db_path, session),
        )
        _locks[side] = threading.Lock()


def budget_json(budget) -> dict | None:
    """Бюджет в вид, который переживёт JSON. None остаётся None.

    Ноль вместо None соврал бы, что запрос ничего не весит; пустой словарь на
    странице пришлось бы отличать от настоящего нуля прямо в шаблоне.
    """
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


def panel_state(name: str) -> dict:
    agent = PANELS[name]
    return {
        "name": agent.name,
        "model": agent.config.model,
        "system_prompt": agent.config.system_prompt,
        "temperature": agent.config.temperature,
        "max_tokens": agent.config.max_tokens,
        "turns": agent.turns,
        "history": agent.history,
        # Сессия и число восстановленных ходов уезжают на страницу не для красоты:
        # без них панель с полной перепиской и панель, только что поднявшая ту же
        # переписку с диска, выглядят одинаково — а это разные вещи.
        "session": agent.store.session,
        "restored_turns": agent.restored_turns,
        "context_limit": agent.config.context_limit,
        "usage_summary": agent.store.stats(),
        "usage": agent.store.usage_by_kind(),
        "summary": agent.summary,
        "covered": agent.covered,
        "active_messages": len(agent.history) - (agent.covered if agent.compression.enabled else 0),
        "compression_event": agent.compression_event,
        "keep_messages": agent.compression.keep_messages,
        "batch_messages": agent.compression.batch_messages,
        # Вес запроса, который уедет, если написать в эту панель прямо сейчас.
        # Считается на пустой вопрос: интересен вес разговора, а не фразы.
        "budget": budget_json(agent.budget("")),
    }


def snapshot(name):
    with _locks[name]:
        return panel_state(name)


def state() -> dict:
    """Всё, что нужно странице при загрузке. Ни одного обращения к API."""
    return {
        "models": {key: entry["params"] for key, entry in MODELS.items()},
        "max_tokens": MAX_TOKENS,
        "panels": {name: snapshot(name) for name in PANELS},
    }


def validate_chat(payload: dict) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "тело JSON должно быть объектом"
    panel = payload.get("panel")
    if not isinstance(panel, str) or panel not in PANELS:
        return None, "нет такой панели"
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
    if not isinstance(request_id, str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,80}", request_id):
        return None, "нужен уникальный request_id"
    return {"panel": panel, "text": text, "request_id": request_id}, None


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

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            body = PAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/app.js":
            body = (PAGE.parent / "app.js").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/results":
            report = PAGE.parent.parent / "results" / "final" / "analysis.json"
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
        """Общая охрана платных endpoint-ов. Возвращает причину отказа или None."""
        if self.headers.get_content_type() != "application/json":
            return "нужен Content-Type: application/json"
        if not is_loopback_host(self.headers.get("Host"), self.server.server_port):
            return "панель доступна только через localhost"
        if not same_origin(self.headers.get("Origin"), self.headers.get("Host")):
            return "запрос с чужого Origin запрещён"
        return None

    def do_POST(self) -> None:
        if self.path not in ("/api/chat", "/api/reset"):
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

        if self.path == "/api/chat":
            self.handle_chat(payload)
        else:
            self.handle_reset(payload)

    def handle_chat(self, payload: dict) -> None:
        args, error = validate_chat(payload)
        if error or args is None:
            self.send_json({"error": error or "не разобрали запрос"}, 400)
            return

        panel = args["panel"]
        if not _locks[panel].acquire(blocking=False):
            self.send_json({"error": "эта панель уже ждёт ответ"}, 409)
            return
        try:
            agent = PANELS[panel]
            cached = agent.store.begin_request(args["request_id"], args["text"])
            if cached is not None:
                result = {**cached, "state": panel_state(panel)}
            else:
                reply = agent.ask(args["text"])
                result = {"panel": panel, "text": reply.text, "elapsed": reply.elapsed,
                          "error": reply.error, "empty": reply.empty, "truncated": reply.truncated,
                          "store_error": reply.store_error, "state": panel_state(panel)}
                agent.store.finish_request(args["request_id"], result)
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
            self.send_json({"error": str(error)}, 409)
            return
        finally:
            _locks[panel].release()
        self.send_json(result)

    def handle_reset(self, payload: dict) -> None:
        panel = payload.get("panel") if isinstance(payload, dict) else None
        if not isinstance(panel, str) or panel not in PANELS:
            self.send_json({"error": "нет такой панели"}, 400)
            return
        if not _locks[panel].acquire(blocking=False):
            self.send_json({"error": "панель ещё отвечает"}, 409)
            return
        try:
            PANELS[panel].reset()
            result = panel_state(panel)
        except (OSError, sqlite3.Error) as error:
            self.send_json({"error": f"не удалось очистить историю: {error}"}, 503)
            return
        finally:
            _locks[panel].release()
        self.send_json(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--budget", type=float, default=0.50)
    parser.add_argument("--port", type=int, default=8039)
    parser.add_argument("--db", default=DEFAULT_DB, help="файл базы с историей")
    parser.add_argument("--left", default="left", help="сессия левой панели")
    parser.add_argument("--right", default="right", help="сессия правой панели")
    parser.add_argument(
        "--context-limit",
        type=int,
        default=None,
        help="окно модели в токенах: вход и ответ вместе. Общее на обе панели",
    )
    args = parser.parse_args()

    if args.left == args.right:
        parser.error("панелям нужны разные сессии, иначе они станут одним разговором")

    from dotenv import load_dotenv
    from experiment import BudgetLedger, MeasuredClient, real_client, DEFAULT_LEDGER
    load_dotenv(args.env_file) if args.env_file else load_dotenv()
    ledger = BudgetLedger(args.ledger or DEFAULT_LEDGER, args.budget)
    build_panels(args.db, {"left": args.left, "right": args.right}, args.context_limit)
    for side, agent in PANELS.items():
        agent.client = MeasuredClient(real_client(), ledger, "panel:"+side)

    for side, agent in PANELS.items():
        restored = agent.restored_turns
        note = f"восстановлено ходов: {restored}" if restored else "новый разговор"
        print(f"{side:>5}: сессия {agent.store.session!r} — {note}")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"история: {args.db}")
    print(f"панель: http://127.0.0.1:{args.port}   (Ctrl+C чтобы остановить)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
