"""Записать обзор сохранённых доказательств реального cron-запуска Day 18."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


HERE = Path(__file__).resolve().parent
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
VIDEO = HERE / "day18-scheduled-agent.mp4"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="day18-video-") as directory:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=str(CHROME) if CHROME.is_file() else None,
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                record_video_dir=directory,
                record_video_size={"width": 1440, "height": 900},
                device_scale_factor=1,
            )
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(HERE.joinpath("evidence.html").as_uri())
            for number, seconds in ((1, 5), (2, 6), (3, 6), (4, 6)):
                page.evaluate("n => { document.querySelectorAll('.slide').forEach(s => s.classList.remove('active')); document.querySelector('#s' + n).classList.add('active'); }", number)
                page.wait_for_timeout(seconds * 1000)
            raw_video = page.video
            context.close()
            browser.close()
            if errors:
                raise RuntimeError("page errors: " + json.dumps(errors))
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", raw_video.path(),
                 "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", "-an", str(VIDEO)],
                check=True,
            )
            print(json.dumps({"video": str(VIDEO), "page_errors": errors}))


if __name__ == "__main__":
    main()
