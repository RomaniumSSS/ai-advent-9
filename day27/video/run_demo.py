"""Один живой сценарий для сухого прогона и записи; фикстуры не подменяют модель."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import uuid

QUESTIONS = [
    'Наш учебный проект называется „Маяк“. Предложи три коротких шага создания локального чат-приложения. Ответь по-русски, до 60 слов.',
    'Как называется наш учебный проект? Ответь только названием.',
    'Сколько будет 17 + 25? Ответь только числом.',
]

def run(args):
    from playwright.sync_api import sync_playwright
    output = Path(args.output) if args.output else Path(__file__).parent / 'runs' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    results = {'mode':'record' if args.record else 'dry-run','started_at':datetime.now(timezone.utc).isoformat(),
               'url':args.url,'requests':[],'page_errors':[],'status':'running'}
    video = None
    print(f'Каталог прогона: {output.resolve()}', flush=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = None
            try:
                options = {'viewport':{'width':1280,'height':1000}}
                if args.record:
                    options.update(record_video_dir=str(output/'raw'), record_video_size={'width':1280,'height':1000})
                context = browser.new_context(**options)
                page = context.new_page()
                page.on('pageerror', lambda error: results['page_errors'].append(str(error)))
                def capture_request(request):
                    if request.url.endswith('/api/chat') and request.method == 'POST':
                        results['requests'].append({'request_id':len(results['requests'])+1,
                            'started_at':datetime.now(timezone.utc).isoformat(),
                            'payload':json.loads(request.post_data), 'status':'running'})
                page.on('request', capture_request)
                page.goto(args.url)
                page.wait_for_function("document.querySelector('#connection').textContent !== 'Проверяем модель…'")
                if not page.locator('#connection-dot.ready').count():
                    raise RuntimeError(page.locator('#connection').inner_text())
                page.screenshot(path=str(output/'ready.png'))
                if args.record: page.wait_for_timeout(2500)
                for index, question in enumerate(QUESTIONS):
                    if index == 2:
                        page.locator('#new-chat').click()
                        if page.locator('.message').count(): raise RuntimeError('История не очищена')
                        if args.record: page.wait_for_timeout(2000)
                    page.locator('#prompt').fill(question)
                    started = time.monotonic()
                    page.locator('#send').click()
                    ident = index+1
                    page.wait_for_function("id => {const e=document.querySelector(`[data-request-id=\"${id}\"]`); return e && ['done','error'].includes(e.dataset.state)}", arg=ident, timeout=330000)
                    article = page.locator(f'[data-request-id="{ident}"]')
                    result = results['requests'][-1]
                    result.update(request_id=int(article.get_attribute('data-request-id')),
                        elapsed_seconds=time.monotonic()-started,
                        actual_output=article.locator('.text').inner_text(),
                        status=article.get_attribute('data-state'),
                        visible_status=article.locator('.meta').inner_text(),
                        metrics=json.loads(article.get_attribute('data-metrics') or 'null'))
                    result['quality'] = ('requires_human_review' if index == 0 else
                        ('pass' if (('Маяк' in result['actual_output']) if index == 1 else result['actual_output'].strip() == '42') else 'fail'))
                    page.screenshot(path=str(output/f'answer-{ident}.png'))
                    if result['status'] != 'done': raise RuntimeError(result['visible_status'])
                    if results['page_errors']: raise RuntimeError(str(results['page_errors']))
                    expected_length = 3 if index == 1 else 1
                    if len(result['payload']['messages']) != expected_length: raise RuntimeError('Неверная длина контекста')
                    if index == 1 and result['payload']['messages'][1]['content'] != results['requests'][0]['actual_output']:
                        raise RuntimeError('Контекст не содержит настоящий первый ответ')
                    if args.record: page.wait_for_timeout(7000)
                    print(f'Запрос {ident}: {result["visible_status"]}', flush=True)
                results['status'] = 'completed'
                video = page.video
            finally:
                if context is not None:
                    if video is None and args.record and context.pages: video = context.pages[0].video
                    context.close()
                    if video is not None: video.save_as(str(output/'live.webm'))
                browser.close()
        if args.record:
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',str(output/'live.webm'),
                '-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(output/'live.mp4')], check=True)
    except Exception as error:
        results['status'] = 'error'; results['error'] = str(error)
        if results['requests'] and results['requests'][-1]['status'] == 'running':
            results['requests'][-1].update(status='error', error=str(error))
        raise
    finally:
        results['finished_at'] = datetime.now(timezone.utc).isoformat()
        (output/'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Живой сценарий Day27')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--record', action='store_true')
    parser.add_argument('--url', default='http://127.0.0.1:8067')
    parser.add_argument('--output')
    run(parser.parse_args())
