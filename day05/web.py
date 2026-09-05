"""Панель дня 5: чтение публичное, запуск только с самой машины.

В процессе живёт токен HuggingFace, поэтому запуск и чтение разведены по разным
слушателям. Публичный отдаёт страницу и историю; локальный принимает POST и тратит
кредиты. Снаружи до локального не достучаться — по открытому каналу не передаётся
ничего секретного вообще, поэтому отсутствие TLS ничего не компрометирует.

Запуск:
    uv run day05/web.py                       # чтение 0.0.0.0:8035, запуск 127.0.0.1:8036
    uv run day05/web.py --read-port 9000 --run-port 9001
    uv run day05/web.py --local               # оба слушателя на 127.0.0.1, для работы дома
"""

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from compare import compare, load_sessions, save_session  # noqa: E402
from models import (  # noqa: E402
    DEFAULT_TRIO,
    MAX_TOKENS,
    MODELS,
    estimate_calls,
    estimate_worst_cost,
)

PAGE = Path(__file__).parent / "web" / "index.html"
MAX_RUNS = 10


def state() -> dict:
    """Всё, что нужно странице при загрузке. Без обращений к API."""
    return {
        "models": MODELS,
        "default_trio": list(DEFAULT_TRIO),
        "max_tokens": MAX_TOKENS,
        "max_runs": MAX_RUNS,
        "sessions": load_sessions(),
    }


def validate(payload: dict) -> tuple[dict | None, str | None]:
    """Разбор тела POST. Возвращает (аргументы, ошибка)."""
    question = (payload.get("question") or "").strip()
    if not question:
        return None, "пустой вопрос"

    model_keys = payload.get("models") or list(DEFAULT_TRIO)
    if not isinstance(model_keys, list) or len(model_keys) != 3:
        return None, "нужно ровно три модели"
    for key in model_keys:
        if key not in MODELS:
            return None, f"неизвестная модель {key!r}"

    runs = payload.get("runs", 3)
    if not isinstance(runs, int) or not 1 <= runs <= MAX_RUNS:
        return None, f"прогонов должно быть от 1 до {MAX_RUNS}"

    temperature = payload.get("temperature")
    if temperature is not None:
        if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
            return None, "температура вне диапазона 0..2"

    return {
        "question": question,
        "model_keys": model_keys,
        "runs": runs,
        "temperature": temperature,
        "judge": bool(payload.get("judge")),
    }, None


class ReadHandler(BaseHTTPRequestHandler):
    """Публичный слушатель. Только GET, кредиты не тратит."""

    def log_message(self, fmt, *args):  # тише в консоли
        pass

    def send_json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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
        elif self.path == "/api/state":
            self.send_json(state())
        else:
            self.send_json({"error": "нет такого адреса"}, 404)

    def do_POST(self) -> None:
        self.send_json({"error": "запуск только с машины владельца"}, 403)


class RunHandler(ReadHandler):
    """Локальный слушатель. Тот же GET плюс запуск сравнения."""

    def read_json(self) -> tuple[dict | None, str | None]:
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length) or b"{}"), None
        except json.JSONDecodeError:
            return None, "тело запроса не разобралось как JSON"

    def do_POST(self) -> None:
        if self.path != "/api/compare":
            self.send_json({"error": "нет такого адреса"}, 404)
            return

        payload, error = self.read_json()
        if error or payload is None:
            self.send_json({"error": error or "пустое тело"}, 400)
            return

        args, error = validate(payload)
        if error or args is None:
            self.send_json({"error": error or "не разобрали запрос"}, 400)
            return

        if payload.get("dry_run"):
            self.send_json(
                {
                    "calls": estimate_calls(
                        args["model_keys"], args["runs"], args["judge"]
                    ),
                    "worst_cost": estimate_worst_cost(
                        args["model_keys"],
                        args["runs"],
                        args["judge"],
                        args["question"],
                    ),
                }
            )
            return

        result = compare(
            args["question"],
            args["model_keys"],
            args["runs"],
            args["temperature"],
            args["judge"],
        )
        save_session(result)
        self.send_json(result)


def serve(handler, host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-port", type=int, default=8035)
    parser.add_argument("--run-port", type=int, default=8036)
    parser.add_argument(
        "--local", action="store_true", help="оба слушателя на 127.0.0.1"
    )
    args = parser.parse_args()

    read_host = "127.0.0.1" if args.local else "0.0.0.0"
    serve(ReadHandler, read_host, args.read_port)
    serve(RunHandler, "127.0.0.1", args.run_port)

    print(f"чтение: http://{read_host}:{args.read_port}   (форма заблокирована)")
    print(f"запуск: http://127.0.0.1:{args.run_port}   (Ctrl+C чтобы остановить)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
