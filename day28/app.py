"""Loopback UI и CLI без общих зависимостей и импорта соседних дней."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import uuid
from urllib.parse import urlsplit

from core import Engine, GEN_OPTIONS, MODEL, EMBED_MODEL, load_index, save_private, validate_question

HERE=Path(__file__).resolve().parent

def public_result(result):
    if result.get('scope')!='public':raise ValueError('private_result_not_public')
    if any(c.get('source')!='assignment' for c in result.get('selected',[])):raise ValueError('private_context_not_public')
    keys=('run_id','request_id','question','scope','model','embedding_model','model_identity','generation_options',
          'index','status','answer','selected','citations_valid','groundedness_semantic','metrics','times','error',
          'generation_called','context_check','no_generation_reason','prompt_sha256','citation_mode')
    return {k:result[k] for k in keys if k in result}

class Application:
    def __init__(self,engine,receipts,port=8068):
        self.engine=engine;self.receipts=Path(receipts);self.port=port
        self.run_id=uuid.uuid4().hex;self.jobs={};self.mutex=threading.Lock()
    def submit(self,question):
        question=validate_question(question)
        with self.mutex:
            if any(j['status']=='running' for j in self.jobs.values()):raise ValueError('local_generation_busy')
            request_id=uuid.uuid4().hex
            self.jobs={k:v for k,v in list(self.jobs.items())[-15:]}
            self.jobs[request_id]={'request_id':request_id,'run_id':self.run_id,'status':'running'}
        def work():
            result=self.engine.ask(question,'public',run_id=self.run_id,request_id=request_id)
            try:save_private(self.receipts/self.run_id/(request_id+'.json'),result)
            except Exception as error:
                result.update(status='error',error={'phase':'receipt','type':type(error).__name__,'message':str(error)[:200]})
            safe=public_result(result)
            with self.mutex:self.jobs[request_id]=safe
        threading.Thread(target=work,daemon=True).start()
        return self.jobs[request_id].copy()

def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,data,content_type='application/json; charset=utf-8'):
            body=json.dumps(data,ensure_ascii=False).encode() if isinstance(data,(dict,list)) else data
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(body)
        def trusted(self):
            expected=f'127.0.0.1:{app.port}'
            if self.headers.get('Host')!=expected:return False
            origin=self.headers.get('Origin')
            return origin is None or origin==f'http://{expected}'
        def do_GET(self):
            if not self.trusted():return self.send(403,{'error':'loopback_host_required'})
            path=urlsplit(self.path).path
            assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),
                    '/style.css':('style.css','text/css; charset=utf-8')}
            if path in assets:
                name,kind=assets[path];return self.send(200,(HERE/'static'/name).read_bytes(),kind)
            if path=='/api/state':return self.send(200,{'scope':'public','model':MODEL,'embedding_model':EMBED_MODEL,
                'generation_options':GEN_OPTIONS,'index':app.engine.identity,'run_id':app.run_id})
            if path.startswith('/api/requests/'):
                rid=path.removeprefix('/api/requests/')
                with app.mutex:job=app.jobs.get(rid)
                return self.send(200 if job else 404,job or {'error':'request_not_found'})
            if path=='/api/summary':
                file=HERE/'results'/'public-summary.json'
                return self.send(200,json.loads(file.read_text()) if file.exists() else {'status':'not_available',
                    'message':'Оценка ещё не опубликована локально. Код проверен офлайн; видео и live-прогоны ожидаются.'})
            self.send(404,{'error':'not_found'})
        def do_POST(self):
            if not self.trusted():return self.send(403,{'error':'loopback_host_required'})
            if self.path!='/api/ask':return self.send(404,{'error':'not_found'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=6000:raise ValueError('request_size_limit')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('json_required')
                data=json.loads(self.rfile.read(n))
                if not isinstance(data,dict) or set(data)!={'question'}:raise ValueError('public_question_only')
                return self.send(202,app.submit(data['question']))
            except (ValueError,TypeError) as error:self.send(400,{'error':str(error)})
    return Handler

def main():
    parser=argparse.ArgumentParser(description='Day28: полностью локальный RAG')
    parser.add_argument('--index-root',type=Path,default=HERE/'private'/'index-release-v1')
    parser.add_argument('--port',type=int,default=8068)
    parser.add_argument('--question');parser.add_argument('--scope',choices=('public','all'),default='public')
    parser.add_argument('--output',type=Path,help='Приватный каталог receipts (для all обязателен)')
    args=parser.parse_args()
    if args.scope=='all' and (not args.question or not args.output or HERE/'private' not in args.output.resolve().parents):
        parser.error('all доступен только в CLI с --output внутри day28/private/')
    identity,chunks=load_index(args.index_root);engine=Engine(chunks,identity)
    if args.question:
        result=engine.ask(args.question,args.scope)
        output=args.output or HERE/'private'/'runs'
        save_private(output/result['run_id']/(result['request_id']+'.json'),result)
        # Приватный CLI выводит только путь и статус; полный текст остаётся в receipt.
        print(json.dumps(public_result(result) if args.scope=='public' else {'status':result['status'],
            'run_id':result['run_id'],'request_id':result['request_id'],'receipt':str(output/result['run_id']/(result['request_id']+'.json'))},ensure_ascii=False,indent=2))
        return 1 if result['status']=='error' else 0
    if args.port!=8068:parser.error('порт интерфейса фиксирован: 8068')
    app=Application(engine,args.output or HERE/'private'/'runs',args.port)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(app))
    print(f'http://127.0.0.1:{args.port} · public · run {app.run_id}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0

if __name__=='__main__':raise SystemExit(main())
