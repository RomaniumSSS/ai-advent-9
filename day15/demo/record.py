"""Записать офлайн-сценарий Дня 15 в браузере."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
VIDEO = Path(__file__).with_name("day15-controlled-transitions.webm")
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8045"
VIEWPORTS = ((1280, 800), (768, 1024), (375, 812))


def overflow(page) -> dict:
    return page.evaluate("""() => ({
      viewport: document.documentElement.clientWidth,
      page: document.documentElement.scrollWidth,
      offenders: [...document.querySelectorAll('body *')]
        .filter((el) => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
        .map((el) => `${el.tagName.toLowerCase()}#${el.id}.${el.className}`).slice(0, 10)
    })""")


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="day15-video-") as video_dir:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=str(CHROME) if CHROME.is_file() else None,
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                record_video_dir=video_dir,
                record_video_size={"width": 1280, "height": 800},
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(URL, wait_until="networkidle")

            checks = []
            for width, height in VIEWPORTS:
                page.set_viewport_size({"width": width, "height": height})
                checks.append(overflow(page))
            page.set_viewport_size({"width": 1280, "height": 800})

            page.locator("#task-objective").fill("Подготовить текстовый план релиза")
            page.locator("#start-task").click()
            page.wait_for_function("document.querySelector('#task-status').textContent === 'active'")
            page.wait_for_timeout(700)
            page.locator("#try-skip").click()
            page.wait_for_function("document.querySelector('#transition-denials').textContent.includes('approve')")
            page.locator("#transition-denials").scroll_into_view_if_needed()
            page.wait_for_timeout(1800)
            page.screenshot(path=RESULTS / "rejected-skip.png", full_page=True)

            page.locator("#workflow-run").click()
            page.wait_for_function("document.querySelector('#workflow-actor').textContent === 'user'")
            page.wait_for_timeout(900)
            page.locator("#workflow-approve").click()
            page.wait_for_function("document.querySelector('#task-status').textContent === 'active' && document.querySelector('#pipeline .active span').textContent === 'validation'")
            page.wait_for_timeout(1800)
            page.screenshot(path=RESULTS / "validation.png", full_page=True)

            page.locator("#pause").click()
            page.wait_for_function("document.querySelector('#task-status').textContent === 'paused'")
            page.wait_for_timeout(1200)
            page.locator("#restart").click()
            page.wait_for_timeout(1000)
            page.locator("#resume").click()
            page.wait_for_function("document.querySelector('#task-status').textContent === 'active'")
            page.wait_for_timeout(1000)
            page.locator("#workflow-approve").click()
            page.wait_for_function("document.querySelector('#pipeline .active span').textContent === 'done'")
            page.wait_for_timeout(1800)
            page.screenshot(path=RESULTS / "done-after-resume.png", full_page=True)

            video = page.video
            context.close()
            shutil.copyfile(video.path(), VIDEO)
            browser.close()

    report = {"video": str(VIDEO.relative_to(ROOT)), "responsive": checks, "page_errors": errors}
    (RESULTS / "browser-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if errors or any(item["page"] > item["viewport"] or item["offenders"] for item in checks):
        raise RuntimeError("ошибки страницы или переполнение: " + json.dumps(report, ensure_ascii=False))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
