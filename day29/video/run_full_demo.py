"""Новый 3-call live сценарий. Без --dry-run/--record ничего не запускает.

Capture privacy filter скрывает чужую историю; runtime приложений не меняется.
Все submitted ответы новые; сохранённые B/F metrics явно исторические.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import core
import full_chat_core as chat

BENCH='http://127.0.0.1:8069'
FULL='http://127.0.0.1:8070'
VIEWPORT={'width':1280,'height':1000}


def now():return datetime.now(timezone.utc).isoformat()
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def actions(day=11,candidate='candidate'):
    if day not in (11,16,17) or candidate!='candidate':raise ValueError('public_scenario_only')
    question=next(c['question'] for c in json.loads((HERE/'eval-suite.json').read_text())['cases'] if c['case_id']=='E02')
    return [{'app':'benchmark','profile_id':'baseline','question':question},
            {'app':'benchmark','profile_id':candidate,'question':question},
            {'app':'full_chat','question':f'Что нужно сделать в задании дня {day}?','day':day}]


def validate_index(identity):
    if not isinstance(identity,dict) or identity.get('generation')!=core.GENERATION or identity.get('db_sha256')!=core.DB_SHA:
        raise ValueError('frozen_index_mismatch')
    if identity.get('corpus_sha256',core.CORPUS_SHA)!=core.CORPUS_SHA:raise ValueError('frozen_corpus_mismatch')


def validate_state(kind,state):
    validate_index(state.get('index'))
    if state.get('model')!=core.MODEL or not re.fullmatch(r'[a-f0-9]{32}',state.get('run_id','')):raise ValueError('app_model_or_run_mismatch')
    if kind=='benchmark':
        # AICODE-NOTE: public /api/state exposes this projection; full profile
        # hash, digest and generation payload remain checked on each receipt.
        expected={k:{'options':p['options'],'quantization':p['quantization'],'model':p['model']} for k,p in core.load_profiles().items()}
        if state.get('scope')!='public' or state.get('embedding_model')!=core.EMBED_MODEL or state.get('profiles')!=expected:raise ValueError('benchmark_state_profile_mismatch')
    elif (state.get('scope')!='all' or state.get('options')!=chat.OPTIONS or
          state['index'].get('chunk_count')!=724 or state['index'].get('document_count')!=663):raise ValueError('full_state_profile_mismatch')


def validate_identity(actual,full=False):
    validate_index(actual.get('index'))
    if actual.get('model')!=core.MODEL or actual.get('digest')!=core.GEN_DIGEST:raise ValueError('receipt_model_digest_mismatch')
    verified=actual.get('model_identity',{})
    if verified.get('generator_digest')!=core.GEN_DIGEST or verified.get('embedding_digest')!=core.EMBED_DIGEST:raise ValueError('receipt_preflight_identity_mismatch')
    if full:
        if actual.get('options')!=chat.OPTIONS:raise ValueError('full_receipt_options_mismatch')
        if actual.get('embedding_model')!=core.EMBED_MODEL or actual.get('embedding_digest')!=core.EMBED_DIGEST:raise ValueError('embedding_identity_mismatch')
        payload=actual.get('payload',{})
        messages=actual.get('messages',[])
        if not messages or messages[0]!={'role':'system','content':chat.SYSTEM} or payload!=core.profile_payload(chat.PROFILE,messages):raise ValueError('full_payload_profile_mismatch')
    else:
        profile=core.load_profiles().get(actual.get('profile_id'))
        if profile is None or actual.get('profile_sha256')!=core.sha(profile) or actual.get('generation_options')!=profile['options']:raise ValueError('benchmark_receipt_profile_mismatch')
        if actual.get('profile',profile)!=profile:raise ValueError('benchmark_receipt_profile_mismatch')


def validate_benchmark(actual,step,rid):
    validate_identity(actual)
    if (actual.get('request_id')!=rid or actual.get('profile_id')!=step['profile_id'] or
        actual.get('question')!=step['question'] or actual.get('scope')!='public' or
        actual.get('status')!='done' or not actual.get('citations_valid') or not actual.get('generation_called')):raise ValueError('benchmark_receipt_contract')
    if not actual.get('selected') or any(c.get('source')!='assignment' for c in actual['selected']):raise ValueError('benchmark_private_selected')
    answer=actual.get('answer') or {};sources=answer.get('sources') or []
    if not {'assignment:19','assignment:20'}<={s.get('source') for s in sources}:raise ValueError('benchmark_required_sources_missing')
    if any(not re.fullmatch(r'assignment:\d+',s.get('source','')) for s in sources):raise ValueError('benchmark_private_reference')
    if not isinstance(answer.get('answer'),str) or not answer['answer'].strip():raise ValueError('empty_answer')
    core.validate_answer(answer,actual['selected'])
    return actual


def validate_full(turn,receipt,cid,question):
    validate_identity(receipt,full=True)
    if turn.get('model')!=core.MODEL or turn.get('options')!=chat.OPTIONS:raise ValueError('full_visible_profile_mismatch')
    rid=turn.get('request_id');answer=turn.get('answer') or {};sources=answer.get('sources') or []
    if (turn.get('conversation_id')!=cid or turn.get('question')!=question or turn.get('status')!='done' or
        not turn.get('citations_valid') or receipt.get('request_id')!=rid or receipt.get('conversation_id')!=cid or
        receipt.get('question')!=question or receipt.get('answer')!=answer or receipt.get('scope')!='all' or
        receipt.get('status')!='done' or not receipt.get('generation_called')):raise ValueError('full_receipt_contract')
    if not sources or any(s.get('source')!='assignment' or not re.fullmatch(r'assignment:\d+',s.get('document_id','')) for s in sources):raise ValueError('full_private_cited_source')
    selected={s['chunk_id']:s for s in receipt.get('selected',[])}
    for source in sources:
        original=selected.get(source.get('chunk_id'))
        if (source.get('request_id')!=rid or original is None or original.get('source')!='assignment' or
            original.get('document_id')!=source['document_id'] or original.get('text')!=source.get('text')):raise ValueError('full_source_scope_or_original_mismatch')
    expected='assignment:'+re.search(r'дня (\d+)',question)[1]
    if expected not in {s['document_id'] for s in sources}:raise ValueError('full_expected_public_source_missing')
    # Hidden selected discussion допустимы для честного scope all; только
    # materialized public sources проходят в кадр. Support claims проверяет root.
    return {'selected_count':len(selected),'hidden_private_selected_count':sum(c.get('source')!='assignment' for c in selected.values()),
            'cited_public_count':len(sources),'citations_valid':True,'semantic_claim_review':'required'}


class CaptureGate:
    def __init__(self,storage,question):
        self.storage=Path(storage);self.question=question;self.owned=set();self.requests=set();self.errors=[];self.checks={}
    def receipt(self,cid,rid):
        if not re.fullmatch(r'[a-f0-9]{32}',cid or '') or not re.fullmatch(r'[a-f0-9]{32}',rid or ''):raise ValueError('invalid_capture_ids')
        return json.loads((self.storage/'receipts'/cid/(rid+'.json')).read_text())
    def inspect_turn(self,turn):
        cid=turn.get('conversation_id');rid=turn.get('request_id')
        if cid not in self.owned or rid not in self.requests or turn.get('question')!=self.question:raise ValueError('unowned_turn_in_capture')
        if turn.get('status') in ('running','pending'):return
        if turn.get('status')!='done':raise ValueError('full_live_request_failed')
        self.checks[rid]=validate_full(turn,self.receipt(cid,rid),cid,self.question)
    def filter_response(self,path,method,value):
        if path=='/api/conversations':
            if method=='GET':return {'conversations':[c for c in value.get('conversations',[]) if c.get('conversation_id') in self.owned]}
            cid=value.get('conversation_id')
            if value.get('turns') or not re.fullmatch(r'[a-f0-9]{32}',cid or ''):raise ValueError('new_conversation_not_empty')
            self.owned.add(cid);return value
        if path=='/api/ask':
            if value.get('conversation_id') not in self.owned or value.get('question')!=self.question:raise ValueError('submission_mismatch')
            self.requests.add(value['request_id']);return value
        if path=='/api/reset':
            if value.get('conversation_id') not in self.owned or value.get('turns'):raise ValueError('reset_unowned_or_nonempty')
            return value
        if path.startswith('/api/conversations/'):
            if value.get('conversation_id') not in self.owned:raise ValueError('private_conversation_blocked')
            for turn in value.get('turns',[]):self.inspect_turn(turn)
            return value
        if path.startswith('/api/requests/'):
            self.inspect_turn(value);return value
        return value
    def route(self,route):
        path=route.request.url.removeprefix(FULL)
        try:
            method=route.request.method
            if method=='POST':
                body=route.request.post_data_json
                if path=='/api/conversations':
                    if body!={}:raise ValueError('empty_new_payload_required')
                elif path=='/api/ask':
                    if not isinstance(body,dict) or set(body)!={'conversation_id','question'} or body['conversation_id'] not in self.owned or body['question']!=self.question:raise ValueError('capture_submission_not_owned')
                elif path=='/api/reset':
                    if not isinstance(body,dict) or set(body)!={'conversation_id'} or body['conversation_id'] not in self.owned:raise ValueError('capture_reset_not_owned')
                else:raise ValueError('unexpected_capture_post')
            elif path.startswith('/api/conversations/') and path.rsplit('/',1)[1] not in self.owned:raise ValueError('capture_read_not_owned')
            elif path.startswith('/api/requests/') and path.rsplit('/',1)[1] not in self.requests:raise ValueError('capture_request_not_owned')
            response=route.fetch();value=response.json()
            if response.status>=400:raise ValueError('capture_api_error')
            value=self.filter_response(path,route.request.method,value)
            route.fulfill(response=response,json=value)
        except Exception as error:
            self.errors.append(type(error).__name__+':'+str(error))
            route.fulfill(status=409,content_type='application/json',body='{"error":"capture_privacy_or_receipt_gate"}')


def quality_snapshot(path):
    if path is None:return None
    path=Path(path).resolve()
    if not path.is_relative_to((HERE/'quality-results').resolve()) or path.suffix!='.html':raise ValueError('public_quality_html_only')
    return {'file':path.name,'sha256':file_sha(path)}


def qualify(dry_file,steps,quality=None,storage=None):
    dry=json.loads(Path(dry_file).read_text())
    if (dry.get('fixture_only') is True or dry.get('mode')!='dry-run' or dry.get('status')!='completed' or dry.get('actions')!=steps or
        dry.get('script_sha256')!=file_sha(__file__) or len(dry.get('requests',[]))!=3 or dry.get('quality_summary')!=quality):
        raise ValueError('matching_completed_dry_required')
    if dry.get('page_errors')!=[] or dry.get('privacy_gate_errors')!=[] or dry.get('live_pair_same_input') is not True:raise ValueError('dry_ui_or_privacy_gate_failed')
    for kind,key in (('benchmark','benchmark_state'),('full_chat','full_state')):
        validate_state(kind,dry.get(key,{}))
    ids=[];bench=[];gate=CaptureGate(storage or HERE/'private/full-chat',steps[-1]['question'])
    for item,step in zip(dry['requests'],steps):
        rid=item.get('request_id');actual=item.get('actual',{})
        if item.get('app')!=step['app'] or item.get('status')!='done' or not re.fullmatch(r'[a-f0-9]{32}',rid or '') or item.get('ui_answer_matches_receipt') is not True:raise ValueError('dry_live_receipt_missing')
        if item['app']=='benchmark':
            if item.get('profile_id')!=step['profile_id'] or actual.get('run_id')!=dry['benchmark_state']['run_id']:raise ValueError('dry_benchmark_identity_mismatch')
            validate_benchmark(actual,step,rid);bench.append(actual)
        else:
            cid=item.get('conversation_id');receipt=gate.receipt(cid,rid)
            if actual.get('run_id')!=dry['full_state']['run_id'] or core.sha(receipt)!=item.get('receipt_sha256'):raise ValueError('dry_full_receipt_binding_mismatch')
            check=validate_full(actual,receipt,cid,step['question'])
            if check!=item.get('qualification') or check!=dry.get('privacy_gate_checks',{}).get(rid):raise ValueError('dry_source_qualification_missing')
        for receipt_time in ('started_at','finished_at'):
            try:
                stamp=datetime.fromisoformat(actual[receipt_time]);start=datetime.fromisoformat(dry['started_at']);end=datetime.fromisoformat(dry['finished_at'])
                if not start<=stamp<=end:raise ValueError('dry_receipt_outside_take_replay')
            except (KeyError,TypeError):raise ValueError('dry_receipt_time_missing') from None
        ids.append(rid)
    if len(set(ids))!=3:raise ValueError('dry_request_ids_not_unique')
    if core.context_messages(bench[0]['question'],bench[0]['selected'])[1]!=core.context_messages(bench[1]['question'],bench[1]['selected'])[1]:raise ValueError('dry_comparison_context_changed')
    attempts=dry.get('submission_attempts',[])
    if len(attempts)!=3 or [a.get('app') for a in attempts]!=[a['app'] for a in steps] or [a.get('profile_id') for a in attempts[:2]]!=['baseline','candidate']:raise ValueError('dry_submission_protocol_mismatch')
    required={'baseline-candidate-identity','parameter-temperature','parameter-max-output','parameter-context','live-baseline','live-candidate','historical-table',
              'full-index-own-empty-history','live-full-public-question','durable-own-history-after-reload','own-history-reset','own-new-conversation'}
    if quality is not None:required.add('saved-five-new-questions')
    frames=dry.get('frames',[])
    if not required<={f.get('name') for f in frames}:raise ValueError('dry_frames_missing')
    for frame in frames:
        if not re.fullmatch(r'[a-z0-9-]+\.png',frame.get('file','')):raise ValueError('dry_frame_path_invalid')
        if file_sha(Path(dry_file).parent/frame['file'])!=frame.get('sha256'):raise ValueError('dry_frame_hash_mismatch')
    return {'run_id':dry['run_id'],'results_sha256':file_sha(dry_file)}


def wait_terminal(page,locator,gate=None):
    started=time.monotonic()
    while time.monotonic()-started<330:
        if gate is not None and gate.errors:raise ValueError('capture_gate_rejected_before_dom')
        if locator.count() and locator.get_attribute('data-state') in ('done','error','unknown','interrupted','rejected'):return
        page.wait_for_timeout(500)
    raise TimeoutError('live_request_not_terminal_no_retry')


def run(args):
    steps=actions(args.full_day);quality_path=getattr(args,'quality_summary',None);quality=quality_snapshot(quality_path)
    qualified=qualify(args.qualified_dry,steps,quality,args.full_storage) if args.record else None
    run_id=uuid.uuid4().hex;output=args.output or HERE/'video/runs'/('full-chat-'+run_id)
    if output.exists():raise ValueError('new_take_directory_required')
    output.mkdir(parents=True,exist_ok=False,mode=0o700);output.chmod(0o700)
    result={'run_id':run_id,'mode':'record' if args.record else 'dry-run','status':'running','started_at':now(),
            'actions':steps,'script_sha256':file_sha(__file__),'viewport':VIEWPORT,'qualified_dry':qualified,
            'quality_summary':quality,
            'requests':[],'frames':[],'page_errors':[],'capture_privacy_filter':'Only own conversations; reject non-assignment cited sources before DOM',
            'semantic_claim_review':'required','maximum_submissions':3,'submission_attempts':[]}
    core.save_private(output/'results.json',result)
    gate=CaptureGate(args.full_storage,steps[-1]['question']);video=None;capture_start=None
    print(json.dumps({'run_id':run_id,'mode':result['mode']}),flush=True)
    try:
        from playwright.sync_api import sync_playwright,expect
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True);context=None
            try:
                options={'viewport':VIEWPORT}
                if args.record:options.update(record_video_dir=str(output/'raw'),record_video_size=VIEWPORT)
                context=browser.new_context(**options)
                def local_only(route):
                    url=route.request.url
                    if url.startswith(BENCH+'/') or url.startswith(FULL+'/') or (quality_path is not None and url==Path(quality_path).resolve().as_uri()):route.continue_()
                    else:route.abort()
                context.route('**/*',local_only);context.route(FULL+'/api/**',gate.route)
                page=context.new_page();page.on('pageerror',lambda error:result['page_errors'].append(str(error)))
                capture_start=time.monotonic()
                def frame(name,pause=3000):
                    if gate.errors or result['page_errors']:raise ValueError('capture_error_before_frame')
                    target=output/(name+'.png');page.screenshot(path=str(target));target.chmod(0o600)
                    result['frames'].append({'name':name,'video_seconds':time.monotonic()-capture_start,'file':target.name,'sha256':file_sha(target)})
                    core.save_private(output/'results.json',result)
                    if args.record:page.wait_for_timeout(pause)
                page.goto(BENCH);expect(page.locator('#profile option')).to_have_count(6)
                bench_state=page.request.get(BENCH+'/api/state').json()
                validate_state('benchmark',bench_state)
                result['benchmark_state']=bench_state
                frame('baseline-candidate-identity')
                for profile in ('temperature','max-output','context'):
                    page.locator('#profile').select_option(profile);frame('parameter-'+profile)
                for number,step in enumerate(steps[:2],1):
                    page.locator('#profile').select_option(step['profile_id']);page.locator('#question').fill(step['question'])
                    page.locator('#question').scroll_into_view_if_needed();started=time.monotonic()
                    with page.expect_response(lambda response:response.url==BENCH+'/api/ask' and response.request.method=='POST') as submitted:
                        result['submission_attempts'].append({'app':'benchmark','profile_id':step['profile_id'],'at':now()});core.save_private(output/'results.json',result)
                        page.locator('#send').click()
                    response=submitted.value;job=response.json();rid=job.get('request_id')
                    if response.status!=202 or not rid:raise ValueError('benchmark_not_submitted')
                    result['requests'].append({'app':'benchmark','request_id':rid,'profile_id':step['profile_id'],'status':'submitted'})
                    core.save_private(output/'results.json',result)
                    expect(page.locator('#result')).to_have_attribute('data-request-id',rid,timeout=330000)
                    wait_terminal(page,page.locator('#result'))
                    expect(page.locator('#send')).to_be_enabled()
                    actual=page.request.get(BENCH+'/api/requests/'+rid).json();validate_benchmark(actual,step,rid)
                    current=page.request.get(BENCH+'/api/state').json();validate_state('benchmark',current)
                    if actual.get('run_id')!=bench_state['run_id'] or current['run_id']!=bench_state['run_id']:raise ValueError('benchmark_app_restarted')
                    if page.locator('#answer').inner_text().strip()!=actual['answer']['answer'].strip():raise ValueError('benchmark_visible_receipt_mismatch')
                    result['requests'][-1].update(status='done',actual=actual,ui_answer_matches_receipt=True,elapsed_seconds=time.monotonic()-started)
                    page.locator('#result').scroll_into_view_if_needed();frame('live-'+step['profile_id'],5000)
                    for index,card in enumerate(page.locator('#sources .source').all(),1):card.scroll_into_view_if_needed();frame(f'public-source-{number}-{index}')
                a,b=[r['actual'] for r in result['requests']]
                contexts=[core.context_messages(r['question'],r['selected'])[1] for r in (a,b)]
                if contexts[0]!=contexts[1] or a['index']!=b['index']:raise ValueError('benchmark_live_context_changed')
                result['live_pair_same_input']=True
                summary_response=page.request.get(BENCH+'/api/summary');result['historical_summary_sha256']=hashlib.sha256(summary_response.body()).hexdigest()
                for number,block in enumerate(page.locator('#summary .summary-block').all(),1):block.scroll_into_view_if_needed();frame(f'historical-summary-{number}',4500)
                page.locator('#summary table').scroll_into_view_if_needed();frame('historical-table',5000)
                result['visible_historical_summary']=page.locator('#summary').inner_text()
                page.goto(FULL);expect(page.locator('#send')).to_be_enabled(timeout=15000)
                if gate.errors:raise ValueError('full_initial_privacy_gate_failed')
                state=page.request.get(FULL+'/api/state').json()
                validate_state('full_chat',state)
                if state.get('active_request'):raise ValueError('full_scope_or_busy')
                result['full_state']=state;frame('full-index-own-empty-history',4500)
                step=steps[-1];page.locator('#question').fill(step['question']);started=time.monotonic()
                with page.expect_response(lambda response:response.url==FULL+'/api/ask' and response.request.method=='POST') as submitted:
                    result['submission_attempts'].append({'app':'full_chat','at':now()});core.save_private(output/'results.json',result)
                    page.locator('#send').click()
                response=submitted.value;job=response.json();rid=job.get('request_id');cid=job.get('conversation_id')
                if response.status!=202 or rid not in gate.requests or cid not in gate.owned:raise ValueError('full_not_submitted')
                result['requests'].append({'app':'full_chat','request_id':rid,'conversation_id':cid,'status':'submitted'})
                core.save_private(output/'results.json',result)
                turn=page.locator(f'.turn[data-request-id="{rid}"]')
                wait_terminal(page,turn,gate)
                expect(page.locator('#send')).to_be_enabled(timeout=15000)
                if gate.errors:raise ValueError('full_answer_gate_failed')
                actual=page.request.get(FULL+'/api/requests/'+rid).json();receipt=gate.receipt(cid,rid)
                qualification=validate_full(actual,receipt,cid,step['question'])
                current=page.request.get(FULL+'/api/state').json();validate_state('full_chat',current)
                if receipt.get('run_id')!=state['run_id'] or current['run_id']!=state['run_id']:raise ValueError('full_app_restarted')
                if turn.locator('.answer').inner_text().strip()!=actual['answer']['answer'].strip():raise ValueError('full_visible_receipt_mismatch')
                result['requests'][-1].update(status='done',actual=actual,ui_answer_matches_receipt=True,receipt_sha256=core.sha(receipt),qualification=qualification,elapsed_seconds=time.monotonic()-started)
                turn.scroll_into_view_if_needed();frame('live-full-public-question',6000)
                for index,source in enumerate(turn.locator('details.source').all(),1):
                    source.locator('summary').first.click();source.scroll_into_view_if_needed();frame(f'full-public-source-{index}',4500)
                    whole=source.locator('details.whole');whole.locator('summary').click();whole.scroll_into_view_if_needed();frame(f'full-original-{index}')
                page.reload();expect(page.locator(f'.turn[data-request-id="{rid}"]')).to_have_attribute('data-state','done',timeout=15000)
                frame('durable-own-history-after-reload',4500)
                page.locator('#reset').click();expect(page.locator('.turn')).to_have_count(0);frame('own-history-reset',3000)
                page.locator('#new').click();expect(page.locator('#send')).to_be_enabled();expect(page.locator('.turn')).to_have_count(0);frame('own-new-conversation',3000)
                if quality_path is not None:
                    if quality_snapshot(quality_path)!=quality:raise ValueError('quality_summary_changed_during_take')
                    page.goto(Path(quality_path).resolve().as_uri())
                    page.get_by_text('Сохранённый тест пяти новых вопросов',exact=False).first.wait_for(state='visible')
                    frame('saved-five-new-questions',9000)
                    result['visible_quality_summary']=page.locator('body').inner_text()
                result.update(status='completed',privacy_gate_checks=gate.checks,source_semantic_review='required',video_review='required')
                if args.record:video=page.video
            finally:
                try:
                    if context is not None:
                        if args.record and video is None and context.pages:video=context.pages[0].video
                        try:context.close()
                        finally:
                            if video is not None:video.save_as(str(output/'live.webm'))
                finally:browser.close()
        if args.record:
            mp4=output/'live.mp4'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',str(output/'live.webm'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(mp4)],check=True)
            probe=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(mp4)],capture_output=True,text=True,check=True)
            result['ffprobe']=json.loads(probe.stdout);result['video_sha256']=file_sha(mp4)
    except Exception as error:
        result.update(status='error',error_type=type(error).__name__);raise
    finally:
        result.update(finished_at=now(),privacy_gate_errors=gate.errors)
        for file in output.rglob('*'):
            file.chmod(0o700 if file.is_dir() else 0o600)
        core.save_private(output/'results.json',result)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--dry-run',action='store_true');modes.add_argument('--record',action='store_true')
    parser.add_argument('--full-day',type=int,choices=(11,16,17),default=11)
    parser.add_argument('--qualified-dry',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--quality-summary',type=Path,help='Root-owned publicsafe standalone HTML результатов пяти новых вопросов')
    parser.add_argument('--full-storage',type=Path,default=HERE/'private/full-chat')
    args=parser.parse_args(argv)
    if args.record and args.qualified_dry is None:parser.error('--record requires matching --qualified-dry results.json')
    run(args)


if __name__=='__main__':main()
