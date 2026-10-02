"""Оценщик получает эталоны отдельно; поиск видит только вопрос и индекс."""
import argparse
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from common import packed, save
from retrieval import Config, MODES, retrieve


def covered(anchor, chunks):
    cursor=anchor['start_char']
    for c in sorted(chunks,key=lambda x:x['start_char']):
        if c['start_char']>cursor:break
        cursor=max(cursor,c['end_char'])
        if cursor>=anchor['end_char']:return True
    return False


def measure(case, trace):
    answerable=case['answerable']
    result={'id':case['id'],'category':case['category'],'answerable':answerable,
            'empty':trace['empty'],'context_bytes':trace['context_bytes']}
    for stage in ('candidates','selected'):
        chunks=trace[stage]; details=[]
        for s in case['support']:
            matching=[c for c in chunks if c['document_id']==s['document_id']]
            details.append({'document_id':s['document_id'],'document_found':bool(matching),
                            'anchors':[covered(a,matching) for a in s['anchors']]})
        result[stage]={'all_anchors':all(all(s['anchors']) for s in details) if answerable else None,
                       'all_documents':all(s['document_found'] for s in details) if answerable else None,
                       'details':details}
    return result


def summarize(rows):
    groups=defaultdict(list)
    for row in rows:
        for label in {'all',row['category'],'answerable' if row['answerable'] else 'unanswerable'}:
            groups[label].append(row)
    out={}
    for name,items in groups.items():
        yes=[r for r in items if r['answerable']]
        out[name]={'questions':len(items),'answerable':len(yes),
                   'all_anchors':sum(r['selected']['all_anchors'] for r in yes),
                   'all_documents':sum(r['selected']['all_documents'] for r in yes),
                   'candidate_all_anchors':sum(r['candidates']['all_anchors'] for r in yes),
                   'empty':sum(r['empty'] for r in items),
                   'context_bytes':sum(r['context_bytes'] for r in items)}
    return out


def run(prepared, benchmark, configs):
    gold={c['id']:c for c in benchmark['cases']}
    ids=[q['id'] for q in prepared['cases']]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate_prepared_ids')
    for q in prepared['cases']:
        if q['id'] not in gold or q['question']!=gold[q['id']]['question']:raise ValueError('question_gold_mismatch')
    result={}
    for name, cfg in configs.items():
        cfg=Config(**cfg) if isinstance(cfg,dict) else cfg
        rows=[];traces={};started=time.monotonic()
        for q in prepared['cases']:
            v=q['query_vectors']['rewritten' if cfg.rewrite else 'original']
            t=retrieve(prepared['chunks'],q['question'],v,cfg)
            traces[q['id']]=t;rows.append(measure(gold[q['id']],t))
        result[name]={'config':asdict(cfg),'elapsed_seconds':time.monotonic()-started,'rows':rows,'summary':summarize(rows),'traces':traces}
        print(json.dumps({'mode':name,**result[name]['summary']['all']},ensure_ascii=False),flush=True)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepared',required=True);p.add_argument('--benchmark',required=True);p.add_argument('--output',required=True);p.add_argument('--configs')
    args=p.parse_args()
    configs=json.loads(Path(args.configs).read_text()) if args.configs else MODES|{'C035':Config(mixed=True,threshold=.35),'C050':Config(mixed=True,threshold=.5)}
    prepared=json.loads(Path(args.prepared).read_text());benchmark=json.loads(Path(args.benchmark).read_text())
    result=run(prepared,benchmark,configs)
    save(args.output,{'retrieval_code_sha256':hashlib.sha256(Path(__file__).with_name('retrieval.py').read_bytes()).hexdigest(),'benchmark_sha256':hashlib.sha256(Path(args.benchmark).read_bytes()).hexdigest(),'results':result})

if __name__=='__main__':main()
