"""Визуальный офлайн-прогон на собственном ephemeral HTTP fixture."""
import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
from contextlib import nullcontext
from unittest.mock import patch
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Application, handler_for
from core import Engine
import core
from test_core import Fake, chunk

def run(output):
    output.mkdir(parents=True,exist_ok=False)
    errors=[];checks=[]
    with patch.object(core,'generation_lock',return_value=nullcontext()),tempfile.TemporaryDirectory() as receipts:
        fake=Fake();app=Application(Engine([chunk(),chunk('b',day=19,text='👉 Обработка.\n  Сохранение результата.'),
            chunk('private','discussion')],{},fake),receipts)
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(app));app.port=server.server_port
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(app.port)
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True)
                try:
                    for name,width,height in [('desktop',1280,1000),('tablet',768,1024),('mobile',375,812)]:
                        context=browser.new_context(viewport={'width':width,'height':height})
                        try:
                            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url)
                            page.wait_for_function("() => document.querySelector('#identity').textContent.includes('8192')")
                            page.locator('#question').fill('Что требуется сделать в задании дня 18?')
                            page.locator('#send').click()
                            page.wait_for_function("() => document.querySelector('#result').dataset.state==='done'")
                            assert page.locator('#answer').inner_text()=='Поиск.'
                            assert page.locator('#sources blockquote').text_content()=='Нужно сделать поиск.'
                            assert 'discussion' not in page.locator('body').inner_text()
                            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                            assert page.locator('#result').get_attribute('data-request-id')
                            page.locator('#sources details').evaluate('e=>e.open=true')
                            page.screenshot(path=str(output/(name+'.png')),full_page=True)
                            checks.append({'viewport':name,'width':width,'height':height,'status':'pass'})
                        finally:context.close()
                    context=browser.new_context(viewport={'width':1280,'height':1000})
                    try:
                        page=context.new_page();page.goto(url)
                        fake.response['message']['content']=json.dumps({'answer':'Поиск и обработка.','source_refs':['S1','S2']})
                        page.locator('#question').fill('Чем отличаются задания дней 18 и 19?');page.locator('#send').click()
                        page.wait_for_function("() => document.querySelector('#result').dataset.state==='done'")
                        assert page.locator('#sources .source').count()==2
                        assert 'приложение показывает их оригинальный текст' in page.locator('#metrics').inner_text()
                        for source in page.locator('#sources .source').all():
                            source.locator('details').evaluate('e=>e.open=true');source.scroll_into_view_if_needed()
                        assert '\n' in page.locator('#sources blockquote').nth(1).text_content()
                        page.screenshot(path=str(output/'two-sources.png'),full_page=True)
                        checks.append({'case':'two_model_selected_original_sources','status':'pass'})
                    finally:context.close()
                    context=browser.new_context()
                    try:
                        page=context.new_page();page.goto(url);fake.response['done_reason']='length'
                        page.locator('#question').fill('Задание дня 18');page.locator('#send').click()
                        page.wait_for_function("() => document.querySelector('#result').dataset.state==='error'")
                        assert 'incomplete' in page.locator('#answer').inner_text()
                        checks.append({'case':'incomplete_answer_visible','status':'pass'})
                    finally:context.close()
                finally:browser.close()
        finally:server.shutdown();server.server_close();thread.join()
    if errors:raise RuntimeError(str(errors))
    result={'environment':'offline fixture; cached uv Playwright/Chromium; Mac','real_model':False,
            'checks':checks,'page_errors':errors,'status':'pass'}
    (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
