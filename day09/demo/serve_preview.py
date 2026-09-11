"""Только визуальная проверка с подставной моделью; реальных вызовов нет."""
import sys
import tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import web
from test_compression import Fake
with tempfile.TemporaryDirectory(prefix='day09-preview-') as tmp:
    web.build_panels(Path(tmp)/'preview.db',{'left':'left','right':'right'})
    for a in web.PANELS.values():
        a.client=Fake(summary='Проект «Маяк». Бюджет 1200 евро. Русский и польский языки. Онлайн-оплата исключена. Срок перенесён с 18 на 25 октября.')
        for i in range(8):a.ask('Обсуждаем проект «Маяк». '+ 'Нужно сохранить ограничения и проверить работу формы на телефоне. '*12)
    ThreadingHTTPServer(('127.0.0.1',8050),web.Handler).serve_forever()
