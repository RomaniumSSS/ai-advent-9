"""Absolute deadline и bounded workers: настоящие fragmented TCP/HTTP, без inference."""
import http.client
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,service
import test_service as fixture

class LimitedServer(server.Server):
    max_connection_workers=2
    connection_deadline=.45

class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=server.Application(fixture.StubEngine(),service.Store(Path(self.tmp.name)/'state'),'test-secret')
        self.http=LimitedServer(('127.0.0.1',0),server.Handler);self.http.app=self.app;self.port=self.http.server_address[1]
        self.app.hosts={f'127.0.0.1:{self.port}'};self.app.origins={f'http://127.0.0.1:{self.port}'}
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();self.sockets=[]
    def tearDown(self):
        for s in self.sockets:s.close()
        self.http.shutdown();self.http.server_close();self.thread.join();self.app.wait_workers();self.tmp.cleanup()
    def connection(self):
        s=socket.create_connection(('127.0.0.1',self.port),timeout=1);s.settimeout(.15);self.sockets.append(s);return s
    def good(self):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=1)
        try:
            c.request('GET','/api/state',headers={'Authorization':'Bearer test-secret'});r=c.getresponse();r.read();return r.status
        finally:c.close()
    def drip_closed(self,s,initial):
        s.sendall(initial);started=time.monotonic();closed=False
        # Каждый байт приходит чаще idle timeout, но общий deadline уже пройдёт.
        while time.monotonic()-started<1:
            try:
                s.sendall(b'x');data=s.recv(1)
                if not data:closed=True;break
            except socket.timeout:pass
            except (ConnectionResetError,BrokenPipeError,OSError):closed=True;break
            time.sleep(.04)
        return closed,time.monotonic()-started
    def test_fragmented_headers_absolute_deadline_and_release(self):
        s=self.connection();closed,elapsed=self.drip_closed(s,b'GET /api/state HTTP/1.1\r\nX-Slow: ')
        self.assertTrue(closed,'fragmented headers survived absolute deadline')
        self.assertLess(elapsed,.9);self.assertEqual(self.good(),200)
    def test_fragmented_body_absolute_deadline_before_inference(self):
        s=self.connection();header=(f'POST /api/chat HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\nAuthorization: Bearer test-secret\r\nContent-Type: application/json\r\nContent-Length: 500\r\n\r\n').encode()
        closed,elapsed=self.drip_closed(s,header)
        self.assertTrue(closed,'fragmented body survived absolute deadline');self.assertLess(elapsed,.9)
        self.assertEqual(len(self.app.accepted),0);self.assertEqual(self.good(),200)
    def test_capacity_rejects_immediately_and_recovers(self):
        first=self.connection();first.sendall(b'GET /api/state HTTP/1.1\r\nX-Slow: ')
        second=self.connection();second.sendall(b'GET /api/state HTTP/1.1\r\nX-Slow: ')
        time.sleep(.07);extra=self.connection();extra.sendall(b'GET /api/state HTTP/1.1\r\n')
        try:closed=extra.recv(1)==b''
        except ConnectionResetError:closed=True
        except socket.timeout:closed=False
        self.assertTrue(closed,'capacity overflow connection was retained')
        time.sleep(.55);self.assertEqual(self.good(),200)
    def test_completed_and_malformed_connections_release_capacity(self):
        for _ in range(6):self.assertEqual(self.good(),200)
        malformed=self.connection();malformed.sendall(b'BAD\r\n\r\n')
        try:malformed.recv(1024)
        except ConnectionResetError:pass
        time.sleep(.05);self.assertEqual(self.good(),200)

if __name__=='__main__':unittest.main()
