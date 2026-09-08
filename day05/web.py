"""Панель дня 5: чтение публичное, запуск только с самой машины.

В процессе живёт ключ OpenRouter, поэтому запуск и чтение разведены по разным
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
import math
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

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
MAX_BODY_BYTES = 64 * 1024
MAX_QUESTION_CHARS = 20_000
_run_lock = threading.Lock()


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
    if not isinstance(payload, dict):
        return None, "тело JSON должно быть объектом"

    question_value = payload.get("question")
    if not isinstance(question_value, str):
        return None, "вопрос должен быть строкой"
    question = question_value.strip()
    if not question:
        return None, "пустой вопрос"
    if len(question) > MAX_QUESTION_CHARS:
        return None, f"вопрос длиннее {MAX_QUESTION_CHARS} символов"

    model_keys = payload.get("models") or list(DEFAULT_TRIO)
    if not isinstance(model_keys, list) or len(model_keys) != 3:
        return None, "нужно ровно три модели"
    for key in model_keys:
        if key not in MODELS:
            return None, f"неизвестная модель {key!r}"
    if len(set(model_keys)) != 3:
        return None, "нужно выбрать три разные модели"

    runs = payload.get("runs", 3)
    if type(runs) is not int or not 1 <= runs <= MAX_RUNS:
        return None, f"прогонов должно быть от 1 до {MAX_RUNS}"

    temperature = payload.get("temperature")
    if temperature is not None:
        if (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or not math.isfinite(temperature)
            or not 0 <= temperature <= 2
        ):
            return None, "температура вне диапазона 0..2"

    judge = payload.get("judge", False)
    if type(judge) is not bool:
        return None, "judge должен быть true или false"

    dry_run = payload.get("dry_run", False)
    if type(dry_run) is not bool:
        return None, "dry_run должен быть true или false"

    return {
        "question": question,
        "model_keys": model_keys,
        "runs": runs,
        "temperature": temperature,
        "judge": judge,
        "dry_run": dry_run,
    }, None


def same_origin(origin: str | None, host: str | None) -> bool:
    """CLI без Origin разрешён; браузер обязан обращаться к своему же Host."""
    if origin is None:
        return True
    if not host:
        return False
    parsed = urlsplit(origin)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == host.lower()


def is_loopback_host(host: str | None, port: int) -> bool:
    """Не даёт DNS rebinding выдать чужой домен за локальный endpoint."""
    if not host:
        return False
    return host.lower() in {f"127.0.0.1:{port}", f"localhost:{port}"}


class ReadHandler(BaseHTTPRequestHandler):
    """Публичный слушатель. Только GET, кредиты не тратит."""

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
        elif self.path == "/api/state":
            self.send_json(state())
        else:
            self.send_json({"error": "нет такого адреса"}, 404)

    def do_POST(self) -> None:
        self.send_json({"error": "запуск только с машины владельца"}, 403)


class RunHandler(ReadHandler):
    """Локальный слушатель. Тот же GET плюс запуск сравнения."""

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

    def do_POST(self) -> None:
        if self.path != "/api/compare":
            self.send_json({"error": "нет такого адреса"}, 404)
            return

        if self.headers.get_content_type() != "application/json":
            self.send_json({"error": "нужен Content-Type: application/json"}, 415)
            return
        if not is_loopback_host(self.headers.get("Host"), self.server.server_port):
            self.send_json(
                {"error": "платный endpoint доступен только через localhost"}, 403
            )
            return
        if not same_origin(self.headers.get("Origin"), self.headers.get("Host")):
            self.send_json({"error": "запрос с чужого Origin запрещён"}, 403)
            return

        payload, error = self.read_json()
        if error or payload is None:
            self.send_json({"error": error or "пустое тело"}, 400)
            return

        args, error = validate(payload)
        if error or args is None:
            self.send_json({"error": error or "не разобрали запрос"}, 400)
            return

        if args["dry_run"]:
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

        if not _run_lock.acquire(blocking=False):
            self.send_json({"error": "сравнение уже выполняется"}, 409)
            return
        try:
            # AICODE-NOTE: один блокирующий вызов на весь прогон. Замеру это не мешает:
            # elapsed снимается внутри ask() вокруг одного запроса, поэтому отчёт о
            # прогрессе МЕЖДУ вызовами время не искажает. Единственное ограничение —
            # ничего не делать внутри замеряемого участка.
            # AICODE-ASK: панель молчит все 4 минуты ожидания Kimi, и «модель думает»
            # неотличимо от «всё зависло». Чинить отдачей результата по мере готовности
            # каждой модели — или оставить как есть?
            result = compare(
                args["question"],
                args["model_keys"],
                args["runs"],
                args["temperature"],
                args["judge"],
            )
            save_session(result)
            self.send_json(result)
        finally:
            _run_lock.release()


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
