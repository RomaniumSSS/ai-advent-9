"""Локальный DevHelper на stdlib HTTP, тот же Assistant, что в CLI."""
from __future__ import annotations
import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from day31.config import ROOT, add_arguments, build_assistant


def make_server(app, port=8071):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def respond(self,status,body,content_type='application/json; charset=utf-8'):
            raw=json.dumps(body,ensure_ascii=False).encode() if isinstance(body,dict) else body
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers(); self.wfile.write(raw)

        def local(self):
            authority=f'127.0.0.1:{self.server.server_address[1]}'
            return self.headers.get('Host')==authority and self.headers.get('Origin',f'http://{authority}')==f'http://{authority}'

        def do_GET(self):
            if not self.local():
                return self.respond(403,{'error':'Доступ разрешён только с локального интерфейса'})
            if self.path=='/api/config':
                return self.respond(200,{'model':app.provider.model,'provider':app.provider.provider,'git_root':str(app.mcp.repo),'live':app.provider.model!='offline-extract','token':token})
            routes={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            if self.path not in routes:
                return self.respond(404,{'error':'Маршрут не найден'})
            name,mime=routes[self.path]
            return self.respond(200,(ROOT/'web'/name).read_bytes(),mime)

        def do_POST(self):
            if not self.local() or not secrets.compare_digest(self.headers.get('X-DevHelper-Token',''),token):
                return self.respond(403,{'error':'Некорректный локальный запрос'})
            if self.path!='/api/answer':
                return self.respond(404,{'error':'Маршрут не найден'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.respond(415,{'error':'Ожидается application/json'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=20000:
                    raise ValueError('Размер запроса')
                value=json.loads(self.rfile.read(length))
                if not isinstance(value,dict) or set(value)!={'question'} or not isinstance(value['question'],str):
                    raise ValueError('Контракт запроса')
            except (ValueError,UnicodeError):
                return self.respond(400,{'error':'Нужен JSON с единственным строковым полем question'})
            try:
                result=app.answer(value['question'])
            except Exception:
                return self.respond(500,{'error':'Ошибка обработки запроса'})
            return self.respond(200,result.to_dict())

    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument('--port',type=int,default=8071)
    args=parser.parse_args()
    try:
        app=build_assistant(args)
        server=make_server(app,args.port)
    except (ValueError,OSError) as error:
        parser.error(str(error))
    print(f'DevHelper: http://127.0.0.1:{server.server_address[1]} · {app.provider.model} / {app.provider.provider}',flush=True)
    print(f'Git-root: {app.mcp.repo}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=='__main__':
    main()
