"""Локальный HTTP-сервер: явные маршруты, без файлового доступа к private."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlsplit
from service import Service
from common import key_from_env
from search import PUBLIC_DOCUMENTS

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,status,data,kind='application/json'):
        body=data.encode() if isinstance(data,str) else json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def local(self):
        return self.headers.get('Host')==self.server.address
    def chat_visible(self,chat):
        return not self.server.public_only or chat.get('scope')=='public'
    def visible(self,item):
        if not self.server.public_only:return bool(item)
        if not item or item.get('scope')!='public' or item.get('historical'):return False
        trace=item.get('search',{}).get('trace',{})
        materials=trace.get('candidates',[])+trace.get('selected',[])+trace.get('removed',[])+item.get('generation',{}).get('transmitted_chunks',[])
        return all(c.get('document_id') in PUBLIC_DOCUMENTS for c in materials)
    def do_GET(self):
        if not self.local(): return self.reply(403,{'error':'invalid_host'})
        route=self.path.split('?',1)[0]
        if route in ('/','/app.js','/style.css'):
            name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[route]
            kind={'/':'text/html','/app.js':'text/javascript','/style.css':'text/css'}[route]
            content=(Path(__file__).parent/name).read_text()
            if route=='/' and self.server.public_only:
                content=content.replace('<option value="all">Весь мой корпус</option>','').replace('Локальное приложение · Источники можно открыть и проверить','Публичный корпус: условие дня 18 · тот же путь поиска и проверки').replace('<header>','<header><p class="public-banner">Публичный корпус: условие дня 18</p>').replace('<textarea id="question"','<div class="examples"><button type="button" class="example-question">Какие требования у задания дня 18?</button><button type="button" class="example-question">Что должен сохранять и возвращать планировщик из задания 18?</button></div><textarea id="question"')
            return self.reply(200,content,kind)
        if route=='/api/chats':
            return self.reply(200, [c for c in self.server.service.chats() if self.chat_visible(c)])
        if route.startswith('/api/chat/'):
            try:
                chat_id=route.removeprefix('/api/chat/')
                chat=self.server.service.chat(chat_id)
                if not self.chat_visible(chat):return self.reply(404, {'error':'not_found'})
                history=[item for item in self.server.service.history(chat_id) if self.visible(item)]
                return self.reply(200, {'chat':chat, 'messages':self.server.service.messages_from_history(history),
                                       'history':history})
            except ValueError:return self.reply(404, {'error':'not_found'})
        if route=='/api/state':
            cloud=self.server.service.cloud_state()
            if self.server.public_only:cloud['scopes']=[s for s in cloud['scopes'] if s=='public']
            return self.reply(200,{'token':self.server.token,'chats':[c for c in self.server.service.chats() if self.chat_visible(c)],'cloud':cloud,'public_only':self.server.public_only,'test_fixture':getattr(self.server,'test_fixture',False),
                                   'test_metrics':getattr(self.server,'test_metrics',lambda:None)()})
        if route.startswith('/api/result/'):
            try:
                chat_id=parse_qs(urlsplit(self.path).query).get('chat_id', [''])[0]
                chat=self.server.service.chat(chat_id)
                if not self.chat_visible(chat):return self.reply(404, {'error':'not_found'})
                item=self.server.service.get(chat_id,route.removeprefix('/api/result/'))
                return self.reply(200 if self.visible(item) else 404,item if self.visible(item) else {'error':'not_found'})
            except ValueError: return self.reply(400,{'error':'invalid_id'})
        return self.reply(404,{'error':'not_found'})
    def do_POST(self):
        if not self.local() or self.headers.get('Origin')!='http://'+self.server.address or self.headers.get('X-Mentor-Token')!=self.server.token:
            return self.reply(403,{'error':'invalid_origin_or_token'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=32000: raise ValueError('invalid_body_size')
            data=json.loads(self.rfile.read(length))
            if self.path=='/api/chats':
                scope=data.get('scope','all')
                if self.server.public_only and scope!='public':raise ValueError('public_scope_required')
                return self.reply(200,self.server.service.create_chat(data.get('title',''),scope))
            chat=self.server.service.chat(data['chat_id'])
            if not self.chat_visible(chat):raise ValueError('chat_not_found')
            if self.path=='/api/task-state':
                item=self.server.service.update_task_state(data['chat_id'],data['state'],data['expected_version'])
                return self.reply(200,item)
            elif self.path=='/api/task-state/clear':
                return self.reply(200,self.server.service.clear_task_state(data['chat_id'],data['expected_version']))
            elif self.path=='/api/ask':
                if self.server.public_only and data.get('scope')!='public':raise ValueError('public_scope_required')
                if self.server.public_only and (old:=self.server.service.get(data['chat_id'],data.get('id'))) and not self.visible(old):raise ValueError('result_not_found')
                item=self.server.service.ask(data['chat_id'],data['id'],data['question'],data['scope'])
                if not self.visible(item):raise ValueError('public_data_violation')
            elif self.path=='/api/feedback':
                if self.server.public_only and not self.visible(self.server.service.get(data['chat_id'],data.get('id'))):raise ValueError('result_not_found')
                item=self.server.service.feedback(data['chat_id'],data['id'],data['marks'],data['comment'])
            else: return self.reply(404,{'error':'not_found'})
            return self.reply(200,item)
        except (ValueError,KeyError,TypeError) as error:
            return self.reply(409 if str(error)=='request_in_progress' else 400,{'error':str(error) if isinstance(error,ValueError) else 'invalid_request'})
        except Exception: return self.reply(500,{'error':'storage_or_server_error'})

def make_server(port=8053,directory=None,service=None,public_only=False):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.address='127.0.0.1:'+str(server.server_port)
    server.token=secrets.token_urlsafe(32)
    server.public_only=public_only
    server.service=service or Service(directory or Path(__file__).parent/'private')
    return server

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8053);parser.add_argument('--env-file');parser.add_argument('--data-dir',type=Path,default=Path(__file__).parent/'private');parser.add_argument('--public-only',action='store_true');args=parser.parse_args()
    service=Service(args.data_dir,key_fn=lambda _:key_from_env(args.env_file))
    server=make_server(args.port,service=service,public_only=args.public_only)
    print('http://'+server.address,flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
