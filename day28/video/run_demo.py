"""Три новых public-запроса: один сценарий для dry run и настоящей записи."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from urllib.parse import urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import save_private, sha
from evaluate import assess

HERE=Path(__file__).resolve().parents[1]

def run(args):
    from playwright.sync_api import sync_playwright
    if args.url!='http://127.0.0.1:8068':raise ValueError('demo_fixed_loopback_required')
    suite=json.loads(args.suite.read_text())
    if suite.get('scope')!='public' or len(suite['cases'])!=3:raise ValueError('demo_requires_three_public_cases')
    run_id=uuid.uuid4().hex
    output=args.output or HERE/'video'/'runs'/run_id
    output.mkdir(parents=True,exist_ok=False,mode=0o700);output.chmod(0o700)
    results={'run_id':run_id,'mode':'record' if args.record else 'dry-run','status':'running',
        'suite_id':suite['suite_id'],'suite_sha256':sha(suite),'started_at':datetime.now(timezone.utc).isoformat(),
        'requests':[],'page_errors':[],'url':args.url}
    video=None
    print(f'run {run_id} · {output}',flush=True)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True);context=None
            try:
                options={'viewport':{'width':1280,'height':1000}}
                if args.record:options.update(record_video_dir=str(output/'raw'),record_video_size=options['viewport'])
                context=browser.new_context(**options);page=context.new_page()
                page.on('pageerror',lambda error:results['page_errors'].append(str(error)))
                page.goto(args.url);page.wait_for_function("() => !document.querySelector('#identity').textContent.includes('Читаем')")
                if 'public' not in page.locator('.state').inner_text():raise RuntimeError('public_scope_not_visible')
                page.screenshot(path=str(output/'ready.png'))
                if args.record:page.wait_for_timeout(3500)
                for number,case in enumerate(suite['cases'],1):
                    page.locator('#question').fill(case['question']);started=time.monotonic()
                    with page.expect_response(lambda r:r.url==args.url+'/api/ask' and r.request.method=='POST') as response:
                        page.locator('#send').click()
                    submission=response.value.json()
                    if response.value.status!=202 or not submission.get('request_id'):raise RuntimeError('request_not_submitted')
                    rid=submission['request_id']
                    page.wait_for_function("rid => {const e=document.querySelector('#result');return e.dataset.requestId===rid && ['done','unknown','error'].includes(e.dataset.state)}",arg=rid,timeout=330000)
                    actual=page.request.get(args.url+'/api/requests/'+rid).json()
                    if actual.get('request_id')!=rid or actual.get('scope')!='public':raise RuntimeError('wrong_request_or_scope')
                    if any(c.get('source')!='assignment' for c in actual.get('selected',[])):raise RuntimeError('private_context_leak')
                    quality=assess(actual,case.get('expected',{}))
                    results['requests'].append({'case_id':case['case_id'],'request_id':rid,'elapsed_seconds':time.monotonic()-started,
                        'actual':actual,'assessment':quality,'visible_answer':page.locator('#answer').inner_text()})
                    save_private(output/'results.json',results)
                    page.locator('#result').scroll_into_view_if_needed()
                    page.screenshot(path=str(output/f'answer-{number}.png'))
                    if actual['status']=='error':raise RuntimeError('model_request_error:'+rid)
                    if quality['required_sources_present'] is False or quality['unknown_without_sources'] is False:
                        raise RuntimeError('required_demo_fact_or_unknown_failed:'+rid)
                    if results['page_errors']:raise RuntimeError('browser_error')
                    if args.record:page.wait_for_timeout(6500)
                    for details in page.locator('#sources details').all():
                        details.evaluate('e => e.open = true')
                    page.locator('#sources').scroll_into_view_if_needed()
                    page.screenshot(path=str(output/f'sources-{number}.png'))
                    if args.record:page.wait_for_timeout(4500)
                    for source_number,source in enumerate(page.locator('#sources .source').all(),1):
                        source.scroll_into_view_if_needed()
                        page.screenshot(path=str(output/f'source-{number}-{source_number}.png'))
                        if args.record:page.wait_for_timeout(4500)
                    page.locator('#form').scroll_into_view_if_needed()
                    print(f"{case['case_id']} · request {rid} · {actual['status']}",flush=True)
                page.locator('#summary').scroll_into_view_if_needed();page.screenshot(path=str(output/'summary.png'))
                results['evaluation_summary']=page.request.get(args.url+'/api/summary').json()
                if args.record:page.wait_for_timeout(6500)
                results['status']='completed';results['human_semantic_review']='required'
                video=page.video
            finally:
                if context is not None:
                    if video is None and args.record and context.pages:video=context.pages[0].video
                    context.close()
                    if video is not None:video.save_as(str(output/'live.webm'))
                browser.close()
        if args.record:
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',str(output/'live.webm'),
                '-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(output/'live.mp4')],check=True)
            info=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(output/'live.mp4')],check=True,capture_output=True,text=True)
            results['ffprobe']=json.loads(info.stdout);results['video_human_review']='required'
    except Exception as error:
        results.update(status='error',error={'type':type(error).__name__,'message':str(error)})
        raise
    finally:
        results['finished_at']=datetime.now(timezone.utc).isoformat();save_private(output/'results.json',results)

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Day28: новые запросы в браузере, dry-run или record')
    modes=p.add_mutually_exclusive_group(required=True);modes.add_argument('--dry-run',action='store_true');modes.add_argument('--record',action='store_true')
    p.add_argument('--url',default='http://127.0.0.1:8068');p.add_argument('--suite',type=Path,default=HERE/'eval-suite.json')
    p.add_argument('--output',type=Path);run(p.parse_args())
