"""Бюджет: повторный процесс, резерв неизвестных списаний, конкурентные вызовы."""
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace as NS
from experiment import BudgetLedger, MeasuredClient, MODEL_ID

def main():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'ledger.db'
        ledger=BudgetLedger(p,0.5)
        def reserve(_):
            try: return ledger.reserve(0.1,'test')
            except RuntimeError: return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            tickets=list(pool.map(reserve,range(8)))
        assert len([t for t in tickets if t]) == 5
        assert BudgetLedger(p,0.5).report()['available'] == 0
        ledger.settle(tickets[0],0.01)
        assert abs(ledger.report()['available']-0.09)<1e-8
        ledger.settle(tickets[1],None)
        assert ledger.report()['held_for_unknown']==0.4
        try: BudgetLedger(p,1)
        except ValueError: pass
        else: raise AssertionError('бюджет незаметно вырос')
        print('ok: конкурентный резерв, восстановление, неизвестное списание, неизменность лимита')
        calls=[]
        fake=NS(chat=NS(completions=NS(create=lambda **kw: calls.append(kw))))
        small=BudgetLedger(Path(d)/'small.db',0.001)
        wrapped=MeasuredClient(fake,small,'blocked')
        wrapped.create(model=MODEL_ID,max_tokens=4000,messages=[{'role':'user','content':'x'}])
        try: wrapped.create(model=MODEL_ID,max_tokens=4000,messages=[{'role':'user','content':'x'}])
        except RuntimeError: pass
        else: raise AssertionError('вызов ушёл сверх бюджета')
        assert len(calls)==1
        print('ok: отказ до сети, неизвестный usage удерживает резерв')
if __name__=='__main__': main()
