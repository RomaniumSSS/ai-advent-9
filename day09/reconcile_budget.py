"""Сверка общего расхода с дневным счётчиком ключа, без раскрытия ключа.

Только для этого однодневного эксперимента. Не присваивает ошибочным вызовам
нулевой usage: уменьшает общий резерв по независимому счётчику сервиса.
"""
import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from experiment import BudgetLedger

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--through-ticket',type=int,required=True,help='сверять только завершённый старый префикс журнала')
    args=parser.parse_args();load_dotenv(args.env_file)
    ledger=BudgetLedger()
    today=datetime.now(timezone.utc).date().isoformat()
    starts=[]
    for p in (Path(__file__).parent/'results').rglob('*-r[0-9]*.json'):
        if '-calls' in p.name:continue
        data=json.loads(p.read_text())
        if 'started' in data:starts.append(data['started'][:10])
    if not starts or set(starts)!={today}:
        raise RuntimeError('дневная сверка допустима только для эксперимента, целиком начатого сегодня UTC')
    with ledger.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        rows=db.execute('SELECT id,reserved,actual,state FROM reservations').fetchall()
        if any(r[3]=='overrun' for r in rows):raise RuntimeError('нарушена граница резерва, автоматическая сверка запрещена')
        prefix=[r for r in rows if r[0]<=args.through_ticket]
        if not prefix or any(r[3]=='pending' for r in prefix):
            raise RuntimeError('префикс пуст или ещё содержит выполняющийся вызов')
        known=sum(r[2] for r in prefix if r[2] is not None)
        config='header = "Authorization: Bearer '+os.environ['OPENROUTER_API_KEY']+'"\n'
        proc=subprocess.run(['curl','-fsS','--max-time','20','-K','-','https://openrouter.ai/api/v1/key'],input=config,text=True,capture_output=True)
        if proc.returncode:raise RuntimeError('дневной счётчик недоступен')
        daily=json.loads(proc.stdout)['data']['usage_daily']
        if daily is None or daily+1e-10<known:
            raise RuntimeError(f'счётчик сервиса {daily} отстаёт от журнала {known}; резерв не изменён')
        unresolved=[r for r in prefix if r[2] is None]
        evidence={'at':datetime.now(timezone.utc).isoformat(),'source':'https://openrouter.ai/api/v1/key',
                  'through_ticket':args.through_ticket,'usage_daily':daily,'known_success_cost':known,'unattributed_upper_bound':max(0,daily-known),
                  'unresolved_before':[{'id':r[0],'reserved':r[1],'state':r[3]} for r in unresolved],
                  'pending_untouched':[r[0] for r in rows if r[3]=='pending'],
                  'note':'Сверяется старый завершённый префикс. Дневной расход всего ключа включает также более новые вызовы и возможное другое использование, поэтому разница консервативно завышает неизвестный расход префикса. Индивидуальный usage ошибок неизвестен; сверка относится к общему списанию на этот момент.'}
        old_bound=sum(r[1] for r in unresolved)
        new_bound=min(old_bound,max(0,daily-known))
        # Один общий остаток хранится в первой строке; все actual остаются NULL.
        for i,r in enumerate(unresolved):
            db.execute("UPDATE reservations SET reserved=?,state='reconciled_daily' WHERE id=?",(new_bound if i==0 else 0,r[0]))
        db.execute('CREATE TABLE IF NOT EXISTS reconciliations (id INTEGER PRIMARY KEY, evidence TEXT NOT NULL)')
        db.execute('INSERT INTO reconciliations(evidence) VALUES (?)',(json.dumps(evidence,ensure_ascii=False),))
        result=db.execute('SELECT evidence FROM reconciliations ORDER BY id').fetchall()
    out=Path(__file__).parent/'results'/'billing-reconciliation.json'
    out.write_text(json.dumps([json.loads(r[0]) for r in result],ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:evidence[k] for k in ('at','usage_daily','known_success_cost','unattributed_upper_bound')},ensure_ascii=False))
if __name__=='__main__':main()
