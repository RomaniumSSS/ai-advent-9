"""Новый сценарный прогон уже запущенного DevHelper, без воспроизведения фикстур."""
from __future__ import annotations
import argparse
import datetime
import json
import math
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

QUESTIONS = [
    ('/help За что отвечают git_mcp_server.py, mcp_client.py и tool_calling.py в примере Day17?', 'ok'),
    ('/help Какая сейчас Git-ветка?', 'ok'),
    ('/help Какая погода завтра в Барселоне?', 'unknown'),
]


def show_region(page, locator, output, index, section, event, hold):
    """Показать неизменённую область целиком, с перекрытием соседних кадров."""
    bounds=locator.evaluate('(item)=>{const r=item.getBoundingClientRect(); return {top:r.top+scrollY,bottom:r.bottom+scrollY}}')
    height=page.viewport_size['height']
    maximum=page.evaluate('Math.max(0,document.documentElement.scrollHeight-innerHeight)')
    first=min(maximum,max(0,bounds['top']-24))
    last=min(maximum,max(first,bounds['bottom']-height+24))
    positions=[first]
    while positions[-1]<last:
        positions.append(min(last,positions[-1]+height-180))
    for frame,position in enumerate(positions,1):
        page.evaluate('(position)=>window.scrollTo(0,position)',position)
        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        suffix='' if frame==1 else f'-{frame:02d}'
        filename=f'{index:02d}-{section}{suffix}.png'
        page.screenshot(path=str(output/filename))
        event('reading_frame',index=index,section=section,frame=frame,frame_count=len(positions),screenshot=filename,scroll_y=page.evaluate('scrollY'))
        hold(section,index)


def show_mcp(page, output, index, git_context, event, hold):
    """Показать начало вызова и конец того же JSON с branch/head."""
    details=page.locator('#stages .stage').nth(1).locator('details')
    details.evaluate('(item)=>{item.open=true}')
    details.scroll_into_view_if_needed()
    pre=details.locator('pre')
    stage=json.loads(pre.inner_text())
    if stage.get('name')!='mcp' or stage.get('result')!=git_context:
        raise RuntimeError('MCP JSON в UI не совпал с фактическим ответом API')
    for part,scroll in [('call',False),('result',True)]:
        pre.evaluate('(item,bottom)=>{item.scrollTop=bottom?item.scrollHeight:0}',scroll)
        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        visibility=None
        if part=='result':
            # AICODE-NOTE: прокручиваем настоящий text node, не заменяем JSON краткой копией.
            visibility=pre.evaluate(r'''(item)=>Object.fromEntries(['branch','head'].map(key=>{
                const start=item.textContent.indexOf('"'+key+'":');
                if(start<0) return [key,false];
                const newline=item.textContent.indexOf('\n',start);
                const range=document.createRange(); range.setStart(item.firstChild,start);
                range.setEnd(item.firstChild,newline<0?item.textContent.length:newline);
                const r=range.getBoundingClientRect(),box=item.getBoundingClientRect();
                return [key,r.top>=Math.max(0,box.top)&&r.bottom<=Math.min(innerHeight,box.bottom)];
            }))''')
            if not all(visibility.values()):
                raise RuntimeError('result.branch/head не попали в видимую часть MCP JSON')
        filename=f'{index:02d}-mcp.png' if part=='call' else f'{index:02d}-mcp-result.png'
        page.screenshot(path=str(output/filename))
        event('reading_frame',index=index,section='mcp_'+part,screenshot=filename,pre_scroll_top=pre.evaluate('(item)=>item.scrollTop'),visible_result_keys=visibility)
        hold('mcp_'+part,index)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run',action='store_true')
    mode.add_argument('--record',action='store_true')
    parser.add_argument('--url',default='http://127.0.0.1:8071')
    parser.add_argument('--expect-mode',choices=['offline','live'],default='offline',help='live — явный запуск новых платных ответов уже настроенного сервера')
    parser.add_argument('--hold-seconds',type=float,default=6.0,help='Пауза чтения отдельно для ответа, источника и MCP в записи; dry-run не задерживается')
    parser.add_argument('--output',type=Path,required=True,help='Новый, ещё не существующий каталог')
    args=parser.parse_args()
    if not math.isfinite(args.hold_seconds) or not 0 < args.hold_seconds <= 60:
        parser.error('--hold-seconds должен быть конечным числом больше 0 и не больше 60')
    hold_seconds=args.hold_seconds if args.record else 0.0
    url=urlparse(args.url)
    if url.scheme!='http' or url.hostname!='127.0.0.1' or url.path not in ('','/') or url.username or url.password or url.query or url.fragment:
        parser.error('Нужен локальный http://127.0.0.1:<порт> без дополнительных частей')
    output=args.output.expanduser().resolve()
    if output.exists(): parser.error('Каталог результата уже существует: старый прогон не перезаписывается')
    output.mkdir(parents=True)
    journal=output/'events.jsonl'
    def event(name,**data):
        row={'time':datetime.datetime.now(datetime.UTC).isoformat(),'event':name,**data}
        with journal.open('a') as file: file.write(json.dumps(row,ensure_ascii=False)+'\n')
    manifest={'kind':'record' if args.record else 'dry-run','expected_mode':args.expect_mode,'url':args.url,'hold_seconds_requested':args.hold_seconds,'hold_seconds_effective':hold_seconds,'answers':[],'cli':'Проверяется отдельно командой python -m day31.cli; в этой записи только браузер'}
    event('start',kind=manifest['kind'],expected_mode=args.expect_mode)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            options={'viewport':{'width':1280,'height':1000},'device_scale_factor':1}
            if args.record:
                options.update(record_video_dir=str(output/'raw-video'),record_video_size={'width':1280,'height':1000})
            context=browser.new_context(**options)
            page=context.new_page(); video=page.video
            def hold(section,index):
                if hold_seconds:
                    event('reading_hold',index=index,section=section,seconds=hold_seconds)
                    page.wait_for_timeout(hold_seconds*1000)
            page_errors=[]; page.on('pageerror',lambda error:page_errors.append(str(error)))
            try:
                page.goto(args.url,wait_until='networkidle')
                config=page.evaluate("fetch('/api/config').then(r=>r.json())")
                actual='live' if config['live'] else 'offline'
                if actual!=args.expect_mode:
                    raise RuntimeError('Режим сервера не совпал с --expect-mode: ни одного вопроса не отправлено')
                manifest['model']=config['model']; manifest['provider']=config['provider']; manifest['git_root']=config['git_root']
                # Токен CSRF из config не записывается в журнал/manifest.
                event('connected',actual_mode=actual,model=config['model'],provider=config['provider'])
                page.screenshot(path=str(output/'00-start.png'))
                for index,(question,expected) in enumerate(QUESTIONS,1):
                    page.locator('#question').fill(question)
                    page.evaluate('window.scrollTo(0,0)')
                    event('question_started',index=index,question=question)
                    with page.expect_response(lambda r:r.url.endswith('/api/answer') and r.request.method=='POST',timeout=180000) as response_info:
                        page.locator('#send').click()
                    response=response_info.value
                    if response.status!=200: raise RuntimeError('API вернул ошибку HTTP')
                    value=response.json()
                    page.locator('#response[aria-busy="false"]').wait_for(timeout=10000)
                    (output/f'{index:02d}-answer.json').write_text(json.dumps(value,ensure_ascii=False,indent=2))
                    manifest['answers'].append({'index':index,'trace_id':value['trace_id'],'status':value['status'],'expected':expected,'elapsed_seconds':value['elapsed_seconds'],'usage':value['usage']})
                    event('question_finished',index=index,trace_id=value['trace_id'],status=value['status'],elapsed_seconds=value['elapsed_seconds'],usage=value['usage'])
                    if value['status']!=expected: raise RuntimeError(f'Ответ {index}: ожидался статус {expected}, получен {value["status"]}')
                    if page.locator('#answer').text_content()!=value['text']:
                        raise RuntimeError('UI изменил текст фактического ответа')
                    show_region(page,page.locator('#response'),output,index,'answer',event,hold)
                    if value['source_ids']:
                        page.locator('#citations a').first.click()
                        show_region(page,page.locator('#sources details[open]').first,output,index,'source',event,hold)
                    show_mcp(page,output,index,value['git_context'],event,hold)
                if len({answer['trace_id'] for answer in manifest['answers']})!=len(QUESTIONS):
                    raise RuntimeError('Повторён trace_id: новый запуск не доказан')
                if page_errors: raise RuntimeError('Браузер сообщил ошибку JavaScript')
                manifest['status']='complete'
                event('scenario_complete',answer_count=len(manifest['answers']),page_errors=0)
            finally:
                context.close(); browser.close()
            if args.record and video:
                raw=video.path()
                mp4=output/('Day31-live.mp4' if args.expect_mode=='live' else 'Day31-offline.mp4')
                converted=subprocess.run(['ffmpeg','-n','-i',raw,'-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(mp4)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                if converted.returncode: raise RuntimeError('ffmpeg не смог преобразовать новую запись; raw сохранён')
                probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,r_frame_rate','-of','json',str(mp4)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                metadata=json.loads(probe.stdout)
                (output/'ffprobe.json').write_text(json.dumps(metadata,indent=2))
                manifest['video']=str(mp4); manifest['raw_video']=raw; manifest['ffprobe']=metadata
                event('video_converted',video=str(mp4),ffprobe=metadata)
    except Exception as error:
        manifest['status']='failed'; manifest['error']=str(error)
        event('failed',reason=str(error))
        raise
    finally:
        (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
