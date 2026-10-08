"""Офлайн-проверки: никаких настоящих HTTP-вызовов."""
import json
import hashlib
import sqlite3
import fcntl
import os
import sys
from unittest.mock import patch
from pathlib import Path
import tempfile
import rag


def fails(fn):
    try:
        fn()
    except (ValueError, RuntimeError):
        return
    raise AssertionError('expected failure')


def index_checks():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        generation = root/'abc123'
        generation.mkdir()
        (root/'current.json').write_text(json.dumps({'generation':'abc123'}))
        dbpath = generation/'structure.db'
        unit = [1.0] + [0.0]*1023
        model = {'model':rag.EMBED_MODEL, 'digest':'fixture-digest', 'options':rag.OPTIONS, 'truncate':False}
        identity = {'config':{'model':model}}
        metadata = {'chunk_id':'c1', 'document_id':'assignment:22', 'text':'fixture text',
                    'text_sha256':hashlib.sha256(b'fixture text').hexdigest(),
                    'provenance':'PRIVATE_PATH', 'members':['PRIVATE_AUTHOR']}
        with sqlite3.connect(dbpath) as db:
            db.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY,value TEXT)')
            db.execute('CREATE TABLE chunks (chunk_id TEXT PRIMARY KEY,metadata_json TEXT,vector_json TEXT)')
            db.execute('INSERT INTO metadata VALUES (?,?)', ('identity',json.dumps(identity)))
            db.execute('INSERT INTO chunks VALUES (?,?,?)', ('c1',json.dumps(metadata),json.dumps(unit)))
        original_connect = sqlite3.connect
        observed=[]
        def readonly_connect(path, **kwargs):
            assert str(path).endswith('?mode=ro') and kwargs.get('uri') is True
            connection = original_connect(path, **kwargs)
            try:
                connection.execute('CREATE TABLE forbidden (x)')
            except sqlite3.OperationalError:
                observed.append(True)
            else:
                raise AssertionError('index connection permits writing')
            return connection
        with patch.object(rag.sqlite3, 'connect', readonly_connect):
            _, chunks=rag.load_index(root,'structure')
        assert observed == [True] and chunks[0]['text']=='fixture text'
        cases={'cases':[{'id':'Q01', 'question':'QUESTION', 'expected_facts':['SECRET_EXPECTED'], 'expected_document_ids':['SECRET_DOCUMENT']}]}
        calls=[]
        def mock_request(url, payload=None, key=None):
            calls.append((url,payload))
            if url.endswith('/api/tags'):
                return {'models':[{'name':rag.EMBED_MODEL,'digest':'fixture-digest'}]}
            if url.endswith('/api/show'):
                return {}
            assert url.endswith('/api/embed')
            assert payload['truncate'] is False and payload['options']==rag.OPTIONS
            assert payload['input'].endswith('Query:QUESTION')
            return {'embeddings':[unit]}
        with patch.object(rag,'request',mock_request):
            prepared=rag.prepare(root,cases,'http://127.0.0.1:11434')
        msgs=json.dumps(prepared['cases'][0]['messages'])
        for private in ('SECRET_EXPECTED','SECRET_DOCUMENT','PRIVATE_PATH','PRIVATE_AUTHOR'):
            assert private not in msgs
        assert 'fixture text' in msgs
        def remote_request(url, payload=None, key=None):
            if url.endswith('/api/show'):
                return {'remote_host':'https://remote.invalid'}
            return mock_request(url,payload,key)
        with patch.object(rag,'request',remote_request):
            fails(lambda:rag.prepare(root,cases,'http://127.0.0.1:11434'))
        def wrong_digest(url,payload=None,key=None):
            return {'models':[{'name':rag.EMBED_MODEL,'digest':'different'}]}
        with patch.object(rag,'request',wrong_digest):
            fails(lambda:rag.prepare(root,cases,'http://127.0.0.1:11434'))
        with original_connect(dbpath) as db:
            broken_identity=json.loads(json.dumps(identity))
            broken_identity['config']['model']['options']['num_ctx']=4096
            db.execute('UPDATE metadata SET value=? WHERE key=?',(json.dumps(broken_identity),'identity'))
        fails(lambda:rag.load_index(root,'structure'))
        with original_connect(dbpath) as db:
            db.execute('UPDATE metadata SET value=? WHERE key=?',(json.dumps(identity),'identity'))
            broken_metadata=dict(metadata,text='tampered')
            db.execute('UPDATE chunks SET metadata_json=?',(json.dumps(broken_metadata),))
        fails(lambda:rag.load_index(root,'structure'))


def lock_and_plain_checks():
    prepared={'model':rag.MODEL,'cases':[]}
    with tempfile.TemporaryDirectory() as directory:
        with open(Path(directory)/'run.lock','w') as held:
            fcntl.flock(held,fcntl.LOCK_EX | fcntl.LOCK_NB)
            fails(lambda:rag.evaluate(prepared,directory,'test',.10,{'prompt':0,'completion':0}))
        output=Path(directory)/'prepared.json'
        run=Path(directory)/'answers'
        def fake_evaluate(data,output_dir,key,budget):
            assert data['modes']==['plain']
            assert data['cases'][0]['messages']=={'plain':rag.messages('question')}
            rag.save(Path(output_dir)/'single-plain.json',{'response':{'choices':[{'message':{'content':'answer'}}]}})
            return {'entries':[]}
        argv=['rag.py','ask','--mode','plain','--question','question','--output',str(output),'--output-dir',str(run)]
        with patch.object(sys,'argv',argv), patch.object(rag,'prepare',side_effect=AssertionError('plain requested embedding')), patch.object(rag,'request',side_effect=AssertionError('unexpected HTTP')), patch.object(rag,'key_from_env',return_value='test'), patch.object(rag,'evaluate',side_effect=fake_evaluate), patch('builtins.print'):
            rag.main()
        assert output.exists()


def main():
    index_checks()
    lock_and_plain_checks()
    chunks = [{'chunk_id':'b','document_id':'d','text':'B','vector':[0,1]}, {'chunk_id':'a','document_id':'d','text':'A','vector':[1,0]}]
    assert [c['chunk_id'] for c in rag.rank([1,0], chunks, 2)] == ['a','b']
    for bad in ([0,0], [float('nan'),0], [2,0], [True,0], [1]):
        fails(lambda: rag.vector(bad,2))
    context, selected = rag.select_context('q', [dict(chunks[0],score=1,text='я'*10000), dict(chunks[1],score=0)])
    assert len(selected) == 1 and selected[0]['text'] == 'A' and len(context.encode()) <= 18000
    assert rag.messages('q')[0] == rag.messages('q','context')[0]
    assert 'context' not in rag.messages('q')[1]['content']
    assert rag.payload(rag.messages('q'))['provider'] == {'only':['deepinfra/fp8'],'allow_fallbacks':False}
    fails(lambda: rag.loopback('https://example.com'))
    pricing = {'prompt':.14/1e6,'completion':.42/1e6}
    prepared = {'model':rag.MODEL,'cases':[{'id':'Q01','messages':{'plain':rag.messages('q'),'rag':rag.messages('q','context')}}]}
    response = {'model':rag.MODEL,'provider':'DeepInfra','choices':[{'finish_reason':'stop','message':{'content':'answer'}}],'usage':{'cost':.001}}
    with tempfile.TemporaryDirectory() as directory:
        calls=[]
        def dispatch(*args):
            ledger=json.loads((Path(directory)/'ledger.json').read_text())
            assert ledger['entries'][-1]['status'] == 'inflight'
            calls.append(args)
            return response
        ledger=rag.evaluate(prepared,directory,'test',.10,pricing,dispatch,max_new_calls=1)
        assert len(calls)==1 and len(ledger['entries'])==1
        rag.evaluate(prepared,directory,'test',.10,pricing,dispatch)
        assert len(calls)==2
        rag.evaluate(prepared,directory,'test',.10,pricing,dispatch)
        assert len(calls)==2
        assert (Path(directory)/'ledger.json').stat().st_mode & 0o777 == 0o600
    with tempfile.TemporaryDirectory() as directory:
        fails(lambda:rag.evaluate(prepared,directory,'test',.00001,pricing,lambda *a:response))
        assert not (Path(directory)/'ledger.json').exists()
    with tempfile.TemporaryDirectory() as directory:
        unknown=dict(response,usage={})
        fails(lambda:rag.evaluate(prepared,directory,'test',.10,pricing,lambda *a:unknown))
        ledger=json.loads((Path(directory)/'ledger.json').read_text())
        assert ledger['entries'][0]['status']=='unknown_cost' and ledger['entries'][0]['cost'] > 0
        fails(lambda:rag.evaluate(prepared,directory,'test',.10,pricing,lambda *a:response))
    with tempfile.TemporaryDirectory() as directory:
        def broken(*a):
            raise RuntimeError('ambiguous network failure')
        fails(lambda:rag.evaluate(prepared,directory,'test',.10,pricing,broken))
        fails(lambda:rag.evaluate(prepared,directory,'test',.10,pricing,lambda *a:response))
        path=Path(directory)/'ledger.json'
        ledger=json.loads(path.read_text())
        ledger['entries'][0].update(review='skip_without_retry',review_reason='Проверено: ответа нет, резерв сохраняется')
        rag.save(path,ledger)
        calls=[]
        def after_review(*args):
            calls.append(args)
            return response
        resumed=rag.evaluate(prepared,directory,'test',.10,pricing,after_review)
        assert len(calls)==1 and resumed['entries'][0]['status']=='failed_ambiguous'
        assert resumed['entries'][0]['cost']==resumed['entries'][0]['reserve']
        assert resumed['entries'][1]['mode']=='rag' and resumed['entries'][1]['status']=='completed'
        resumed['entries'][0]['review']='retry_authorized'
        resumed['entries'][0]['review_reason']='Пользователь разрешил повтор; резерв старой попытки остаётся'
        rag.save(path,resumed)
        retried=rag.evaluate(prepared,directory,'test',.10,pricing,after_review)
        assert len(calls)==2 and len(retried['entries'])==3
        assert retried['entries'][-1]['mode']=='plain' and retried['entries'][-1]['attempt']==2
        assert retried['entries'][0]['cost']==retried['entries'][0]['reserve']
        rag.evaluate(prepared,directory,'test',.10,pricing,after_review)
        assert len(calls)==2
    fails(lambda:rag.validate_answer(dict(response,provider='Other')))
    fails(lambda:rag.validate_answer(dict(response,choices=[{'finish_reason':'length'}])))
    print('ok: ranking, vectors, context, prompts, provider, budget, checkpoint, resume, unknown cost, network failure, readonly SQLite, digest/config/text integrity, privacy, remote rejection, lock, plain CLI')

if __name__ == '__main__':
    main()
