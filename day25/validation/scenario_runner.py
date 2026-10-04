"""Plan-only by default; explicit offline/live UI execution after external approval.

Never writes authorization/ledger and never retries an ambiguous action.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from common import save, packed
from answers import check_answer
from structured_evidence import check_response
from budget import proposal
from privacy import private_output

SCENARIOS=Path(__file__).with_name('scenarios.json')
TERMINAL={'verified','no_context','model_refusal','insufficient_context','unverified','error','not_authorized','interrupted','unknown'}


def validate_scenarios(data):
    if data['proposed_scopes']!=['public','all']:raise ValueError('public_and_frozen_all_required')
    if len(data['scenarios'])!=2:raise ValueError('two_scenarios_required')
    ids=set()
    for scenario in data['scenarios']:
        if scenario['scope'] not in ('public','all'):raise ValueError('invalid_scope')
        if scenario['scope']=='public' and scenario['allowed_document_ids']!=['assignment:18']:raise ValueError('only_public_assignment18_planned')
        if scenario['scope']=='all' and scenario['allowed_document_ids'] is not None:raise ValueError('full_frozen_scope_required')
        if scenario['id'] in ids:raise ValueError('duplicate_scenario')
        ids.add(scenario['id'])
        if not 10<=len(scenario['turns'])<=15:raise ValueError('scenario_length')
        if not any('state_before' in turn for turn in scenario['turns']):raise ValueError('memory_change_required')
        for state in [scenario['initial_state']]+[t['state_before'] for t in scenario['turns'] if 'state_before' in t]:
            if set(state)!={'goal','clarifications','constraints'}:raise ValueError('invalid_state')
            if not isinstance(state['goal'],str) or not state['goal']:raise ValueError('goal_required')
            if any(not isinstance(state[k],list) or not all(isinstance(x,str) for x in state[k]) for k in ('clarifications','constraints')):raise ValueError('invalid_state_lists')
        if not all(isinstance(t['question'],str) and t['question'] and t['review'] for t in scenario['turns']):raise ValueError('invalid_turn')
    return data


def mechanical_check(item, chat_id, prior_ids, expected_state, scope='public', expected_identity=None):
    if item.get('chat_id')!=chat_id or item.get('scope')!=scope:raise ValueError('chat_or_scope_violation')
    if item.get('stage')!='terminal' or item.get('status') not in TERMINAL:raise ValueError('nonterminal_result')
    if item['status'] in ('error','unknown','interrupted','not_authorized'):raise ValueError('stop_and_audit_'+item['status'])
    if not item.get('saved'):raise ValueError('unsaved_result')
    if not item.get('conversation',{}).get('search_performed'):raise ValueError('fresh_search_not_proven')
    if item.get('task_state')!=expected_state:raise ValueError('wrong_task_snapshot')
    history=item['conversation'].get('history',[])
    if any(m['request_id'] not in prior_ids for m in history):raise ValueError('foreign_history')
    trace=item.get('search',{}).get('trace',{})
    chunks=trace.get('candidates',[])+trace.get('selected',[])+trace.get('removed',[])+item.get('generation',{}).get('transmitted_chunks',[])
    if scope=='public' and any(c.get('document_id')!='assignment:18' for c in chunks):raise ValueError('private_document')
    if scope=='all':
        actual=__import__('hashlib').sha256(packed(item.get('search',{}).get('identity'))).hexdigest()
        if not expected_identity or actual!=expected_identity:raise ValueError('frozen_identity_mismatch')
        if item['generation'].get('started') and item.get('authorization',{}).get('identity_sha256')!=expected_identity:raise ValueError('authorization_identity_mismatch')
    if item['status'] in ('verified','insufficient_context'):
        generation=item['generation']
        checked=(check_response(item.get('raw_answer'),generation.get('transmitted_chunks',[]),item['question'],item['task_state'])
                 if item.get('version')=='day25-chat-v3' else check_answer(item.get('raw_answer'),generation.get('transmitted_chunks',[])))
        if generation.get('transmission')!='confirmed' or generation.get('transmitted_chunk_ids')!=[c['chunk_id'] for c in generation.get('transmitted_chunks',[])] or (not checked['valid'] if item['status']=='verified' else not checked.get('structure_valid') or checked.get('outcome')!='insufficient_context'):raise ValueError('invalid_verified_evidence')
        if checked['answer']!=item.get('answer'):raise ValueError('shown_answer_mismatch')
    if item['status']=='no_context' and (item.get('cost')!=0 or item.get('generation',{}).get('started')):raise ValueError('local_refusal_paid')
    if item['status'] in ('no_context','model_refusal'):
        if item['answer']['sources'] or item['answer']['quotes']:raise ValueError('refusal_sources')
    return {'mechanical':'PASS','semantic':'NOT_REVIEWED'}


def local_pid(url):
    port=urlsplit(url).port
    result=subprocess.run(['lsof','-t','-iTCP:'+str(port),'-sTCP:LISTEN'],capture_output=True,text=True,check=False)
    values=result.stdout.strip().splitlines()
    if len(values)!=1:raise ValueError('unique_preview_pid_required_for_restart_evidence')
    return int(values[0])


def preflight(request_client, urls, mode, expected_identity, data, completed_results):
    states={}
    for scope,url in urls.items():
        response=request_client.get(url+'/api/state')
        if response.status!=200:raise ValueError('preflight_state_unavailable')
        state=response.json()
        if state.get('public_only')!=(scope=='public'):raise ValueError('wrong_server_scope_mode')
        if mode=='offline' and not state.get('test_fixture'):raise ValueError('offline_requires_synthetic_server')
        if mode=='live':
            if state.get('test_fixture'):raise ValueError('live_cannot_use_synthetic_server')
            cloud=state.get('cloud',{})
            if cloud.get('identity_sha256')!=expected_identity:raise ValueError('preflight_frozen_identity_mismatch')
            if not cloud.get('enabled') or scope not in cloud.get('scopes',[]):raise ValueError('server_authorization_missing')
            remaining=sum(len(s['turns']) for s in data['scenarios'] if s['scope']==scope)-sum(r['scope']==scope for r in completed_results)
            needed=float(proposal(data)['reserve_upper_estimate_per_call_usd'])*remaining
            if cloud['budget']-cloud['charged_or_reserved']<needed:raise ValueError('insufficient_scope_budget')
        states[scope]=state
    return states


def run(args,data):
    urls={'public':args.public_url.rstrip('/'),'all':args.all_url.rstrip('/')}
    for url in urls.values():
        parsed=urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.port in (None,8050) or parsed.path not in ('','/') or parsed.query or parsed.fragment:
            raise ValueError('dedicated_loopback_server_required_not_day24_8050')
    if args.mode=='live' and (not args.identity_sha256 or not __import__('re').fullmatch(r'[0-9a-f]{64}',args.identity_sha256)):raise ValueError('approved_frozen_identity_required')
    if args.mode=='live' and not args.approved_live:raise ValueError('external_live_approval_required')
    out=private_output(args.output) if args.mode=='live' else Path(args.output).resolve()
    from playwright.sync_api import sync_playwright
    private_root=Path(__file__).resolve().parents[1]/'private'
    if out.is_relative_to(private_root):
        private_root.mkdir(parents=True,exist_ok=True,mode=0o700);private_root.chmod(0o700)
    video_dir=private_output(args.public_video_dir) if getattr(args,'public_video_dir',None) else None
    if video_dir:video_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    manifest=out/'run.json'
    if args.resume:
        journal=json.loads(manifest.read_text())
        if journal.get('current_action'):raise ValueError('ambiguous_action_manual_audit_no_automatic_retry')
        if journal['mode']!=args.mode or journal['urls']!=urls or journal.get('identity_sha256')!=args.identity_sha256:raise ValueError('resume_run_changed')
        if journal.get('scenario_sha256')!=__import__('hashlib').sha256(packed(data)).hexdigest():raise ValueError('scenario_changed')
    else:
        out.mkdir(parents=True,exist_ok=False,mode=0o700)
        journal={'mode':args.mode,'urls':urls,'identity_sha256':args.identity_sha256,'scope_by_scenario':{s['id']:s['scope'] for s in data['scenarios']},'created_at':time.time(),
                 'scenario_sha256':__import__('hashlib').sha256(packed(data)).hexdigest(),
                 'completed_actions':[], 'chats':{},'results':[], 'current_action':None,
                 'restart':None, 'status':'RUNNING','semantic':'NOT_REVIEWED','approval':'external; CLI flag is not authorization'}
        save(manifest,journal)
    if journal.get('public_video_dir')!=(str(video_dir) if video_dir else None) and args.resume:raise ValueError('resume_video_destination_changed')
    journal['public_video_dir']=str(video_dir) if video_dir else None
    def event(kind,**fields):
        path=out/'events.jsonl'
        import os
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        with os.fdopen(fd,'a') as stream:stream.write(json.dumps({'at':time.time(),'event':kind,**fields},ensure_ascii=False)+'\n')
    def persist():save(manifest,journal)
    def finish(key):
        journal['completed_actions'].append(key);journal['current_action']=None;journal.pop('current_request',None);persist();event('completed',action=key)
    def begin(key):
        if key in journal['completed_actions']:return False
        journal['current_action']=key;persist();event('started',action=key);return True
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        options={'viewport':{'width':1280,'height':900}}
        context=browser.new_context(**options)
        page=context.new_page()
        recording=False;recorded_ids=[]
        def close_context():
            nonlocal recording
            video=page.video if recording else None
            if video:page.wait_for_timeout(700)
            context.close()
            if video:
                number=len(journal.get('public_video_segments',[]))+1
                path=video_dir/('public-part-'+str(number).zfill(2)+'.webm')
                video.save_as(str(path))
                journal.setdefault('public_video_segments',[]).append({'path':str(path),'scope':'public','request_ids':list(recorded_ids),'fresh_search_captured':bool(recorded_ids),'extra_asks':0,'publication':'NOT_APPROVED'})
                persist()
            recording=False
        def capture_request(request):
            if request.method=='POST' and request.url.endswith('/api/ask'):
                body=request.post_data_json
                if recording:
                    if body.get('scope')!='public':raise ValueError('non_public_recording_request')
                    recorded_ids.append(body['id'])
                journal['current_request']={'id':body['id'],'chat_id':body['chat_id']}
                persist();event('request_dispatched',request_id=body['id'],chat_id=body['chat_id'])
        page.on('request',capture_request)
        try:
            preflight(context.request,urls,args.mode,args.identity_sha256,data,journal['results'])
            event('read_only_preflight_passed',scopes=list(urls),identity_sha256=args.identity_sha256)
            if journal.get('restart') and not journal['restart'].get('checked'):
                checkpoint=journal['restart']
                archive=page.request.get(checkpoint['url']+'/api/chat/'+checkpoint['chat_id']).json()
                if archive['chat']['task_state']!=checkpoint['task_state'] or [x['id'] for x in archive['history']]!=checkpoint['request_ids']:
                    raise ValueError('restart_state_changed')
                pid=local_pid(checkpoint['url'])
                if pid==checkpoint['pid_before']:raise ValueError('server_not_restarted')
                checkpoint.update(checked=True,pid_after=pid,checked_at=time.time());journal['status']='RUNNING';persist();event('restart_read_verified',pid_before=checkpoint['pid_before'],pid_after=pid)
            for scenario in data['scenarios']:
                sid=scenario['id']
                scope=scenario['scope'];url=urls[scope]
                if video_dir and ((scope=='public')!=recording):
                    close_context()
                    if scope=='public':
                        check_context=browser.new_context()
                        try:state=check_context.request.get(url+'/api/state').json()
                        finally:check_context.close()
                        if state.get('public_only') is not True:raise ValueError('public_recording_server_required')
                        context=browser.new_context(**options,record_video_dir=str(video_dir),record_video_size={'width':1280,'height':900})
                        context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(urls['public']+'/') else route.abort())
                        recording=True;recorded_ids=[]
                    else:context=browser.new_context(**options)
                    page=context.new_page();page.on('request',capture_request)
                page.goto(url,wait_until='networkidle')
                preflight(context.request,{scope:url},args.mode,args.identity_sha256,data,journal['results'])
                create_key=sid+':create'
                if begin(create_key):
                    page.locator('#chat-title').fill(scenario['title']+' · '+out.name)
                    with page.expect_response(lambda r:r.url.endswith('/api/chats') and r.request.method=='POST') as response:
                        page.locator('#create-chat').click()
                    if response.value.status!=200:raise ValueError('create_failed')
                    chat=response.value.json();journal['chats'][sid]=chat['chat_id'];finish(create_key)
                chat_id=journal['chats'][sid]
                page.locator('#chats button[data-chat-id="'+chat_id+'"]').click()
                page.wait_for_function("id=>document.querySelector('#chats button[aria-pressed=true]')?.dataset.chatId===id",arg=chat_id)
                changes=[(0,scenario['initial_state'])]+[(i,t['state_before']) for i,t in enumerate(scenario['turns'],1) if 'state_before' in t]
                def memory(number,task):
                    key=sid+':memory:'+str(number)
                    if not begin(key):return
                    page.locator('#memory-editor').evaluate('el=>el.open=true')
                    page.locator('#goal').fill(task['goal'])
                    page.locator('#clarifications').fill('\n'.join(task['clarifications']))
                    page.locator('#constraints').fill('\n'.join(task['constraints']))
                    with page.expect_response(lambda r:r.url.endswith('/api/task-state') and r.request.method=='POST') as response:
                        page.locator('#save-memory').click()
                    if response.value.status!=200:raise ValueError('memory_failed')
                    expected=response.value.json()['task_state'];journal.setdefault('task_states',{})[sid]=expected;finish(key)
                    page.locator('#memory-editor').evaluate('el=>el.open=false')
                memory(0,scenario['initial_state'])
                for number,turn in enumerate(scenario['turns'],1):
                    if 'state_before' in turn:memory(number,turn['state_before'])
                    key=sid+':ask:'+str(number)
                    if begin(key):
                        page.locator('#question').fill(turn['question'])
                        with page.expect_response(lambda r:r.url.endswith('/api/ask') and r.request.method=='POST',timeout=360000) as response:
                            page.locator('#send').click()
                        if response.value.status!=200:raise ValueError('ask_failed_no_retry')
                        item=response.value.json()
                        prior={row['request_id'] for row in journal['results'] if row['scenario']==sid}
                        materials=item.get('search',{}).get('trace',{})
                        public_materials=materials.get('candidates',[])+materials.get('selected',[])+materials.get('removed',[])
                        if item.get('scope')==scope and (scope=='all' or all(c.get('document_id')=='assignment:18' for c in public_materials)):
                            save(out/(sid+'-'+str(number).zfill(2)+'.json'),item)
                        expected_identity=args.identity_sha256 if args.mode=='live' else __import__('hashlib').sha256(packed(item.get('search',{}).get('identity'))).hexdigest()
                        checks=mechanical_check(item,chat_id,prior,journal['task_states'][sid],scope,expected_identity)
                        journal['results'].append({'scenario':sid,'scope':scope,'turn':number,'request_id':item['id'],
                            'status':item['status'],'generation_started':item['generation']['started'],
                            'cost':item.get('cost'),'task_state_version':item['task_state_version'],
                            **checks,'review_prompts':turn['review']})
                        finish(key)
                        page.wait_for_function('()=>!document.getElementById("send").disabled')
                    if turn.get('refresh_after'):
                        reload_key=sid+':refresh:'+str(number)
                        if begin(reload_key):
                            before=page.request.get(url+'/api/state').json()['cloud']['charged_or_reserved']
                            posted=[]
                            def observe(request):
                                if request.method=='POST':posted.append(request.url)
                            page.on('request',observe)
                            page.reload(wait_until='networkidle')
                            page.remove_listener('request',observe)
                            after=page.request.get(url+'/api/state').json()['cloud']['charged_or_reserved']
                            if posted or before!=after:raise ValueError('reload_generated_or_mutated')
                            if page.locator('#goal').input_value()!=journal['task_states'][sid]['goal']:raise ValueError('reload_memory_changed')
                            finish(reload_key)
                    if turn.get('restart_after'):
                        restart_key=sid+':restart:'+str(number)
                        if restart_key not in journal['completed_actions']:
                            if (journal.get('restart') or {}).get('checked'):
                                journal['completed_actions'].append(restart_key);persist()
                            else:
                                archive=page.request.get(url+'/api/chat/'+chat_id).json()
                                journal['restart']={'chat_id':chat_id,'task_state':archive['chat']['task_state'],
                                                    'request_ids':[x['id'] for x in archive['history']],
                                                    'pid_before':local_pid(url),'url':url,'checked':False}
                                journal['status']='AWAITING_SERVER_RESTART';persist();event('restart_checkpoint',chat_id=chat_id)
                                print('CHECKPOINT: stop/start only this dedicated server with same data directory, then rerun with --resume. No request is retried.')
                                return 2
            journal['status']='MECHANICAL_RUN_COMPLETE';journal['semantic']='NOT_REVIEWED';persist();event('finished',result_count=len(journal['results']))
            print(json.dumps({'status':journal['status'],'semantic':journal['semantic'],'user_messages':len(journal['results']),
                  'provider_calls':sum(x['generation_started'] for x in journal['results']) if args.mode=='live' else 0,
                  'mock_generation_calls':sum(x['generation_started'] for x in journal['results']) if args.mode=='offline' else 0,
                  'known_cost_sum_usd':sum(x['cost'] for x in journal['results'] if x['cost'] is not None),
                  'unknown_cost_count':sum(x['cost'] is None for x in journal['results']),
                  'cost_kind':'provider-reported' if args.mode=='live' else 'synthetic-not-real-charge', 'output':str(out)},ensure_ascii=False))
            return 0
        except BaseException as error:
            journal['status']='STOPPED_REQUIRES_AUDIT';journal['error']=type(error).__name__+':'+str(error);persist();event('stopped',action=journal.get('current_action'),reason=journal['error'])
            raise
        finally:
            close_context();browser.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['plan','offline','live'],default='plan')
    parser.add_argument('--public-url',default='http://127.0.0.1:8054')
    parser.add_argument('--all-url',default='http://127.0.0.1:8053')
    parser.add_argument('--identity-sha256',help='Exact separately approved frozen index identity; required for live mode')
    parser.add_argument('--output',default=str(Path(__file__).resolve().parents[1]/'private'/'validation-run'))
    parser.add_argument('--approved-live',action='store_true',help='External user authorization must already exist; does not create authorization.')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--public-video-dir',help='Optional private output for public-only fresh UI recording; never records all scope')
    args=parser.parse_args()
    data=validate_scenarios(json.loads(SCENARIOS.read_text()))
    if args.mode=='plan':print(json.dumps(proposal(data),ensure_ascii=False,indent=2));return 0
    return run(args,data)


if __name__=='__main__':raise SystemExit(main())
