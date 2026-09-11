"""Дневная сверка не освобождает активные резервы и отвергает отставший счётчик."""
import json
import sys
import tempfile
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace as NS
import reconcile_budget
from experiment import BudgetLedger

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);(root/'results').mkdir()
        (root/'results/project-r1.json').write_text(json.dumps({'started':datetime.now(timezone.utc).isoformat()}))
        (root/'test.env').write_text('OPENROUTER_API_KEY=fake-not-a-credential\n')
        ledger=BudgetLedger(root/'budget.db')
        first=ledger.reserve(.07,'known');ledger.settle(first,.01)
        failed=ledger.reserve(.07,'unknown');ledger.settle(failed,None)
        pending=ledger.reserve(.07,'pending')
        reconcile_budget.BudgetLedger=lambda:ledger
        reconcile_budget.__file__=str(root/'reconcile_budget.py')
        sys.argv=['test','--env-file',str(root/'test.env'),'--through-ticket',str(failed)]
        reconcile_budget.subprocess.run=lambda *a,**kw:NS(returncode=0,stdout=json.dumps({'data':{'usage_daily':.005}}))
        try:reconcile_budget.main()
        except RuntimeError:pass
        else:raise AssertionError('приняли устаревший счётчик')
        assert abs(ledger.report()['held_for_unknown']-.14)<1e-8
        reconcile_budget.subprocess.run=lambda *a,**kw:NS(returncode=0,stdout=json.dumps({'data':{'usage_daily':.02}}))
        reconcile_budget.main()
        rows=ledger.report()['reservations']
        assert rows[1]['actual'] is None and rows[1]['state']=='reconciled_daily'
        assert abs(rows[1]['reserved']-.01)<1e-8
        assert rows[2]['state']=='pending' and rows[2]['reserved']==.07
        print('ok: старый счётчик отвергнут, сверка префикса сохранена, неизвестный actual не обнулён, активный резерв не изменён')
if __name__=='__main__':main()
