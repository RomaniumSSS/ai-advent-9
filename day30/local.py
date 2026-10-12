"""Самостоятельные identity/Ollama/flock из Day29 core.py, база b3e607e."""
from contextlib import closing, contextmanager
import re
import http.client
import socket
from urllib.parse import urlsplit
import fcntl, hashlib, json, math, os, sqlite3, tempfile, time, urllib.request, uuid
from pathlib import Path
from protocol import strict_json,normalize_wire
from limits import SYNTHESIS_DEADLINE_SECONDS,provider_deadline_cap
MODEL = 'qwen3:8b-q8_0'
GEN_DIGEST = 'e56358ca25dd14db6853a9f68a92d717aaa6f0a94250a72d1a0f3d86a9f30130'
EMBED_MODEL = 'qwen3-embedding:0.6b'
EMBED_DIGEST = 'ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d'
EMBED_OPTIONS = {'num_ctx':2048,'num_thread':1,'num_batch':128}
GEN_OPTIONS = {'num_ctx':8192,'num_predict':1024,'temperature':0}
GENERATION = '5d5502c69976163325ad6c35'
DB_SHA = '9894d937c4bcbae653459a6fe758f231992571e436622a0cd33fcda7f707f11b'
CORPUS_SHA = '90bae6a60fc91b8419a07a5ba445beecf95dd5701f69ea84a423a845d4dcf240'
OLLAMA_URL = 'http://127.0.0.1:11434'
TIMEOUT = SYNTHESIS_DEADLINE_SECONDS
SOURCE_SCHEMA = {'properties':{'source_refs':{'maxItems':5}}}
def packed(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')

def provider_body(value):
    # AICODE-NOTE: сохраняем wire insertion order. Native Qwen3 Go-map path может
    # сортировать keys повторно; structural aliases отдельно защищают этот порядок.
    return json.dumps(value,ensure_ascii=False,sort_keys=False,separators=(',',':')).encode('utf-8')

def save_private(path, value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    path.parent.chmod(0o700)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:out.write(packed(value));out.flush();os.fsync(out.fileno())
    os.replace(tmp,path);path.chmod(0o600)

def vector(value):
    if not isinstance(value,list) or len(value)!=1024 or any(type(x) not in (int,float) or not math.isfinite(x) for x in value):
        raise ValueError('invalid_vector')
    norm=math.sqrt(sum(x*x for x in value))
    if norm==0 or abs(norm-1)>.001:raise ValueError('vector_not_unit')
    return value

def load_index(root):
    root=Path(root).resolve()
    generation=json.loads((root/'current.json').read_text())['generation']
    if generation!=GENERATION:raise ValueError('frozen_generation_mismatch')
    path=root/generation/'structure.db'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=DB_SHA:raise ValueError('index_sha_mismatch')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        identity=json.loads(db.execute("SELECT value FROM metadata WHERE key='identity'").fetchone()[0])
        m=identity['config']['model']
        if (identity.get('corpus_sha256')!=CORPUS_SHA or identity.get('strategy')!='structure' or
            m['model']!=EMBED_MODEL or m['digest']!=EMBED_DIGEST or m['options']!=EMBED_OPTIONS or m['truncate'] is not False):
            raise ValueError('incompatible_index_identity')
        chunks=[];seen=set()
        for cid,metadata,vec in db.execute('SELECT chunk_id,metadata_json,vector_json FROM chunks'):
            c=json.loads(metadata)
            if cid in seen or c.get('chunk_id',cid)!=cid or not isinstance(c.get('text'),str) or not isinstance(c.get('document_id'),str):
                raise ValueError('invalid_chunk_metadata')
            if c.get('text_sha256')!=hashlib.sha256(c['text'].encode()).hexdigest():raise ValueError('chunk_hash_mismatch')
            seen.add(cid)
            chunks.append({k:c.get(k) for k in ('document_id','text','source','day')} |
                          {'chunk_id':cid,'vector':vector(json.loads(vec))})
    if len(chunks)!=724 or len({c['document_id'] for c in chunks})!=663:raise ValueError('index_count_mismatch')
    return dict(generation=generation,db_sha256=DB_SHA,corpus_sha256=CORPUS_SHA,identity=identity),chunks

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('ollama_redirect_forbidden')

def opaque_response_body(raw,stage=None,completed=False,http_status=None):
    data=raw.encode('utf-8',errors='surrogatepass') if isinstance(raw,str) else bytes(raw)
    return {'bytecount':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'transport_stage':stage,'completed':bool(completed),'http_status':http_status}

def safe_final_shape(value):
    """Persistence allowlist only; refs/coverage/meaning still use strict local gates."""
    strings=lambda item:isinstance(item,list) and all(isinstance(v,str) for v in item)
    if not isinstance(value,dict):return False
    stage='selection' if set(value)=={'a_evidence','b_coverage'} else 'synthesis'
    try:value=normalize_wire(stage,value)
    except ValueError:return False
    if set(value)=={'evidence','coverage'}:
        evidence=value['evidence'];coverage=value['coverage']
        return (isinstance(evidence,dict) and isinstance(coverage,dict) and
            all(isinstance(eid,str) and re.fullmatch(r'S\d+\.U\d+',eid) and strings(groups)
                for eid,groups in evidence.items()) and
            all(isinstance(qid,str) and re.fullmatch(r'Q\d+',qid) and
                isinstance(status,str) and status in ('full','partial','none') for qid,status in coverage.items()))
    if set(value)!={'points','doubtful_aspect_ids','conclusion'}:return False
    if not isinstance(value['points'],list) or not strings(value['doubtful_aspect_ids']):return False
    for point in value['points']:
        if (not isinstance(point,dict) or set(point)!={'aspect_ids','evidence_id','text'} or
                not strings(point['aspect_ids']) or not isinstance(point['evidence_id'],str) or
                not isinstance(point['text'],str)):return False
    conclusion=value['conclusion']
    return (isinstance(conclusion,dict) and set(conclusion)=={'text','point_refs'} and
            isinstance(conclusion['text'],str) and strings(conclusion['point_refs']))

def sanitized_response(response):
    """Persistence copy only: final JSON/metrics; provider reasoning stays in RAM."""
    if not isinstance(response,dict):return {'response_type':type(response).__name__}
    safe={}
    for key in ('model','created_at','done','done_reason','prompt_eval_count','eval_count',
                'total_duration','load_duration','prompt_eval_duration','eval_duration'):
        value=response.get(key)
        if type(value) in (int,bool) or (isinstance(value,str) and len(value)<=256):safe[key]=value
    message=response.get('message')
    if isinstance(message,dict):
        final={}
        if message.get('role') in ('assistant','user','system'):final['role']=message['role']
        content=message.get('content')
        if isinstance(content,str):
            try:
                parsed=strict_json(content)
                # AICODE-NOTE: denylist имён пропускал arbitrary analysis поля в private state.
                # Только protocol shape безопасен для копии; unknown payload opaque, не repair.
                if not safe_final_shape(parsed):raise ValueError('unsafe_final_copy')
            except (ValueError,TypeError):final['content_metadata']=opaque_response_body(content)
            else:final['content']=content
        elif 'content' in message:final['content_type']=type(content).__name__
        safe['message']=final
        if 'thinking' in message:safe['reasoning_present']=bool(message['thinking'])
    return safe

class ProviderTimeout(TimeoutError):
    def __init__(self,body,stage,http_status=None):
        super().__init__('provider_deadline')
        self.response_metadata=opaque_response_body(body,stage,http_status=http_status);self.transport_stage=stage

class DeadlineSocket(socket.socket):
    def __init__(self,*args,deadline,**kwargs):
        super().__init__(*args,**kwargs);self.deadline=deadline
    def prepare_io(self):
        remaining=self.deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('provider_deadline')
        self.settimeout(remaining)
    def connect(self,address):self.prepare_io();return super().connect(address)
    def sendall(self,data,flags=0):self.prepare_io();return super().sendall(data,flags)
    def recv_into(self,buffer,nbytes=0,flags=0):self.prepare_io();return super().recv_into(buffer,nbytes,flags)
    def recv(self,bufsize,flags=0):self.prepare_io();return super().recv(bufsize,flags)

class DeadlineConnection(http.client.HTTPConnection):
    def __init__(self,host,port,deadline):
        super().__init__(host,port,timeout=max(.001,deadline-time.monotonic()))
        self.deadline=deadline;self.transport_socket=None
    def connect(self):
        # Фиксированный IPv4 loopback: нет DNS/proxy/redirect и фонового reader.
        sock=DeadlineSocket(socket.AF_INET,socket.SOCK_STREAM,deadline=self.deadline)
        self.transport_socket=sock;self.sock=sock
        sock.connect((self.host,self.port))
    def cancel_transport(self):
        sock=self.transport_socket
        if sock is not None:
            try:sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            sock.close()
        self.close()


def provider_deadline_seconds(stage='default'):
    # AICODE-NOTE: общий ceiling300 не заменяет явный stage cap в trace/budget.
    # Короткий fixture TIMEOUT по-прежнему сокращает absolute deadline любой стадии.
    return min(TIMEOUT,provider_deadline_cap(stage))

class Ollama:
    def __init__(self,url=OLLAMA_URL):
        if url!=OLLAMA_URL:raise ValueError('ollama_fixed_loopback_required')
        self.url=url;self.network=[]
    def request(self,path,payload=None,deadline_seconds=None):
        if path not in ('/api/tags','/api/show','/api/embed','/api/chat','/api/ps','/api/version','/api/generate'):raise ValueError('invalid_local_route')
        bound=provider_deadline_seconds() if deadline_seconds is None else min(TIMEOUT,SYNTHESIS_DEADLINE_SECONDS,deadline_seconds)
        if bound<=0:raise ValueError('invalid_provider_deadline')
        self.network.append({'url':self.url+path,'method':'POST' if payload is not None else 'GET','deadline_seconds':bound})
        deadline=time.monotonic()+bound
        endpoint=urlsplit(self.url);connection=DeadlineConnection(endpoint.hostname,endpoint.port,deadline)
        response=None;body=bytearray();stage='connect';complete=False
        try:
            connection.request('POST' if payload is not None else 'GET',path,
                body=provider_body(payload) if payload is not None else None,
                headers={'Content-Type':'application/json','Connection':'close'})
            stage='headers';response=connection.getresponse()
            stage='body'
            while True:
                if time.monotonic()>=deadline:raise TimeoutError('provider_deadline')
                part=response.read1(min(65536,8*1024*1024+1-len(body)))
                if not part:break
                body.extend(part)
                if len(body)>8*1024*1024:raise ValueError('ollama_response_too_large')
            if time.monotonic()>=deadline:raise TimeoutError('provider_deadline')
            complete=True
            if 300<=response.status<400:raise ValueError('ollama_redirect_forbidden')
            if response.status!=200:raise ValueError('ollama_response_error')
            data=strict_json(body)
            if not isinstance(data,dict) or data.get('error'):
                exc=ValueError('ollama_response_error');exc.response_data=data;raise exc
        except (TimeoutError,socket.timeout):
            raise ProviderTimeout(body,stage,response.status if response else None) from None
        except (ValueError,http.client.HTTPException,OSError) as exc:
            exc.response_metadata=opaque_response_body(body,stage,complete,response.status if response else None);exc.transport_stage=stage
            exc.response_complete=complete;exc.response_status=response.status if response else None
            raise
        finally:
            # Синхронный shutdown/close завершён до выхода в caller и освобождения flock.
            # HTTPResponse может владеть socket после Connection:close, поэтому держим transport.
            connection.cancel_transport()
            if response is not None:response.close()
        return data
    def verify(self, profile=None):
        tags=self.request('/api/tags').get('models',[])
        profile=profile or {'model':MODEL,'digest':GEN_DIGEST,'options':GEN_OPTIONS}
        for name,digest in ((profile['model'],profile['digest']),(EMBED_MODEL,EMBED_DIGEST)):
            entries=[m for m in tags if m.get('name')==name or m.get('model')==name]
            if len(entries)!=1 or entries[0].get('digest')!=digest:raise ValueError('model_digest_mismatch:'+name)
            show=self.request('/api/show',{'model':name})
            if show.get('remote_host') or show.get('remote_model') or 'cloud' in show.get('capabilities',[]):
                raise ValueError('remote_model_forbidden')
            if not isinstance(show.get('model_info'),dict) or not show['model_info']:raise ValueError('missing_local_model_info')
            info=show['model_info']
            windows=[v for k,v in info.items() if k.endswith('.context_length')]
            required=profile['options']['num_ctx'] if name==profile['model'] else EMBED_OPTIONS['num_ctx']
            if not windows or any(type(v) is not int for v in windows) or max(windows)<required:raise ValueError('model_context_too_small')
        return {'generator_digest':profile['digest'],'embedding_digest':EMBED_DIGEST,'generator_show':self.request('/api/show',{'model':profile['model'],'verbose':True})}
    def embed(self,question,deadline_seconds=None):
        r=self.request('/api/embed',{'model':EMBED_MODEL,'input':query_input(question),
            'truncate':False,'options':EMBED_OPTIONS,'keep_alive':'5m'},
            **({'deadline_seconds':deadline_seconds} if deadline_seconds is not None else {}))
        try:
            if r.get('model')!=EMBED_MODEL or len(r.get('embeddings',[]))!=1:raise ValueError('invalid_embedding_response')
            return vector(r['embeddings'][0])
        except (ValueError,TypeError,KeyError) as exc:
            exc.response_data=r;raise
    def chat(self,messages,schema=None,options=None,think=False,native_format=True,deadline_seconds=None):
        payload={'model':MODEL,'messages':messages,'stream':False,'think':think,
                 'options':dict(GEN_OPTIONS if options is None else options),'keep_alive':'5m'}
        # AICODE-NOTE: thinking+native format вызывает внутренний restart в Ollama0.33.3.
        # При explicit native_format=False ключ omit; текущий12 всегда native/think=false.
        if native_format:payload['format']=schema
        return self.request('/api/chat',payload,**({'deadline_seconds':deadline_seconds} if deadline_seconds is not None else {}))

def query_input(question):
    return 'Instruct: Given a question about the course, retrieve relevant passages that answer the question\nQuery:'+question

def validate_question(question):
    if not isinstance(question,str) or not question.strip() or len(question)>500:raise ValueError('question_length_1_to_500')
    return question.strip()

def words(text):return set(re.findall(r'[^\W_]{3,}',text.casefold()))

@contextmanager
def generation_lock():
    # AICODE-NOTE: общий lock берётся первым; Day28 lock сохраняет совместимость
    # со старым UI, который ещё может работать на той же машине.
    fds=[]
    try:
        for name in ('ai-advent-local-inference','day28-local-rag'):
            fd=os.open(Path(tempfile.gettempdir())/f'{name}-{os.getuid()}.lock',os.O_WRONLY|os.O_CREAT,0o600)
            fds.append(fd)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise ValueError('local_generation_busy')
        yield
    finally:
        for fd in reversed(fds):os.close(fd)
