"""Одинаковые короткие агентные сценарии для локальных моделей Ollama."""
import argparse
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.request import ProxyHandler, Request, build_opener

BASE = "http://127.0.0.1:11434"
CLIENT = build_opener(ProxyHandler({}))
SYSTEM = (
    "Ты проверяешь учебный каталог через инструменты. Все сведения о товарах и "
    "расчётах получай из результатов инструментов. После ошибки используй её "
    "данные для исправления запроса. Не придумывай результаты. Финальный ответ "
    "должен быть только JSON с полями, указанными пользователем."
)
TOOLS = [
    {"type": "function", "function": {
        "name": "find_product", "description": "Найти товар в учебном каталоге по названию.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                       "required": ["query"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "quote_order", "description": "Рассчитать стоимость заказа с доставкой по ID найденного товара; может вернуть ошибку недостаточного остатка.",
        "parameters": {"type": "object", "properties": {
            "product_id": {"type": "string"}, "quantity": {"type": "integer", "minimum": 1, "maximum": 100}},
            "required": ["product_id", "quantity"], "additionalProperties": False}}},
]
SCENARIOS = [
    {"id": "lookup", "prompt": "Найди клавиатуру в каталоге. Верни JSON с product_id, unit_price_eur и stock.",
     "expected": {"product_id": "KB-204", "unit_price_eur": 37, "stock": 4}},
    {"id": "dependent", "prompt": "Найди клавиатуру в каталоге, затем запроси расчёт заказа на 3 штуки. Верни JSON с quantity и total_eur, включая доставку.",
     "expected": {"quantity": 3, "total_eur": 118}},
    {"id": "recovery", "prompt": "Найди клавиатуру. Для проверки ошибки обязательно сначала запроси расчёт на 6 штук. Если инструмент сообщит недостаточный остаток, запроси расчёт на максимально доступное количество. Верни JSON с quantity и total_eur, включая доставку.",
     "expected": {"quantity": 4, "total_eur": 155}},
]


def now():
    return datetime.now(timezone.utc).isoformat()


def api(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with CLIENT.open(request, timeout=180) as response:
        return json.load(response)


def memory():
    return {"time": now(), "swap": subprocess.check_output(["sysctl", "vm.swapusage"], text=True).strip(),
            "pressure": subprocess.check_output(["memory_pressure", "-Q"], text=True).strip(),
            "pressure_level": int(subprocess.check_output(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"], text=True)),
            "loaded": api("/api/ps")}


def execute(name, args, seen):
    # AICODE-NOTE: модель предлагает вызов, но исполняется только этот закрытый
    # набор функций с проверенными аргументами; shell и реальные заказы недоступны.
    if not isinstance(args, dict):
        return {"error": "INVALID_ARGUMENTS"}
    if name == "find_product":
        if set(args) != {"query"} or not isinstance(args["query"], str):
            return {"error": "INVALID_ARGUMENTS"}
        query = args["query"].casefold()
        if "клав" not in query and "keyboard" not in query:
            return {"products": []}
        seen.add("KB-204")
        return {"products": [{"product_id": "KB-204", "name": "Клавиатура", "unit_price_eur": 37, "stock": 4}]}
    if name == "quote_order":
        if set(args) != {"product_id", "quantity"} or not isinstance(args["product_id"], str) or type(args["quantity"]) is not int or not 1 <= args["quantity"] <= 100:
            return {"error": "INVALID_ARGUMENTS"}
        if args["product_id"] not in seen:
            return {"error": "PRODUCT_NOT_OBSERVED", "message": "Сначала найдите товар"}
        if args["quantity"] > 4:
            return {"error": "INSUFFICIENT_STOCK", "available": 4}
        quantity = args["quantity"]
        return {"product_id": "KB-204", "quantity": quantity, "subtotal_eur": quantity * 37,
                "shipping_eur": 7, "total_eur": quantity * 37 + 7}
    return {"error": "UNKNOWN_TOOL"}


def parse_final(content):
    content = content.strip()
    if content.startswith("```") and content.endswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None


def judge(scenario, record):
    final = parse_final(record.get("final", ""))
    checks = {"finished": record.get("stop") == "final", "final_fields": final == scenario["expected"],
              "lookup": any(t["name"] == "find_product" and t["result"].get("products") for t in record["tools"]),
              "valid_calls": all(t["result"].get("error") in (None, "INSUFFICIENT_STOCK") for t in record["tools"])}
    if scenario["id"] == "dependent":
        checks["quote"] = any(t["name"] == "quote_order" and t["result"].get("quantity") == 3 for t in record["tools"])
    if scenario["id"] == "recovery":
        outcomes = [t["result"] for t in record["tools"] if t["name"] == "quote_order"]
        error_index = next((i for i, r in enumerate(outcomes) if r.get("error") == "INSUFFICIENT_STOCK"), None)
        checks["recover"] = error_index is not None and any(r.get("quantity") == 4 for r in outcomes[error_index+1:])
    return {"checks": checks, "pass": all(checks.values()), "parsed_final": final}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=["qwen3.5:9b-q4_K_M", "qwen3:8b"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"started_at": now(), "endpoint": BASE, "server": api("/api/version"),
              "machine": platform.machine(), "fixture": "Синтетический каталог; реальные локальные model calls",
              "models": [], "before": memory()}
    def save():
        (args.output / "run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    save()
    for model in args.models:
        if api("/api/ps")["models"]:
            raise RuntimeError("Перед сравнением другая модель ещё занимает память")
        model_run = {"model": model, "started_at": now(), "details": api("/api/show", {"model": model}).get("details"), "scenarios": []}
        report["models"].append(model_run)
        save()
        try:
            for scenario in SCENARIOS:
                print(f"{model}: {scenario['id']}", flush=True)
                record = {"id": scenario["id"], "steps": [], "tools": [], "stop": "step_limit"}
                model_run["scenarios"].append(record)
                messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": scenario["prompt"]}]
                seen = set()
                for _ in range(5):
                    if int(subprocess.check_output(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"], text=True)) >= 4:
                        raise RuntimeError("macOS сообщает критическое давление памяти; модель будет выгружена")
                    payload = {"model": model, "messages": messages, "tools": TOOLS, "stream": False,
                               "think": False, "keep_alive": "5m", "options": {
                                   "num_ctx": 8192, "num_predict": 384, "temperature": 0.2, "seed": 42}}
                    start = perf_counter()
                    response = api("/api/chat", payload)
                    elapsed = perf_counter() - start
                    message = response["message"]
                    message.pop("thinking", None)
                    record["steps"].append({"request": json.loads(json.dumps(payload)), "response": response, "elapsed_seconds": elapsed})
                    messages.append(message)
                    save()
                    if not response.get("done") or response.get("done_reason") == "length":
                        record["stop"] = "incomplete"
                        break
                    calls = message.get("tool_calls", [])
                    if not calls:
                        record.update(final=message.get("content", ""), stop="final")
                        break
                    if len(calls) > 8:
                        for call in calls:
                            messages.append({"role": "tool", "tool_name": call["function"]["name"], "content": '{"error":"CALL_LIMIT"}'})
                        record["stop"] = "tool_limit"
                        break
                    for call in calls:
                        function = call["function"]
                        name, arguments = function["name"], function.get("arguments")
                        result = execute(name, arguments, seen)
                        record["tools"].append({"name": name, "arguments": arguments, "result": result})
                        messages.append({"role": "tool", "tool_name": name, "content": json.dumps(result, ensure_ascii=False)})
                        save()
                record["judgement"] = judge(scenario, record)
                record["elapsed_seconds"] = sum(s["elapsed_seconds"] for s in record["steps"])
                model_run["loaded"] = memory()
                save()
                print(f"  {'PASS' if record['judgement']['pass'] else 'FAIL'}: {record['elapsed_seconds']:.2f} с; tools={len(record['tools'])}; final={record.get('final')}", flush=True)
        except Exception as exc:
            model_run["error"] = f"{type(exc).__name__}: {exc}"
            save()
            raise
        finally:
            model_run["unload"] = api("/api/generate", {"model": model, "keep_alive": 0})
            model_run["after_unload"] = memory()
            save()
    report["finished_at"] = now()
    report["after"] = memory()
    save()
    raise SystemExit(0 if all(s["judgement"]["pass"] for m in report["models"] for s in m["scenarios"]) else 1)


if __name__ == "__main__":
    main()
