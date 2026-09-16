"""Записать немое видео кода и панели. Сначала запустить serve_recording.py."""

import html
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
BUILD = OUT / ".build"
BUILD.mkdir(exist_ok=True)
PANEL = "http://127.0.0.1:8042"
REPORT = json.loads((ROOT / "results" / "live-memory.json").read_text())
FORMAT_CALL = next(row for row in REPORT["calls"] if row["case"] == "format_after")

FRAGMENTS = [
    ("Три таблицы", "store.py", "CREATE TABLE IF NOT EXISTS short_notes", '"""'),
    ("Области", "store.py", "    def _scope", "    def notes"),
    ("Запрос модели", "agent.py", "    def memory_messages", "    def budget"),
]


def code_sections() -> list[tuple[str, str, str]]:
    sections = []
    for title, filename, start, end in FRAGMENTS:
        source = (ROOT / filename).read_text()
        begin = source.index(start)
        finish = source.index(end, begin)
        body = source[begin:finish].rstrip()
        first_line = source[:begin].count("\n") + 1
        numbered = "\n".join(
            f"{first_line + index:>3}  {line}"
            for index, line in enumerate(body.splitlines())
        )
        sections.append((title, f"day11/{filename}", numbered))
    return sections


sections = code_sections()
viewer = BUILD / "code.html"
viewer.write_text(
    '<!doctype html><meta charset="utf-8"><style>'
    "body{margin:0;background:#14201d;color:#e0e9e3;font:20px/1.65 Menlo,monospace}"
    "nav{padding:22px;background:#1e3028}"
    "button{font:18px Menlo;background:#304c3b;color:#fff;border:0;padding:12px 18px;"
    "margin-right:12px;border-radius:6px}"
    "pre{padding:24px 30px;white-space:pre-wrap;font-size:16px}"
    "section{display:none}section:first-of-type{display:block}"
    "h3{padding:0 30px;margin:18px 0 0;color:#8fb9a3;font:15px Menlo}</style>"
    "<nav>День 11 &nbsp;"
    + "".join(
        f'<button onclick="show({index})">{title}</button>'
        for index, (title, _, _) in enumerate(sections)
    )
    + "</nav>"
    + "".join(
        f"<section><h3>{path}</h3><pre>{html.escape(code)}</pre></section>"
        for _, path, code in sections
    )
    + "<script>function show(i){document.querySelectorAll('section')"
    ".forEach((el,j)=>el.style.display=i===j?'block':'none')}</script>"
)


def open_scope(page, user: str, task: str, session: str) -> None:
    page.locator("#user").fill(user)
    page.locator("#task").fill(task)
    page.locator("#session").fill(session)
    page.locator("#open-scope").click()
    page.wait_for_function(
        "scope => document.getElementById('user').value === scope.user "
        "&& document.getElementById('task').value === scope.task "
        "&& document.getElementById('session').value === scope.session "
        "&& document.getElementById('status').textContent.includes('Область открыта')",
        arg={"user": user, "task": task, "session": session},
    )


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1100},
        record_video_dir=str(BUILD),
        record_video_size={"width": 1440, "height": 1100},
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    page.goto(viewer.as_uri())
    page.wait_for_timeout(4500)
    page.get_by_role("button", name="Области", exact=True).click()
    page.wait_for_timeout(4500)
    page.get_by_role("button", name="Запрос модели", exact=True).click()
    page.wait_for_timeout(4500)

    page.goto(PANEL)
    page.wait_for_function("document.querySelectorAll('#history .message').length === 4")

    # Один вопрос до записи срока и тот же вопрос после неё: рабочая память
    # показана через изменение ответа, а не только через заполненную карточку.
    history = page.locator("#history")
    messages = page.locator("#history .message")
    assert "не знаю" in messages.nth(1).inner_text().lower()
    assert "27 октября 2031" in messages.nth(3).inner_text().lower()
    history.evaluate("element => { element.scrollTop = 0; }")
    for index in (0, 1):
        messages.nth(index).evaluate(
            "element => { element.style.outline = '3px solid #d9aa45'; }"
        )
    page.wait_for_timeout(4500)
    for index in (0, 1):
        messages.nth(index).evaluate("element => { element.style.outline = ''; }")
    history.evaluate("element => { element.scrollTop = element.scrollHeight; }")
    for index in (2, 3):
        messages.nth(index).evaluate(
            "element => { element.style.outline = '3px solid #399d79'; }"
        )
    page.wait_for_timeout(4500)
    for index in (2, 3):
        messages.nth(index).evaluate("element => { element.style.outline = ''; }")

    # Явный выбор: одна запись уходит именно в рабочую память.
    page.locator("#key").fill("формат ответа")
    page.locator("#value").fill("Показывать итог маркированным списком.")
    page.get_by_role("button", name="В задачу", exact=False).click()
    page.wait_for_function(
        "document.getElementById('working-notes').textContent.includes('маркированным')"
    )
    page.wait_for_timeout(2500)

    # Результат этой настройки: реальный сохранённый ответ модели приходит
    # через тот же Agent.ask(), а сервер сверяет вопрос и весь memory prompt.
    page.locator("#question").fill(FORMAT_CALL["question"])
    page.get_by_role("button", name="Спросить", exact=True).click()
    page.wait_for_function("document.querySelectorAll('#history .message').length === 6")
    format_answer = page.locator("#history .message").last.inner_text()
    assert "27 октября 2031" in format_answer
    assert "Новосибирск" in format_answer
    assert sum(
        line.lstrip().startswith(("-", "•", "*"))
        for line in format_answer.splitlines()
    ) >= 2
    page.wait_for_timeout(4500)

    # Натуральная ошибка области: существующую сессию нельзя молча привязать
    # к другой задаче. Сообщение приходит из SqliteStore, а не из декорации видео.
    page.locator("#task").fill("shop")
    page.locator("#open-scope").click()
    page.wait_for_function(
        "document.getElementById('status').textContent.includes('уже принадлежит')"
    )
    assert "error" in (page.locator("#status").get_attribute("class") or "")
    natural_error = page.locator("#status").inner_text()
    assert page.locator("#task").input_value() == "landing"
    assert page.locator("#session").input_value() == "landing-1"
    page.wait_for_timeout(4500)

    snapshots = {}
    snapshots["landing-1"] = {
        layer: page.locator(f"#{layer}-notes").inner_text()
        for layer in ("short", "working", "long")
    }

    open_scope(page, "roman", "landing", "landing-2")
    page.wait_for_function(
        "document.getElementById('short-notes').textContent.includes('Пока нет')"
    )
    snapshots["landing-2"] = {
        layer: page.locator(f"#{layer}-notes").inner_text()
        for layer in ("short", "working", "long")
    }
    page.wait_for_timeout(4500)

    open_scope(page, "roman", "shop", "shop-2")
    page.wait_for_function(
        "document.getElementById('working-notes').textContent.includes('Пока нет')"
    )
    snapshots["shop-2"] = {
        layer: page.locator(f"#{layer}-notes").inner_text()
        for layer in ("short", "working", "long")
    }
    page.wait_for_timeout(4500)

    open_scope(page, "anna", "shop", "anna-1")
    page.wait_for_function(
        "document.getElementById('long-notes').textContent.includes('Пока нет')"
    )
    snapshots["anna-1"] = {
        layer: page.locator(f"#{layer}-notes").inner_text()
        for layer in ("short", "working", "long")
    }
    page.wait_for_timeout(5000)
    page.screenshot(path=str(BUILD / "final.png"), full_page=True)

    assert "янтарный маяк" in snapshots["landing-1"]["short"]
    assert "срок" in snapshots["landing-2"]["working"]
    assert "Новосибирск" in snapshots["shop-2"]["long"]
    assert all("Пока нет" in value for value in snapshots["anna-1"].values())

    video = page.video
    context.close()
    raw = video.path()
    browser.close()
    if errors:
        raise RuntimeError(errors)

silent = OUT / "day11-memory-silent.mp4"
subprocess.run(
    [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw),
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "19",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(silent),
    ],
    check=True,
)
fast = OUT / "day11-memory-fast.mp4"
subprocess.run(
    [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent),
        "-filter:v", "setpts=PTS/1.25", "-an", "-c:v", "libx264",
        "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(fast),
    ],
    check=True,
)
(OUT / "recording-meta.json").write_text(
    json.dumps(
        {
            "source_report": "day11/results/live-memory.json",
            "network_calls_during_recording": 0,
            "viewport": [1440, 1100],
            "speed_up": 1.25,
            "page_errors": errors,
            "format_answer": format_answer,
            "natural_error": natural_error,
            "scope_snapshots": snapshots,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n"
)
print(fast)
