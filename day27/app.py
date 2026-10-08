"""Самостоятельный локальный веб-чат; только стандартная библиотека Python."""
import argparse
import json
from pathlib import Path
import socket
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = 'qwen3:8b'
OLLAMA = 'http://127.0.0.1:11434'
STATIC = Path(__file__).with_name('static')
MAX_BODY = 65536
GENERATION_LOCK = threading.Lock()

class ProviderError(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError('Локальный сервер модели попытался перенаправить запрос.')

def local_opener():
    # AICODE-NOTE: системный proxy не должен отправлять локальные сообщения наружу.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

def validate_request(body):
    if not isinstance(body, dict) or set(body) != {'messages'}:
        raise ValueError('Ожидается объект с полем messages.')
    messages = body['messages']
    if not isinstance(messages, list) or not messages or len(messages) > 17 or len(messages) % 2 != 1:
        raise ValueError('История должна содержать завершённые пары и новый вопрос; максимум 17 сообщений.')
    total = 0
    for index, item in enumerate(messages):
        if not isinstance(item, dict) or set(item) != {'role','content'}:
            raise ValueError('Сообщение должно содержать role и content.')
        if item['role'] != ('user' if index % 2 == 0 else 'assistant'):
            raise ValueError('Роли истории должны чередоваться, начиная с user.')
        content = item['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError('Текст сообщения не может быть пустым.')
        total += len(content)
    if total > 12000:
        raise ValueError('История слишком длинная (максимум 12000 символов). Начните новый чат.')
    return messages

def provider_payload(messages):
    return {'model': MODEL, 'messages': messages, 'stream': True, 'think': False,
            'options': {'num_ctx': 4096, 'num_predict': 384}}

def parse_provider_stream(response):
    content_seen = False
    for raw in response:
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise ProviderError('Модель вернула повреждённый поток.') from error
        if not isinstance(item, dict):
            raise ProviderError('Модель вернула неверный формат ответа.')
        if item.get('error'):
            raise ProviderError('Ошибка локальной модели: ' + str(item['error'])[:400])
        message = item.get('message', {})
        if not isinstance(message, dict) or not isinstance(message.get('content',''), str):
            raise ProviderError('Модель вернула неверный формат сообщения.')
        content = message.get('content', '')
        if content:
            content_seen = True
            yield {'type':'delta', 'content':content}
        if item.get('done') is True:
            if not content_seen:
                raise ProviderError('Модель завершила запрос без текста ответа.')
            yield {'type':'done', **{key:item.get(key) for key in (
                'done_reason','total_duration','load_duration','prompt_eval_count',
                'prompt_eval_duration','eval_count','eval_duration')}}
            return
    raise ProviderError('Поток модели оборвался до подтверждения завершения.')

def chat_events(messages):
    request = urllib.request.Request(OLLAMA+'/api/chat',
        data=json.dumps(provider_payload(messages), ensure_ascii=False).encode(),
        headers={'Content-Type':'application/json'})
    try:
        with local_opener().open(request, timeout=300) as response:
            yield from parse_provider_stream(response)
    except urllib.error.HTTPError as error:
        raise ProviderError(f'Локальная модель недоступна (HTTP {error.code}). Проверьте Ollama и модель {MODEL}.') from error
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as error:
        raise ProviderError('Нет ответа от локальной модели. Проверьте, что Ollama запущена; таймаут генерации — 300 секунд.') from error

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Сообщения пользователей не попадают в журналы сервера.
        pass

    def json_response(self, code, body):
        encoded = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(encoded)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == '/api/health':
            try:
                with local_opener().open(OLLAMA+'/api/tags', timeout=3) as response:
                    tags = json.load(response)
                available = any(m.get('name') == MODEL for m in tags.get('models', []))
                self.json_response(200, {'ready':available,'model':MODEL,
                    'message':'Модель готова' if available else f'В Ollama нет модели {MODEL}'})
            except (OSError, ValueError, ProviderError, AttributeError, TypeError):
                self.json_response(200, {'ready':False,'model':MODEL,'message':'Ollama недоступна'})
            return
        filenames = {'/':'index.html', '/app.js':'app.js', '/style.css':'style.css'}
        filename = filenames.get(self.path)
        if filename is None:
            self.json_response(404, {'error':'Страница не найдена.'}); return
        raw = (STATIC / filename).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html':'text/html','js':'text/javascript','css':'text/css'}[filename.rsplit('.',1)[1]]+'; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        self.end_headers(); self.wfile.write(raw)

    def do_POST(self):
        if self.path != '/api/chat':
            self.json_response(404, {'error':'Маршрут не найден.'}); return
        expected = f'http://127.0.0.1:{self.server.server_port}'
        if self.headers.get('Origin') not in (None, expected):
            self.json_response(403, {'error':'Запрос разрешён только из локального приложения.'}); return
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            self.json_response(415, {'error':'Требуется application/json.'}); return
        try:
            length = int(self.headers.get('Content-Length','0'))
            if length < 1 or length > MAX_BODY:
                raise ValueError('Недопустимый размер запроса.')
            messages = validate_request(json.loads(self.rfile.read(length)))
        except (ValueError, UnicodeError) as error:
            self.json_response(400, {'error':str(error)}); return
        if not GENERATION_LOCK.acquire(blocking=False):
            self.json_response(409, {'error':'Модель уже отвечает. Дождитесь завершения.'}); return
        try:
            self.send_response(200)
            self.send_header('Content-Type','application/x-ndjson; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Connection','close')
            self.end_headers()
            self.close_connection = True
            try:
                for event in chat_events(messages):
                    self.write_event(event)
            except ProviderError as error:
                self.write_event({'type':'error','error':str(error)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            GENERATION_LOCK.release()

    def write_event(self, event):
        self.wfile.write((json.dumps(event, ensure_ascii=False)+'\n').encode())
        self.wfile.flush()

def make_server(port=8067):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Локальный чат с Ollama')
    parser.add_argument('--port', type=int, default=8067)
    args = parser.parse_args()
    with make_server(args.port) as server:
        print(f'Локальный чат: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
