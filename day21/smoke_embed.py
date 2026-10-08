"""Проверка эмбеддера на нейтральном тексте, без корпуса и внешнего API."""

import json
import math
import time
from datetime import datetime, timezone
from urllib.request import ProxyHandler, Request, build_opener


MODEL = "qwen3-embedding:0.6b"
BASE = "http://127.0.0.1:11434"
OPENER = build_opener(ProxyHandler({}))
TEXTS = [
    "Документы разделены на фрагменты. Каждый фрагмент сохраняется вместе с источником.",
    "На кухне стоят стол и два стула. За окном растёт дерево.",
    (
        "Учебная библиотека содержит условия заданий и пояснения к ним. "
        "Для каждого документа сохраняются заголовок и дата. "
        "Большие разделы делятся на небольшие фрагменты, а короткие остаются целыми. "
        "После обработки можно проверить, что все фрагменты связаны с исходными документами. "
    ) * 4,
]


def request(path, payload=None):
    req = Request(
        BASE + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with OPENER.open(req, timeout=180) as response:
        return json.load(response)


def main():
    info = request("/api/show", {"model": MODEL})
    if info.get("remote_host") or info.get("remote_model"):
        raise RuntimeError("Требуется локальная модель")
    models = request("/api/tags")["models"]
    model = next(item for item in models if item["name"] == MODEL)
    report = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "digest": model["digest"],
        "ollama_version": request("/api/version")["version"],
        "input_characters": list(map(len, TEXTS)),
        "private_corpus_used": False,
        "runs": [],
    }
    for label in ("first", "warm"):
        started = time.monotonic()
        result = request("/api/embed", {
            "model": MODEL,
            "input": TEXTS,
            "truncate": False,
            "keep_alive": "60s",
            "options": {"num_ctx": 2048, "num_thread": 1, "num_batch": 128},
        })
        elapsed = time.monotonic() - started
        vectors = result["embeddings"]
        if len(vectors) != len(TEXTS):
            raise RuntimeError("Число векторов не совпало с числом текстов")
        for vector in vectors:
            if len(vector) != 1024 or not all(math.isfinite(value) for value in vector):
                raise RuntimeError("Некорректный вектор")
        norms = [math.sqrt(sum(value * value for value in vector)) for vector in vectors]
        if any(abs(norm - 1) > 0.001 for norm in norms) or vectors[0] == vectors[1]:
            raise RuntimeError("Не прошла проверка норм и различия векторов")
        report["runs"].append({
            "label": label, "elapsed_seconds": round(elapsed, 3),
            "vectors": len(vectors), "dimensions": len(vectors[0]),
            "norms": norms, "prompt_eval_count": result.get("prompt_eval_count"),
            "load_seconds": result.get("load_duration", 0) / 1e9,
        })
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
