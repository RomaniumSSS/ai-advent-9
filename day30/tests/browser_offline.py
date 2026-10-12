"""Playwright проверка UI с явной mock моделью, без Ollama и без live evidence."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,service

class Mock:
    def answer(self,q,turns,scope='all',phase=None):
        for p in ('embedding','selection','synthesis'):
            if phase:phase(p)
        return {'status':'done','answer':{'summary':'Нужно создать индекс документов и проверить поиск. Метаданные помогают показать источник ответа.',
            'conclusion':'Вывод: сначала проверьте происхождение и целостность каждого фрагмента.',
            'sources':[{'evidence_id':'S1.U1','chunk_id':'mock-c1','source':'assignment','author':None,'date':None,
                        'attribution':'unknown','text':'Это mock original: создайте индекс документов.\n<img src=x onerror="window.injected=true">'}]},
            'metrics':{'generation_calls':2,'embedding_calls':1,'embedding_seconds':0.1,'selection':{'elapsed_seconds':0.2,'prompt_eval_count':500,'eval_count':40},
                       'synthesis':{'elapsed_seconds':0.3,'prompt_eval_count':600,'eval_count':90},'total_seconds':0.6}}

async def run():
    from playwright.async_api import async_playwright
    output=Path(__file__).resolve().parents[1]/'results';events=[]
    with tempfile.TemporaryDirectory() as d:
        app=server.Application(Mock(),service.Store(Path(d)/'state'),'preview-only',scope='assignment')
        http=server.make_server('127.0.0.1',0,app);port=http.server_address[1];app.hosts={f'127.0.0.1:{port}'};app.origins={f'http://127.0.0.1:{port}'}
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            async with async_playwright() as p:
                browser=await p.chromium.launch();context=await browser.new_context(viewport={'width':1280,'height':800});page=await context.new_page()
                page.on('pageerror',lambda e:events.append(str(e)))
                await page.goto(f'http://127.0.0.1:{port}');await page.locator('#token').fill('preview-only');await page.locator('#connect').click()
                await page.locator('#chat').wait_for(state='visible');await page.locator('#question').fill('Что требуется при создании индекса документов?');await page.locator('#send').click()
                await page.wait_for_selector('.turn[data-status="done"]');await page.locator('details summary').first.click()
                assert await page.locator('.original img').count()==0
                assert await page.evaluate('window.injected === undefined')
                assert await page.locator('#token').input_value()==''
                assert await page.locator('.source-id').inner_text()=='S1.U1'
                assert 'только открытые' in await page.locator('#scope').inner_text()
                for name,width,height in [('desktop',1280,800),('tablet',768,1024),('mobile',375,812)]:
                    await page.set_viewport_size({'width':width,'height':height});await page.screenshot(path=str(output/f'ui-mock-{name}.png'),full_page=True)
                    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),name
                await page.locator('#new-conversation').click();assert await page.locator('.turn').count()==0
                assert not events,events
                await context.close();await browser.close()
        finally:http.shutdown();http.server_close();thread.join();app.wait_workers()
    (output/'browser-offline.json').write_text(json.dumps({'result':'PASS','provider':'mock','layouts':['desktop1280x800','tablet768x1024','mobile375x812'],
        'checks':['login token cleared','assignment label','actual mock HTTP receipt','safe textContent hostile source','no horizontal overflow','new conversation','no browser errors']},indent=2)+'\n')
    print('browser mock PASS')
if __name__=='__main__':asyncio.run(run())
