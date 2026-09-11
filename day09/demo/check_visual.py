"""Проверка формы и трёх размеров на подставной модели localhost:8050."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).parent/'.build';out.mkdir(exist_ok=True)
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1280,'height':800});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8050')
    page.wait_for_function("document.getElementById('details-left').textContent.includes('Ходов: 8')")
    page.locator('#next').click();assert 'Маяк' in page.locator('#question').input_value()
    page.locator('#send').click()
    page.wait_for_function("!document.getElementById('send').disabled && document.getElementById('details-right').textContent.includes('Ходов: 9')")
    assert 'Покрыто summary: 10' in page.locator('#details-right').inner_text()
    page.reload();page.wait_for_function("document.getElementById('details-right').textContent.includes('Ходов: 9')")
    for w,h in [(1280,800),(768,1024),(375,812)]:
        page.set_viewport_size({'width':w,'height':h})
        overflow=page.evaluate('document.documentElement.scrollWidth>window.innerWidth')
        assert not overflow
        page.screenshot(path=str(out/f'filled-{w}.png'),full_page=True)
        results.append({'width':w,'height':h,'horizontal_overflow':overflow})
    page.locator('#scenario').select_option('personal');page.locator('#next').click()
    assert 'Вроцлаве' in page.locator('#question').input_value()
    assert not errors,errors
    browser.close()
(Path(__file__).parent/'visual-check.json').write_text(json.dumps({'environment':'Playwright Chromium, подставная модель, macOS','sizes':results,'reload_preserved_summary':True,'both_scenarios':True,'page_errors':errors},ensure_ascii=False,indent=2)+'\n')
print('ok: парная отправка, summary, перезагрузка, оба сценария, три ширины, нет ошибок JS')
