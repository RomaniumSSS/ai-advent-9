"""Запись обычного HTTP-приложения: настоящие вопросы, поиск и генерация.

Использовать только сервер --public-only и действующий общий бюджет.
Без подмены HTTP/DOM, сценарные паузы нужны для чтения. Raw видео и ответы private.
"""
import argparse
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url',default='http://127.0.0.1:8052')
    p.add_argument('--output',default='day24/private/interface-video')
    p.add_argument('--operate',action='store_true')
    args=p.parse_args()
    if not args.operate: raise SystemExit('Нужен --operate: сценарий отправляет реальные запросы в общий бюджет.')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True,mode=0o700)
    if (out/'events.json').exists(): raise SystemExit('Запись уже начата: используйте сохранённое видео; повтор автоматически запрещён.')
    events=[]
    def save(): (out/'events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(out),record_video_size={'width':1440,'height':1000},reduced_motion='reduce')
        page=ctx.new_page()
        try:
            page.goto(args.url,wait_until='networkidle')
            state=page.request.get(args.url+'/api/state').json()
            if not state.get('public_only'): raise RuntimeError('Нужен подтверждённый публичный режим сервера.')
            events.append({'event':'start','at':time.time(),'url':args.url});save()
            page.screenshot(path=str(out/'00-start.png'))
            page.wait_for_timeout(5000)
            cases=[
                ('prepared','Какие требования у задания дня 18?'),
                ('free','В задании 18 хочу сделать напоминалку. Что она должна сохранять и возвращать?'),
                ('semantic','Какой инструмент выполняется по расписанию и возвращает агрегированный результат?'),
                ('outside','Какая температура нужна для выпечки яблочного штруделя?'),
            ]
            first_id=None
            for index,(kind,question) in enumerate(cases,1):
                page.locator('#question').scroll_into_view_if_needed()
                if kind=='prepared':
                    page.get_by_role('button',name=question,exact=True).click()
                else:
                    page.locator('#question').fill('')
                    page.locator('#question').press_sequentially(question,delay=35)
                page.wait_for_timeout(1800)
                started=time.time()
                with page.expect_response(lambda r:r.url.endswith('/api/ask') and r.request.method=='POST',timeout=360000) as response:
                    page.locator('#send').click()
                result=response.value.json()
                if response.value.status!=200:raise RuntimeError('HTTP '+str(response.value.status))
                selected=result.get('search',{}).get('trace',{}).get('selected',[])
                if result.get('scope')!='public' or any(c['document_id']!='assignment:18' for c in selected):raise RuntimeError('Нарушение публичной области')
                (out/f'{index:02d}-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
                events.append({'event':'answer','kind':kind,'id':result['id'],'question':question,'status':result['status'],'started':started,'finished':time.time(),'cost':result.get('cost')});save()
                if first_id is None:first_id=result['id']
                page.locator('#result').scroll_into_view_if_needed()
                page.wait_for_timeout(9000)
                page.screenshot(path=str(out/f'{index:02d}-answer.png'))
                if index in (1,3) and selected:
                    sources=page.locator('#result > details').filter(has=page.locator('summary')).first
                    sources.locator(':scope > summary').click()
                    nested=sources.locator(':scope > details').first
                    nested.locator(':scope > summary').click()
                    nested.scroll_into_view_if_needed();page.wait_for_timeout(9000)
                    page.screenshot(path=str(out/f'{index:02d}-source.png'))
                if index in (3,4):
                    diag=page.get_by_text('Диагностика поиска и ответа',exact=True)
                    diag.click();diag.scroll_into_view_if_needed();page.wait_for_timeout(7000)
                    page.screenshot(path=str(out/f'{index:02d}-diagnostics.png'))
            page.reload(wait_until='networkidle');page.wait_for_timeout(2000)
            page.get_by_role('button',name=cases[0][1],exact=True).last.click()
            page.locator('#result').scroll_into_view_if_needed();page.wait_for_timeout(6000)
            page.screenshot(path=str(out/'05-history.png'))
            events.append({'event':'end','at':time.time()});save()
        finally:
            video=page.video;ctx.close();video.save_as(str(out/'raw.webm'));browser.close()
    print(json.dumps({'recorded':str(out/'raw.webm'),'queries':len([e for e in events if e['event']=='answer'])}))

if __name__=='__main__':main()
