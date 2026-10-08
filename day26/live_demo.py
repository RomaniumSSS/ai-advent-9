"""Живая демонстрация: браузер → Python → локальный потоковый API Ollama."""
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:11434'
MODEL = 'qwen3:8b'
CLIENT = build_opener(ProxyHandler({}))
LOCK = threading.Lock()
QUESTIONS = [
    ('Простой', 'Сколько будет 17 + 25? Ответь одним числом.'),
    ('Средний', 'Объясни разницу list и set в Python и покажи короткий пример удаления дубликатов. Ответ до 60 слов.'),
    ('Сложный', 'Напиши функцию Python merge_intervals(intervals), объединяющую пересекающиеся и касающиеся интервалы. Верни только код функции, пример вызова для [[1,3],[2,6],[8,10],[10,12]] и комментарии с ожидаемым результатом, сложностью и поведением при пустом входе. До 25 строк.'),
]
HTML = r'''<!doctype html><html lang="ru"><meta charset="utf-8"><title>День 26 — локальная LLM</title>
<style>*{box-sizing:border-box}body{margin:0;background:#101723;color:#eef3fc;font:22px system-ui}main{max-width:1200px;margin:32px auto;padding:0 24px}h1{font-size:34px;margin:0 0 10px}.muted{color:#aebed5;font-size:18px}.badge{color:#7ee6bd}nav{display:flex;gap:12px;margin:26px 0}button{font:inherit;background:#26364d;color:#eef3fc;border:1px solid #526985;border-radius:10px;padding:12px 22px;cursor:pointer}button.active{background:#296450}button:disabled{opacity:.65;cursor:wait}section{background:#192536;border:1px solid #344860;border-radius:16px;padding:24px}h2{font-size:23px;margin:0 0 12px}#prompt{line-height:1.5;margin:0 0 20px}#answer{font:19px/1.4 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:0;min-height:120px}#status{color:#7ee6bd;margin-top:20px;font-size:18px}#summary{margin-top:16px;font-size:18px}@media(max-width:650px){body{font-size:18px}main{padding:0 12px;margin:20px auto}h1{font-size:26px}nav{flex-wrap:wrap}button{padding:10px}#answer{font-size:15px}section{padding:16px}}</style>
<main><h1>День 26 · Локальная LLM</h1><div class="muted">Apple M2 · 16 ГБ RAM · <span class="badge">Qwen3 8B / Ollama</span></div>
<p class="muted">HTTP API: http://127.0.0.1:11434/api/generate · потоковый ответ</p>
<nav><button data-id="0">1. Простой</button><button data-id="1">2. Средний</button><button data-id="2">3. Сложный</button></nav>
<section><h2 id="title">Три запроса разной сложности</h2><p id="prompt">Нажмите на запрос. Каждый запуск обращается к модели на этом Mac.</p><pre id="answer">Ответ будет появляться здесь по мере генерации.</pre><div id="status">Готов к запуску</div></section><div id="summary"></div></main>
<script>const questions=QUESTIONS_JSON;let completed=0;window.finished=-1;window.failure=null;
for(const button of document.querySelectorAll('button'))button.onclick=async()=>{
 const id=Number(button.dataset.id);document.querySelectorAll('button').forEach(b=>{b.disabled=true;b.classList.toggle('active',b===button)});
 document.getElementById('title').textContent=(id+1)+'. '+questions[id][0];document.getElementById('prompt').textContent=questions[id][1];
 const answer=document.getElementById('answer'),status=document.getElementById('status');answer.textContent='';const start=performance.now();
 const timer=setInterval(()=>status.textContent='Модель генерирует ответ… '+((performance.now()-start)/1000).toFixed(1)+' с',100);
 try{const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});if(!response.ok)throw Error('HTTP '+response.status);
 const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
 while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let nl;while((nl=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,nl);buffer=buffer.slice(nl+1);if(!line)continue;const item=JSON.parse(line);if(item.error)throw Error(item.error);if(item.response)answer.textContent+=item.response;if(item.done){clearInterval(timer);status.textContent='Ответ получен · '+item.elapsed_seconds.toFixed(2)+' с · '+item.eval_count+' токенов · '+item.done_reason;window.finished=id;completed++;document.getElementById('summary').textContent='Получено ответов: '+completed+' / 3';}}}
 if(window.finished!==id)throw Error('Поток завершился без подтверждения');
 }catch(e){window.failure=String(e);status.textContent='Ошибка: '+e;}finally{clearInterval(timer);document.querySelectorAll('button').forEach(b=>b.disabled=false);}
};</script></html>'''.replace('QUESTIONS_JSON', json.dumps(QUESTIONS, ensure_ascii=False))
# AICODE-NOTE: ответы сохраняются в отдельный каталог, исходный прогон не перезаписывается.
RUN = ROOT / 'results' / ('live-' + datetime.now().strftime('%Y%m%d-%H%M%S'))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path != '/':
            self.send_error(404)
            return
        body = HTML.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/run':
            self.send_error(404)
            return
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get('Content-Length', 0)), 1024)))
            ident = body['id']
            if type(ident) is not int or not 0 <= ident < len(QUESTIONS):
                raise ValueError('invalid_id')
        except (ValueError, KeyError):
            self.send_error(400)
            return
        if not LOCK.acquire(blocking=False):
            self.send_error(409)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        payload = {'model': MODEL, 'prompt': QUESTIONS[ident][1], 'think': False,
                   'stream': True, 'keep_alive': '5m',
                   'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': 600}}
        record = {'started_at': datetime.now(timezone.utc).isoformat(), 'endpoint': BASE,
                  'request': payload, 'chunks': [], 'answer': ''}
        start = time.perf_counter()
        try:
            request = Request(BASE + '/api/generate', data=json.dumps(payload).encode(),
                              headers={'Content-Type': 'application/json'})
            with CLIENT.open(request, timeout=300) as response:
                for line in response:
                    item = json.loads(line)
                    record['chunks'].append(item)
                    record['answer'] += item.get('response', '')
                    if item.get('done'):
                        item['elapsed_seconds'] = time.perf_counter() - start
                    self.wfile.write((json.dumps(item) + '\n').encode())
                    self.wfile.flush()
        except Exception as exc:
            record['error'] = str(exc)
            self.wfile.write((json.dumps({'error': str(exc)}) + '\n').encode())
        finally:
            (RUN / f'request-{ident + 1}.json').write_text(json.dumps(record, ensure_ascii=False, indent=2))
            LOCK.release()

if __name__ == '__main__':
    RUN.mkdir(parents=True, exist_ok=False)
    print(f'http://127.0.0.1:8066 — результаты: {RUN}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8066), Handler).serve_forever()
