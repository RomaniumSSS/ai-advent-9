"""Публичный режим: server scope/history/get/feedback, общий Service; только синтетика."""
import json
from pathlib import Path
import tempfile
import threading
import urllib.error
import urllib.request
from unittest.mock import patch
from common import save
from service import Service
from test_mentor import synthetic
from web import make_server

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);s=Service(root,synthetic)
        public=s.ask('public','тест','public')
        private=s.ask('private','тест','all')
        malicious=dict(public,id='malicious',search={'trace':{'candidates':[{'document_id':'private:note'}]}})
        save(root/'result-malicious.json',malicious)
        server=make_server(0,service=s,public_only=True);threading.Thread(target=server.serve_forever,daemon=True).start();base='http://'+server.address
        state=json.load(urllib.request.urlopen(base+'/api/state'))
        assert state['public_only'] and [r['id'] for r in state['history']]==['public']
        html=urllib.request.urlopen(base).read().decode();assert 'value="all"' not in html and 'Публичный корпус: условие дня 18' in html and 'Какие требования у задания дня 18?' in html
        assert json.load(urllib.request.urlopen(base+'/api/result/public'))['scope']=='public'
        for ident in ('private','malicious'):
            try:urllib.request.urlopen(base+'/api/result/'+ident);raise AssertionError('private disclosure')
            except urllib.error.HTTPError as e:assert e.code==404
        def post(route,body):
            return urllib.request.urlopen(urllib.request.Request(base+route,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':base,'X-Mentor-Token':state['token']}))
        for route,body in [('/api/ask',{'id':'blocked','question':'тест','scope':'all'}),('/api/feedback',{'id':'private','marks':[],'comment':'no'})]:
            try:post(route,body);raise AssertionError('private mutation')
            except urllib.error.HTTPError as e:assert e.code==400
        assert not s.get('blocked') and not s.get('private')['feedback']
        with post('/api/ask',{'id':'newpublic','question':'тест','scope':'public'}) as response:assert json.load(response)['scope']=='public'
        server.shutdown();server.server_close()
    print('PASS public-only: filtered history/get, private/unsafe snapshots denied, all-scope ask and private feedback blocked, DOM public banner/options; cloud=0')
if __name__=='__main__':
    with patch('requests.Session.request',side_effect=AssertionError('offline network forbidden')):main()
