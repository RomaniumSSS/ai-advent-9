"""Loopback-панель: живой поиск и ответы; внешние операции включает оператор."""
import argparse
import base64
import json
import shlex
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import MODEL, key_from_env, save, validate_answer
from evaluate import evaluate
from retrieval import Config
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='http://127.0.0.1:8053'
QUESTION='Что нужно сдать в Day21?'
STATE={'phase':'idle','message':'Готов к живому поиску','result':None}
LOCK=threading.Lock()
OPERATE=False
ENV_FILE=None
PRIVATE_PREVIEW=False
PAGE='''<!doctype html><html lang="ru"><meta charset="utf-8"><title>Day23 · практика</title><style>
body{background:#111a29;color:#eef3fa;font:19px/1.45 system-ui;margin:0}main{max-width:1320px;margin:auto;padding:25px}h1{font-size:30px}h2{font-size:24px}section{background:#1b2a3f;border:1px solid #405674;border-radius:12px;padding:18px;margin:14px 0}button,input{font:inherit;border-radius:8px;padding:10px;border:1px solid #526581;background:#28405c;color:white}input{width:90%}button{cursor:pointer}button:disabled{opacity:.4}.muted{color:#acbfd7}pre{white-space:pre-wrap;font:17px/1.4 system-ui}table{width:100%;border-collapse:collapse;font-size:15px}td,th{padding:6px;border-bottom:1px solid #405674;text-align:left}.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}.hidden{display:none}</style><main><h1>Day23 · поиск → отбор → новые ответы</h1><p class="muted">Векторный поиск по всему замороженному индексу. Приватные тексты скрыты при отображении.</p><section><h2>1. Новый вопрос</h2><input aria-label="Вопрос" id="question"><p><button id="search">Запустить поиск на VPS</button></p><p id="status">Готов к запуску</p></section><section id="retrieval" class="hidden"><h2>2. Кандидаты и причины отбора</h2><p id="rewrite"></p><div class="cols"><div><h3>A · cosine top-5</h3><div id="A"></div></div><div><h3>E · выбранная конфигурация</h3><div id="E"></div></div></div><details><summary>Текст найденного условия Day21</summary><pre id="source"></pre></details><p><button id="generate">Получить два новых ответа A/E</button></p></section><section id="answers" class="hidden"><h2>3. DeepSeek · DeepInfra/fp8 · реальные ответы</h2><p id="cost"></p><div class="cols"><div><h3>A</h3><pre id="answerA"></pre></div><div><h3>E</h3><pre id="answerE"></pre></div></div></section></main><script>
const el=id=>document.getElementById(id);let timer;el('question').value='';
function table(hits){const t=document.createElement('table');const head=document.createElement('tr');['Источник','Cosine','Mixed','Решение'].forEach(x=>{let c=document.createElement('th');c.textContent=x;head.append(c)});t.append(head);hits.forEach(x=>{let r=document.createElement('tr');[x.source,x.cosine.toFixed(3),x.mixed.toFixed(3),x.reason].forEach(y=>{let c=document.createElement('td');c.textContent=y;r.append(c)});t.append(r)});return t}
async function poll(){const s=await(await fetch('/state')).json();el('status').textContent=s.message;if(s.result){const d=s.result;el('retrieval').classList.remove('hidden');el('rewrite').textContent='Поисковый вопрос E: '+d.search_question+' · '+d.config;for(const m of ['A','E'])el(m).replaceChildren(table(d.modes[m].hits));el('source').textContent=d.assignment;if(d.answers){el('answers').classList.remove('hidden');el('cost').textContent=d.cost;for(const m of ['A','E'])el('answer'+m).textContent=d.answers[m];}}if(s.phase==='searched'){el('generate').disabled=false;el('search').disabled=false}else if(s.phase==='completed'||s.phase==='error'){clearInterval(timer);el('search').disabled=false;el('generate').disabled=s.phase==='completed';}}
async function start(path){el('search').disabled=true;el('generate').disabled=true;const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:el('question').value})});if(!r.ok){el('status').textContent=(await r.json()).error;el('search').disabled=false;return}clearInterval(timer);timer=setInterval(poll,750);poll()}
el('search').onclick=()=>start('/search');el('generate').onclick=()=>start('/generate');
</script></html>'''

def remote_prepare(config):
    settings={'root':'/opt/day21/private/index-release-v1','questions':{'cases':[{'id':'VIDEO01','question':QUESTION}]},'configs':{'A':vars(Config(before=5)),'E':config}}
    modules={name:base64.b64encode((ROOT/(name+'.py')).read_bytes()).decode() for name in ('common','retrieval','prepare_remote')}
    wrapper='import base64,json,sys,types\n'
    for name,source in modules.items():
        wrapper+=f"module=types.ModuleType({name!r});sys.modules[{name!r}]=module\nexec(compile(base64.b64decode({source!r}), {name!r}, 'exec'),module.__dict__)\n"
    wrapper+=f"settings=json.loads({json.dumps(settings,ensure_ascii=False)!r})\nresult=sys.modules['prepare_remote'].prepare(settings['root'],settings['questions'],configs=settings['configs'])\nprint(json.dumps(result,ensure_ascii=False))\n"
    result=subprocess.run(['ssh','-o','BatchMode=yes','crm-agent',shlex.quote('/opt/day21/pipeline-venv/bin/python')+' -'],input=wrapper.encode(),capture_output=True,timeout=600)
    if result.returncode:raise ValueError('remote_prepare_failed')
    data=json.loads(result.stdout)
    if data.get('model')!=MODEL or len(data.get('cases',[]))!=1:raise ValueError('invalid_remote_result')
    return data


def safe_search(prepared):
    case=prepared['cases'][0];result={'modes':{},'assignment':'','search_question':case['traces']['E']['search_question'],'config':json.dumps(case['traces']['E']['config'],ensure_ascii=False)}
    for mode in ('A','E'):
        trace=case['traces'][mode]
        selected={c['chunk_id']:c for c in trace['selected']}
        removed={c['chunk_id']:c['removal_reason'] for c in trace['removed']}
        hits=[]
        for c in trace['candidates']:
            public=c.get('source')=='assignment'
            hits.append({'source':c['document_id'] if public else 'Приватный источник (скрыт)','cosine':c['cosine'],'mixed':c['mixed_score'],
                         'reason':('выбран: '+selected[c['chunk_id']]['selection_reason']) if c['chunk_id'] in selected else ('отсечён: '+removed.get(c['chunk_id'],'не выбран'))})
            if public and c['document_id']=='assignment:21' and c['chunk_id'] in selected:
                result['assignment']=c['text']
        result['modes'][mode]={'hits':hits,'private_selected':any(c.get('source')!='assignment' for c in trace['selected'])}
    return result


def safe_answer(text, private_selected):
    if private_selected or any(marker in text.casefold() for marker in ('discussion:', 'personal-note:', 'personal_note')):
        return 'Ответ скрыт: контекст или ответ ссылается на приватные источники. Полный ответ сохранён локально.'
    return text


def update(**values):
    with LOCK:STATE.update(values)


def run_search():
    try:
        update(message='SSH → локальный Qwen → реальные кандидаты A/E…')
        config=json.loads((ROOT/'private/selected-config.json').read_text())['config']
        prepared=remote_prepare(config)
        save(ROOT/'private/video-live-prepared.json',prepared)
        safe=safe_search(prepared)
        save(ROOT/'private/video-safe-result.json',safe)
        update(phase='searched',message='Поиск завершён. Кандидаты и причины отбора получены сейчас.',result=safe)
    except Exception as error:update(phase='error',message='Остановка: '+type(error).__name__)


def run_answers():
    try:
        prepared=json.loads((ROOT/'private/video-live-prepared.json').read_text())
        directory=ROOT/'private/run-v1'
        old=json.loads((directory/'ledger.json').read_text()) if (directory/'ledger.json').exists() else {'entries':[]}
        done={(e['id'],e['mode']) for e in old['entries'] if e['status']=='completed'}
        update(message='Два ответа A/E → OpenRouter → DeepInfra/fp8; общий бюджет Day23 $1…')
        ledger=evaluate(prepared,directory,key_from_env(ENV_FILE),budget=1)
        result=safe_search(prepared);result['answers']={}
        for mode in ('A','E'):
            entry=next(e for e in reversed(ledger['entries']) if e['id']=='VIDEO01' and e['mode']==mode and e['status']=='completed')
            raw=json.loads((directory/entry['response_file']).read_text())
            response=json.loads(raw['body']) if 'http_status' in raw else raw
            validate_answer(response)
            text=response['choices'][0]['message']['content']
            text=text if PRIVATE_PREVIEW else safe_answer(text,result['modes'][mode]['private_selected'])
            provenance='Сохранённый ответ, повторный вызов не выполнен.' if ('VIDEO01',mode) in done else 'Новый ответ, получен в этой демонстрации.'
            result['answers'][mode]=provenance+'\n\n'+text
        result['cost']=f"Общий журнал Day23: {len(ledger['entries'])} попыток · учтено ${sum(e.get('charged',e['reserve']) for e in ledger['entries']):.6f} / $1"
        save(ROOT/'private/video-safe-result.json',result)
        update(phase='completed',message='Ответы получены. Приватный просмотр: перед публикацией нужна проверка.' if PRIVATE_PREVIEW else 'Ответы получены. Приватные тексты скрыты.',result=result)
    except Exception as error:update(phase='error',message='Остановка: '+type(error).__name__)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,data,kind='application/json'):
        body=data if isinstance(data,str) else json.dumps(data,ensure_ascii=False)
        self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body.encode())
    def do_GET(self):
        if self.headers.get('Host')!='127.0.0.1:8053':return self.send(403,{'error':'host_rejected'})
        if self.path=='/':return self.send(200,PAGE,'text/html')
        if self.path=='/state':
            with LOCK:data=dict(STATE)
            data['private_preview']=PRIVATE_PREVIEW
            return self.send(200,data)
        return self.send(404,{})
    def do_POST(self):
        if self.path not in ('/search','/generate'):return self.send(404,{})
        if self.headers.get('Origin')!=ORIGIN or self.headers.get('Host')!='127.0.0.1:8053':return self.send(403,{'error':'origin_rejected'})
        if not OPERATE:return self.send(403,{'error':'external_operations_disabled'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=4096:raise ValueError('invalid_request_size')
            body=json.loads(self.rfile.read(length))
            if body!={'question':QUESTION}:raise ValueError('use_fixed_video_question')
            with LOCK:
                if STATE['phase'] in ('searching','generating'):raise ValueError('job_already_running')
                if self.path=='/generate' and STATE['phase']!='searched':raise ValueError('search_required')
                STATE['phase']='searching' if self.path=='/search' else 'generating'
                if self.path=='/search':STATE['result']=None
            threading.Thread(target=run_search if self.path=='/search' else run_answers,daemon=True).start()
            return self.send(202,{'status':'started'})
        except Exception as error:return self.send(400,{'error':str(error) if isinstance(error,ValueError) else 'invalid_request'})


def main():
    global OPERATE,ENV_FILE,PRIVATE_PREVIEW
    parser=argparse.ArgumentParser();parser.add_argument('--operate',action='store_true');parser.add_argument('--env-file');parser.add_argument('--private-preview',action='store_true')
    args=parser.parse_args();OPERATE=args.operate;ENV_FILE=args.env_file;PRIVATE_PREVIEW=args.private_preview
    ThreadingHTTPServer(('127.0.0.1',8053),Handler).serve_forever()

if __name__=='__main__':main()
