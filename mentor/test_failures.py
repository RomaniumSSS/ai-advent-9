"""Синтетические аварии и блокировки; генераторы — локальные функции."""
from pathlib import Path
import tempfile
from unittest.mock import patch
from common import save
from service import Service, read
from test_mentor import synthetic, auth, raw, VALID

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);auth(root);calls=[]
        s=Service(root,synthetic,lambda *_:(calls.append(1) or raw(VALID)),lambda _:'synthetic-key',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        with s.lock():
            try:s.ask('busy','тест','public');raise AssertionError('lock')
            except ValueError as e:assert str(e)=='request_in_progress'
        original=save
        def fail_reserve(path,item):
            if Path(path).name=='ledger.json':raise OSError('synthetic reserve failure')
            original(path,item)
        with patch('service.save',side_effect=fail_reserve):
            r=s.ask('reserve','тест','public')
        assert not calls and r['status']=='error'
        s=Service(root,synthetic,lambda *_:raw(VALID),lambda _:'synthetic-key',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        def fail_final(path,item):
            if item.get('status')=='verified' and Path(path).name.startswith('result-'):raise OSError('synthetic result failure')
            original(path,item)
        with patch('service.save',side_effect=fail_final):r=s.ask('unsaved','тест','public')
        assert r['status']=='verified' and r['saved'] is False and r['answer']
        assert s.ask('unsaved','тест','public')['saved'] is False
        writes=[]
        def fail_ledger_final(path,item):
            if Path(path).name=='ledger.json':
                writes.append(1)
                if len(writes)==2:raise OSError('synthetic final ledger failure')
            original(path,item)
        with patch('service.save',side_effect=fail_ledger_final):r=s.ask('ledgerfailed','тест','public')
        assert r['status']=='verified' and r['ledger_save_error'] and r['answer']
        assert s.ask('ledgerblocked','тест','public')['error']=='explicit_recovery_required'
        # Отдельная синтетическая область для следующего независимого сбоя.
        ledger=read(root/'ledger.json');ledger['entries'][-1]['status']='completed';save(root/'ledger.json',ledger)
        def timeout(*_):raise TimeoutError('synthetic unknown provider outcome')
        s=Service(root,synthetic,timeout,lambda _:'synthetic-key',pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6})
        assert s.ask('unknown','тест','public')['status']=='unknown'
        s=Service(root,synthetic,lambda *_:(_ for _ in ()).throw(AssertionError('repeat')))
        assert s.get('unknown')['status']=='unknown'
        assert s.ask('blocked','тест','public')['error']=='explicit_recovery_required'
        save(root/'result-interrupted.json',{'id':'interrupted','status':'searching','question':'тест','scope':'public'})
        s=Service(root,synthetic)
        assert s.get('interrupted')['status']=='interrupted'
    print('PASS: synthetic concurrent lock, failed reserve, unsaved answer, final ledger-save failure, unknown outcome/restart, interrupted search; cloud=0')
if __name__=='__main__':
    with patch('requests.Session.request',side_effect=AssertionError('offline network forbidden')):
        main()
