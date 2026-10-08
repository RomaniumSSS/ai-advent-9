"""Запись реального окна браузера во время трёх локальных генераций."""
from pathlib import Path
import subprocess
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'video' / 'live-capture'
OUT.mkdir(exist_ok=False)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1280, 'height': 1000},
                                  record_video_dir=str(OUT),
                                  record_video_size={'width': 1280, 'height': 1000})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8066')
    page.screenshot(path=str(OUT / 'ready.png'))
    page.wait_for_timeout(3500)
    for ident in range(3):
        page.locator(f'button[data-id="{ident}"]').click()
        page.wait_for_function('(id) => window.finished === id || window.failure', arg=ident, timeout=300000)
        if page.evaluate('window.failure') or errors:
            raise RuntimeError(str(errors or page.evaluate('window.failure')))
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / f'answer-{ident+1}.png'), full_page=True)
        print(f'Запрос {ident+1}: '+page.locator('#status').inner_text(), flush=True)
        # Если ответ длиннее кадра, показываем его нижнюю часть реальным скроллом.
        if page.evaluate('document.documentElement.scrollHeight > window.innerHeight'):
            page.wait_for_timeout(5000)
            page.locator('#status').scroll_into_view_if_needed()
        page.wait_for_timeout(7000)
        if ident < 2:
            page.evaluate('window.scrollTo(0, 0)')
    video = page.video
    context.close()
    video.save_as(str(OUT / 'live.webm'))
    browser.close()
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(OUT/'live.webm'),
                '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-an',
                '-movflags', '+faststart', str(ROOT/'video/Day26-live.mp4')], check=True)
print('Готово: day26/video/Day26-live.mp4', flush=True)
