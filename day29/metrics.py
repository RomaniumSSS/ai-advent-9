"""Наблюдаемые RSS Ollama и системный swap; это не полный пик unified memory."""
from datetime import datetime, timezone
import math, re, subprocess, threading, time

def command(args):
    try:return subprocess.run(args,text=True,capture_output=True,timeout=3,check=True).stdout
    except (OSError,subprocess.SubprocessError):return None

def system_snapshot():
    swap=command(['sysctl','-n','vm.swapusage']);vm=command(['vm_stat'])
    match=re.search(r'used\s*=\s*([\d.]+)([MG])',swap or '')
    used=float(match[1])* (1024**2 if match[2]=='M' else 1024**3) if match else None
    counters={}
    for label in ('Pageouts','Swapins','Swapouts'):
        m=re.search(r'^'+label+r':\s*(\d+)',vm or '',re.M);counters[label.lower()]=int(m[1]) if m else None
    return {'timestamp':datetime.now(timezone.utc).isoformat(),'swap_used_bytes':used,'vm_counters':counters,
            'missing_reason':None if used is not None else 'system_swap_unavailable'}

def parse_processes(raw):
    if raw is None:return None
    rows={}
    for line in raw.splitlines():
        fields=line.strip().split(None,3)
        if len(fields)!=4:continue
        try:
            pid,ppid,rss=map(int,fields[:3]);identity=fields[3]
        except ValueError:continue
        rows[pid]={'pid':pid,'ppid':ppid,'rss_bytes':rss*1024,'identity':identity}
    def descended_from(pid,ancestors):
        seen=set()
        while pid in rows and pid not in seen:
            if pid in ancestors:return True
            seen.add(pid);pid=rows[pid]['ppid']
        return False
    # AICODE-NOTE: Ollama 0.33.3 запускает llama-server как дочерний процесс;
    # имя «ollama runner» здесь отсутствует. comm не собирает аргументы/секреты.
    candidates={pid for pid,p in rows.items() if p['identity'].rsplit('/',1)[-1]=='ollama'}
    daemons={pid for pid in candidates if not descended_from(rows[pid]['ppid'],candidates)}
    result=[]
    for pid,p in rows.items():
        name=p['identity'].rsplit('/',1)[-1]
        role='daemon' if pid in daemons else 'runner' if name in ('llama-server','ollama') and descended_from(p['ppid'],daemons) else None
        if role:result.append({**p,'role':role})
    return result

def process_sample():
    processes=parse_processes(command(['ps','-axo','pid=,ppid=,rss=,comm=']))
    return {'timestamp':datetime.now(timezone.utc).isoformat(),'processes':processes,
            'sum_rss_bytes':sum(p['rss_bytes'] for p in processes) if processes else None,
            'missing_reason':None if processes else 'no_ollama_process_observed' if processes==[] else 'ps_unavailable'}

def summarize_samples(samples,interval):
    values=[s['sum_rss_bytes'] for s in samples if s.get('sum_rss_bytes') is not None]
    roles={p['role'] for s in samples for p in (s.get('processes') or [])}
    incomplete=sum({p['role'] for p in (s.get('processes') or [])}!={'daemon','runner'} for s in samples)
    sets={tuple(sorted((p['pid'],p['role']) for p in (s.get('processes') or []))) for s in samples}
    counts=sorted({len(s.get('processes') or []) for s in samples})
    reason='missing_process_samples' if len(values)!=len(samples) else 'incomplete_process_roles' if incomplete else 'process_set_changed' if len(sets)!=1 else None
    return {'sample_interval_seconds':interval,'sample_count':len(samples),'missing_samples':len(samples)-len(values),
            'observed_max_sum_rss_bytes':max(values) if values else None,
            'pids':sorted({p['pid'] for s in samples for p in (s.get('processes') or [])}),
            'observed_roles':sorted(roles),'samples':samples,
            'missing_reason':None if values else 'no_valid_process_samples',
            'comparison_eligible':bool(values) and reason is None,'incomplete_process_samples':incomplete,
            'process_counts':counts,'comparison_reason':reason,
            'limitations':'Observed daemon+runner RSS, shared pages may be counted twice; sampling may miss peaks; Metal/unified memory is incomplete.'}

class Sampler:
    def __init__(self,interval=.5):self.interval=interval;self.samples=[];self.event=threading.Event();self.thread=None
    def start(self):
        self.before=system_snapshot();self.samples.append(process_sample())
        def run():
            while not self.event.wait(self.interval):self.samples.append(process_sample())
        self.thread=threading.Thread(target=run,daemon=True);self.thread.start()
    def stop(self):
        self.event.set()
        if self.thread:self.thread.join(timeout=4)
        self.samples.append(process_sample());after=system_snapshot()
        return {**summarize_samples(self.samples,self.interval),'system_before':self.before,'system_after':after}

def ollama_metrics(raw):
    keys=('total_duration','load_duration','prompt_eval_count','prompt_eval_duration','eval_count','eval_duration')
    values={k:raw.get(k) if type(raw.get(k)) in (int,float) and math.isfinite(raw[k]) and raw[k]>=0 else None for k in keys}
    values['seconds']={k:values[k]/1e9 if values[k] is not None else None for k in keys if k.endswith('duration')}
    values['tokens_per_second']=values['eval_count']/(values['eval_duration']/1e9) if values['eval_count'] is not None and values['eval_duration'] and values['eval_duration']>0 else None
    return values
