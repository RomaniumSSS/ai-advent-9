"""SSH читает Structure; наружу выходят только кандидаты и снимки, без векторов."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
from common import packed

PUBLIC_DOCUMENTS = ('assignment:18',)

def search(question, scope):
    if scope not in ('all', 'public'):
        raise ValueError('invalid_scope')
    here = Path(__file__).parent
    sources = {n: (here / (n + '.py')).read_text() for n in ('common', 'temporal', 'retrieval')}
    job = {'sources': sources, 'question': question, 'scope': scope, 'public': PUBLIC_DOCUMENTS}
    encoded = base64.b64encode(packed(job)).decode()
    script = '''import base64,json,sys,types,time
job=json.loads(base64.b64decode(%r))
for name in ('common','temporal','retrieval'):
 module=types.ModuleType(name);sys.modules[name]=module
 exec(compile(job['sources'][name],name+'.py','exec'),module.__dict__)
from common import *
from retrieval import *
t=time.monotonic()
identity,chunks=load_index('/opt/day21/private/index-release-v1','structure')
if job['scope']=='public': chunks=[c for c in chunks if c['document_id'] in job['public']]
url='http://127.0.0.1:11434'
tags=request(url+'/api/tags')['models']
m=next((m for m in tags if m.get('name')==EMBED_MODEL or m.get('model')==EMBED_MODEL),None)
if not m or m['digest']!=identity['config']['model']['digest']: raise ValueError('embedding_digest_mismatch')
show=request(url+'/api/show',{'model':EMBED_MODEL})
if show.get('remote_host') or show.get('remote_model'): raise ValueError('remote_embedding_forbidden')
v=vector(request(url+'/api/embed',{'model':EMBED_MODEL,'input':[query_input(job['question'])],'truncate':False,'options':OPTIONS})['embeddings'][0])
trace=retrieve(chunks,job['question'],v,Config())
print(json.dumps({'identity':identity,'trace':trace,'remote_seconds':time.monotonic()-t},ensure_ascii=False))
''' % encoded
    started = time.monotonic()
    result = subprocess.run(['ssh', '-o', 'ConnectTimeout=10', 'crm-agent', '/opt/day21/pipeline-venv/bin/python -'], input=script.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240)
    if result.returncode:
        raise RuntimeError('search_failed_exit_' + str(result.returncode))
    output = json.loads(result.stdout)
    output.update(seconds=time.monotonic()-started, code_sha256=hashlib.sha256(packed(sources)).hexdigest(), backend='SSH Structure / Ollama')
    return output

def manifest():
    """Снимок области разрешения: только IDs и идентичность, без приватных текстов."""
    sources=(Path(__file__).parent/'common.py').read_text()
    job=base64.b64encode(packed({'source':sources})).decode()
    script='''import base64,json,sys,types
job=json.loads(base64.b64decode(%r))
module=types.ModuleType('common');sys.modules['common']=module
exec(compile(job['source'],'common.py','exec'),module.__dict__)
from common import load_index
identity,chunks=load_index('/opt/day21/private/index-release-v1','structure')
print(json.dumps({'identity':identity,'document_ids':sorted({c['document_id'] for c in chunks})},ensure_ascii=False))
''' % job
    result=subprocess.run(['ssh','-o','ConnectTimeout=10','crm-agent','/opt/day21/pipeline-venv/bin/python -'],input=script.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
    if result.returncode:raise RuntimeError('manifest_failed_exit_'+str(result.returncode))
    return json.loads(result.stdout)
