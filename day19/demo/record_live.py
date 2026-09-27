"""Записать прямой показ нового CLI-прогона с реальной моделью и MCP."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from day19.evals.audit import audit_trace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
VIDEO = HERE / "day19-live-agent.mp4"
REQUEST = ("Собери сводку реального бизнес- и личного применения ИИ-агентов. "
           "Отличай практику от мнений и учебных примеров; сохрани отчёт.")


def main() -> None:
    fixture = ROOT / "evals" / "fixtures" / "mixed_fact_noise.xml"
    with tempfile.TemporaryDirectory(prefix="day19-live-screen-") as directory:
        temporary = Path(directory)
        trace_path = temporary / "trace.json"
        command = [
            sys.executable, "-m", "day19.cli", "--show-steps",
            "--db", str(temporary / "state.sqlite3"),
            "--trace", str(trace_path),
            "--rss-file", str(fixture),
            "--start", "2026-09-22T00:00:00Z",
            "--end", "2026-09-27T09:38:00Z",
            "--request", REQUEST,
        ]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, executable_path=str(CHROME) if CHROME.is_file() else None)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                record_video_dir=str(temporary),
                record_video_size={"width": 1440, "height": 900},
                device_scale_factor=1)
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto((HERE / "live-console.html").as_uri())
            page.evaluate("(request) => window.setRequest(request)", REQUEST)
            page.wait_for_timeout(1800)
            page.click("#startButton")

            process = subprocess.Popen(
                command, cwd=ROOT.parent, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1)
            lines: list[str] = []
            summary: dict | None = None
            assert process.stdout is not None
            for line in process.stdout:
                lines.append(line)
                payload = json.loads(line)
                if payload.get("event"):
                    page.evaluate("(event) => window.pushEvent(event)", payload)
                else:
                    summary = payload
                    page.evaluate("(result) => window.showSummary(result)", payload)
            if process.stderr:
                process.stderr.read()
            if process.wait() != 0 or summary is None or summary["status"] != "saved":
                raise RuntimeError("live_cli_failed")
            trace = audit_trace(trace_path)
            if len(trace["tool_calls"]) != 3 or summary["tool_calls"] != 3:
                raise ValueError("live_demo_requires_three_mcp_calls")
            report_path = ROOT / "output" / f"report-{trace['run_id']}.txt"
            report = report_path.read_text(encoding="utf-8")
            if errors:
                raise RuntimeError("page_errors:" + json.dumps(errors))

            page.wait_for_timeout(3200)
            page.evaluate(
                "(data) => window.showReport(data)",
                {"run_id": trace["run_id"],
                 "path": str(report_path.relative_to(ROOT)),
                 "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                 "report": report})
            page.wait_for_timeout(6700)
            raw_video = page.video
            context.close()
            browser.close()
            if errors:
                raise RuntimeError("page_errors:" + json.dumps(errors))
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-i", raw_video.path(), "-c:v", "libx264", "-preset", "medium",
                 "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                 "-an", str(VIDEO)],
                check=True)
        shutil.copy2(trace_path, HERE / "live-screen-trace.json")
        (HERE / "live-screen-cli.jsonl").write_text("".join(lines), encoding="utf-8")
    print(json.dumps(
        {"video": str(VIDEO), "trace": str(HERE / "live-screen-trace.json"),
         "status": "saved", "tool_calls": 3, "run_id": trace["run_id"],
         "reported_cost_usd": trace["reported_cost_usd"], "page_errors": errors},
        ensure_ascii=False))


if __name__ == "__main__":
    main()
