"""День 6: панель с двумя агентами. Только localhost.

Весь слушатель висит на 127.0.0.1, в отличие от дня 5, где наружу отдавалась
безопасная половина. Здесь безопасной половины нет: каждое сообщение тратит
кредиты, а в процессе живёт ключ OpenRouter. TLS на машине нет, значит наружу
не открываем ничего.

Две панели — это два объекта Agent в одном процессе с разными конфигами.
Ровно та проверка, которую задал автор задания: спросить слева «меня зовут Роман»,
потом справа «как меня зовут» и получить «не знаю».

Запуск:
    uv run day06/web.py
    uv run day06/web.py --port 9000
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

from agent import DEFAULT_SYSTEM_PROMPT, Agent, AgentConfig  # noqa: E402
from models import DEFAULT_MODEL, MAX_TOKENS, MODELS  # noqa: E402

PAGE = Path(__file__).parent / "web" / "index.html"
MAX_BODY_BYTES = 64 * 1024
MAX_MESSAGE_CHARS = 20_000

# Два агента поднимаются при старте и живут, пока живёт процесс. Замок у каждого
# свой: два одновременных сообщения в одну панель испортили бы историю, а замок
# на обе панели сразу мешал бы им работать параллельно — то есть скрывал бы
# главное, что панель должна показать.
PANELS = {
    "left": Agent(
        config=AgentConfig(model=DEFAULT_MODEL, system_prompt=DEFAULT_SYSTEM_PROMPT),
        name="левый",
    ),
    "right": Agent(
        config=AgentConfig(model=DEFAULT_MODEL, system_prompt=DEFAULT_SYSTEM_PROMPT),
        name="правый",
    ),
}
_locks = {name: threading.Lock() for name in PANELS}


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
    }


def state() -> dict:
    """Всё, что нужно странице при загрузке. Ни одного обращения к API."""
    return {
        "models": {key: entry["params"] for key, entry in MODELS.items()},
        "max_tokens": MAX_TOKENS,
        "panels": {name: panel_state(name) for name in PANELS},
    }


def validate_chat(payload: dict) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "тело JSON должно быть объектом"
    panel = payload.get("panel")
    if panel not in PANELS:
        return None, "нет такой панели"
    text_value = payload.get("text")
    if not isinstance(text_value, str):
        return None, "сообщение должно быть строкой"
    text = text_value.strip()
    if not text:
        return None, "пустое сообщение"
    if len(text) > MAX_MESSAGE_CHARS:
        return None, f"сообщение длиннее {MAX_MESSAGE_CHARS} символов"
    return {"panel": panel, "text": text}, None


def validate_config(payload: dict) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "тело JSON должно быть объектом"
    panel = payload.get("panel")
    if panel not in PANELS:
        return None, "нет такой панели"

    changes = {}
    if "model" in payload:
        if payload["model"] not in MODELS:
            return None, f"неизвестная модель {payload['model']!r}"
        changes["model"] = payload["model"]
    if "system_prompt" in payload:
        if not isinstance(payload["system_prompt"], str):
            return None, "роль должна быть строкой"
        changes["system_prompt"] = payload["system_prompt"].strip()
    if "temperature" in payload:
        temperature = payload["temperature"]
        if temperature is not None:
            if (
                isinstance(temperature, bool)
                or not isinstance(temperature, (int, float))
                or not math.isfinite(temperature)
                or not 0 <= temperature <= 2
            ):
                return None, "температура вне диапазона 0..2"
        changes["temperature"] = temperature
    if not changes:
        return None, "нечего менять"
    return {"panel": panel, "changes": changes}, None


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
        if self.path not in ("/api/chat", "/api/reset", "/api/config"):
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
        elif self.path == "/api/reset":
            self.handle_reset(payload)
        else:
            self.handle_config(payload)

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
            reply = PANELS[panel].ask(args["text"])
        finally:
            _locks[panel].release()

        self.send_json(
            {
                "panel": panel,
                "text": reply.text,
                "debug": reply.debug_line(),
                "model": reply.model,
                "elapsed": reply.elapsed,
                "prompt_tokens": reply.prompt_tokens,
                "completion_tokens": reply.completion_tokens,
                "cost": reply.cost,
                "cost_reported": reply.cost_reported,
                "served_by": reply.served_by,
                "finish_reason": reply.finish_reason,
                "truncated": reply.truncated,
                "turns": PANELS[panel].turns,
                "error": reply.error,
            }
        )

    def handle_reset(self, payload: dict) -> None:
        panel = payload.get("panel") if isinstance(payload, dict) else None
        if panel not in PANELS:
            self.send_json({"error": "нет такой панели"}, 400)
            return
        PANELS[panel].reset()
        self.send_json(panel_state(panel))

    def handle_config(self, payload: dict) -> None:
        args, error = validate_config(payload)
        if error or args is None:
            self.send_json({"error": error or "не разобрали запрос"}, 400)
            return
        panel = args["panel"]
        # Смена конфига поднимает нового агента с пустой историей. Перенести
        # переписку было бы удобнее, но она снята на другой роли и другой модели —
        # приписать её новому конфигу значило бы соврать в замерах.
        PANELS[panel] = PANELS[panel].with_config(**args["changes"])
        self.send_json(panel_state(panel))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8037)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"панель: http://127.0.0.1:{args.port}   (Ctrl+C чтобы остановить)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
