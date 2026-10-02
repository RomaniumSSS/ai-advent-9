"""Подготовка локальным Ollama; SSH исполняет отдельно оператор."""
import argparse
import json
import re
import sys
from pathlib import Path
from common import EMBED_MODEL, MODEL, OPTIONS, load_index, loopback, request, save, vector
from retrieval import Config, MODES, query_input, retrieve, rewrite


def query_cases(data):
    cases = data['cases'] if isinstance(data,dict) else data
    if not isinstance(cases,list) or not cases:
        raise ValueError('empty_cases')
    output=[]
    for c in cases:
        if set(c) != {'id','question'}:
            raise ValueError('query_only_fields_required')
        if not isinstance(c['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]+',c['id']):
            raise ValueError('invalid_case_id')
        if not isinstance(c['question'],str) or not c['question'].strip():
            raise ValueError('invalid_question')
        output.append(dict(c))
    if len({c['id'] for c in output}) != len(output):
        raise ValueError('duplicate_case_ids')
    return output


def prepare(root, questions_data, ollama_url='http://127.0.0.1:11434', configs=None, dispatch=request):
    cases=query_cases(questions_data)
    url=loopback(ollama_url)
    identity,chunks=load_index(root,'structure')
    tags=dispatch(url+'/api/tags')['models']
    match=next((m for m in tags if m.get('name') == EMBED_MODEL or m.get('model') == EMBED_MODEL),None)
    if not match or match['digest'] != identity['config']['model']['digest']:
        raise ValueError('embedding_digest_mismatch')
    show=dispatch(url+'/api/show',{'model':EMBED_MODEL})
    if show.get('remote_host') or show.get('remote_model'):
        raise ValueError('remote_embedding_forbidden')
    inputs=list(dict.fromkeys(query_input(q) for c in cases for q in (c['question'],rewrite(c['question'])['after'])))
    embeddings={}
    # Небольшие батчи сохраняют память эмбеддера и порядок входов.
    for offset in range(0,len(inputs),8):
        batch=inputs[offset:offset+8]
        response=dispatch(url+'/api/embed',{'model':EMBED_MODEL,'input':batch,'truncate':False,'options':OPTIONS})
        if len(response['embeddings']) != len(batch):
            raise ValueError('embedding_response_count')
        for question,values in zip(batch,response['embeddings']):
            embeddings[question]=vector(values)
    configs=configs or MODES
    output=[]
    for c in cases:
        original=embeddings[query_input(c['question'])]
        rewritten=embeddings[query_input(rewrite(c['question'])['after'])]
        traces={}
        for name,config in configs.items():
            config=Config(**config) if isinstance(config,dict) else config
            traces[name]=retrieve(chunks,c['question'],rewritten if config.rewrite else original,config)
        output.append({**c,'query_vectors':{'original':original,'rewritten':rewritten},
                       'traces':traces,'messages':{name:t['messages'] for name,t in traces.items()}})
    return {'version':1,'identity':identity,'model':MODEL,'strategy':'structure','cases':output,
            'chunks':chunks,'modes':list(configs)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True)
    p.add_argument('--questions',default='-')
    p.add_argument('--output',required=True)
    p.add_argument('--ollama-url',default='http://127.0.0.1:11434')
    p.add_argument('--configs')
    args=p.parse_args()
    data=json.load(sys.stdin) if args.questions == '-' else json.loads(Path(args.questions).read_text())
    configs=json.loads(Path(args.configs).read_text()) if args.configs else None
    save(args.output,prepare(args.root,data,args.ollama_url,configs))
    print(json.dumps({'status':'prepared','paid_requests':0}))

if __name__ == '__main__':
    main()
