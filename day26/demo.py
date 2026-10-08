"""Три реальных запроса к локальной Qwen3 через Ollama HTTP API."""
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.request import ProxyHandler, Request, build_opener

BASE = "http://127.0.0.1:11434"
MODEL = "qwen3:8b"
ROOT = Path(__file__).resolve().parent
CLIENT = build_opener(ProxyHandler({}))
QUESTIONS = [
    ("Простой", "Сколько будет 17 + 25? Ответь одним числом."),
    ("Средний", "Объясни разницу между списком и множеством в Python. Дай короткий пример, показывающий удаление дубликатов. Не более 120 слов."),
    ("Сложный", "Напиши функцию Python merge_intervals(intervals), объединяющую пересекающиеся интервалы. Вход: [[1,3],[2,6],[8,10],[10,12]]. Укажи результат для этого входа, сложность алгоритма и поведение при пустом входе. Интервалы, касающиеся концами, объединяются. Ответ до 220 слов."),
]


def api(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with CLIENT.open(request, timeout=300) as response:
        return json.load(response)


def main():
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    run = {"started_at": datetime.now(timezone.utc).isoformat(), "endpoint": BASE,
           "model": MODEL, "version": api("/api/version"), "models": api("/api/tags"),
           "requests": []}
    for level, prompt in QUESTIONS:
        print(f"\n[{level}] {prompt}", flush=True)
        payload = {"model": MODEL, "prompt": prompt, "think": False, "stream": False,
                   "keep_alive": "30m", "options": {"temperature": 0, "num_predict": 700, "num_ctx": 4096}}
        start = perf_counter()
        response = api("/api/generate", payload)
        elapsed = perf_counter() - start
        run["requests"].append({"level": level, "request": payload,
                                "elapsed_seconds": elapsed, "response": response})
        (out / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n")
        if not response.get("done") or not response.get("response", "").strip():
            raise RuntimeError("Модель не вернула законченный непустой ответ")
        if response.get("done_reason") == "length":
            raise RuntimeError("Ответ обрезан лимитом токенов; результат сохранён")
        print(response["response"], flush=True)
        print(f"Время: {elapsed:.2f} с; токенов: {response.get('eval_count')}", flush=True)
    run["loaded_models"] = api("/api/ps")
    (out / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n")
    print("\nВсе три запроса получили ответы. Доказательство: day26/results/run.json")


if __name__ == "__main__":
    main()
