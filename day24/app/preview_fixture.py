"""Только ручная проверка UI: синтетические поиск и генерация, отдельный временный каталог."""
import tempfile
from pathlib import Path
from service import Service
from test_mentor import synthetic, auth, raw, VALID
from web import make_server

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);auth(root)
        service=Service(root,synthetic,lambda *_:raw(VALID),lambda _:'synthetic-key',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        server=make_server(8051,service=service)
        print('СИНТЕТИЧЕСКАЯ ПРОВЕРКА UI http://127.0.0.1:8051; cloud=0',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()
if __name__=='__main__':main()
