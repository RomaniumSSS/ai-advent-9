"""Синтетический browser/API helper: временный loopback сервер, без Ollama/корпуса.

Запуск root: uv run --offline --no-project --with playwright python
             day29/tests/full_chat_browser.py --output-root [private directory]
"""
import argparse,json,sys,tempfile,threading,time,uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,full_chat,full_chat_core as chat

TEXT='<img src=x onerror="window.fullChatXss=true"> Синтетический источник интерфейса, не текст архива.'
class FixtureEngine:
    identity={'generation':'synthetic-browser-fixture','db_sha256':'synthetic-only','chunk_count':3,'document_count':3,
              'source_counts':{'assignment':1,'discussion':1,'personal_note':1},'scope':'all'}
    def ask(self,question,turns,cid,request_id,run_id):
        if 'slow' in question:time.sleep(2)
        result={'conversation_id':cid,'request_id':request_id,'run_id':run_id,'scope':'all','question':question,
                'model':core.MODEL,'options':chat.OPTIONS,'status':'done','started_at':chat.now(),'finished_at':chat.now(),
                'citations_valid':True,'semantic_support':'FIXTURE_ONLY','generation_called':False,
                'query':{'intent':'new_topic','search_query':question},'times':{'generation':None,'total':.01},
                'answer':{'answer':TEXT,'source_refs':['S1'],'sources':[{'source_ref':'S1','request_id':request_id,
                    'source':'discussion','document_id':'synthetic:discussion','chunk_id':'synthetic-'+('a'*64),'text':TEXT,
                    'excerpts':[{'text':TEXT,'author':'Synthetic author','date':'synthetic date','attribution':'original','start_char':0,'end_char':len(TEXT)}]}]}}
        if 'unknown' in question:result.update(status='unknown',answer={'answer':'Не знаю по переданному контексту. Синтетический unknown.','source_refs':[],'sources':[]})
        if 'error' in question:result.update(status='error',answer=None,error={'phase':'fixture','message':'synthetic error; no model call'})
        return result

class DelayedRead:
    def __init__(self):self.target=None;self.enabled=False;self.bootstrap_enabled=False;self.captured=threading.Event();self.release=threading.Event();self.lock=threading.Lock()
    def arm_bootstrap(self):
        with self.lock:self.bootstrap_enabled=True;self.captured.clear();self.release.clear()
    def take_bootstrap(self,path):
        with self.lock:
            if self.bootstrap_enabled and path=='/api/state':self.bootstrap_enabled=False;return True
        return False
    def arm(self,cid):
        with self.lock:self.target=cid;self.enabled=True;self.captured.clear();self.release.clear()
    def take(self,path):
        with self.lock:
            if self.enabled and path=='/api/conversations/'+self.target:self.enabled=False;return True
        return False

def delayed_handler(app,delay):
    base=full_chat.handler_for(app)
    class Handler(base):
        def do_GET(self):
            if self.trusted() and delay.take_bootstrap(self.path):
                delay.captured.set();delay.release.wait(12)
                return self.send(500,{'error':'synthetic delayed bootstrap failure'})
            if self.trusted() and delay.take(self.path):
                snapshot=app.store.get(delay.target);delay.captured.set();delay.release.wait(12)
                return self.send(200,snapshot)
            return super().do_GET()
    return Handler

def run_delayed_races(browser,app,url,delay,output,result):
    from playwright.sync_api import expect
    for origin,action in [('send','reset'),('poll','new')]:
        context=browser.new_context(viewport={'width':1280,'height':800});page=context.new_page();page.goto(url)
        expect(page.locator('#send')).to_be_enabled(timeout=8000);page.locator('#new').click();expect(page.locator('.turn')).to_have_count(0)
        page.locator('#question').fill('synthetic initial source');page.locator('#send').click();expect(page.locator('.turn').last).to_have_attribute('data-state','done',timeout=8000);expect(page.locator('#send')).to_be_enabled(timeout=8000)
        cid=page.locator('#conversations').input_value()
        if origin=='send':delay.arm(cid)
        page.locator('#question').fill('synthetic slow');page.locator('#send').click()
        if origin=='poll':
            expect(page.locator('.turn').last).to_have_attribute('data-state','running',timeout=5000);delay.arm(cid)
        assert delay.captured.wait(4),'delayed conversation response was not captured'
        page.locator('#'+action).click();expect(page.locator('.turn')).to_have_count(0,timeout=5000)
        delay.release.set();page.wait_for_timeout(1000)
        expect(page.locator('.turn')).to_have_count(0,timeout=1000)
        if action=='new':assert page.locator('#conversations').input_value()!=cid
        expect(page.locator('#send')).to_be_enabled(timeout=8000)
        page.screenshot(path=str(output/(origin+'-delayed-'+action+'.png')),full_page=True)
        result['checks'].append({'group':'delayed '+origin+' response / '+action,'status':'PASS','real_model_calls':0})
        context.close()

def run_bootstrap_race(browser,url,delay,output,result):
    from playwright.sync_api import expect
    context=browser.new_context(viewport={'width':1280,'height':800});page=context.new_page()
    delay.arm_bootstrap();page.goto(url,wait_until='domcontentloaded');assert delay.captured.wait(4),'bootstrap response not captured'
    page.locator('#new').click();expect(page.locator('#send')).to_be_enabled(timeout=6000);expect(page.locator('.turn')).to_have_count(0)
    delay.release.set();page.wait_for_timeout(1000);expect(page.locator('#error')).to_be_empty(timeout=1000)
    page.screenshot(path=str(output/'delayed-bootstrap-after-new.png'),full_page=True)
    result['checks'].append({'group':'delayed old bootstrap error / new conversation','status':'PASS','real_model_calls':0})
    context.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-root',type=Path,default=chat.core.HERE/'private'/'full-chat'/'browser-fixtures');parser.add_argument('--race-only',action='store_true');parser.add_argument('--bootstrap-only',action='store_true');args=parser.parse_args()
    from playwright.sync_api import sync_playwright,expect
    output=args.output_root/uuid.uuid4().hex
    missing=[];cursor=output
    while not cursor.exists():missing.append(cursor);cursor=cursor.parent
    for directory in reversed(missing):directory.mkdir(mode=0o700,exist_ok=True);directory.chmod(0o700)
    args.output_root.chmod(0o700);output.chmod(0o700)
    result={'fixture':True,'real_model_calls':0,'status':'RUNNING','checks':[],'page_errors':[]}
    with tempfile.TemporaryDirectory() as directory:
        app=full_chat.Application(FixtureEngine(),chat.ConversationStore(Path(directory)/'chat'))
        delay=DelayedRead();server=ThreadingHTTPServer(('127.0.0.1',0),delayed_handler(app,delay));app.port=server.server_port
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                for name,width,height in ([] if args.race_only or args.bootstrap_only else [('desktop',1280,800),('tablet',768,1024),('mobile',375,812)]):
                    context=browser.new_context(viewport={'width':width,'height':height});page=context.new_page();page.on('pageerror',lambda error:result['page_errors'].append(str(error)))
                    page.goto(f'http://127.0.0.1:{app.port}/');expect(page.locator('#send')).to_be_enabled(timeout=8000)
                    page.locator('#new').click();expect(page.locator('.turn')).to_have_count(0)
                    page.locator('#question').fill('synthetic discussion question');page.locator('#send').click();expect(page.locator('.turn').last).to_have_attribute('data-state','done',timeout=10000)
                    source=page.locator('.source').last;source.locator('>summary').click();expect(source.locator('.part pre')).to_have_text(TEXT);expect(page.locator('img')).to_have_count(0)
                    assert source.get_attribute('data-request-id')==page.locator('.turn').last.get_attribute('data-request-id')
                    page.screenshot(path=str(output/(name+'-answer.png')),full_page=True)
                    page.reload();expect(page.locator('.turn')).to_have_count(1);expect(page.locator('#send')).to_be_enabled()
                    page.locator('#question').fill('synthetic unknown');page.locator('#send').click();expect(page.locator('.turn').last).to_have_attribute('data-state','unknown',timeout=10000);expect(page.locator('.turn').last.locator('.source')).to_have_count(0)
                    page.locator('#question').fill('synthetic error');page.locator('#send').click();expect(page.locator('.turn').last).to_have_attribute('data-state','error',timeout=10000);expect(page.locator('.turn').last.locator('.answer')).to_contain_text('synthetic error')
                    expect(page.locator('#send')).to_be_enabled(timeout=8000);page.locator('#question').fill('synthetic slow');page.locator('#send').click();expect(page.locator('.turn').last).to_have_attribute('data-state','running',timeout=5000)
                    page.locator('#reset').click();expect(page.locator('.turn')).to_have_count(0);expect(page.locator('#send')).to_be_enabled(timeout=8000);expect(page.locator('.turn')).to_have_count(0)
                    page.locator('#question').fill('synthetic slow');page.locator('#send').click();expect(page.locator('.turn').last).to_have_attribute('data-state','running',timeout=5000)
                    page.locator('#new').click();expect(page.locator('.turn')).to_have_count(0);expect(page.locator('#send')).to_be_enabled(timeout=8000);expect(page.locator('.turn')).to_have_count(0)
                    for e in page.locator('main,aside,.chat,#composer,header').all():
                        bounds=e.bounding_box()
                        if bounds:assert bounds['x']>=-1 and bounds['x']+bounds['width']<=width+1,(name,bounds)
                    page.screenshot(path=str(output/(name+'-new.png')),full_page=True)
                    result['checks'].append({'viewport':name,'size':[width,height],'status':'PASS','contracts':['fresh request','sources scoped to request','XSS text-only','reload history','unknown/error','pending reset/new late result isolation','no layout overflow']})
                    context.close()
                if not args.bootstrap_only:run_delayed_races(browser,app,f'http://127.0.0.1:{app.port}/',delay,output,result)
                run_bootstrap_race(browser,f'http://127.0.0.1:{app.port}/',delay,output,result)
                browser.close()
            if result['page_errors']:raise AssertionError('page_errors')
            result['status']='PASS'
        except Exception as error:
            result.update(status='FAIL',error={'type':type(error).__name__,'message':str(error)[:500]});raise
        finally:
            for f in output.glob('*.png'):f.chmod(0o600)
            core.save_private(output/'result.json',result);delay.release.set();server.shutdown();server.server_close()
    print(json.dumps({'status':result['status'],'evidence':str(output/'result.json'),'real_model_calls':0}));return 0
if __name__=='__main__':raise SystemExit(main())
