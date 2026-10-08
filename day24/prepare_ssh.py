"""Подготовка через SSH stdin: код выполняется в памяти, индекс только читается."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
from common import packed, save
from prepare_remote import query_cases


def remote_prepare(cases, host='crm-agent', root='/opt/day21/private/index-release-v1'):
    here=Path(__file__).parent
    sources={name:(here/(name+'.py')).read_text() for name in ('common','retrieval','answers','prepare_remote')}
    job={'sources':sources,'cases':query_cases(cases),'root':root}
    encoded=base64.b64encode(packed(job)).decode()
    script="""import base64,json,sys,types
job=json.loads(base64.b64decode(%r))
for name in ('common','retrieval','answers','prepare_remote'):
    module=types.ModuleType(name);sys.modules[name]=module
    exec(compile(job['sources'][name],name+'.py','exec'),module.__dict__)
from prepare_remote import prepare
from retrieval import Config
result=prepare(job['root'],job['cases'],configs={'rag':Config()})
print(json.dumps(result,ensure_ascii=False))
""" % encoded
    started=time.monotonic()
    p=subprocess.run(['ssh','-o','ConnectTimeout=10',host,'/opt/day21/pipeline-venv/bin/python -'],input=script.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
    if p.returncode:
        raise RuntimeError('remote_prepare_failed_exit_'+str(p.returncode))
    output=json.loads(p.stdout)
    output['elapsed_seconds']=time.monotonic()-started
    output['code_sha256']=hashlib.sha256(packed(sources)).hexdigest()
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--questions',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--host',default='crm-agent')
    parser.add_argument('--root',default='/opt/day21/private/index-release-v1')
    args=parser.parse_args()
    cases=query_cases(json.loads(Path(args.questions).read_text()))
    directory=Path(args.output_dir)
    sources={name:(Path(__file__).parent/(name+'.py')).read_text() for name in ('common','retrieval','answers','prepare_remote')}
    code_sha=hashlib.sha256(packed(sources)).hexdigest()
    combined=[]; index=None
    for offset in range(0,len(cases),8):
        batch=cases[offset:offset+8]
        digest=hashlib.sha256(packed(batch)).hexdigest()
        path=directory/('batch-'+digest[:16]+'.json')
        if path.exists():
            result=json.loads(path.read_text())
            if result.get('questions_sha256')!=digest:raise ValueError('batch_changed')
            if result.get('code_sha256')!=code_sha:raise ValueError('cached_code_changed_use_new_output_dir')
        else:
            result=remote_prepare(batch,args.host,args.root)
            result['questions_sha256']=digest
            save(path,result)
        if index is not None and index['identity']!=result['identity']:raise ValueError('index_changed')
        index=result
        combined.extend(result['cases'])
        print(json.dumps({'prepared':len(combined),'total':len(cases),'batch_seconds':result['elapsed_seconds'],'cloud_calls':0}),flush=True)
    save(directory/'prepared.json',{k:v for k,v in index.items() if k not in ('cases','elapsed_seconds','questions_sha256')}|{'cases':combined})

if __name__=='__main__':main()
