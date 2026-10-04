"""Offline Chromium check of the actual structured DOM renderer; no API/provider."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'private/structured-runtime-ui'
OUTPUT.mkdir(parents=True,exist_ok=True)
script=(ROOT/'app/app.js').read_text().split("$('new-chat').onsubmit",1)[0]
unsafe='<img src=x onerror=window.pwned=1><script>window.pwned=1</script>'
metadata={'day':22,'message_id':4154,'source':'discussion','chunk_id':'synthetic','author':unsafe,'date':'2026-10-01'}
item={'version':'day25-chat-v3','status':'verified','structured_evidence':{'attributions':[metadata],
      'comparison':[{'aspect':unsafe,'requirement':{'metadata':dict(metadata,source='assignment',day=24),'quote':unsafe},
      'discussion':{'metadata':metadata,'quote':'Synthetic quote'},'relationship':'supplements','analysis':unsafe}]}}
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page()
    page.route('**/*',lambda route:route.abort())
    page.set_content('<html lang="ru"><head><meta charset="utf-8"></head><body><main id="out"></main></body></html>')
    page.add_style_tag(content=(ROOT/'app/style.css').read_text())
    page.add_script_tag(content=script)
    page.evaluate('(item)=>renderStructured(document.getElementById("out"),item)',item)
    assert page.locator('#out img, #out script').count()==0
    assert page.evaluate('window.pwned === undefined')
    assert 'message_id: 4154' in page.locator('#out').inner_text()
    for name,width,height in [('desktop',1280,900),('mobile',390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        page.locator('details').evaluate_all('(xs)=>xs.forEach(x=>x.open=true)')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(OUTPUT/(name+'.png')),full_page=True)
    item['status']='insufficient_context'
    item['structured_evidence']['comparison']=[{'status':'insufficient_context','aspect':'Synthetic unavailable side',
        'reason':'No discussion evidence','missing_sides':['discussion'],'available_evidence':[]}]
    page.evaluate('(item)=>{out.replaceChildren();renderStructured(out,item)}',item)
    assert 'сравнение не завершено' in page.locator('#out').inner_text()
    browser.close()
(OUTPUT/'report.json').write_text(json.dumps({'result':'PASS','viewports':[1280,390],'unsafe_dom_nodes':0,
    'provider_calls':0,'http_requests':0,'scope':'isolated actual renderer; HTTP integration tested separately'},indent=2))
print('Structured renderer: desktop/mobile PASS; provider/API requests 0')
