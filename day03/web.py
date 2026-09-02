"""Локальная смотрелка для дня 3: собрать дрон руками и сравнить с моделью.

Только для localhost: в процессе живёт ключ от DeepSeek, наружу выставлять нельзя.
Никаких зависимостей сверх тех, что уже стоят — сервер из стандартной библиотеки.

Запуск:
    uv run day03/web.py          # http://127.0.0.1:8033
    uv run day03/web.py --port 9000
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build import (  # noqa: E402
    BUDGET,
    CATALOGS,
    GOAL_TEXT,
    PARTS,
    QUANTITY,
    RULES_TEXT,
    best_build,
    broken_rules,
    minutes_of,
    price_of,
    score,
    weight_of,
)
from reasoning import MODES, RESULTS, run_once  # noqa: E402

PAGE = Path(__file__).parent / "web" / "index.html"


def state() -> dict:
    """Всё, что нужно странице при загрузке. Без обращений к API."""
    optimum, valid_count = best_build()
    records = []
    if RESULTS.exists():
        records = json.loads(RESULTS.read_text(encoding="utf-8"))

    table = []
    for mode in MODES:
        rows = [r for r in records if r["mode"] == mode]
        if not rows:
            continue
        scored = [score(r["answer"]) for r in rows if not r["stop"].startswith("error")]
        parsed = [s for s in scored if s["parsed"]]
        table.append(
            {
                "mode": mode,
                "runs": len(scored),
                "parsed": len(parsed),
                "valid": sum(s["valid"] for s in parsed),
                "optimal": sum(s["optimal"] for s in parsed),
                "calls": sum(r["calls"] for r in rows),
            }
        )

    return {
        "parts": list(PARTS),
        "quantity": QUANTITY,
        "catalogs": CATALOGS,
        "rules": RULES_TEXT,
        "goal": GOAL_TEXT,
        "budget": BUDGET,
        "optimum": optimum,
        "optimum_minutes": round(minutes_of(optimum), 2),
        "optimum_price": price_of(optimum),
        "valid_total": valid_count,
        "modes": list(MODES),
        "table": table,
    }


def check(build: dict) -> dict:
    """Проверка собранной руками конфигурации. Без обращений к API."""
    problems = broken_rules(build)
    known = all(build.get(part) in CATALOGS[part] for part in PARTS)
    return {
        "problems": problems,
        "valid": not problems,
        "optimal": known and not problems and build == best_build()[0],
        # Вес и цену считаем только когда все позиции настоящие:
        # для выдуманной детали их не на чем вычислить.
        "weight": weight_of(build) if known else None,
        "price": price_of(build) if known else None,
        "minutes": round(minutes_of(build), 2) if known and not problems else None,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # тише в консоли
        pass

    def send_json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            body = PAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/state":
            self.send_json(state())
        else:
            self.send_json({"error": "нет такого адреса"}, 404)

    def do_POST(self) -> None:
        if self.path == "/api/check":
            self.send_json(check(self.read_json()))
        elif self.path == "/api/ask":
            mode = self.read_json().get("mode")
            if mode not in MODES:
                self.send_json({"error": f"нет режима {mode!r}"}, 400)
                return
            record = run_once(mode)
            self.send_json({**record, "score": score(record["answer"])})
        else:
            self.send_json({"error": "нет такого адреса"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8033)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"открой http://127.0.0.1:{args.port}   (Ctrl+C чтобы остановить)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
