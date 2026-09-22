"""Записать короткое live-видео MCP discovery для сдачи Дня 16."""

from __future__ import annotations

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
VIDEO = Path(__file__).with_name("day16-mcp-discovery.mp4")
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_server(url: str) -> None:
    for _ in range(60):
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
    with tempfile.TemporaryDirectory(prefix="day16-video-") as directory:
        temporary = Path(directory)
        port = free_port()
        url = f"http://127.0.0.1:{port}"
        server = subprocess.Popen(
            [sys.executable, str(ROOT / "web.py"), "--db", str(temporary / "demo.db"),
             "--port", str(port)],
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
                  const title = document.createElement('strong');
                  const detail = document.createElement('span');
                  box.append(title, detail);
                  document.body.appendChild(box);
                  window.scrollTo(0, 0);
                }""")
                caption(
                    page,
                    "День 16 · MCP discovery",
                    "Агент дня 15 сохранён; MCP — отдельное действие приложения",
                    3.0,
                )

                page.locator("#mcp-discover").click()
                page.wait_for_function("""() => {
                  const text = document.querySelector('#mcp-count').textContent;
                  return /^Tools: [1-9]/.test(text);
                }""", timeout=120_000)
                count = page.locator("#mcp-count").text_content()
                protocol = page.locator("#mcp-protocol").text_content()
                caption(
                    page,
                    "Соединение → negotiation → tools/list → close",
                    f"Everything MCP Server · {protocol} · {count}",
                    7.0,
                )
                caption(
                    page,
                    "Discovery ≠ execution",
                    "Нет call_tool, tools не переданы модели и не записаны в SQLite",
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
