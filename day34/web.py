"""Локальный UI. Без --live используется только явно обозначенный mock."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core import HERE, run
from mock_model import MockModel


def make_server(port=8134, model_factory=MockModel, runs=HERE / "runs"):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, data, kind="application/json; charset=utf-8"):
            body = data.encode() if isinstance(data, str) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def allowed_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.allowed_host():
                return self.reply(403, {"error": "Host запрещён"})
            if self.path == "/favicon.ico":
                return self.reply(204, "")
            if self.path == "/":
                return self.reply(200, (HERE / "static/index.html").read_text(), "text/html; charset=utf-8")
            if self.path == "/api/status":
                return self.reply(200, {"mode": "offline mock" if model_factory is MockModel else "live OpenRouter"})
            self.reply(404, {"error": "Не найдено"})

        def do_POST(self):
            if not self.allowed_host():
                return self.reply(403, {"error": "Host запрещён"})
            origin = self.headers.get("Origin")
            if origin and origin != f"http://127.0.0.1:{self.server.server_port}":
                return self.reply(403, {"error": "Origin запрещён"})
            if self.path != "/api/run":
                return self.reply(404, {"error": "Не найдено"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 10000:
                    raise ValueError("Размер запроса")
                request = json.loads(self.rfile.read(length))
                if set(request) != {"goal"}:
                    raise ValueError("Нужна только цель")
                if not lock.acquire(blocking=False):
                    return self.reply(409, {"error": "Запуск уже выполняется"})
                try:
                    result = run(request["goal"], model_factory(), parent=Path(runs))
                finally:
                    lock.release()
                self.reply(200, result)
            except (ValueError, TypeError):
                self.reply(400, {"error": "Невалидная цель или запрос"})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8134)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--budget-ledger")
    args = parser.parse_args()
    factory = MockModel
    if args.live:
        from budget import Budget
        from model import OpenRouterModel
        if not args.budget_ledger:
            parser.error("--live требует --budget-ledger с общим абсолютным путём")
        budget = Budget(args.budget_ledger)
        factory = lambda: OpenRouterModel(budget)
    server = make_server(args.port, model_factory=factory)
    print(f"Day34 {'LIVE' if args.live else 'OFFLINE MOCK'} http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()
