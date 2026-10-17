"""Реальный loopback HTTP без API: заголовки/тело не обходят общий дедлайн."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import unittest
from urllib.request import Request
from transport import request_with_deadline, MAX_RESPONSE_BYTES

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        try:
            if self.path=='/headers':
                self.wfile.write(b'HTTP/1.1 200 OK\r\nX-Slow: ');self.wfile.flush()
                for _ in range(20):self.wfile.write(b'a');self.wfile.flush();time.sleep(.08)
                self.wfile.write(b'\r\n\r\n{}')
            else:
                self.send_response(200);self.end_headers()
                if self.path=='/large':self.wfile.write(b'x'*(MAX_RESPONSE_BYTES+1))
                elif self.path=='/body':
                    for _ in range(20):self.wfile.write(b' ');self.wfile.flush();time.sleep(.08)
                else:self.wfile.write(b'{}')
        except (BrokenPipeError,ConnectionResetError):pass

class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path,timeout):return request_with_deadline(Request(f'http://127.0.0.1:{self.server.server_port}{path}',data=b'{}'),timeout)
    def test_normal(self):
        with self.request('/normal',2) as response:self.assertEqual(response.read(),b'{}')
    def test_size(self):
        with self.assertRaisesRegex(RuntimeError,'ValueError'):self.request('/large',2)
    def test_deadlines(self):
        for path in ('/headers','/body'):
            start=time.monotonic()
            with self.subTest(path=path),self.assertRaises(TimeoutError):self.request(path,.35)
            self.assertLess(time.monotonic()-start,1.5)

if __name__=='__main__':unittest.main(verbosity=2)
