"""Немая запись кода и настоящей панели дня 10. Сначала запустить serve_recording.py.

Порядок сцен выбран так, чтобы видео отвечало на вопрос задания без слов:
сперва три стратегии в коде, затем они же на живой панели — переключением,
которое историю не трогает, — затем ветки, затем один настоящий ход с памятью.
"""

import html
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
BUILD = OUT / ".build"
BUILD.mkdir(exist_ok=True)
PANEL = "http://127.0.0.1:8050"

# Фрагменты берутся из настоящих файлов по границам функций: перепечатать код
# в шаблон значило бы показать на видео то, чего в репозитории может не быть.
FRAGMENTS = [
    ("Стратегии", "strategies.py", "def context_history", None),
    ("Ключи фактов", "facts.py", "FACT_KEYS = (", "MAX_FACT_VALUE_CHARS"),
    ("Ветка", "branches.py", "def fork", "def switch"),
]

sections = []
for title, filename, start, end in FRAGMENTS:
    source = (ROOT / filename).read_text()
    begin = source.index(start)
    finish = source.index(end, begin) if end else len(source)
    body = source[begin:finish].rstrip()
    first_line = source[:begin].count("\n") + 1
    numbered = "\n".join(
        f"{first_line + index:>3}  {line}"
        for index, line in enumerate(body.splitlines())
    )
    sections.append((title, f"day10/{filename}", numbered))

viewer = BUILD / "code.html"
viewer.write_text(
    '<!doctype html><meta charset="utf-8"><style>'
    "body{margin:0;background:#14201d;color:#e0e9e3;font:20px/1.7 Menlo,monospace}"
    "nav{padding:22px;background:#1e3028}"
    "button{font:18px Menlo;background:#304c3b;color:#fff;border:0;padding:12px 18px;"
    "margin-right:12px;border-radius:6px}"
    "pre{padding:30px;white-space:pre-wrap;font-size:17px}"
    "section{display:none}section:first-of-type{display:block}"
    "h3{padding:0 30px;margin:18px 0 0;color:#8fb9a3;font:15px Menlo}</style><nav>День 10 &nbsp;"
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

    # 1. Код: три фрагмента.
    page.goto(viewer.as_uri())
    page.wait_for_timeout(6000)
    page.get_by_role("button", name="Ключи фактов", exact=True).click()
    page.wait_for_timeout(6000)
    page.get_by_role("button", name="Ветка", exact=True).click()
    page.wait_for_timeout(6000)

    # 2. Панель с реальной историей.
    page.goto(PANEL)
    page.wait_for_function(
        "document.getElementById('details').textContent.includes('Ходов: 13')"
    )
    page.wait_for_timeout(4000)

    # 3. Переключение стратегий: меняется только то, что уедет в модель.
    measurements = {}
    for label in ("Полная история", "Sliding Window", "Sticky Facts"):
        page.get_by_role("button", name=label, exact=True).click()
        page.wait_for_function(
            "label => document.getElementById('panel-title').textContent.startsWith(label)",
            arg=label,
        )
        page.wait_for_timeout(3500)
        measurements[label] = {
            "metrics": page.locator("#metrics").inner_text().replace("\n", " "),
            "details": page.locator("#details").inner_text(),
        }
    assert "Ходов: 13" in measurements["Полная история"]["details"], (
        "история не должна меняться"
    )

    # 4. Ветка от текущей точки и переход в неё.
    page.locator("#branch-name").fill("alt")
    page.wait_for_timeout(1500)
    page.locator("#branch").click()
    page.wait_for_function(
        "document.getElementById('status').textContent.includes('Создана ветка')"
    )
    page.wait_for_timeout(2500)
    page.get_by_role("button", name="demo/alt", exact=True).click()
    page.wait_for_function(
        "document.getElementById('panel-title').textContent.includes('demo/alt')"
    )
    page.wait_for_timeout(3000)
    page.get_by_role("button", name="demo", exact=True).click()
    page.wait_for_function(
        "document.getElementById('panel-title').textContent.endsWith('demo')"
    )
    page.wait_for_timeout(2500)

    # 5. Настоящий ход: контрольный вопрос про память.
    question = (
        "Повторная проверка памяти: только факты — название, бюджет, "
        "актуальный срок, языки, что не входит в проект и какой срок отменён."
    )
    page.locator("#question").fill(question)
    page.wait_for_timeout(2500)
    started = time.monotonic()
    page.locator("#send").click()
    page.wait_for_function("!document.getElementById('send').disabled", timeout=300000)
    elapsed = time.monotonic() - started
    details = page.locator("#details").inner_text()
    assert "Ходов: 14" in details, details
    answer = page.locator("#history .message").last.inner_text()
    page.wait_for_timeout(6000)

    # 6. Память после хода и перезагрузка: состояние пережило обновление.
    page.locator("#facts").scroll_into_view_if_needed()
    page.wait_for_timeout(6000)
    facts_text = page.locator("#facts").inner_text()
    page.reload()
    page.wait_for_function(
        "document.getElementById('details').textContent.includes('Ходов: 14')"
    )
    page.wait_for_timeout(5000)
    page.screenshot(path=str(BUILD / "final.png"))

    video = page.video
    context.close()
    raw = video.path()
    browser.close()
    if errors:
        raise RuntimeError(errors)

silent = OUT / "day10-panel-silent.mp4"
subprocess.run(
    [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(raw),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(silent),
    ],
    check=True,
)
fast = OUT / "day10-panel-fast.mp4"
subprocess.run(
    [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(silent),
        "-filter:v",
        "setpts=PTS/1.25",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(fast),
    ],
    check=True,
)

(OUT / "recording-meta.json").write_text(
    json.dumps(
        {
            "live_wait_seconds": round(elapsed, 2),
            "seeded_turns": 13,
            "live_turn": 14,
            "viewport": [1440, 1100],
            "speed_up": 1.25,
            "page_errors": errors,
            "strategy_metrics": measurements,
            "facts_after_turn": facts_text,
            "answer_tail": answer[-400:],
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n"
)
print(fast, flush=True)
