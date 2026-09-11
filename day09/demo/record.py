"""Немая запись исходного кода и настоящей панели. Запустить serve_recording.py."""
import html
import json
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
BUILD=OUT/'.build';BUILD.mkdir(exist_ok=True)
sections=[]
source=(ROOT/'agent.py').read_text()
for title,start,end in [('Настройки','class CompressionConfig:','    def __post_init__'),
                        ('Контекст','    def context_history','    def budget'),
                        ('Сжатие','    def compact','        output_limit =')]:
    a=source.index(start);b=source.index(end,a)
    lines=source[a:b].rstrip();number=source[:a].count('\n')+1
    code='\n'.join(f'{number+i:>3}  {line}' for i,line in enumerate(lines.splitlines()))
    sections.append((title,code))
viewer=BUILD/'code.html'
viewer.write_text('''<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#14201d;color:#e0e9e3;font:20px/1.7 Menlo,monospace}
nav{padding:22px;background:#1e3028}button{font:18px Menlo;background:#304c3b;color:#fff;border:0;padding:12px 18px;margin-right:12px;border-radius:6px}pre{padding:30px;white-space:pre-wrap;font-size:18px}section{display:none}section:first-of-type{display:block}</style><nav>day09/agent.py &nbsp;'''+''.join(f'<button onclick="show({i})">{title}</button>' for i,(title,_) in enumerate(sections))+'</nav>'+''.join(f'<section><pre>{html.escape(code)}</pre></section>' for _,code in sections)+'''<script>function show(i){document.querySelectorAll('section').forEach((el,j)=>el.style.display=i===j?'block':'none')}</script>''')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1100},record_video_dir=str(BUILD),record_video_size={'width':1440,'height':1100})
    page=context.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(viewer.as_uri());page.wait_for_timeout(7000)
    page.get_by_role('button',name='Контекст',exact=True).click();page.wait_for_timeout(7000)
    page.get_by_role('button',name='Сжатие',exact=True).click();page.wait_for_timeout(7000)
    page.goto('http://127.0.0.1:8049');page.wait_for_function("document.getElementById('details-left').textContent.includes('Ходов: 8')")
    page.screenshot(path=str(BUILD/'before.png'));page.wait_for_timeout(6000)
    question='Контроль памяти: назови проект, бюджет, актуальный срок, языки и исключённую функцию. Не добавляй новых условий.'
    page.locator('#question').fill(question);page.wait_for_timeout(3000)
    started=time.monotonic()
    page.locator('#send').click()
    page.wait_for_function("!document.getElementById('send').disabled",timeout=300000)
    assert 'Ходов: 9' in page.locator('#details-left').inner_text()
    assert 'Ходов: 9' in page.locator('#details-right').inner_text()
    assert 'Покрыто summary: 10' in page.locator('#details-right').inner_text()
    elapsed=time.monotonic()-started
    page.screenshot(path=str(BUILD/'after.png'));page.wait_for_timeout(16000)
    page.reload();page.wait_for_function("document.getElementById('details-right').textContent.includes('Покрыто summary: 10')")
    page.locator('#memory-right').scroll_into_view_if_needed();page.wait_for_timeout(10000)
    page.screenshot(path=str(BUILD/'restored.png'))
    video=page.video;context.close();raw=video.path();browser.close()
    if errors:raise RuntimeError(errors)
output=OUT/'day09-panel-silent.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(raw),'-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],check=True)
(OUT/'recording-meta.json').write_text(json.dumps({'live_wait_seconds':elapsed,'source_report':json.loads((OUT/'recording-source.json').read_text())['source_report'],'seeded_turns':8,'live_turn':9,'viewport':[1440,1100],'page_errors':errors},indent=2)+'\n')
print(output,flush=True)
