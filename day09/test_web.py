"""Настоящий локальный HTTP и SQLite, но подставная модель: повторы и перезапуск."""
import json
import tempfile
import threading
import sqlite3
from unittest.mock import patch
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import web
from test_compression import Fake

def main():
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/'web.db'
        web.build_panels(db,{'left':'l','right':'r'})
        clients={side:Fake() for side in web.PANELS}
        for side,a in web.PANELS.items(): a.client=clients[side]
        server=ThreadingHTTPServer(('127.0.0.1',0),web.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        root=f'http://127.0.0.1:{server.server_port}'
        def post(payload,origin=None,path='/api/chat'):
            headers={'Content-Type':'application/json'}
            if origin:headers['Origin']=origin
            req=Request(root+path,data=json.dumps(payload).encode(),headers=headers)
            try:
                with urlopen(req) as response:return response.status,json.load(response)
            except HTTPError as e:return e.code,json.load(e)
        try:
            payload={'panel':'left','text':'Роман','request_id':'req-1'}
            code,first=post(payload);assert code==200
            assert first['state']['turns']==1
            code,again=post(payload);assert code==200 and again['text']==first['text']
            assert len(clients['left'].calls)==1
            assert post({**payload,'text':'другой вопрос'})[0]==409
            assert post({**payload,'request_id':None})[0]==400
            assert post({**payload,'panel':{}})[0]==400
            assert post({**payload,'text':'\ud800'})[0]==400
            assert post({**payload,'request_id':'req-2'},'https://example.com')[0]==403
            assert len(clients['left'].calls)==1
            web.build_panels(db,{'left':'l','right':'r'})
            for side,a in web.PANELS.items():a.client=clients[side]
            assert post(payload)[0]==200 and len(clients['left'].calls)==1
            assert web.PANELS['right'].history==[]
            store=web.PANELS['left'].store
            store.begin_request('interrupted','x')
            assert post({'panel':'left','text':'x','request_id':'interrupted'})[0]==409
            assert len(clients['left'].calls)==1
            web._locks['left'].acquire()
            try:assert post({**payload,'request_id':'busy'})[0]==409
            finally:web._locks['left'].release()
            with patch.object(store, 'begin_request', side_effect=sqlite3.OperationalError('disk unavailable')):
                assert post({**payload,'request_id':'disk-error'})[0]==409
            previous=web.PANELS['left'].history
            with patch.object(store, 'clear', side_effect=sqlite3.OperationalError('disk unavailable')):
                assert post({'panel':'left'},path='/api/reset')[0]==503
            assert web.PANELS['left'].history==previous
            assert post(payload)[0]==200 and len(clients['left'].calls)==1
            print('ok: один API-вызов при повторе HTTP, повтор после восстановления, конфликт ID, незавершённый запрос, валидация, Origin, изоляция, занятая панель')
        finally:
            server.shutdown();server.server_close();thread.join()
if __name__=='__main__':main()
