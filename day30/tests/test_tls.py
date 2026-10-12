"""Реальный TLS: зависший TCP-клиент не должен блокировать accept других клиентов."""
import http.client
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,service
import test_service as fixture

class TlsTests(unittest.TestCase):
    def test_stalled_tcp_does_not_block_authenticated_tls(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);config=root/'openssl.cnf';cert=root/'cert.pem';key=root/'key.pem'
            config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=v3\nprompt=no\n[dn]\nCN=localhost\n[v3]\nsubjectAltName=IP:127.0.0.1,DNS:localhost\nbasicConstraints=critical,CA:TRUE\n')
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-config',str(config),'-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            app=server.Application(fixture.StubEngine(),service.Store(root/'state'),'test-secret')
            listener=server.make_server('127.0.0.1',0,app);port=listener.server_address[1]
            app.hosts={f'127.0.0.1:{port}'};app.origins={f'https://127.0.0.1:{port}'}
            listener.connection_deadline=.45
            server.wrap_tls(listener,cert,key)
            thread=threading.Thread(target=listener.serve_forever,daemon=True);thread.start()
            stalled=socket.create_connection(('127.0.0.1',port));conn=None
            try:
                conn=http.client.HTTPSConnection('127.0.0.1',port,timeout=2,context=ssl.create_default_context(cafile=str(cert)))
                conn.request('GET','/api/state',headers={'Authorization':'Bearer test-secret'})
                response=conn.getresponse();self.assertEqual(response.status,200);response.read()
                import time
                time.sleep(.6);stalled.settimeout(.3)
                self.assertEqual(stalled.recv(1),b'', 'TLS worker survived absolute deadline')
            finally:
                stalled.close()
                if conn:conn.close()
                listener.shutdown();listener.server_close();thread.join();app.wait_workers()

if __name__=='__main__':unittest.main()
