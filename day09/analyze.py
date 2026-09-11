"""Сводка расхода и извлечение контрольных ответов без новых вызовов API."""
import json
from pathlib import Path

ROOT=Path(__file__).parent/'results'/'final'

def analyze():
    rows=[]; controls=[]
    for path in sorted(ROOT.glob('*-r[0-9]*.json')):
        if '-calls' in path.name:continue
        report=json.loads(path.read_text())
        if not report.get('complete'):continue
        totals=report['totals']; full=totals['full']['total']; compressed=totals['compressed']['total']
        row={'scenario':report['scenario'],'repeat':report['repeat'],
             'full_tokens':full['tokens'],'compressed_tokens':compressed['tokens'],
             'summary_tokens':totals['compressed']['summary']['tokens'],
             'failed_attempts_without_usage':sum('error' in call for side in ('full','compressed') for call in json.loads((ROOT/(path.stem+'-'+side+'-calls.json')).read_text())),
             'token_scope':'successful API responses including all summary attempts with usage',
             'full_cost':full['cost_reported'],'compressed_cost':compressed['cost_reported'],
             'savings_percent':100*(1-compressed['tokens']/full['tokens']),
             'compressions':[],'checkpoints':[]}
        for turn in report['turns']:
            event=turn['sides']['compressed']['event']
            if event:row['compressions'].append({'turn':turn['number'],**event})
            if turn['number'] in (3,8,9,14,16):
                row['checkpoints'].append({'turn':turn['number'],
                    **{s:{'total':v['usage']['total']['tokens'],
                          'input':v['reply']['prompt_tokens'],
                          'summary':v['usage']['summary']['tokens']}
                       for s,v in turn['sides'].items()}})
            if turn['number'] in (9,14,16):
                for side, data in turn['sides'].items():
                    controls.append({'scenario':report['scenario'],'repeat':report['repeat'],
                        'turn':turn['number'],'side':side,'expected':report['facts'],
                        'answer':data['reply']['text'],'summary':data['summary']})
        rows.append(row)
    (ROOT/'analysis.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'control-answers.json').write_text(json.dumps(controls,ensure_ascii=False,indent=2)+'\n')
    for row in rows:print(json.dumps({k:v for k,v in row.items() if k not in ('compressions','checkpoints')},ensure_ascii=False))
    print('Полных пар:',len(rows),'контрольных ответов:',len(controls))
if __name__=='__main__':analyze()
