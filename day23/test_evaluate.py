"""Офлайн: реальные HTTP не выполняются; ответы транспорта подставлены."""
import json
from pathlib import Path
import tempfile
import requests
from common import MODEL, messages
from evaluate import evaluate

PRICING={'prompt':.14/1e6,'completion':.42/1e6}

def answer(cost=.001):
    return {'model':MODEL,'provider':'DeepInfra','choices':[{'finish_reason':'stop','message':{'content':'ответ'}}],'usage':{'cost':cost}}

def prepared(q='q'):
    return {'model':MODEL,'modes':['A'],'cases':[{'id':'Q1','messages':{'A':messages(q)}}]}

def expect(reason,fn):
    try:fn()
    except ValueError as e:assert str(e)==reason,(reason,str(e))
    else:raise AssertionError(reason)

def main():
    with tempfile.TemporaryDirectory() as d:
        calls=[]
        def fake(*args):
            calls.append(args)
            ledger=json.loads((Path(d)/'ledger.json').read_text())
            assert ledger['entries'][-1]['status']=='inflight'
            return answer()
        first=evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=fake)
        evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=fake)
        assert len(calls)==1 and first['entries'][0]['charged']==.001
        expect('job_payload_changed',lambda:evaluate(prepared('changed'),d,'fake',pricing=PRICING,dispatch_fn=fake))
    with tempfile.TemporaryDirectory() as d:
        calls=[]
        def retry(*args):
            calls.append(1)
            if len(calls)==1:raise requests.Timeout()
            return answer()
        ledger=evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=retry,sleep=lambda _:None)
        assert len(calls)==2 and ledger['entries'][0]['charged']==ledger['entries'][0]['reserve']
    with tempfile.TemporaryDirectory() as d:
        expect('unknown_cost_stop',lambda:evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=lambda *a:answer(None)))
        ledger=evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=lambda *a:(_ for _ in ()).throw(AssertionError()))
        assert ledger['entries'][0]['cost_unknown']
    with tempfile.TemporaryDirectory() as d:
        expect('transient_retries_exhausted',lambda:evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=lambda *a:(_ for _ in ()).throw(requests.Timeout()),max_retries=0))
        expect('explicit_recovery_required',lambda:evaluate(prepared(),d,'fake',pricing=PRICING))
    with tempfile.TemporaryDirectory() as d:
        expect('budget_exceeded',lambda:evaluate(prepared(),d,'fake',budget=.000001,pricing=PRICING,dispatch_fn=lambda *a:answer()))
    with tempfile.TemporaryDirectory() as d:
        evaluate(prepared(),d,'fake',budget=.002,pricing=PRICING,dispatch_fn=lambda *a:answer(.0018))
        video=prepared()
        video['cases'][0]['id']='video'
        expect('budget_exceeded',lambda:evaluate(video,d,'fake',budget=.002,pricing=PRICING,dispatch_fn=lambda *a:(_ for _ in ()).throw(AssertionError())))
    with tempfile.TemporaryDirectory() as d:
        evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=lambda *a:answer())
        path=Path(d)/'ledger.json'
        ledger=json.loads(path.read_text())
        ledger['entries'][0]['status']='inflight'
        path.write_text(json.dumps(ledger))
        expect('explicit_recovery_required',lambda:evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=lambda *a:(_ for _ in ()).throw(AssertionError())))
    with tempfile.TemporaryDirectory() as d:
        bad=answer(.002)
        bad['provider']='other'
        expect('fatal_response_stop',lambda:evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=lambda *a:bad))
        path=Path(d)/'ledger.json'
        ledger=json.loads(path.read_text())
        entry=ledger['entries'][0]
        assert entry['actual_cost']==entry['charged']==.002
        entry.update(recovery='skip',recovery_reason='Проверено списание')
        path.write_text(json.dumps(ledger))
        evaluate(prepared(),d,'fake',pricing=PRICING,dispatch_fn=lambda *a:(_ for _ in ()).throw(AssertionError()))
    with tempfile.TemporaryDirectory() as d:
        bad=prepared()
        bad['cases'][0]['messages']['A'][0]['content']='changed'
        expect('generator_prompt_changed',lambda:evaluate(bad,d,'fake',pricing=PRICING))
    print('ok budget: reserve before dispatch, resume, changed payload, retry reserve, unknown cost, recovery, cap')

if __name__=='__main__':main()
