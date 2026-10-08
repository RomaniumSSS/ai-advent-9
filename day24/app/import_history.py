"""Однократный импорт сохранённых Day24; никогда не переносит разрешение облака."""
import argparse
import json
from pathlib import Path
from common import save

def import_history(source,destination):
    source,destination=Path(source),Path(destination)
    prepared=json.loads((source/'prepared.json').read_text())
    report=json.loads((source/'report.json').read_text())
    rows={r['id']:r for r in report['rows']}
    ledger=json.loads((source/'run-v1/ledger.json').read_text())
    count=0
    for case in prepared['cases']:
        ident='historical-'+case['id'];path=destination/('result-'+ident+'.json')
        if path.exists():
            existing=json.loads(path.read_text())
            if 'generation' not in existing:
                sent=bool(existing.get('raw_answer'))
                existing['generation']={'started':sent,'transmitted_chunk_ids':[c['chunk_id'] for c in existing['search']['trace']['selected']] if sent else []}
                save(path,existing)
            continue
        row=rows[case['id']]
        entry=next((e for e in ledger['entries'] if e['id']==case['id'] and e['status']=='completed'),None)
        trace=case['traces']['rag']
        item={'id':ident,'question':case['question'],'scope':'historical_day24','status':'verified' if row.get('valid',False) else ('no_context' if trace['empty'] else 'unverified'),'historical':True,'historical_origin':'Day24 @ be94bf73db06bdbc1ed371da031ba40e1f5d73ea','historical_assessment':{'semantic_match':row['semantic_match'],'answers_question':row['answers_question'],'notes':row['notes']},'created_at':entry.get('started_at',0) if entry else 0,'version':'day24-historical','semantic_match':row['semantic_match'],'cost':entry.get('actual_cost') if entry else 0,'saved':True,'feedback':None,'search':{'identity':prepared['identity'],'trace':trace,'backend':'Сохранённый поиск Day24'},'validation':{'valid':row.get('valid',False),'errors':row.get('errors',[])},'raw_answer':row.get('raw_content'),'timings':{'search':None,'generation':entry.get('elapsed_seconds') if entry else None}}
        item['generation']={'started':entry is not None,'transmitted_chunk_ids':[c['chunk_id'] for c in trace['selected']] if entry else []}
        if row.get('valid',False) or trace['empty']: item['answer']=row['answer']
        save(path,item);count+=1
    return count

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',default='day24/private');p.add_argument('--destination',default=str(Path(__file__).parent/'private'));a=p.parse_args();print('Импортировано исторических результатов:',import_history(a.source,a.destination))
if __name__=='__main__':main()
