"""Независимый loopback UI и изолированные серверные demo-сеансы."""
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
import time
import uuid
from domain import ROOT, load_crm, retrieve, string, clarification
from mcp_client import read_context
from model import answer, ModelResponseError
from budget import Budget

class Application:
    def __init__(self, mode='mock', budget=None):
        self.mode, self.budget = mode, budget
        self.sessions = {}
        self.lock = threading.Lock()
    def session(self, token):
        with self.lock:
            if token not in self.sessions:
                token = secrets.token_urlsafe(32)
                self.sessions[token] = 'alice'
            return token, self.sessions[token]
    def select(self, token, user_id):
        if user_id not in {u['id'] for u in load_crm()['users']}: raise ValueError('Неизвестный demo-пользователь')
        with self.lock: self.sessions[token] = user_id
    def catalog(self, user_id):
        crm=load_crm()
        return {'users':[{'id':u['id'],'name':u['name']} for u in crm['users']], 'selected_user':user_id,'tickets':[{'id':t['id'],'subject':t['subject']} for t in crm['tickets'] if t['user_id']==user_id], 'mode':self.mode}
    def ask(self, user_id, payload):
        if not isinstance(payload,dict) or set(payload) != {'ticket_id','question'}: raise ValueError('Нужны только ticket_id и question')
        ticket_id=string(payload['ticket_id'],'ticket_id',50)
        question=string(payload['question'],'question',2000)
        run_id=str(uuid.uuid4()); start=time.monotonic()
        context,mcp=read_context(user_id,ticket_id)
        decision = clarification(question, context['ticket'])
        retrieval_ticket = {**context['ticket'], 'events':[]} if decision and decision[0] == 'bounded_support' else context['ticket']
        sources=retrieve(question,retrieval_ticket)
        if not sources and decision is None:
            decision = ('insufficient_sources', 'В базе нет подходящего источника. Уточните текст ошибки; причина пока не подтверждена.')
        if decision:
            kind, text = decision
            result = {'answer':text, 'source_ids':[]}
            model = {'mode':self.mode, 'response_kind':kind, 'model':None, 'provider':None, 'usage':None, 'cost_usd':None}
        else:
            result,model=answer(question,context,sources,run_id,self.mode,self.budget)
            model['response_kind'] = 'model_answer'
        return {**result,'context':context,'sources':sources,'trace':{'run_id':run_id,'mcp':mcp,'retrieval_ids':[s['id'] for s in sources], 'elapsed_seconds':round(time.monotonic()-start,3),**model}}

def make_server(port=8133, application=None):
    app=application or Application()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,status,value,token=None,html=False):
            raw=value if html else json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if token: self.send_header('Set-Cookie',f'teamdesk={token}; HttpOnly; SameSite=Strict; Path=/')
            self.end_headers(); self.wfile.write(raw)
        def identity(self):
            cookie=SimpleCookie(); cookie.load(self.headers.get('Cookie',''))
            return app.session(cookie['teamdesk'].value if 'teamdesk' in cookie else None)
        def do_GET(self):
            token,user=self.identity()
            if self.path=='/': self.send(200,(ROOT/'static/index.html').read_bytes(),token,True)
            elif self.path=='/api/session': self.send(200,app.catalog(user),token)
            else: self.send(404,{'error':'Не найдено'})
        def do_POST(self):
            if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                self.send(403,{'error':'Недопустимый Origin'}); return
            token,user=self.identity()
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 10000: raise ValueError('Некорректный размер запроса')
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json': raise ValueError('Требуется JSON')
                payload=json.loads(self.rfile.read(length))
                if self.path=='/api/select':
                    if not isinstance(payload,dict) or set(payload)!={'user_id'}: raise ValueError('Нужен user_id')
                    app.select(token,payload['user_id']); self.send(200,app.catalog(payload['user_id']),token)
                elif self.path=='/api/ask': self.send(200,app.ask(user,payload),token)
                else: self.send(404,{'error':'Не найдено'},token)
            except ModelResponseError as exc:
                self.send(502,{'error':'Ошибка модели. Ответ не сформирован.', 'run_id':exc.evidence['run_id'], 'model_error':exc.evidence},token)
            except PermissionError as exc: self.send(403,{'error':str(exc)},token)
            except (ValueError,TypeError,KeyError) as exc: self.send(400,{'error':str(exc)},token)
            except Exception: self.send(502,{'error':'Ошибка MCP/модели. Ответ не сформирован.'},token)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8133); parser.add_argument('--live',action='store_true'); parser.add_argument('--budget-ledger')
    args=parser.parse_args()
    if args.live and not args.budget_ledger: parser.error('--live требует --budget-ledger')
    app=Application('live' if args.live else 'mock',Budget(args.budget_ledger) if args.live else None)
    server=make_server(args.port,app)
    print(f'TeamDesk http://127.0.0.1:{server.server_port} mode={app.mode}',flush=True)
    server.serve_forever()
