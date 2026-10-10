"""Отдельный приватный loopback чат /8070; исходный /8069 не изменяется."""
import argparse,json,threading,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import core
from full_chat_core import ChatEngine,ConversationStore,PROFILE,chat_view,identifier,load_full_index,now
HERE=Path(__file__).resolve().parent

class Application:
    def __init__(self,engine,store,port=8070):
        self.engine=engine;self.store=store;self.port=port;self.run_id=uuid.uuid4().hex;self.lock=threading.Lock();self.active=None
    def state(self):
        with self.lock:active=dict(self.active) if self.active else None
        return {'scope':'all','run_id':self.run_id,'model':PROFILE['model'],'options':PROFILE['options'],'index':{
            k:self.engine.identity.get(k) for k in ('generation','db_sha256','chunk_count','document_count','source_counts')},
            'active_request':active,'semantic_support':'not automatically assessed','privacy':'private local history and sources'}
    def submit(self,cid,question):
        question=core.validate_question(question);identifier(cid)
        with self.lock:
            if self.active is not None:raise ValueError('local_generation_busy')
            rid=uuid.uuid4().hex;epoch,history,turn=self.store.begin(cid,question,rid)
            self.active={'conversation_id':cid,'request_id':rid}
        def work():
            try:
                try:result=self.engine.ask(question,history,cid,request_id=rid,run_id=self.run_id)
                except Exception as error:result={'conversation_id':cid,'request_id':rid,'run_id':self.run_id,'scope':'all','question':question,
                                                 'status':'error','answer':None,'error':{'phase':'worker','type':type(error).__name__,'message':str(error)[:300]}}
                try:self.store.finish(cid,epoch,result)
                except Exception as error:
                    # Ошибка сохранения тоже терминальна для API; не оставляем вечный running.
                    with self.store.lock:
                        c=self.store.data.get(cid)
                        if c and c['epoch']==epoch:
                            t=next((t for t in c['turns'] if t['request_id']==rid),None)
                            if t:t.update(status='error',answer=None,error={'phase':'storage','message':str(error)[:200]})
            finally:
                with self.lock:self.active=None
        threading.Thread(target=work,daemon=True).start();return turn

def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,data,kind='application/json; charset=utf-8'):
            body=core.packed(data) if isinstance(data,(dict,list)) else data
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(body)
        def trusted(self):
            expected=f'127.0.0.1:{app.port}';origin=self.headers.get('Origin')
            return self.headers.get('Host')==expected and (origin is None or origin==f'http://{expected}')
        def do_GET(self):
            if not self.trusted():return self.send(403,{'error':'loopback_host_origin_required'})
            url=urlsplit(self.path);path=url.path
            if url.query:return self.send(404,{'error':'unknown_route'})
            assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            if path in assets:
                name,kind=assets[path];return self.send(200,(HERE/'full_chat_static'/name).read_bytes(),kind)
            if path=='/api/state':return self.send(200,app.state())
            if path=='/api/conversations':return self.send(200,{'conversations':app.store.list()})
            try:
                if path.startswith('/api/conversations/') and path.count('/')==3:return self.send(200,app.store.get(path.rsplit('/',1)[1]))
                if path.startswith('/api/requests/') and path.count('/')==3:return self.send(200,app.store.request(path.rsplit('/',1)[1]))
            except ValueError as error:return self.send(404,{'error':str(error)})
            self.send(404,{'error':'unknown_route'})
        def do_POST(self):
            if not self.trusted():return self.send(403,{'error':'loopback_host_origin_required'})
            if self.path not in ('/api/conversations','/api/ask','/api/reset'):return self.send(404,{'error':'unknown_route'})
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('json_required')
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=6000:raise ValueError('request_size_limit')
                value=json.loads(self.rfile.read(size))
                if not isinstance(value,dict):raise ValueError('object_required')
                if self.path=='/api/conversations':
                    if value:raise ValueError('empty_payload_required')
                    return self.send(201,app.store.create())
                if self.path=='/api/reset':
                    if set(value)!={'conversation_id'}:raise ValueError('conversation_id_only')
                    return self.send(200,app.store.reset(value['conversation_id']))
                if set(value)!={'conversation_id','question'}:raise ValueError('conversation_id_question_only')
                return self.send(202,app.submit(value['conversation_id'],value['question']))
            except OSError:return self.send(503,{'error':'private_storage_unavailable'})
            except (ValueError,TypeError) as error:
                code=409 if str(error)=='local_generation_busy' else 400
                self.send(code,{'error':str(error)})
    return Handler

def main(argv=None):
    parser=argparse.ArgumentParser(description='Полный локальный RAG чат Day29')
    parser.add_argument('--index-root',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8070)
    args=parser.parse_args(argv)
    if args.port!=8070:parser.error('порт фиксирован: 8070')
    root=(HERE/'private'/'full-chat').resolve()
    if not root.is_relative_to((HERE/'private').resolve()):parser.error('private storage outside private root')
    identity,chunks=load_full_index(args.index_root);app=Application(ChatEngine(chunks,identity),ConversationStore(root),args.port)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(app));print('http://127.0.0.1:8070 · all · private local history',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0
if __name__=='__main__':raise SystemExit(main())
