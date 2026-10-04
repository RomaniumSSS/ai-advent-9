"""Record the actual public UI from an approved run archive, GET only.

No ask, memory edit, feedback or new provider call. Output remains private for review.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from common import save
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'validation'))
from privacy import private_output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8054')
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allow-fixture',action='store_true')
    args=parser.parse_args()
    args.output=private_output(args.output)
    parsed=urlsplit(args.url)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.port in (None,8050):raise ValueError('dedicated_loopback_required')
    run=json.loads((args.run_dir/'run.json').read_text())
    if run['status']!='MECHANICAL_RUN_COMPLETE':raise ValueError('complete_run_archive_required')
    if run['mode']=='offline' and not args.allow_fixture:raise ValueError('fixture_video_must_be_labelled')
    from playwright.sync_api import sync_playwright
    args.output.mkdir(parents=True,exist_ok=False,mode=0o700)
    events=[]
    browser_methods=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        ctx=browser.new_context(viewport={'width':1280,'height':900},record_video_dir=str(args.output),
                               record_video_size={'width':1280,'height':900})
        def read_only(route):
            if route.request.method not in ('GET','HEAD'):route.abort('blockedbyclient')
            else:route.continue_()
        ctx.route('**/*',read_only)
        page=ctx.new_page()
        page.on('request',lambda request:browser_methods.append(request.method))
        try:
            state=page.request.get(args.url.rstrip('/')+'/api/state').json()
            if not state.get('public_only'):raise ValueError('public_only_required')
            if state.get('test_fixture') and not args.allow_fixture:raise ValueError('synthetic_not_live_video')
            if state.get('test_fixture')!=(run['mode']=='offline'):raise ValueError('server_and_run_mode_mismatch')
            approved_public={chat_id for sid,chat_id in run['chats'].items() if run.get('scope_by_scenario',{}).get(sid)=='public'}
            if not approved_public or {chat['chat_id'] for chat in state['chats']}!=approved_public:
                raise ValueError('unexpected_visible_chat_no_recording')
            page.goto(args.url,wait_until='networkidle')
            before=state['cloud']['charged_or_reserved']
            counters_before=state.get('test_metrics')
            forbidden=[run['task_states'][sid]['goal'] for sid in run['chats'] if run['scope_by_scenario'][sid]=='all']
            def assert_public_dom():
                text=page.locator('body').inner_text()
                if 'ALL_ONLY_SYNTHETIC_MARKER' in text or any(goal in text for goal in forbidden):
                    raise ValueError('all_material_in_public_dom')
            for sid,chat_id in run['chats'].items():
                if run.get('scope_by_scenario',{}).get(sid)!='public':continue
                response=page.request.get(args.url.rstrip('/')+'/api/chat/'+chat_id)
                if response.status!=200:raise ValueError('saved_chat_unavailable')
                data=response.json()
                expected_ids=[row['request_id'] for row in run['results'] if row['scenario']==sid]
                if data['chat']['scope']!='public' or [x['id'] for x in data['history']]!=expected_ids:
                    raise ValueError('unexpected_archive_no_publication')
                if data['chat']['task_state']!=run['task_states'][sid]:raise ValueError('memory_changed_no_publication')
                for item in data['history']:
                    trace=item.get('search',{}).get('trace',{})
                    chunks=trace.get('candidates',[])+trace.get('selected',[])+trace.get('removed',[])
                    if any(c.get('document_id')!='assignment:18' for c in chunks):raise ValueError('private_material_no_publication')
                page.locator('#chats button[data-chat-id="'+chat_id+'"]').click()
                page.wait_for_function("id=>document.querySelector('#chats button[aria-pressed=true]')?.dataset.chatId===id",arg=chat_id)
                page.locator('#conversation-panel').scroll_into_view_if_needed();page.wait_for_timeout(3000)
                page.locator('#memory-editor').evaluate('el=>el.open=true');page.wait_for_timeout(3000)
                page.locator('#memory-editor').evaluate('el=>el.open=false')
                for index in (0, len(expected_ids)-1):
                    turn=page.locator('.turn').nth(index)
                    turn.scroll_into_view_if_needed();page.wait_for_timeout(3500)
                    if turn.locator('.source-link').count():
                        turn.locator('.source-link').first.click();page.wait_for_timeout(3500)
                    assert_public_dom()
                    page.screenshot(path=str(args.output/(sid+'-'+str(index)+'.png')))
                page.reload(wait_until='networkidle');page.wait_for_timeout(2000)
                events.append({'scenario':sid,'chat_id':chat_id,'viewed_saved_results':len(expected_ids),'at':time.time()})
            final_state=page.request.get(args.url.rstrip('/')+'/api/state').json()
            after=final_state['cloud']['charged_or_reserved']
            counters_after=final_state.get('test_metrics')
            assert_public_dom()
            if counters_before!=counters_after:raise ValueError('fixture_calls_during_readonly_recording')
            if any(method not in ('GET','HEAD') for method in browser_methods):raise ValueError('mutation_attempt_during_recording')
            if before!=after:raise ValueError('ledger_changed_during_readonly_recording')
            save(args.output/'RECORDING.json',{'mode':'saved-public-results-playback','synthetic':run['mode']=='offline',
                 'new_provider_calls':0,'new_searches':0,'fresh_search_demonstrated':False,
                 'ledger_charge_before':before,'ledger_charge_after':after,'events':events,
                 'browser_request_methods':sorted(set(browser_methods)), 'fixture_counters_before':counters_before,
                 'fixture_counters_after':counters_after,'public_dom_check':'PASS',
                 'publication':'NOT_APPROVED','semantic_review':run.get('semantic','NOT_REVIEWED')})
        finally:
            video=page.video;ctx.close()
            if video:video.save_as(str(args.output/'saved-public.webm'))
            browser.close()
    print('Recorded saved public UI only; review output and metadata before any publication.')


if __name__=='__main__':main()
