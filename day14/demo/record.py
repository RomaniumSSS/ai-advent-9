"""Снять офлайн-демонстрацию и responsive screenshots дня 14."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
VIDEO = Path(__file__).with_name("day14-invariants.webm")
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8044"
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
    with tempfile.TemporaryDirectory(prefix="day14-video-") as video_dir:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
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
                page.screenshot(path=RESULTS / f"viewport-{width}.png", full_page=True)
                checks.append(overflow(page))

            page.set_viewport_size({"width": 1280, "height": 800})
            page.locator("#invariants").scroll_into_view_if_needed()
            page.wait_for_timeout(1200)
            page.locator("#test-conflict").click()
            page.wait_for_function("document.querySelector('#status').textContent.includes('ОТКАЗ')")
            page.wait_for_timeout(2200)
            page.screenshot(path=RESULTS / "conflict-refusal.png", full_page=True)

            page.locator("#question").fill("Почему нельзя перейти с SQLite на PostgreSQL?")
            page.locator("#chat-form button[type=submit]").click()
            page.wait_for_function(
                "document.querySelector('#history').textContent.includes('не требует нарушать')"
            )
            page.locator("#history").scroll_into_view_if_needed()
            page.wait_for_timeout(2200)
            page.screenshot(path=RESULTS / "safe-explanation.png", full_page=True)

            page.locator("#task-objective").fill("Подготовить безопасный релиз в рамках инвариантов")
            page.locator("#start-task").click()
            page.locator("#task-state").scroll_into_view_if_needed()
            page.wait_for_timeout(1200)
            page.locator("#pause").click()
            page.wait_for_timeout(900)
            page.locator("#restart").click()
            page.wait_for_timeout(900)
            page.locator("#resume").click()
            page.wait_for_timeout(1800)
            page.screenshot(path=RESULTS / "fsm-resumed.png", full_page=True)

            video = page.video
            context.close()
            shutil.copyfile(video.path(), VIDEO)
            browser.close()

    if errors:
        raise RuntimeError("Ошибки страницы: " + "; ".join(errors))
    if any(item["page"] > item["viewport"] or item["offenders"] for item in checks):
        raise RuntimeError("Горизонтальное переполнение: " + json.dumps(checks, ensure_ascii=False))
    print(json.dumps({"video": str(VIDEO), "responsive": checks, "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
