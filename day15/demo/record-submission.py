"""Записать понятный ролик для сдачи Дня 15 на свежей локальной БД."""

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
VIDEO = Path(__file__).with_name("day15-submission.mp4")
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
      const box = document.getElementById('video-caption');
      box.querySelector('strong').textContent = title;
      box.querySelector('span').textContent = detail;
    }""", [title, detail])
    page.wait_for_timeout(int(seconds * 1000))


def focus(page) -> None:
    page.evaluate("""() => window.scrollTo({
      top: document.querySelector('.fsm').getBoundingClientRect().top + window.scrollY - 110,
      behavior: 'instant'
    })""")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="day15-submission-") as directory:
        temporary = Path(directory)
        port = free_port()
        url = f"http://127.0.0.1:{port}"
        server = subprocess.Popen(
            [sys.executable, str(ROOT / "web.py"), "--db", str(temporary / "demo.db"),
             "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
                  .fsm .btn {font-size: 15px; padding: 12px 14px}
                  .fsm .event, .fsm .fact div {font-size: 15px}
                  .fsm .stage {font-size: 15px}
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
                  box.innerHTML = '<strong></strong><span></span>';
                  document.body.appendChild(box);
                }""")
                focus(page)
                caption(page, "День 15 · Контролируемые переходы",
                        "Офлайн-демо интерфейса · реальный OpenRouter-прогон показан в конце", 3.0)

                page.locator("#task-objective").fill("Подготовить текстовый план релиза")
                page.locator("#start-task").click()
                page.wait_for_function("document.querySelector('#pipeline .active span').textContent === 'planning'")
                focus(page)
                caption(page, "1. Planning · нужен план",
                        "Этап и ожидаемое действие сохранены в SQLite", 3.0)

                page.locator("#try-skip").click()
                page.wait_for_function("document.querySelector('#transition-denials').textContent.includes('approve')")
                focus(page)
                caption(page, "2. Перескок запрещён",
                        "Попытка planning → done отклонена; этап и версия не изменились", 5.0)

                page.locator("#workflow-run").click()
                page.wait_for_function("document.querySelector('#workflow-actor').textContent === 'user'")
                focus(page)
                caption(page, "3. План ждёт человека",
                        "Ассистент подготовил предложение; только пользователь может его принять", 4.0)

                page.locator("#workflow-approve").click()
                page.wait_for_function("document.querySelector('#pipeline .active span').textContent === 'validation'")
                focus(page)
                caption(page, "4. Execution → validation",
                        "После утверждения плана workflow выполнил задачу и подготовил проверку", 5.0)

                page.locator("#task-result").fill("Добавь ответственного за откат")
                page.locator("#changes").click()
                page.wait_for_function("document.querySelector('#pipeline .active span').textContent === 'execution'")
                focus(page)
                caption(page, "5. Возврат на доработку",
                        "Замечание пользователя: validation → execution", 4.0)

                page.locator("#workflow-run").click()
                page.wait_for_function("document.querySelector('#pipeline .active span').textContent === 'validation'")
                focus(page)
                caption(page, "6. Повторная проверка",
                        "Новый результат снова прошёл через validation", 4.0)

                page.locator("#pause").click()
                page.wait_for_function("document.querySelector('#task-status').textContent === 'paused'")
                focus(page)
                caption(page, "7. Пауза сохраняет точку",
                        "Этап остаётся validation; предложение не теряется", 3.0)

                page.locator("#restart").click()
                focus(page)
                caption(page, "8. Новый экземпляр агента",
                        "Состояние и предложение загружены из SQLite", 3.0)

                page.locator("#resume").click()
                page.wait_for_function("document.querySelector('#task-status').textContent === 'active'")
                focus(page)
                caption(page, "9. Продолжение без повторного вызова",
                        "Задача возвращается к тому же решению пользователя", 3.0)

                page.locator("#workflow-approve").click()
                page.wait_for_function("document.querySelector('#pipeline .active span').textContent === 'done'")
                focus(page)
                caption(page, "10. Done · только после принятия",
                        "Финал терминален; обходы и пауза больше недоступны", 4.0)

                page.set_content("""<!doctype html><html lang="ru"><meta charset="utf-8">
                  <style>body{margin:0;background:#153c2e;color:#fff;font-family:system-ui,sans-serif;
                  display:grid;place-items:center;height:100vh}.card{width:1100px}
                  h1{font-size:52px;margin:0 0 30px}p{font-size:30px;line-height:1.5;margin:12px 0}
                  small{font-size:22px;color:#a9e4c4}</style>
                  <div class="card"><small>РЕАЛЬНЫЙ ПРОГОН · OPENROUTER / DEEPINFRA</small>
                  <h1>14 вызовов · 3 задачи в done</h1>
                  <p>23/23 проверок · $0.00615348 фактического списания</p>
                  <p>GitHub Actions: success для d7579e2</p>
                  <small>Детальная трасса и код: github.com/RomaniumSSS/ai-advent-9 · day15/</small>
                  </div></html>""")
                page.wait_for_timeout(6500)
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
