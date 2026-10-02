"""Запись реального браузера: SSH-поиск и просмотр сохранённых ответов."""
import json,os,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent
BUILD=HERE/'frames';BUILD.mkdir(exist_ok=True)
question=json.loads((HERE.parent/'questions.json').read_text())['cases'][0]['question']
with sync_playwright() as p:
 options={'headless':True}
 if os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'):
  options['executable_path']=os.environ['PLAYWRIGHT_CHROMIUM_EXECUTABLE']
 browser=p.chromium.launch(**options)
 context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(BUILD),record_video_size={'width':1440,'height':1000})
 page=context.new_page();page.goto('http://127.0.0.1:8052')
 page.get_by_role('button',name='Код поиска',exact=True).click();page.wait_for_timeout(7000)
 page.screenshot(path=str(BUILD/'live-code.png'))
 page.get_by_role('button',name='К вопросу',exact=True).click()
 page.get_by_role('textbox',name='Вопрос',exact=True).press_sequentially(question,delay=35)
 page.wait_for_timeout(1200);page.get_by_role('button',name='Запустить поиск на VPS',exact=True).click()
 page.wait_for_function("document.getElementById('status').textContent.includes('Поиск завершён')",timeout=180000)
 page.wait_for_timeout(3500);page.screenshot(path=str(BUILD/'live-search.png'))
 page.locator('#source summary').click();page.locator('#source').scroll_into_view_if_needed();page.wait_for_timeout(9000)
 page.screenshot(path=str(BUILD/'live-source.png'));page.locator('#source summary').click()
 page.get_by_role('button',name='Без RAG',exact=True).click();page.wait_for_timeout(8000);page.screenshot(path=str(BUILD/'live-plain.png'))
 page.get_by_role('button',name='С RAG',exact=True).click();page.wait_for_timeout(13000);page.screenshot(path=str(BUILD/'live-rag.png'))
 page.get_by_role('button',name='Итоги 10 вопросов',exact=True).click();page.wait_for_timeout(8000);page.screenshot(path=str(BUILD/'live-totals.png'))
 video=page.video;context.close();video.save_as(str(BUILD/'live-browser.webm'));browser.close()
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(BUILD/'live-browser.webm'),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(HERE/'Day22-practical.mp4')],check=True)
print('recorded actual browser, live search + saved provider answers, no audio')
