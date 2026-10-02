"""Day21 paired SQLite embedding generations; no retrieval or corpus mutation."""
import argparse
from contextlib import closing
from collections import Counter
import fcntl
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import resource
import sqlite3
import statistics
import tempfile
import time
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests

MODEL='qwen3-embedding:0.6b'
TOKENIZER_MODEL='Qwen/Qwen3-Embedding-0.6B'
MAX_TOKENS=400
OVERLAP=60
DIMENSIONS=1024


def packed(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def digest(value):return hashlib.sha256(packed(value)).hexdigest()
def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path,value):
    fd,name=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.')
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(packed(value)+b'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
        descriptor=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
    finally:Path(name).unlink(missing_ok=True)


class PinnedTokenizer:
    def __init__(self,path,revision,expected_sha):
        if not re.fullmatch(r'[0-9a-f]{40}',revision):raise ValueError('immutable_tokenizer_revision_required')
        if file_hash(path)!=expected_sha:raise ValueError('tokenizer_hash_mismatch')
        from tokenizers import Tokenizer
        from importlib.metadata import version
        library_version=version('tokenizers')
        if library_version!='0.22.2':raise ValueError('tokenizers_library_version')
        self.engine=Tokenizer.from_file(str(path))
        self.identity={'model':TOKENIZER_MODEL,'revision':revision,'tokenizer_json_sha256':expected_sha,'add_special_tokens':True,'library_version':library_version}
    def count(self,text):return len(self.engine.encode(text,add_special_tokens=True).ids)
    def offsets(self,text):return [p for p in self.engine.encode(text,add_special_tokens=True).offsets if p[1]>p[0]]


def fixed_ranges(text,tokenizer,limit=MAX_TOKENS,overlap=OVERLAP,start=0,end=None):
    end=len(text) if end is None else end
    if limit<=overlap or overlap<0:raise ValueError('invalid_overlap')
    output=[];position=start
    while position<end:
        remaining=text[position:end]
        if tokenizer.count(remaining)<=limit:finish=end
        else:
            offsets=tokenizer.offsets(remaining)
            candidates=sorted({b for _,b in offsets if b>0})
            low=0;high=len(candidates)
            while low<high:
                middle=(low+high)//2
                if tokenizer.count(remaining[:candidates[middle]])<=limit:low=middle+1
                else:high=middle
            if not low:raise ValueError('one_unicode_unit_exceeds_limit')
            finish=position+candidates[low-1]
        if finish<=position:raise ValueError('chunk_no_progress')
        output.append((position,finish))
        if finish==end:break
        offsets=tokenizer.offsets(text[position:finish])
        next_position=position+(offsets[-overlap][0] if overlap and len(offsets)>overlap else finish-position)
        if next_position<=position:raise ValueError('overlap_no_progress')
        position=next_position
    return output


def validate_vectors(vectors,count):
    if not isinstance(vectors,list) or len(vectors)!=count:raise ValueError('embedding_count')
    for vector in vectors:
        if not isinstance(vector,list) or len(vector)!=DIMENSIONS:raise ValueError('embedding_dimensions')
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in vector):raise ValueError('embedding_nonfinite')
        norm=math.sqrt(sum(x*x for x in vector))
        if not math.isfinite(norm) or norm<=0:raise ValueError('embedding_norm')
    return vectors


class Ollama:
    def __init__(self,url,expected_digest,batch_size=8):
        parsed=urlparse(url)
        if parsed.scheme!='http' or parsed.hostname is None or not ipaddress.ip_address(parsed.hostname).is_loopback or parsed.username or parsed.path not in ['','/']:raise ValueError('loopback_only')
        self.session=requests.Session();self.session.trust_env=False
        self.url=url.rstrip('/');self.expected_digest=expected_digest;self.batch_size=batch_size
        self.calls=0;self.inputs=0;self.seconds=0;self.prompt_eval_count=0
    def verify_model(self):
        response=self.session.get(self.url+'/api/tags',timeout=30,allow_redirects=False);response.raise_for_status();models=response.json()['models']
        entry=next(m for m in models if m['name']==MODEL)
        if entry['digest']!=self.expected_digest:raise ValueError('ollama_model_digest')
        response=self.session.post(self.url+'/api/show',json={'model':MODEL},timeout=30,allow_redirects=False);response.raise_for_status();shown=response.json()
        if shown.get('remote_host') or shown.get('remote_model'):raise ValueError('remote_model_forbidden')
        response=self.session.get(self.url+'/api/version',timeout=30,allow_redirects=False);response.raise_for_status()
        return {'model':MODEL,'digest':entry['digest'],'ollama_version':response.json()['version'],'options':{'num_ctx':2048,'num_thread':1,'num_batch':128},'truncate':False}
    def embed(self,texts):
        result=[]
        for start in range(0,len(texts),self.batch_size):
            batch=texts[start:start+self.batch_size];began=time.monotonic()
            response=self.session.post(self.url+'/api/embed',json={'model':MODEL,'input':batch,'truncate':False,'options':{'num_ctx':2048,'num_thread':1,'num_batch':128}},timeout=180,allow_redirects=False)
            response.raise_for_status();body=response.json();vectors=validate_vectors(body.get('embeddings'),len(batch))
            if any(abs(math.sqrt(sum(x*x for x in v))-1)>1e-3 for v in vectors):raise ValueError('ollama_not_normalized')
            self.calls+=1;self.inputs+=len(batch);self.seconds+=time.monotonic()-began
            if type(body.get('prompt_eval_count')) is int:self.prompt_eval_count+=body['prompt_eval_count']
            result.extend(vectors)
        return result


def units(document):
    text=document['text'];sections=document.get('sections')
    if sections:
        if any(type(s.get('start_char')) is not int or type(s.get('end_char')) is not int for s in sections):raise ValueError('section_offsets')
        if sections[0]['start_char']!=0 or sections[-1]['end_char']!=len(text) or any(a['end_char']!=b['start_char'] for a,b in zip(sections,sections[1:])):raise ValueError('section_coverage')
        return sections
    cuts=[0]+[m.end() for m in re.finditer(r'\n\s*\n',text)]+[len(text)]
    cuts=sorted(set(cuts));return [{'start_char':a,'end_char':b,'section':'paragraph:'+str(n)} for n,(a,b) in enumerate(zip(cuts,cuts[1:]))]


def structure_ranges(document,tokenizer,embedder,threshold=.65):
    text=document['text'];parts=units(document);pieces=[];forced=0
    # Reviewed discussion groups already define a semantic unit; do not split a fitting group.
    if document.get('source')=='discussion' and tokenizer.count(text)<=MAX_TOKENS:
        return [(0,len(text))],{'transition_inputs':0,'protected_boundaries':0,'forced_breaks':0,'whole_document_preserved':True}
    # Bounded transition inputs, and natural cuts before fixed fallback.
    for part in parts:
        start,end=part['start_char'],part['end_char']
        if tokenizer.count(text[start:end])<=MAX_TOKENS:
            pieces.append((start,end));continue
        # AICODE-NOTE: paragraphs/list items are thought candidates; sentence cuts are an oversized-unit fallback.
        natural_cuts=sorted(set([start]+[start+m.end() for m in re.finditer(
            r'(?:\n\s*\n|\n(?=[ \t]*(?:[-*+]|\d+[.)])[ \t]+))',text[start:end])]+[end]))
        for a,b in zip(natural_cuts,natural_cuts[1:]):
            if tokenizer.count(text[a:b])<=MAX_TOKENS:
                pieces.append((a,b));continue
            sentence_cuts=sorted(set([a]+[a+m.end() for m in re.finditer(r'[.!?。！？]\s+',text[a:b])]+[b]))
            for x,y in zip(sentence_cuts,sentence_cuts[1:]):
                if tokenizer.count(text[x:y])<=MAX_TOKENS:pieces.append((x,y))
                else:
                    split=fixed_ranges(text,tokenizer,start=x,end=y);pieces.extend(split);forced+=len(split)-1
    if not pieces:return [],{'transition_inputs':0,'protected_boundaries':0,'forced_breaks':0}
    source_positions={key:n for n,p in enumerate(parts) for key in p.get('source_keys',[])}
    source_positions.update({p['message_id']:n for n,p in enumerate(parts) if p.get('message_id') is not None})
    protected_spans=[];qa_positions={}
    for n,p in enumerate(parts):
        if p.get('qa_group') is not None:qa_positions.setdefault(p['qa_group'],[]).append(n)
        parent=p.get('reply_to_source_key',p.get('reply_to'))
        if parent in source_positions:
            first,last=sorted((source_positions[parent],n));a,b=parts[first]['start_char'],parts[last]['end_char']
            if tokenizer.count(text[a:b])<=MAX_TOKENS:protected_spans.append((a,b))
    for positions in qa_positions.values():
        a,b=parts[min(positions)]['start_char'],parts[max(positions)]['end_char']
        if tokenizer.count(text[a:b])<=MAX_TOKENS:protected_spans.append((a,b))
    vectors=embedder.embed([text[a:b] for a,b in pieces]) if len(pieces)>1 else []
    ranges=[];start=pieces[0][0]
    for n,(a,b) in enumerate(pieces):
        if tokenizer.count(text[start:b])>MAX_TOKENS:
            prior_end=pieces[n-1][1]
            if prior_end>start:ranges.append((start,prior_end))
            crossing=[span for span in protected_spans if span[0]<a<span[1]]
            candidate=min((span[0] for span in crossing),default=a)
            start=candidate if tokenizer.count(text[candidate:b])<=MAX_TOKENS else a
        if n==len(pieces)-1:
            ranges.append((start,b));break
        protected=any(x<b<y for x,y in protected_spans)
        v,w=vectors[n],vectors[n+1];cosine=sum(x*y for x,y in zip(v,w))/(math.sqrt(sum(x*x for x in v))*math.sqrt(sum(x*x for x in w)))
        next_section=next((p for p in parts if p['start_char']==pieces[n+1][0]),{})
        if not protected and (cosine<threshold or next_section.get('hard_boundary')):
            ranges.append((start,b));start=pieces[n+1][0]
    # If competing protected spans need overlap, retain explicit QA as a separate exact range.
    for a,b in protected_spans:
        if not any(x<=a and y>=b for x,y in ranges):ranges.append((a,b))
    ranges=sorted(set(ranges))
    return ranges,{'transition_inputs':len(vectors),'protected_boundaries':len(protected_spans),'forced_breaks':forced}


def chunks(document,ranges,strategy,tokenizer,config):
    result=[];sections=units(document)
    for start,end in ranges:
        text=document['text'][start:end];count=tokenizer.count(text)
        if count>MAX_TOKENS:raise ValueError('reencoded_chunk_limit')
        relevant=[s for s in sections if s['start_char']<end and s['end_char']>start]
        metadata={k:document.get(k) for k in ['document_id','source','title','day','members','context_references','assignment_link','provenance']}
        source_keys={key for section in relevant for key in section.get('source_keys',[])}
        metadata['document_members']=metadata['members']
        if source_keys:metadata['members']=[m for m in (document.get('members') or []) if m.get('source_key') in source_keys]
        metadata.update(strategy=strategy,start_char=start,end_char=end,section=[s.get('section',n) for n,s in enumerate(sections) if s in relevant],
                        source_sections=relevant,text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest(),token_count=count)
        metadata['chunk_id']=digest({'document_id':document['document_id'],'start':start,'end':end,'text_sha256':metadata['text_sha256'],'strategy':strategy,'config':config})
        result.append(metadata)
    cursor=0
    for row in result:
        if row['start_char']>cursor:raise ValueError('chunk_coverage_gap')
        cursor=max(cursor,row['end_char'])
    if cursor!=len(document['text']):raise ValueError('chunk_coverage_end')
    return result


def reply_metrics(documents,output,tokenizer):
    pairs=0;split=0;fit_split=0;fitting=0;oversize=0
    for document in documents:
        sections=units(document);positions={s.get('message_id'):s for s in sections if s.get('message_id') is not None}
        rows=[r for r in output if r['document_id']==document['document_id']]
        for section in sections:
            parent=positions.get(section.get('reply_to'))
            if parent is None:continue
            pairs+=1;start=min(parent['start_char'],section['start_char']);end=max(parent['end_char'],section['end_char'])
            fits=tokenizer.count(document['text'][start:end])<=MAX_TOKENS
            if fits:fitting+=1
            else:oversize+=1
            if not any(r['start_char']<=start and r['end_char']>=end for r in rows):
                split+=1
                if fits:fit_split+=1
    return {'explicit_reply_pairs':pairs,'fitting_reply_pairs':fitting,'oversize_reply_pairs':oversize,'fitting_reply_pairs_split':fit_split,'reply_pairs_without_single_containing_chunk':split}


def open_index(path,identity):
    conn=sqlite3.connect(path);conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS chunks (chunk_id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL,vector_json TEXT NOT NULL)')
    existing=conn.execute("SELECT value FROM metadata WHERE key='identity'").fetchone()
    if existing and json.loads(existing[0])!=identity:conn.close();raise ValueError('index_identity')
    conn.execute("INSERT OR IGNORE INTO metadata VALUES ('identity',?)",(packed(identity).decode(),));conn.commit();return conn


def verify_index(path,identity,expected):
    with closing(sqlite3.connect(path)) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('sqlite_integrity')
        if json.loads(conn.execute("SELECT value FROM metadata WHERE key='identity'").fetchone()[0])!=identity:raise ValueError('reopen_identity')
        rows=conn.execute('SELECT chunk_id,metadata_json,vector_json FROM chunks').fetchall()
        if {r[0] for r in rows}!={r['chunk_id'] for r in expected}:raise ValueError('index_coverage')
        byid={r['chunk_id']:r for r in expected}
        for ident,metadata,vector in rows:
            if json.loads(metadata)!=byid[ident]:raise ValueError('reopen_metadata')
            validate_vectors([json.loads(vector)],1)


def build_pair(documents,tokenizer,embedder,root,model_identity,threshold=.65,fail_before_publish=False):
    root=Path(root)
    if root.is_symlink():raise ValueError('symlink_root')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    config={'max_tokens':MAX_TOKENS,'overlap':OVERLAP,'transition_threshold':threshold,'tokenizer':tokenizer.identity,'model':model_identity,'pipeline_sha256':file_hash(__file__)}
    identity={'corpus_sha256':digest(documents),'config':config};generation=digest(identity)[:24];directory=root/generation;directory.mkdir(mode=0o700,exist_ok=True);directory.chmod(0o700)
    if any(p.is_symlink() for p in directory.iterdir()):raise ValueError('symlink_generation')
    if (directory/'state.json').exists() and json.loads((directory/'state.json').read_text()).get('status')=='complete':
        current=json.loads((root/'current.json').read_text()) if (root/'current.json').exists() else None
        if current and current['generation']==generation:
            if file_hash(directory/'expected-chunks.json')!=current['expected_chunks_sha256']:raise ValueError('expected_manifest_hash')
            expected=json.loads((directory/'expected-chunks.json').read_text())
            if expected['identity']!=identity:raise ValueError('expected_identity')
            for strategy in ['fixed','structure']:verify_index(directory/(strategy+'.db'),identity|{'strategy':strategy},expected['strategies'][strategy])
            return json.loads((directory/'comparison.json').read_text())
    started=time.monotonic();all_chunks={};strategy_reports={}
    with (root/'.build.lock').open('a') as lock:
        (root/'.build.lock').chmod(0o600)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic_json(directory/'state.json',{'status':'building','identity':identity})
        def event(phase,**fields):
            record={'utc':datetime.now(timezone.utc).isoformat(),'phase':phase,**fields}
            with (directory/'actions.jsonl').open('ab') as stream:stream.write(packed(record)+b'\n');stream.flush();os.fsync(stream.fileno())
            (directory/'actions.jsonl').chmod(0o600)
            print(json.dumps(record),flush=True)
        try:
            for strategy in ['fixed','structure']:
                strategy_started=time.monotonic();output=[];transition_inputs=0;forced=0
                event('strategy_start',strategy=strategy)
                usage_before=(embedder.calls,embedder.inputs,embedder.seconds)
                plans=directory/'structure-plans';plans.mkdir(mode=0o700,exist_ok=True)
                for doc_number,document in enumerate(documents):
                    if not document['text']:raise ValueError('empty_document')
                    if strategy=='fixed':ranges=fixed_ranges(document['text'],tokenizer)
                    else:
                        plan_path=plans/(digest(document)+'.json')
                        plan_identity={'document_sha256':digest(document),'config_sha256':digest(config)}
                        if plan_path.exists():
                            plan=json.loads(plan_path.read_text())
                            if plan['identity']!=plan_identity:raise ValueError('structure_plan_identity')
                            ranges=[tuple(r) for r in plan['ranges']];stats=plan['stats']
                        else:
                            ranges,stats=structure_ranges(document,tokenizer,embedder,threshold)
                            atomic_json(plan_path,{'identity':plan_identity,'ranges':ranges,'stats':stats})
                        transition_inputs+=stats['transition_inputs'];forced+=stats['forced_breaks']
                    output.extend(chunks(document,ranges,strategy,tokenizer,config))
                    if doc_number%50==0 or doc_number==len(documents)-1:event('documents_prepared',strategy=strategy,documents=doc_number+1,chunks=len(output))
                if len({r['chunk_id'] for r in output})!=len(output):raise ValueError('duplicate_chunk_id')
                path=directory/(strategy+'.db');conn=open_index(path,identity|{'strategy':strategy})
                try:
                    existing={r[0] for r in conn.execute('SELECT chunk_id FROM chunks')}
                    if existing-{r['chunk_id'] for r in output}:raise ValueError('unexpected_checkpoint_chunk')
                    pending=[r for r in output if r['chunk_id'] not in existing]
                    for start in range(0,len(pending),embedder.batch_size):
                        batch=pending[start:start+embedder.batch_size];vectors=embedder.embed([r['text'] for r in batch])
                        validate_vectors(vectors,len(batch))
                        conn.executemany('INSERT INTO chunks VALUES (?,?,?)',[(r['chunk_id'],packed(r).decode(),packed(v).decode()) for r,v in zip(batch,vectors)]);conn.commit()
                        event('embedding_batch_saved',strategy=strategy,saved=len(existing)+min(start+len(batch),len(pending)),total=len(output))
                finally:conn.close()
                path.chmod(0o600);verify_index(path,identity|{'strategy':strategy},output)
                sizes=sorted(r['token_count'] for r in output);all_chunks[strategy]=output
                strategy_reports[strategy]=reply_metrics(documents,output,tokenizer)|{'chunks':len(output),'tokens':{'min':min(sizes),'median':statistics.median(sizes),'p95':sizes[max(0,math.ceil(len(sizes)*.95)-1)],'max':max(sizes)},
                    'overlap_chars':sum(len(r['text']) for r in output)-sum(len(d['text']) for d in documents),'section_crossings':sum(len(r['source_sections'])>1 for r in output),'forced_breaks':forced,
                    'transition_inputs':transition_inputs,'embedding_calls_measured':embedder.calls-usage_before[0],'embedding_inputs_measured':embedder.inputs-usage_before[1],'embedding_seconds_measured':embedder.seconds-usage_before[2],'elapsed_seconds':time.monotonic()-strategy_started,'file_bytes':path.stat().st_size}
            atomic_json(directory/'expected-chunks.json',{'identity':identity,'strategies':all_chunks})
            for strategy in ['fixed','structure']:verify_index(directory/(strategy+'.db'),identity|{'strategy':strategy},all_chunks[strategy])
            report={'generation':generation,'identity':identity,'strategies':strategy_reports,'elapsed_seconds':time.monotonic()-started,'peak_rss_native':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rss_unit':'KiB_on_Linux_bytes_on_macOS',
                    'embedder_usage':{'calls':embedder.calls,'inputs':embedder.inputs,'seconds':embedder.seconds,'prompt_eval_count':embedder.prompt_eval_count},'semantic_review_required':True}
            atomic_json(directory/'comparison.json',report)
            if fail_before_publish:raise RuntimeError('injected_before_publish')
            atomic_json(directory/'state.json',{'status':'complete','identity':identity})
            atomic_json(root/'current.json',{'generation':generation,'corpus_sha256':identity['corpus_sha256'],'identity_sha256':digest(identity),'expected_chunks_sha256':file_hash(directory/'expected-chunks.json')})
            return report
        except Exception as error:
            atomic_json(directory/'state.json',{'status':'incomplete','identity':identity,'error_type':type(error).__name__});raise


def main():
    os.umask(0o077);cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--documents',type=Path,required=True);cli.add_argument('--tokenizer',type=Path,required=True);cli.add_argument('--tokenizer-revision',required=True);cli.add_argument('--tokenizer-sha256',required=True)
    cli.add_argument('--root',type=Path,required=True);cli.add_argument('--ollama',default='http://127.0.0.1:11434');cli.add_argument('--model-digest',required=True);cli.add_argument('--transition-threshold',type=float,default=.65);cli.add_argument('--build',action='store_true');args=cli.parse_args()
    documents=json.loads(args.documents.read_text());documents=documents['documents'] if isinstance(documents,dict) else documents
    if not documents or len({d['document_id'] for d in documents})!=len(documents):raise ValueError('document_ids')
    tokenizer=PinnedTokenizer(args.tokenizer,args.tokenizer_revision,args.tokenizer_sha256)
    if not args.build:
        print(json.dumps({'documents':len(documents),'corpus_sha256':digest(documents),'fixed_chunks':sum(len(fixed_ranges(d['text'],tokenizer)) for d in documents),'network_calls':0}));return
    embedder=Ollama(args.ollama,args.model_digest);identity=embedder.verify_model();report=build_pair(documents,tokenizer,embedder,args.root,identity,args.transition_threshold)
    print(json.dumps({'generation':report['generation'],'strategies':report['strategies'],'elapsed_seconds':report['elapsed_seconds']}))

if __name__=='__main__':main()
