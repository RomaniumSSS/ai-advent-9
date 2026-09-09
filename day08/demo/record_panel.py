"""Немая запись настоящей панели и исходного кода через Playwright.

Сначала запустите serve_recording.py. Нужны Playwright Chromium и ffmpeg.
"""
import html
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
BUILD=OUT/'.build-panel'
BUILD.mkdir(exist_ok=True)
sections=[]
for filename, start, end in [('agent.py','        usage = getattr(response, "usage", None)',None),
                              ('store.py','    def stats(', '    def growth('),
                              ('agent.py','        budget = self.budget(question)', '    def _refuse(')]:
    source=(ROOT/filename).read_text()
    a=source.index(start);b=source.index(end,a) if end else len(source)
    number=source[:a].count('\n')+1
    lines='\n'.join(f'{number+i:>3}  {line}' for i,line in enumerate(source[a:b].rstrip().splitlines()))
    sections.append((filename,lines))
viewer=BUILD/'code.html'
viewer.write_text('''<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#0f1216;color:#d7dee7;font:20px Menlo,monospace}nav{position:sticky;top:0;background:#161b22;padding:20px;border-bottom:1px solid #303945}button{font:20px Menlo;padding:10px 24px;background:#223449;color:#b3d9ff;border:0;margin-right:12px;cursor:pointer}pre{font:19px/1.65 Menlo,monospace;white-space:pre-wrap;padding:15px 28px}h2{font:20px Menlo;color:#80c5ed;padding:0 28px}section{display:none}section:first-of-type{display:block}</style><nav>day08/ &nbsp;'''+''.join(f'<button onclick="show({i})">{html.escape(name)} · {i+1}</button>' for i,(name,_) in enumerate(sections))+'</nav>'+''.join(f'<section id="s{i}"><h2>{name} — исходный код</h2><pre>{html.escape(code)}</pre></section>' for i,(name,code) in enumerate(sections))+'''<script>function show(i){document.querySelectorAll('section').forEach((s,j)=>s.style.display=i===j?'block':'none');window.scrollTo(0,0)}</script>''')
records=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(BUILD),record_video_size={'width':1440,'height':1000})
    page=context.new_page()
    page.on('pageerror',lambda err: print('PAGE ERROR:',str(err),flush=True))
    page.goto(viewer.as_uri())
    page.wait_for_timeout(8000)
    page.get_by_role('button',name='store.py · 2').click()
    page.wait_for_timeout(8000)
    page.goto('http://127.0.0.1:8048')
    page.locator('[data-panel="left"] .send-btn').wait_for()
    page.screenshot(path=str(BUILD/'panel-start.png'))
    page.wait_for_timeout(4000)
    def ask(side, question, paste=False):
        panel=page.locator(f'[data-panel="{side}"]')
        field=panel.locator('.text')
        field.click()
        if paste:
            field.fill(question)
        else:
            field.press_sequentially(question,delay=55)
        page.wait_for_timeout(1500)
        with page.expect_response(lambda r:r.url.endswith('/api/chat'),timeout=180000) as pending:
            panel.locator('.send-btn').click()
        data=pending.value.json()
        records.append(data)
        (OUT/'panel-recording-results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
        panel.locator('.log').evaluate('(el)=>el.scrollTop=el.scrollHeight')
        print(f"{side}: tokens={data['prompt_tokens']} total={data['usage_summary']['prompt_tokens']} overflow={data['overflow']}",flush=True)
        if not data['overflow']:
            assert not data['error'] and not data['empty'], data['debug']
        page.wait_for_timeout(7000)
        return data
    ask('left','Меня зовут Роман. Код проекта СЕВЕР-824. Запомни.')
    ask('left','Как меня зовут и какой код проекта?')
    notes='Агент отправляет историю вместе с новым вопросом. API сообщает входные и выходные токены. Расход суммируется за каждый вызов. '
    ask('left','Сохрани заметки для проекта:\n'+notes*12+'\nПодтверди одним предложением.',paste=True)
    ask('left','Что происходит с расходом токенов, когда история растёт?')
    page.screenshot(path=str(BUILD/'panel-growth.png'))
    refused=ask('right','Большой текст для проверки локальной защиты:\n'+' x'*6500,paste=True)
    assert refused['overflow'] and refused['usage_summary']['calls']==0
    page.screenshot(path=str(BUILD/'panel-overflow.png'))
    page.reload()
    page.locator('[data-panel="left"] .usage').wait_for()
    assert str(records[-2]['usage_summary']['prompt_tokens']) in page.locator('[data-panel="left"] .usage').inner_text()
    page.locator('[data-panel="left"] .log').evaluate('(el)=>el.scrollTop=el.scrollHeight')
    page.wait_for_timeout(6500)
    page.goto(viewer.as_uri())
    page.get_by_role('button',name='agent.py · 3').click()
    page.wait_for_timeout(9000)
    video=page.video
    context.close()
    source_video=video.path()
    browser.close()
output=OUT/'day08-panel-silent.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source_video),'-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],check=True)
print(output,flush=True)
