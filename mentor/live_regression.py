"""Адресный разрешённый прогон через обычный API; результаты не печатают тексты корпуса."""
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from common import save

CASES=[('day7','ff743ef2-1d39-45c4-9eb2-d2d57ac0a9b3'),('day18','48f9bdfb-e09c-41c1-a9f4-d8456f469451'),('day21','a1148a17-6582-4bea-a92d-023f75145c3c'),('memory','50b43e26-8849-4377-8fd4-faacb837b07c'),('deepseek-date','e908ee13-f448-482b-8c82-d9ddee5b80bc'),('rag-date','346a56fc-7ac5-4e22-bade-84792a040835'),('omp','a32381ff-3fbd-4b94-99b5-8fcb6e103431'),('index','dad2228a-14a0-4110-8037-23d3730f65ea'),('recent','667ed930-17b2-4c9a-90f1-7845fc1402e4')]

def main():
    base='http://127.0.0.1:8050';directory=Path(__file__).parent/'private'
    state=json.load(urllib.request.urlopen(base+'/api/state'))
    candidates=[r for r in state['history'] if not r.get('historical') and re.search(r'(?:д(?:ень|ня)|day)\s*12(?!\d)',r['question'],re.I)]
    jobs=[('day12',candidates[0]['id'] if candidates else None,'Дай условие дня 12: что нужно реализовать?')]+[(name,old,None) for name,old in CASES]
    proof_path=directory/'quality-live-regression.json';proof=json.loads(proof_path.read_text()) if proof_path.exists() else {'rows':[],'regression_not_holdout':True}
    for name,old_id,fallback in jobs:
        new_id='quality-20261003-'+name
        if any(r['new_id']==new_id for r in proof['rows']):continue
        previous=json.loads((directory/('result-'+old_id+'.json')).read_text()) if old_id else None
        question=previous['question'] if previous else fallback
        payload={'id':new_id,'question':question,'scope':previous['scope'] if previous and previous['scope'] in ('all','public') else 'all'}
        state=json.load(urllib.request.urlopen(base+'/api/state'))
        req=urllib.request.Request(base+'/api/ask',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Origin':base,'X-Mentor-Token':state['token']})
        try:result=json.load(urllib.request.urlopen(req,timeout=300))
        except urllib.error.HTTPError as e:
            if e.code==409:
                print(json.dumps({'case':name,'stopped':'user_request_in_progress','paid_retry':False}),flush=True);break
            raise
        trace=result.get('search',{}).get('trace',{})
        row={'case':name,'old_id':old_id,'new_id':new_id,'status':result['status'],'cost':result['cost'],'selected':len(trace.get('selected',[])),'transmitted':len(result.get('generation',{}).get('transmitted_chunk_ids',[])),'validation_errors':result.get('validation',{}).get('errors',[]),'normalization':result.get('validation',{}).get('normalization'),'temporal':{k:trace.get('temporal',{}).get(k) for k in ('enabled','resolved_dates','start','end','error')},'code_sha256':result.get('search',{}).get('code_sha256'),'semantic_match':None,'checked_at':time.time()}
        proof['rows'].append(row);save(proof_path,proof)
        print(json.dumps(row,ensure_ascii=False),flush=True)
        if result['status'] in ('unknown','error'):break
    print(json.dumps({'completed':len(proof['rows']),'known_cost_new_regression':sum(r['cost'] for r in proof['rows'] if r['cost'] is not None),'unknown_cost_cases':[r['case'] for r in proof['rows'] if r['cost'] is None]},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
