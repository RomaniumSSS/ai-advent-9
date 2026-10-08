"""Немая запись браузера: запуск SSH-поиска и двух реальных платных ответов."""
import argparse
import json
import urllib.request
import os
from pathlib import Path
import subprocess
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent
QUESTION='Что нужно сдать в Day21?'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--operate',action='store_true')
    parser.add_argument('--private-preview',action='store_true')
    parser.add_argument('--output-dir')
    args=parser.parse_args()
    if not args.operate:
        raise SystemExit('Съёмка запускает внешние операции; оператор должен явно задать --operate.')
    with urllib.request.urlopen('http://127.0.0.1:8053/state',timeout=5) as response:
        state=json.load(response)
    if state.get('private_preview') != args.private_preview:
        raise SystemExit('Режим private-preview сервера и записи должен совпадать.')
    directory=Path(args.output_dir).resolve() if args.output_dir else (HERE.parent/'private/video-review' if args.private_preview else HERE)
    if args.private_preview and not directory.is_relative_to((HERE.parent/'private').resolve()):
        raise SystemExit('Private preview можно записывать только в day23/private/.')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    if args.private_preview:directory.chmod(0o700)
    build=directory/'frames';build.mkdir(exist_ok=True,mode=0o700)
    with sync_playwright() as p:
        options={'headless':True}
        if os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'):
            options['executable_path']=os.environ['PLAYWRIGHT_CHROMIUM_EXECUTABLE']
        browser=p.chromium.launch(**options)
        context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(build),record_video_size={'width':1440,'height':1000})
        page=context.new_page();page.goto('http://127.0.0.1:8053')
        page.get_by_role('textbox',name='Вопрос',exact=True).press_sequentially(QUESTION,delay=65)
        page.wait_for_timeout(1500)
        page.get_by_role('button',name='Запустить поиск на VPS',exact=True).click()
        page.wait_for_function("document.getElementById('status').textContent.includes('Поиск завершён') || document.getElementById('status').textContent.includes('Остановка')",timeout=650000)
        if 'Остановка' in page.locator('#status').inner_text():raise RuntimeError('search_failed')
        page.locator('#retrieval').scroll_into_view_if_needed();page.wait_for_timeout(6500)
        page.screenshot(path=str(build/'live-selection.png'))
        page.get_by_text('Текст найденного условия Day21',exact=True).click();page.locator('#source').scroll_into_view_if_needed();page.wait_for_timeout(6000)
        page.screenshot(path=str(build/'live-assignment.png'))
        page.get_by_text('Текст найденного условия Day21',exact=True).click()
        page.get_by_role('button',name='Получить два новых ответа A/E',exact=True).click()
        page.wait_for_function("document.getElementById('status').textContent.includes('Ответы получены') || document.getElementById('status').textContent.includes('Остановка')",timeout=650000)
        if 'Остановка' in page.locator('#status').inner_text():raise RuntimeError('answers_failed')
        page.locator('#answers').scroll_into_view_if_needed();page.wait_for_timeout(14000)
        page.screenshot(path=str(build/'live-answers.png'))
        video=page.video;context.close();video.save_as(str(build/'live-browser.webm'));browser.close()
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(build/'live-browser.webm'),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(directory/'Day23-practical.mp4')],check=True)
    if args.private_preview:
        for artifact in directory.rglob('*'):
            artifact.chmod(0o700 if artifact.is_dir() else 0o600)
    print('recorded browser: live search and provider answers, no audio; review before publication')

if __name__=='__main__':main()
