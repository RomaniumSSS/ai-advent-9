"""Локальная панель дня 4: температура на двух запросах, тема Гвинта.

Только для localhost — в процессе живёт ключ от DeepSeek, наружу не выставлять.

Запуск:
    uv run day04/web.py          # http://127.0.0.1:8034
    uv run day04/web.py --port 9000
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from traps import (  # noqa: E402
    GADGET_PROMPT,
    HUMAN_EXAMPLE,
    LETTER,
    LETTER_QUESTION,
    LETTER_WORD,
    check_gadget,
    letter_truth,
    score_letter,
)
from temperature import (  # noqa: E402
    RESULTS,
    TASKS,
    TEMPERATURES,
    annotate,
    judge,
    run_once,
    summarize,
)

PAGE = Path(__file__).parent / "web" / "index.html"


def state() -> dict:
    """Всё, что нужно странице при загрузке. Без обращений к API."""
    table = {"letter": [], "gadget": []}
    records = []
    human_judge = None
    if RESULTS.exists():
        data = json.loads(RESULTS.read_text(encoding="utf-8"))
        table = summarize(data)
        records = annotate(data)
        human_judge = data.get("human_judge")

    return {
        "letter_word": LETTER_WORD,
        "letter": LETTER,
        "letter_question": LETTER_QUESTION,
        "letter_truth": letter_truth(),
        "gadget_prompt": GADGET_PROMPT,
        "human_example": HUMAN_EXAMPLE,
        "human_check": check_gadget(HUMAN_EXAMPLE),
        "human_judge": human_judge,
        "temperatures": list(TEMPERATURES),
        "table": table,
        "records": records,
    }


def ask(task: str, temperature: float) -> dict:
    """Один живой прогон. Обращается к API."""
    record = run_once(task, temperature)
    if record["stop"].startswith("error"):
        score = {"error": record["stop"]}
    elif task == "letter":
        score = score_letter(record["answer"])
    else:
        score = check_gadget(record["answer"])
        score["judge"] = judge(record["answer"])
    return {**record, "score": score}


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
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return {}

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
        if self.path == "/api/ask":
            payload = self.read_json()
            task = payload.get("task")
            temperature = payload.get("temperature")
            if task not in TASKS or temperature not in TEMPERATURES:
                self.send_json(
                    {"error": f"нет task={task!r} temperature={temperature!r}"}, 400
                )
                return
            self.send_json(ask(task, temperature))
        else:
            self.send_json({"error": "нет такого адреса"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8034)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"открой http://127.0.0.1:{args.port}   (Ctrl+C чтобы остановить)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
