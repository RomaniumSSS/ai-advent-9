"""Один браузерный сценарий для dry-run и записи новых запросов через UI."""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

GOALS = ["Найди все использования API send_invite и объясни поток вызовов", "Обнови README по текущему поведению кода и покажи изменения"]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def delivery_warnings(text):
    """Сигнал регрессии синтетического API без I/O; не полная оценка семантики."""
    warnings = []
    claims = re.compile(r"реальн\w*\s+отправ\w*|отправля(?:ет|ют)\s+(?:письм\w*|приглашени\w*)|(?:письм\w*|приглашени\w*)\s+отправля(?:ется|ются)", re.I)
    for clause in re.split(r"[.!?;\n]", text):
        for claim in claims.finditer(clause):
            nearby = clause[max(0, claim.start() - 65):claim.end() + 65]
            if not re.search(r"\b(?:не|нет|без)\b|отсутств\w*", nearby, re.I):
                warnings.append("Проверить вручную контекст отправки: " + claim.group())

    return warnings


def verify(result, index):
    assert result["status"] == "completed", result.get("reason")
    warnings = delivery_warnings(result["answer"])
    events = result["events"]
    assert all(e["result"]["ok"] and not e["result"].get("truncated") for e in events)
    reads = {json.loads(e["arguments"])["path"] for e in events if e["tool"] == "read_file"}
    assert {"src/api.py", "src/service.py", "src/cli.py"} <= reads, "Не прочитаны три файла кода"
    if index == 0:
        searches = [e for e in events if e["tool"] == "search_text"]
        hits = [hit for e in searches for hit in e["result"]["data"]]
        for path, line in [("src/api.py", 1), ("src/service.py", 5), ("src/cli.py", 11)]:
            assert any(h["path"] == path and h["line"] == line and "send_invite(" in h["text"] for h in hits), path
            assert path in result["answer"], f"Ответ не ссылается на {path}"
        assert "send_invite" in result["answer"]
        assert re.search(r"(?:[:#L]|строк[аеёиу]*)\s*\d", result["answer"], re.I), "Нет номеров строк"
        assert result["diff"] == "", "Поиск изменил файлы"
        return {"source_reads": sorted(reads), "definition_and_two_callsites": True, "semantic_warnings": warnings, "human_semantic_acceptance": "required"}
    sandbox = Path(result["sandbox"])
    readme = (sandbox / "README.md").read_text()
    warnings += delivery_warnings(readme)
    for fact in ["send_invite", "email", "role", "dry_run", "member", "admin", "--role", "--dry-run", "@"]:
        assert fact in readme, f"README потерял {fact}"
    assert "username" not in readme and "--team" not in readme and 'team="default"' not in readme
    assert any(e["tool"] == "write_file" and json.loads(e["arguments"])["path"] == "README.md" for e in events)
    assert any(e["tool"] == "show_diff" for e in events)
    assert "--- a/README.md" in result["diff"] and "+++ b/README.md" in result["diff"]
    assert "+" in result["diff"] and "dry_run" in result["diff"]
    return {"source_reads": sorted(reads), "readme_facts_and_real_diff": True, "readme": readme, "semantic_warnings": warnings, "human_semantic_acceptance": "required"}


def scroll_read(page, pause):
    height = page.evaluate("document.documentElement.scrollHeight")
    for offset in range(0, height, 650):
        page.evaluate("y => window.scrollTo(0,y)", offset)
        page.wait_for_timeout(pause * 1000)


def scenario(page, args, out, evidence):
    page.goto(args.url)
    mode = page.request.get(args.url + "/api/status").json()["mode"]
    assert mode == ("offline mock" if args.expect_mode == "mock" else "live OpenRouter"), f"Неверный режим {mode}"
    evidence["mode"] = mode
    page.locator("#mode").filter(has_text="MOCK" if args.expect_mode == "mock" else "LIVE").wait_for()
    page.screenshot(path=str(out / "start.png"))
    page.wait_for_timeout(args.pause * 1000)
    ids = set()
    for index, goal in enumerate(GOALS):
        page.evaluate("window.scrollTo(0,0)")
        page.locator("#goal").fill(goal)
        started = time.monotonic()
        with page.expect_response(lambda r: r.url == args.url + "/api/run" and r.request.method == "POST" and r.request.post_data_json == {"goal": goal}, timeout=240000) as pending:
            page.locator("#start").click()
        response = pending.value
        result = response.json()
        elapsed = time.monotonic() - started
        save(out / f"response-{index + 1}.json", result)
        assert response.status == 200, result
        assert result["goal"] == goal and result["run_id"] not in ids
        ids.add(result["run_id"])
        page.wait_for_function("id => document.querySelector('#receipt').textContent.includes(id)", arg=result["run_id"], timeout=10000)
        trace_path = Path(result["sandbox"]).parent / "trace.json"
        trace = json.loads(trace_path.read_text())
        assert trace == result, "HTTP ответ отличается от сохранённой trace"
        save(out / f"trace-{index + 1}.json", trace)
        checks = verify(result, index)
        if "readme" in checks:
            (out / "README-result.md").write_text(checks.pop("readme"))
        evidence["goals"].append({"goal": goal, "run_id": result["run_id"], "http_seconds": elapsed, "model_seconds": result["elapsed_seconds"], "checks": checks})
        page.screenshot(path=str(out / f"goal-{index + 1}-full.png"), full_page=True)
        page.locator("#events details").first.locator("summary").click()
        scroll_read(page, args.pause)
        page.locator("#answer").scroll_into_view_if_needed()
        page.screenshot(path=str(out / f"goal-{index + 1}-answer.png"))
        page.wait_for_timeout(args.pause * 1000)
        if index == 1:
            page.locator("#diff").scroll_into_view_if_needed()
            page.screenshot(path=str(out / "goal-2-diff.png"))
            scroll_read(page, args.pause)
    assert not evidence["page_errors"], evidence["page_errors"]
    evidence["passed"] = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8134")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expect-mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--pause", type=float, default=4)
    args = parser.parse_args()
    args.url = args.url.rstrip("/")
    parsed = urlparse(args.url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path:
        parser.error("Нужен loopback http://127.0.0.1:port")
    if not 1 <= args.pause <= 20:
        parser.error("Пауза чтения должна быть от 1 до 20 секунд")
    args.out.mkdir(parents=True, exist_ok=False)
    from playwright.sync_api import sync_playwright
    evidence = {"human_semantic_acceptance": "required", "passed": False, "record": args.record, "goals": [], "page_errors": []}
    started = time.monotonic()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = None
            video = None
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 1000}, **({"record_video_dir": str(args.out / "raw"), "record_video_size": {"width": 1280, "height": 1000}} if args.record else {}))
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
                video = page.video
                scenario(page, args, args.out, evidence)
            finally:
                if context is not None:
                    context.close()
                try:
                    if video is not None:
                        video.save_as(str(args.out / "capture.webm"))
                finally:
                    browser.close()
        if args.record:
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(args.out / "capture.webm"), "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(args.out / "capture.mp4")], check=True)
            probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(args.out / "capture.mp4")], text=True)
            probe = json.loads(probe)
            save(args.out / "ffprobe.json", probe)
            assert any(s.get("width") == 1280 and s.get("height") == 1000 for s in probe["streams"]), "Неверный размер видео"
            assert float(probe["format"]["duration"]) > 0, "Пустое видео"
    except Exception as exc:
        evidence["passed"] = False
        evidence["error"] = str(exc)
        raise
    finally:
        evidence["elapsed_seconds"] = time.monotonic() - started
        save(args.out / "evidence.json", evidence)
    print(str(args.out / "evidence.json"))


if __name__ == "__main__":
    main()
