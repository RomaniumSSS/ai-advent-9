"""Офлайн-проверки HTTP-границы панели дня 5. Внешнюю сеть не используют.

Запуск:
    uv run day05/test_web.py
"""

import http.client
import json
import sys
import configparser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import web as web_module  # noqa: E402
from web import RunHandler, serve, validate  # noqa: E402


def check_validate() -> list[str]:
    problems = []
    invalid = [
        ([], "объектом"),
        ({"question": 42}, "строкой"),
        ({"question": "x", "models": ["glm-5.3"] * 3}, "разные"),
        ({"question": "x", "runs": True}, "прогонов"),
        ({"question": "x", "temperature": True}, "температура"),
        ({"question": "x", "judge": "false"}, "judge"),
        ({"question": "x", "dry_run": 1}, "dry_run"),
    ]
    for payload, expected in invalid:
        try:
            args, error = validate(payload)
        except Exception as exc:
            problems.append(
                f"validate упал на {payload!r}: {type(exc).__name__}: {exc}"
            )
            continue
        if args is not None or not error or expected not in error:
            problems.append(
                f"validate принял {payload!r}: args={args!r}, error={error!r}"
            )
    return problems


def request(
    port: int,
    body: object,
    content_type: str,
    origin: str | None = None,
    host: str | None = None,
):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    headers = {"Content-Type": content_type}
    if origin is not None:
        headers["Origin"] = origin
    if host is not None:
        headers["Host"] = host
    connection.request("POST", "/api/compare", json.dumps(body), headers)
    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()
    return response.status, payload


def check_http_boundary() -> list[str]:
    problems = []
    server = serve(RunHandler, "127.0.0.1", 0)
    port = server.server_address[1]
    dry_run = {"question": "x", "dry_run": True}
    try:
        status, _ = request(port, dry_run, "text/plain")
        if status != 415:
            problems.append(f"text/plain POST: ждали 415, получили {status}")

        status, _ = request(port, dry_run, "application/json", "https://evil.example")
        if status != 403:
            problems.append(f"чужой Origin: ждали 403, получили {status}")

        status, _ = request(port, dry_run, "application/json", host="evil.example:8036")
        if status != 403:
            problems.append(f"чужой Host: ждали 403, получили {status}")

        status, payload = request(
            port, dry_run, "application/json", f"http://127.0.0.1:{port}"
        )
        if status != 200 or payload.get("calls") != 9:
            problems.append(
                f"same-origin dry run обязан работать: status={status}, body={payload}"
            )

        status, _ = request(port, [], "application/json")
        if status != 400:
            problems.append(f"JSON-массив: ждали 400, получили {status}")

        web_module._run_lock.acquire()
        try:
            status, _ = request(port, {"question": "x"}, "application/json")
        finally:
            web_module._run_lock.release()
        if status != 409:
            problems.append(
                f"параллельный платный запуск: ждали 409, получили {status}"
            )
    finally:
        server.shutdown()
        server.server_close()
    return problems


def check_service_user() -> list[str]:
    problems = []
    unit = Path(__file__).parent / "deploy" / "day05.service"
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(unit)
    service = parser["Service"] if parser.has_section("Service") else {}
    if service.get("User") != "ai-advent" or service.get("Group") != "ai-advent":
        problems.append("systemd-сервис должен работать от пользователя ai-advent")
    return problems


def main() -> None:
    problems = check_validate() + check_http_boundary() + check_service_user()
    if problems:
        print("FAIL")
        for problem in problems:
            print(f"        {problem}")
        sys.exit(1)

    print("ok    HTTP принимает только JSON с локальным Host и того же Origin")
    print("ok    типы и три разные модели проверяются до запуска")
    print("ok    одновременно разрешено только одно платное сравнение")
    print("ok    systemd запускает панель без прав root")


if __name__ == "__main__":
    main()
