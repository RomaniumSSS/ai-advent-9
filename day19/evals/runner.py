"""Воспроизводимые прогоны реальной модели и локального MCP по RSS-сценариям."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from day19.store import now

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
ORIGINAL=ROOT/'fixtures'/'habr-real-20260927.xml'
START='2026-09-22T00:00:00Z'
END='2026-09-27T09:38:00Z'

def cases():return {case['id']:case for case in json.loads((HERE/'cases.json').read_text(encoding='utf-8'))}

def fixture_for(case: dict) -> Path:
    kind=case['source'];name=case['id'];target=HERE/'fixtures'/f'{name}.xml'
    if kind=='full_real_rss':return ORIGINAL
    if kind=='synthetic_empty':raw=b'<rss><channel></channel></rss>'
    elif kind=='synthetic_malformed':raw=b'<rss><channel><item>'
    else:
        source=ET.fromstring(ORIGINAL.read_bytes())
        items=source.findall('./channel/item')
        root=ET.Element('rss',version='2.0');channel=ET.SubElement(root,'channel')
        for article_id in case['article_ids']:
            matches=[item for item in items if f'/{article_id}/' in (item.findtext('link') or '')]
            if len(matches)!=1:raise ValueError('source_item_missing_or_ambiguous:'+article_id)
            channel.append(matches[0])
        raw=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    target.write_bytes(raw)
    meta={'case_id':name,'source_kind':kind,'source_snapshot':str(ORIGINAL.relative_to(ROOT)),
          'source_sha256':hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
          'fixture_sha256':hashlib.sha256(raw).hexdigest(),'article_ids':case['article_ids'],
          'created_utc':now(),'start':START,'end':END}
    target.with_suffix('.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return target

def run_case(case: dict, repeat: int) -> dict:
    fixture=fixture_for(case)
    name=f"{case['id']}-{repeat}"
    db=HERE/'state'/f'{name}.sqlite3'
    trace=HERE/'traces'/f'{name}.json'
    if db.exists() or trace.exists():raise ValueError('existing_eval_run:'+name)
    cmd=[sys.executable,'-m','day19.cli','--db',str(db),'--rss-file',str(fixture),
         '--start',START,'--end',END,'--request',case['request'],'--trace',str(trace)]
    result=subprocess.run(cmd,cwd=ROOT.parent,capture_output=True,text=True)
    entry={'case_id':case['id'],'repeat':repeat,'run_at_utc':now(),'fixture':str(fixture.relative_to(ROOT)),
           'trace':str(trace.relative_to(ROOT)),'cli_exit_code':result.returncode}
    if trace.is_file():
        data=json.loads(trace.read_text(encoding='utf-8'))
        entry.update({'run_id':data['run_id'],'status':data['status'],'reason':data['reason'],
                      'model_calls':len(data['model_calls']),'tool_calls':len(data['tool_calls']),
                      'reported_cost_usd':data['reported_cost_usd'],
                      'tool_events':[{'name':x['name'],'status':x['result'].get('status'),
                                      'code':x['result'].get('code')} for x in data['tool_calls']]})
    else:entry['status']='no_trace'
    with (HERE/'runs.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(entry,ensure_ascii=False)+'\n')
    return entry

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('case_ids',nargs='*',help='По умолчанию все случаи из cases.json')
    parser.add_argument('--repeat',type=int,help='Переопределить число повторов')
    parser.add_argument('--start-repeat',type=int,default=1,help='Номер первого повтора')
    args=parser.parse_args()
    available=cases()
    names=args.case_ids or list(available)
    for name in names:
        if name not in available:raise SystemExit('unknown_case:'+name)
        case=available[name]
        for repeat in range(args.start_repeat,(args.repeat or case['repeats'])+1):
            row=run_case(case,repeat)
            print(json.dumps({key:row.get(key) for key in ('case_id','repeat','status','reason','model_calls',
                'tool_calls','reported_cost_usd','trace')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
