"""Записать короткое live-видео bounded MCP tool calling для Day 17."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIDEO = Path(__file__).with_name("day17-mcp-tool-calling.mp4")
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_server(url: str) -> None:
    for _ in range(80):
        try:
            with urlopen(url, timeout=1):
                return
        except (URLError, TimeoutError):
            time.sleep(0.1)
    raise RuntimeError("локальная панель не поднялась")


def caption(page, title: str, detail: str, seconds: float) -> None:
    page.evaluate("""([title, detail]) => {
      document.querySelector('#video-caption strong').textContent = title;
      document.querySelector('#video-caption span').textContent = detail;
    }""", [title, detail])
    page.wait_for_timeout(int(seconds * 1000))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="day17-video-") as directory:
        temporary = Path(directory)
        port = free_port()
        url = f"http://127.0.0.1:{port}"
        server = subprocess.Popen(
            [
                sys.executable, "-B", str(ROOT / "web.py"),
                "--db", str(temporary / "demo.db"), "--port", str(port),
                "--env-file", str(args.env_file),
            ],
            cwd=ROOT.parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait_server(url)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    executable_path=str(CHROME) if CHROME.is_file() else None,
                )
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    record_video_dir=str(temporary),
                    record_video_size={"width": 1440, "height": 900},
                    device_scale_factor=1,
                )
                page = context.new_page()
                page_errors: list[str] = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(url, wait_until="networkidle")
                page.add_style_tag(content="""
                  .wrap {padding-top: 118px}
                  #video-caption {
                    position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
                    height: 94px; padding: 13px 48px; color: white;
                    background: #153c2e; box-shadow: 0 7px 22px #153c2e40;
                    display: flex; flex-direction: column; justify-content: center;
                    pointer-events: none;
                  }
                  #video-caption strong {font: 700 27px/1.2 system-ui, sans-serif}
                  #video-caption span {font: 400 17px/1.4 system-ui, sans-serif; opacity: .9}
                """)
                page.evaluate("""() => {
                  const box = document.createElement('div');
                  box.id = 'video-caption';
                  box.append(document.createElement('strong'), document.createElement('span'));
                  document.body.appendChild(box);
                  window.scrollTo(0, 0);
                }""")
                caption(
                    page,
                    "День 17 · первый MCP-инструмент",
                    "Один read-only get_recent_commits в обычном chat flow",
                    2.5,
                )

                page.locator("#mcp-discover").click()
                page.wait_for_function(
                    "() => document.querySelector('#mcp-count').textContent === 'Tools: 1'",
                    timeout=120_000,
                )
                caption(
                    page,
                    "Schema приходит из MCP discovery",
                    "Имя, description и input schema не дублируются вручную в provider payload",
                    4.0,
                )

                page.locator("#question").scroll_into_view_if_needed()
                page.locator("#question").fill(
                    "Покажи 3 последних коммита Git с полным id и subject"
                )
                page.locator("#chat-form button").click()
                page.wait_for_function(
                    "() => document.querySelector('#turn-trace').textContent.includes('provider_final')",
                    timeout=180_000,
                )
                page.locator("#turn-trace").scroll_into_view_if_needed()
                caption(
                    page,
                    "LLM1 → validated tools/call → observation → LLM2",
                    "Audit различает два provider calls и одно MCP execution",
                    6.0,
                )
                page.locator("#history").scroll_into_view_if_needed()
                caption(
                    page,
                    "Сохранён только проверенный final response",
                    "Ответ содержит commit IDs из observation; tool protocol не попал в историю",
                    5.0,
                )

                raw_video = page.video
                context.close()
                browser.close()
                if page_errors:
                    raise RuntimeError("ошибки страницы: " + json.dumps(page_errors))
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", raw_video.path(), "-c:v", "libx264", "-preset", "medium",
                    "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-an", str(VIDEO),
                ], check=True)
                print(json.dumps({"video": str(VIDEO), "page_errors": page_errors}))
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    main()
