"""Частный stdlib HTTPS UI/API. Секреты и provider traceback не журналируются."""
from limits import WORKER_JOIN_SECONDS
import argparse
from collections import deque
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import signal
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit
import service

HERE=Path(__file__).resolve().parent
MAX_BODY=65536

class ApiError(Exception):
    def __init__(self,status,code,headers=None):self.status=status;self.code=code;self.headers=headers or {}

MESSAGES={'unauthorized':'Нужен действующий bearer token.','forbidden_host':'Этот Host не разрешён.',
 'forbidden_origin':'Этот Origin не разрешён.','invalid_request':'Неверный вопрос или формат запроса.',
 'body_too_large':'JSON body должен быть не больше 64 KiB.','unsupported_media_type':'Нужен Content-Type application/json.',
 'busy':'Модель занята другим запросом; повторите после завершения.', 'rate_limit':'Не больше 6 принятых запросов за 60 секунд.',
 'not_found':'Запрос или разговор не найден в этом режиме.','inference_timeout':'Модель не ответила в пределах таймаута.',
 'invalid_model_response':'Ответ модели не прошёл проверку формата или источников.', 'inference_failed':'Локальная генерация завершилась ошибкой.'}

class Application:
    def __init__(self,engine,store,token,hosts=None,origins=None,scope='all'):
        if not isinstance(token,str) or not token:raise ValueError('missing_token')
        if scope not in ('all','assignment'):raise ValueError('invalid_scope')
        self.engine=engine;self.store=store;self.token=token;self.scope=scope
        self.hosts=set(hosts or []);self.origins=set(origins or []);self.guard=threading.Lock();self.active=False
        self.accepted=deque();self.workers=set()
    def scope_for(self,demo): return 'assignment' if demo else self.scope
    def submit(self,data,demo=False):
        if not isinstance(data,dict) or not set(data)<= {'question','conversation_id'} or 'question' not in data:raise ApiError(400,'invalid_request')
        scope=self.scope_for(demo)
        try:
            question=service.validate_question(data['question']);cid=data.get('conversation_id')
            if cid is not None:
                service.identifier(cid);self.store.conversation(cid,scope)
        except ValueError as exc:raise ApiError(400,'invalid_request') from exc
        with self.guard:
            t=time.monotonic()
            while self.accepted and t-self.accepted[0]>=60:self.accepted.popleft()
            if len(self.accepted)>=6:raise ApiError(429,'rate_limit',{'Retry-After':str(max(1,int(60-(t-self.accepted[0]))+1))})
            if self.active:raise ApiError(409,'busy')
            lock=service.generation_lock()
            try:lock.__enter__()
            except ValueError as exc:raise ApiError(409,'busy') from exc
            try:
                cid,rid=self.store.start(question,cid,scope);self.active=True;self.accepted.append(t)
                worker=threading.Thread(target=self._run,args=(cid,rid,question,scope,lock),daemon=False)
                self.workers.add(worker);worker.start()
            except BaseException:
                self.active=False;lock.__exit__(None,None,None);raise
        return self.store.receipt(rid,scope)
    def _run(self,cid,rid,question,scope,lock):
        try:
            turns=self.store.conversation(cid,scope)['turns'][:-1]
            result=self.engine.answer(question,turns,scope,lambda phase:self.store.phase(rid,phase))
            self.store.finish(rid,result)
        except (service.InferenceFailure,service.InferenceTimeout) as exc:
            self.store.finish(rid,{**exc.partial_result,'error':{'code':exc.code,'message':MESSAGES[exc.code]}})
        except Exception as exc:
            code='inference_timeout' if isinstance(exc,(TimeoutError,socket.timeout)) else 'invalid_model_response' if isinstance(exc,(ValueError,KeyError,TypeError)) else 'inference_failed'
            self.store.finish(rid,{'status':'error','error':{'code':code,'message':MESSAGES[code]}})
        finally:
            lock.__exit__(None,None,None)
            with self.guard:self.active=False;self.workers.discard(threading.current_thread())
            try:
                v=self.store.receipt(rid,scope)
                print(json.dumps({'request_id':rid,'status':v['status'],'metrics':v.get('metrics',{})}),flush=True)
            except Exception:pass
    def wait_workers(self):
        with self.guard:workers=list(self.workers)
        for worker in workers:worker.join(WORKER_JOIN_SECONDS)

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def setup(self):
        super().setup();self.connection.settimeout(self.server.connection_deadline)
        if isinstance(self.connection,ssl.SSLSocket):self.connection.do_handshake()
    def log_message(self,*args):pass
    def send(self,status,data,content_type='application/json; charset=utf-8',headers=None):
        raw=service.packed(data) if content_type.startswith('application/json') else data if isinstance(data,bytes) else data.encode()
        self.send_response(status)
        for key,value in {'Content-Type':content_type,'Content-Length':str(len(raw)), 'Cache-Control':'no-store',
            'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            'Strict-Transport-Security':'max-age=86400','Connection':'close',**(headers or {})}.items():self.send_header(key,value)
        self.end_headers();self.wfile.write(raw);self.close_connection=True
    def error(self,exc):self.send(exc.status,{'error':{'code':exc.code,'message':MESSAGES.get(exc.code,exc.code)}},headers=exc.headers)
    def guards(self,auth=True):
        app=self.server.app
        if len(self.headers.get_all('Host',[]))!=1 or self.headers.get('Host') not in app.hosts:raise ApiError(403,'forbidden_host')
        origins=self.headers.get_all('Origin',[])
        if len(origins)>1 or origins and origins[0] not in app.origins:raise ApiError(403,'forbidden_origin')
        if auth:
            values=self.headers.get_all('Authorization',[])
            expected=('Bearer '+app.token).encode('utf-8')
            if len(values)!=1 or not hmac.compare_digest(values[0].encode('utf-8'),expected):raise ApiError(401,'unauthorized')
    def route(self):
        parsed=urlsplit(self.path)
        if parsed.query or parsed.fragment:raise ApiError(400,'invalid_request')
        path=parsed.path;demo=path.startswith('/api/demo/')
        return path.replace('/api/demo/','/api/',1) if demo else path,demo
    def do_GET(self):
        try:
            path,demo=self.route();self.guards(auth=path.startswith('/api/'))
            if path in ('/','/demo','/app.js','/style.css'):
                name='index.html' if path in ('/','/demo') else path[1:]
                ct='text/html; charset=utf-8' if name.endswith('.html') else 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8'
                return self.send(200,(HERE/'static'/name).read_bytes(),ct)
            app=self.server.app;scope=app.scope_for(demo)
            if path=='/api/state':return self.send(200,{'scope':scope,'model':service.MODEL,'num_ctx':8192,'rate_limit':'6 / 60 s','active':app.active})
            if path.startswith('/api/requests/'):
                return self.send(200,service.public_receipt(app.store.receipt(path.rsplit('/',1)[1],scope)))
            if path.startswith('/api/conversations/'):
                conv=app.store.conversation(path.rsplit('/',1)[1],scope)
                return self.send(200,{**conv,'turns':[service.public_receipt(t) for t in conv['turns']]})
            raise ApiError(404,'not_found')
        except ApiError as exc:self.error(exc)
        except ValueError:self.error(ApiError(404,'not_found'))
        except (BrokenPipeError,ConnectionResetError,socket.timeout):pass
    def do_POST(self):
        try:
            path,demo=self.route();self.guards()
            if path!='/api/chat':raise ApiError(404,'not_found')
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[]))!=1:raise ApiError(400,'invalid_request')
            try:length=int(self.headers.get('Content-Length'))
            except (ValueError,TypeError):raise ApiError(400,'invalid_request')
            if length<0:raise ApiError(400,'invalid_request')
            if length>MAX_BODY:raise ApiError(413,'body_too_large')
            if self.headers.get('Content-Type','').split(';')[0].strip().lower()!='application/json':raise ApiError(415,'unsupported_media_type')
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ApiError(400,'invalid_request')
            try:data=json.loads(raw)
            except (ValueError,UnicodeError):raise ApiError(400,'invalid_request')
            receipt=self.server.app.submit(data,demo)
            self.send(202,service.public_receipt(receipt),headers={'Location':('/api/demo/requests/' if demo else '/api/requests/')+receipt['request_id']})
        except ApiError as exc:self.error(exc)
        except (BrokenPipeError,ConnectionResetError):pass
        except socket.timeout:self.error(ApiError(400,'invalid_request'))
        except Exception:self.error(ApiError(500,'inference_failed'))

class Server(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    max_connection_workers=16
    connection_deadline=15
    def __init__(self,*args,**kwargs):
        self.connection_slots=threading.BoundedSemaphore(self.max_connection_workers)
        self.connections={};self.connection_guard=threading.Lock()
        super().__init__(*args,**kwargs)
    @staticmethod
    def expire_connection(request):
        # AICODE-NOTE: абсолютный watchdog закрывает только своё соединение:
        # частые небольшие fragments не продлевают TLS/headers/body deadline.
        try:request.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        request.close()
    def process_request(self,request,client_address):
        if not self.connection_slots.acquire(blocking=False):
            self.shutdown_request(request);return
        timer=threading.Timer(self.connection_deadline,self.expire_connection,args=(request,));timer.daemon=True
        with self.connection_guard:self.connections[request]=timer
        try:
            timer.start();super().process_request(request,client_address)
        except BaseException:
            self.release_connection(request);self.shutdown_request(request);raise
    def release_connection(self,request):
        with self.connection_guard:timer=self.connections.pop(request,None)
        if timer is not None:timer.cancel();self.connection_slots.release()
    def process_request_thread(self,request,client_address):
        try:super().process_request_thread(request,client_address)
        finally:self.release_connection(request)
    def server_close(self):
        with self.connection_guard:connections=list(self.connections.items())
        for request,timer in connections:
            timer.cancel();self.expire_connection(request)
        super().server_close()
    def handle_error(self,request,client_address):
        print(json.dumps({'service':'day30','status':'connection_error'}),flush=True)

def make_server(bind,port,app):
    server=Server((bind,port),Handler);server.app=app;return server

def wrap_tls(http,cert,key):
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(cert,key)
    # AICODE-NOTE: handshake в accept блокировал бы весь listener на stalled TCP.
    # Worker выполняет его после socket timeout, независимо от новых клиентов.
    http.socket=tls.wrap_socket(http.socket,server_side=True,do_handshake_on_connect=False)


def load_env(path):
    path=Path(path)
    if path.stat().st_mode & 0o077:raise ValueError('env_must_be_mode_0600')
    values={}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        key,sep,value=line.partition('=')
        if not sep or not key.startswith('DAY30_'):raise ValueError('invalid_env_line')
        values[key]=value
    return values

def main():
    parser=argparse.ArgumentParser(description='Отдельный private Day30 HTTPS service')
    parser.add_argument('--env',default=str(HERE/'private/.env'));parser.add_argument('--scope',choices=('all','assignment'))
    args=parser.parse_args();env=load_env(args.env);bind=env['DAY30_BIND'];port=int(env.get('DAY30_PORT','8080'))
    ip=ipaddress.ip_address(bind)
    if ip.version!=4 or ip.is_unspecified or not ip.is_private:raise ValueError('explicit_private_ipv4_required')
    if not 1024<=port<=65535:raise ValueError('invalid_private_port')
    key=Path(env['DAY30_KEY']);cert=Path(env['DAY30_CERT'])
    if key.stat().st_mode & 0o077:raise ValueError('tls_key_must_be_0600')
    scope=args.scope or env.get('DAY30_SCOPE','all')
    engine=service.Engine.real(env['DAY30_INDEX']);store=service.Store(Path(env['DAY30_PRIVATE'])/'state')
    hosts={f'{bind}:{port}',f'localhost:{port}',f'127.0.0.1:{port}'};origins={'https://'+h for h in hosts}
    app=Application(engine,store,env['DAY30_TOKEN'],hosts,origins,scope)
    http=make_server(bind,port,app);wrap_tls(http,cert,key)
    def stop(*_):threading.Thread(target=http.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    print(json.dumps({'service':'day30','bind':bind,'port':port,'scope':scope,'status':'started'}),flush=True)
    try:http.serve_forever()
    finally:http.server_close();app.wait_workers()

if __name__=='__main__':main()
