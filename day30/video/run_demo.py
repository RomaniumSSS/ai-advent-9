"""Один сценарий dry/record: три новых live-запроса assignment-сервера.

Запуск: uv run --no-project --with playwright python day30/video/run_demo.py ...
Подробные receipts остаются private; record context закрывается даже при ошибке.
"""
import argparse
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import load_env
from local import save_private
from client import request
from limits import POLL_TIMEOUT_SECONDS

QUESTIONS=[
    'Что требуется в задании дня 21 при создании индекса документов?',
    'Какие метаданные требуется сохранять для документов в этом задании?',
    'Что требуется в задании дня 24: как показывать источники и когда отказываться отвечать?']

def certificate_pin(cafile):
    public=subprocess.run(['openssl','x509','-in',cafile,'-pubkey','-noout'],check=True,capture_output=True).stdout
    der=subprocess.run(['openssl','pkey','-pubin','-outform','DER'],input=public,check=True,capture_output=True).stdout
    return base64.b64encode(hashlib.sha256(der).digest()).decode()

def observed_limits(value):
    result={}
    for phase in ('selection','synthesis'):
        budget=value.get('trace',{}).get('budgets',{}).get(phase,{})
        options=budget.get('options',{});metrics=value.get('metrics',{}).get(phase,{})
        selected={key:options.get(key) for key in ('num_ctx','num_predict','temperature','top_p') if key in options}
        result[phase]={'options':selected,**{key:budget.get(key) for key in ('input_upper_bound','output_reserved','template_reserve','num_ctx')},
                      **{key:metrics.get(key) for key in ('prompt_eval_count','eval_count')}}
        if any(type(result[phase].get(key)) is not int for key in ('input_upper_bound','output_reserved','template_reserve','num_ctx','prompt_eval_count','eval_count')):
            raise ValueError('missing_observed_context_metrics')
        if (options.get('num_ctx')!=8192 or budget['num_ctx']!=8192 or
                budget['output_reserved']!=options.get('num_predict') or
                budget['input_upper_bound']+budget['output_reserved']>8192 or
                metrics['prompt_eval_count']+options['num_predict']+budget['template_reserve']>8192 or
                metrics['eval_count']>options['num_predict']):
            raise ValueError('observed_context_or_output_limit_failed')
    return result

async def show_api(page,values):
    # AICODE-NOTE: этот блок показывает только ответы настоящих запросов и allowlist
    # метрик; runtime trace/prompt и credential никогда не вставляются в DOM.
    await page.evaluate('''values=>{
        let panel=document.getElementById('demo-api-verification');
        if(!panel){panel=document.createElement('section');panel.id='demo-api-verification';panel.className='card';
            const title=document.createElement('h2');title.textContent='Проверка живого HTTP API';panel.append(title);
            const text=document.createElement('pre');text.style.whiteSpace='pre-wrap';text.style.fontSize='14px';panel.append(text);
            document.querySelector('main').append(panel);}
        panel.querySelector('pre').textContent=JSON.stringify(values,null,2);
        panel.scrollIntoView({block:'start'});
    }''',values)
    await page.wait_for_timeout(3000)

async def browser_api(page,path,payload=None,authenticated=True):
    return await page.evaluate('''async args=>{
        const headers={'Content-Type':'application/json'};
        if(args.authenticated)headers.Authorization='Bearer '+token;
        const response=await fetch(prefix+args.path,{method:args.payload===null?'GET':'POST',headers,
            body:args.payload===null?undefined:JSON.stringify(args.payload),cache:'no-store'});
        return {http_status:response.status,body:await response.json()};
    }''',{'path':path,'payload':payload,'authenticated':authenticated})

async def probe(page,out,receipt,name,path,payload,authenticated,status,code):
    result=await browser_api(page,path,payload,authenticated)
    item={'name':name,**result};receipt['probes'].append(item);save_private(out/'run.json',receipt)
    await show_api(page,item)
    if result['http_status']!=status or result['body'].get('error',{}).get('code')!=code:
        raise ValueError('unexpected_api_probe_'+name)
    return item

async def wait_for_terminal_turn(page,rid):
    await page.wait_for_function('''rid=>{
        const turn=document.querySelector('[data-request-id="'+rid+'"]');
        return turn && ['done','error','unknown','interrupted'].includes(turn.dataset.status);
    }''',arg=rid,timeout=POLL_TIMEOUT_SECONDS*1000)

async def run(args):
    from playwright.async_api import async_playwright
    env=load_env(args.env);token=env['DAY30_TOKEN'];state_dir=Path(env['DAY30_PRIVATE'])/'state'
    if not state_dir.is_dir():raise ValueError('private_state_directory_missing')
    out=Path(args.output).resolve()
    if out.exists():raise ValueError('new_output_directory_required')
    out.mkdir(parents=True,mode=0o700);out.chmod(0o700)
    initial_ids={path.stem.removeprefix('request-') for path in state_dir.glob('request-*.json')}
    receipt={'mode':args.mode,'questions':QUESTIONS,'started_at':time.time(),'steps':[],'probes':[],'scope':'assignment','success':False}
    save_private(out/'run.json',receipt)
    # Строгая CA+hostname проверка до Chromium; никакого -k/ignore_https_errors.
    state=request(args.base_url,'/api/state',token,args.cafile)
    receipt['state']=state;receipt['tls_preflight']='CA_and_hostname_verified';save_private(out/'run.json',receipt)
    if state['scope']!='assignment':raise ValueError('assignment_server_required_for_public_video')
    if state['active']:raise ValueError('assignment_service_must_be_idle')
    video_path=None;failure=None
    async with async_playwright() as p:
        browser=await p.chromium.launch(args=['--ignore-certificate-errors-spki-list='+certificate_pin(args.cafile)])
        context=None;video=None;errors=[]
        try:
            options={'viewport':{'width':1280,'height':1000},'device_scale_factor':1}
            if args.mode=='record':options.update(record_video_dir=str(out/'raw'),record_video_size={'width':1280,'height':1000})
            context=await browser.new_context(**options);page=await context.new_page();video=page.video
            page.on('pageerror',lambda error:errors.append(str(error).replace(token,'[credential]')))
            await page.goto(args.base_url,wait_until='networkidle')
            if await page.locator('#token').get_attribute('type')!='password':raise ValueError('credential_input_not_masked')
            try:
                await page.locator('#token').fill(token);await page.locator('#connect').click()
            except Exception:
                raise ValueError('authentication_ui_failed') from None
            await page.locator('#chat').wait_for(state='visible')
            if await page.locator('#token').input_value():raise ValueError('credential_input_not_cleared')
            await show_api(page,{'GET /api/state':state,'TLS':'CA + hostname проверены'})
            await probe(page,out,receipt,'auth_required','/state',None,False,401,'unauthorized')
            await probe(page,out,receipt,'max_length_501','/chat',{'question':'а'*501},True,400,'invalid_request')
            for number,question in enumerate(QUESTIONS,1):
                if number!=2:await page.locator('#new-conversation').click()
                await page.locator('#question').fill(question);await page.locator('#question').scroll_into_view_if_needed()
                started=time.monotonic()
                async with page.expect_response(lambda response:response.request.method=='POST' and response.url==args.base_url+'/api/chat') as pending:
                    await page.locator('#send').click()
                accepted_response=await pending.value;accepted=await accepted_response.json()
                save_private(out/f'accepted-{number}.json',{'http_status':accepted_response.status,'body':accepted})
                if accepted_response.status!=202:raise ValueError('generation_request_not_accepted')
                rid=accepted['request_id'];cid=accepted['conversation_id']
                turn=page.locator('[data-request-id="'+rid+'"]');await turn.wait_for()
                if rid in initial_ids or rid in [step['request_id'] for step in receipt['steps']]:raise ValueError('request_id_reused')
                step={'question_number':number,'request_id':rid,'conversation_id':cid,'status':accepted['status'],'accepted_http_status':202,'accepted_at':time.time()}
                receipt['steps'].append(step);save_private(out/'run.json',receipt)
                if number==1:
                    active=await browser_api(page,'/requests/'+rid)
                    save_private(out/'active-before-busy.json',active)
                    if active['body'].get('status') not in ('accepted','running'):raise ValueError('first_request_not_active_for_busy_probe')
                    busy=await probe(page,out,receipt,'busy_while_first_runs','/chat',{'question':QUESTIONS[2]},True,409,'busy')
                    busy['while_request_id']=rid;save_private(out/'run.json',receipt)
                    await turn.scroll_into_view_if_needed()
                await wait_for_terminal_turn(page,rid)
                response=await browser_api(page,'/requests/'+rid);value=response['body']
                save_private(out/f'response-{number}.json',value)
                private=json.loads((state_dir/('request-'+rid+'.json')).read_text())
                save_private(out/f'private-response-{number}.json',private)
                step.update(status=value.get('status'),metrics=value.get('metrics',{}),elapsed_seconds=round(time.monotonic()-started,3))
                save_private(out/'run.json',receipt)
                if response['http_status']!=200 or value['request_id']!=rid or value['conversation_id']!=cid or private['request_id']!=rid or private['conversation_id']!=cid or private['metrics']!=value['metrics'] or private['status']!=value['status']:
                    raise ValueError('browser_api_private_receipt_mismatch')
                if value['status']!='done' or await turn.get_attribute('data-status')!='done':raise ValueError('demo_step_not_successful')
                answer=value.get('answer') or {}
                if value['scope']!='assignment' or private['scope']!='assignment' or not answer.get('sources') or not answer.get('summary') or not answer.get('conclusion'):
                    raise ValueError('missing_assignment_answer_or_originals')
                if any(source['source']!='assignment' for source in answer['sources']):raise ValueError('private_source_in_demo')
                if value['metrics'].get('generation_calls')!=2 or value['metrics'].get('generation_completed_calls')!=2:
                    raise ValueError('demo_not_two_completed_generation_calls')
                if number==2 and cid!=receipt['steps'][0]['conversation_id']:raise ValueError('followup_conversation_mismatch')
                if number==3 and cid==receipt['steps'][0]['conversation_id']:raise ValueError('new_conversation_not_created')
                step['observed_limits']=observed_limits(private);step['visible_chat_turns']=await page.locator('.turn').count()
                if step['visible_chat_turns']!=(2 if number==2 else 1):raise ValueError('unexpected_visible_chat_turns')
                save_private(out/'run.json',receipt)
                await turn.scroll_into_view_if_needed();await page.wait_for_timeout(5000)
                await turn.locator('.conclusion').scroll_into_view_if_needed();await page.wait_for_timeout(4000)
                await turn.locator('.metrics').last.scroll_into_view_if_needed();await page.wait_for_timeout(4000)
                details=turn.locator('details').first;await details.locator('summary').click();await details.scroll_into_view_if_needed();await page.wait_for_timeout(6000)
                await page.screenshot(path=str(out/f'answer-{number}.png'),full_page=True)
                step['original_opened']=await details.get_attribute('open') is not None;save_private(out/'run.json',receipt)
                if not step['original_opened']:raise ValueError('assignment_original_not_opened')
                observed=step['observed_limits']
                await show_api(page,{'request_id':rid,'conversation_id':cid,'status':value['status'],'chat_turns':step['visible_chat_turns'],
                    'total_seconds':value['metrics']['total_seconds'],'generation_attempted_completed':[value['metrics']['generation_calls'],value['metrics']['generation_completed_calls']],
                    'stages':{phase:{'prompt_tokens':observed[phase]['prompt_eval_count'],'output_tokens':observed[phase]['eval_count'],
                        'max_output':observed[phase]['options']['num_predict'],'context':observed[phase]['num_ctx']} for phase in observed}})
                if errors:raise ValueError('browser_errors')
            for cid in dict.fromkeys(step['conversation_id'] for step in receipt['steps']):
                conv=await browser_api(page,'/conversations/'+cid);save_private(out/('conversation-'+cid+'.json'),conv)
                expected=[step['request_id'] for step in receipt['steps'] if step['conversation_id']==cid]
                if conv['http_status']!=200 or [turn['request_id'] for turn in conv['body']['turns']]!=expected or any(turn['status']!='done' for turn in conv['body']['turns']):
                    raise ValueError('completed_conversation_readback_failed')
            if errors:raise ValueError('browser_errors')
            receipt['scenario_success']=True;receipt['success']=args.mode=='dry'
        except Exception as exc:
            failure=type(exc).__name__;receipt['failure']={'type':failure,'message':str(exc).replace(token,'[credential]')}
        finally:
            if context:await context.close()
            if video:video_path=await video.path();receipt['raw_video']=str(video_path)
            await browser.close()
            receipt.update(finished_at=time.time(),browser_errors=errors);save_private(out/'run.json',receipt)
    if failure:raise RuntimeError('demo_failed_see_private_run_receipt') from None
    if video_path:
        output=out/'Day30-live.mp4'
        try:
            subprocess.run(['ffmpeg','-i',str(video_path),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(output)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            output.chmod(0o600)
            probe_result=json.loads(subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(output)],check=True,capture_output=True,text=True).stdout)
            streams=probe_result['streams']
            if len(streams)!=1 or streams[0].get('codec_name')!='h264' or streams[0].get('width')!=1280 or streams[0].get('height')!=1000 or float(probe_result['format']['duration'])<=0:
                raise ValueError('unexpected_mp4_streams_or_dimensions')
            receipt.update(mp4=str(output),ffprobe=probe_result,success=True);save_private(out/'run.json',receipt)
        except Exception as exc:
            receipt['failure']={'type':type(exc).__name__,'message':'video_conversion_or_probe_failed'};save_private(out/'run.json',receipt)
            raise RuntimeError('video_failed_see_private_run_receipt') from None
    safe={'mode':args.mode,'success':receipt['success'],'scope':'assignment','state':state,'steps':receipt['steps'],
          'probes':[{'name':probe['name'],'http_status':probe['http_status'],'error_code':probe['body']['error']['code']} for probe in receipt['probes']],
          'quality':'Semantic correctness is not proven; existing profile12 private semantic FAIL is retained.'}
    save_private(out/'safe-public-summary.json',safe)
    print(json.dumps({'success':receipt['success'],'request_ids':[step['request_id'] for step in receipt['steps']],'output':str(out)}))

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('dry','record'),required=True)
    p.add_argument('--env',required=True);p.add_argument('--base-url',required=True);p.add_argument('--cafile',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();args.base_url=args.base_url.rstrip('/')
    asyncio.run(run(args))
if __name__=='__main__':main()
