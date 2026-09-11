"""Прерванная пара: успешная сторона не вызывается повторно после resume."""
import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
import test_live
from experiment import BudgetLedger
from test_compression import Fake

class FailOnce(Fake):
    def __init__(self):super().__init__();self.failed=False
    def create(self,**kw):
        if not self.failed:
            self.failed=True
            raise RuntimeError('контролируемая остановка без автоматического повтора')
        return super().create(**kw)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        test_live.OUT=Path(tmp)
        ledger=BudgetLedger(Path(tmp)/'budget.db')
        clients=iter([FailOnce(),Fake()])
        test_live.real_client=lambda:next(clients)
        with redirect_stdout(io.StringIO()):
            first=test_live.run_pair('project',2,ledger)
        assert not first['complete'] and len(first['turns'])==1
        test_live.real_client=Fake
        with redirect_stdout(io.StringIO()):
            final=test_live.run_pair('project',2,ledger,resume=True)
        assert final['complete'] and len(final['turns'])==16
        assert len(json.loads((Path(tmp)/'project-r2-full-calls.json').read_text()))==17
        assert len(json.loads((Path(tmp)/'project-r2-compressed-calls.json').read_text()))==18
        assert final['failed_attempts_without_usage']==1
        assert final['turns'][0]['sides']['compressed']['reply']==first['turns'][0]['sides']['compressed']['reply']
        assert ledger.report()['held_for_unknown']>0
        print('ok: продолжение неполной пары, без дубля успешного ответа, история попыток и неизвестный расход сохранены')
        class Truncated(Fake):
            def create(self, **kwargs):
                response=super().create(**kwargs)
                response.choices[0].finish_reason='length'
                return response
        clients=iter([Truncated(),Fake()])
        test_live.real_client=lambda:next(clients)
        with redirect_stdout(io.StringIO()):
            stopped=test_live.run_pair('personal',2,ledger)
        assert not stopped['complete']
        test_live.real_client=Fake
        try:
            test_live.run_pair('personal',2,ledger,resume=True)
        except RuntimeError as error:
            assert 'обрезанный' in str(error)
        else:raise AssertionError('обрезанный ход был отправлен ещё раз')
        assert len(json.loads((Path(tmp)/'personal-r2-full-calls.json').read_text()))==1
        print('ok: обрезанный сохранённый ответ не дублируется при resume')
if __name__=='__main__':main()
