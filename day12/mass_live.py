"""Mass-live: серверный at-most-once dispatch и owner runner без HTTP retry."""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.parse import urlsplit

from live_budget import BudgetStop, canonical, decimal, digest, raw, MODEL
from mass_checkpoint import Checkpoint, PRIOR_COST, PRIOR_LEDGER, ROOT, TERMINAL, file_hash
from mass_fixture import prepare, open_agent, snapshot, expected_initial, save_response
from mass_grade import grade


def utc():
    return datetime.now(timezone.utc).isoformat()


def require(ok, reason):
    if not ok:
        raise BudgetStop(reason)


def telemetry(response, reserve, total, policy):
    require(response.get('model') == MODEL, 'response model mismatch')
    require(response.get('provider') in policy['provider_raw_names'], 'response provider mismatch')
    require(isinstance(response.get('id'),str) and bool(response['id']), 'request id missing')
    u = response.get('usage') or {}
    for key in ('prompt_tokens','completion_tokens','total_tokens'):
        require(type(u.get(key)) is int and u[key] >= 0, 'invalid '+key)
    require(u['total_tokens'] == u['prompt_tokens']+u['completion_tokens'],'total tokens mismatch')
    require(u['prompt_tokens'] <= policy['max_prompt_tokens'] and u['completion_tokens'] <= 256,'token reservation exceeded')
    cached = (u.get('prompt_tokens_details') or {}).get('cached_tokens')
    reasoning = (u.get('completion_tokens_details') or {}).get('reasoning_tokens')
    require(type(cached) is int and 0 <= cached <= u['prompt_tokens'],'cached tokens missing/invalid')
    require(type(reasoning) is int and reasoning == 0,'reasoning none violated/unknown')
    charge = decimal(u.get('cost'))
    require(charge <= reserve and total <= Decimal('0.02'),'cost reservation exceeded')
    choices = response.get('choices')
    require(isinstance(choices,list) and len(choices)==1,'invalid choices')
    m = choices[0].get('message',{})
    require(not m.get('tool_calls') and not m.get('function_call'),'unexpected action')
    require(m.get('content') is None or isinstance(m.get('content'),str),'invalid content')
    require(choices[0].get('finish_reason') in ('stop','length','content_filter'),'unexpected finish reason')


class Campaign:
    def __init__(self, ledger, policy, db, gate_path, send=None):
        policy = json.loads(Path(policy).read_text()) if not isinstance(policy,dict) else policy
        template = json.loads((ROOT/'deploy/mass-live-policy.json').read_text())
        require(policy == template,'campaign policy differs from pinned policy')
        if os.environ.get('DAY12_MASS_LEDGER'):
            require(Path(ledger).resolve() == Path(os.environ['DAY12_MASS_LEDGER']).resolve(),'wrong global campaign ledger')
        self.policy = policy
        self.id = policy['campaign_id']
        self.db = Path(db).resolve()
        self.gate_path = Path(gate_path)
        self.ledger = Checkpoint(ledger,policy,self.id)
        self.cases = {c['id']:c for c in self.ledger.manifest['cases']}
        self.send = send or self._send

    def _send(self, **kwargs):
        # AICODE-NOTE: создан только под durable in_flight + межпроцессным lock.
        # Клиент legacy/manual_resume сюда не попадает и не меняет extra_body.
        from openai import OpenAI
        with OpenAI(api_key=os.environ['OPENROUTER_API_KEY'],base_url='https://openrouter.ai/api/v1',
                    max_retries=0,timeout=600) as client:
            return client.chat.completions.create(**kwargs)

    def gate(self, state):
        g = json.loads(self.gate_path.read_text())
        require(g.get('campaign_id') == self.id and g.get('manifest_hash') == state['manifest_hash'],'preflight manifest mismatch')
        require(g.get('db_path') == str(self.db),'preflight DB path mismatch')
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(g['verified_at'])).total_seconds()
        require(0 <= age <= 86400,'preflight expired')
        for key in ('public_mutations_denied','public_evidence_denied','direct_ports_denied','loopback_listeners',
                    'sqlite_integrity','neighbours_healthy','owner_ssh_tunnel','legacy_paid_disabled','parameters_supported'):
            require(g.get(key) is True,'preflight missing: '+key)
        for key in ('network_evidence','tariff_evidence'):
            evidence = g[key]
            require(file_hash(evidence['path']) == evidence['sha256'],'preflight evidence changed')
        require(g.get('provider_raw_names') == self.policy['provider_raw_names'],'provider aliases not verified')
        for key in ('prompt_usd_per_million','completion_usd_per_million'):
            require(0 < decimal(g[key]) <= decimal(self.policy[key]),'tariff ceiling invalid')
        old_path = g['prior_ledger']['path']
        require(file_hash(old_path)==g['prior_ledger']['sha256'],'VPS prior ledger bytes changed')
        require(digest(json.loads(Path(old_path).read_text()))==PRIOR_LEDGER,'VPS prior ledger differs')
        if state.get('gate_anchor'):
            require(state['gate_anchor']==digest(g),'preflight changed after campaign start')
        else:
            state['gate_anchor']=digest(g)
        return g

    def evidence(self):
        with self.ledger.locked():
            state = self.ledger.checked()
            return self.report(state)

    def report(self,state):
        groups = {}
        for group in ('profile','memory','state','adversarial'):
            entries = [state['cases'][c['id']] for c in self.cases.values() if c['group']==group]
            counts = {status:sum(e['status']==status for e in entries) for status in sorted(TERMINAL)}
            executed = sum('response' in e for e in entries)
            groups[group] = {**counts,'planned':len(entries),'executed':executed,
                             'pass_rate_planned':counts['pass']/len(entries),
                             'pass_rate_executed':counts['pass']/executed if executed else None}
        return {'provenance':'mass campaign; only entries with raw response are provider evidence',
                'ledger':state,'groups':groups,'prior_reported_cost_usd':PRIOR_COST,
                'total_reported_cost_usd':str(decimal(PRIOR_COST)+decimal(state['new_reported_cost_usd'])),
                'cost_complete':all(not e.get('sent') or 'reported_cost_usd' in e for e in state['cases'].values()),
                'unresolved_reservations_usd':str(sum((decimal(e['reserved_usd']) for e in state['cases'].values() if e.get('sent') and 'reported_cost_usd' not in e),Decimal('0'))),
                'defects':[{'id':k,'status':e['status'],'grading':e.get('grading'),'error':e.get('error')}
                           for k,e in state['cases'].items() if e['status'] in TERMINAL-{'pass'}]}

    def restart_prepare(self):
        with self.ledger.locked():
            s = self.ledger.checked()
            require(not s['stopped'],'campaign stopped')
            require(all(s['cases'][k]['status'] in ('pass','quality_fail') for k in list(self.cases)[:18]),'restart must follow first 18 terminal responses')
            require(s['cases']['S03']['status']=='pending','restart boundary passed')
            if not s['restart']:
                invocation = os.environ.get('INVOCATION_ID')
                require(bool(invocation),'systemd InvocationID required')
                s['restart']={'status':'restart_pending','invocation':invocation,'pid':os.getpid(),'at':utc(),
                              'snapshot':snapshot(open_agent(self.db,self.id,self.cases['S01'])),
                              'completed_hash':digest({k:s['cases'][k] for k in list(self.cases)[:18]}),
                              'cost':s['new_reported_cost_usd'],'db_path':str(self.db)}
                self.ledger.checkpoint(s,'restart_pending')
            return s['restart']

    def restart_verify(self, evidence):
        with self.ledger.locked():
            s = self.ledger.checked()
            try:
                self.gate(s)
                r=s['restart']; require(r is not None,'restart not prepared')
                invocation=os.environ.get('INVOCATION_ID')
                require(bool(invocation) and invocation != r['invocation'] and os.getpid()!=r['pid'],'service not restarted')
                require(r['snapshot']==snapshot(open_agent(self.db,self.id,self.cases['S01'])),'restart state changed')
                require(r['completed_hash']==digest({k:s['cases'][k] for k in list(self.cases)[:18]}) and r['cost']==s['new_reported_cost_usd'],'restart evidence changed')
                require(evidence['invocation']==invocation and evidence['pid']==os.getpid(),'restart identity mismatch')
                for k in ('loopback_listeners','public_mutations_denied','public_evidence_denied','direct_ports_denied','neighbours_healthy','sqlite_integrity'):
                    require(evidence.get(k) is True,'restart check missing: '+k)
                require(file_hash(evidence['path'])==evidence['sha256'],'restart raw evidence changed')
                r.update(status='restart_verified',new_invocation=invocation,new_pid=os.getpid(),verified_at=utc(),evidence=evidence)
                self.ledger.checkpoint(s,'restart_verified')
                return r
            except Exception as error:
                self.ledger.stop(s,'restart validation:'+type(error).__name__)
                raise BudgetStop('restart validation failed') from None

    def dispatch(self, case_id):
        require(case_id in self.cases,'unknown case')
        with self.ledger.locked():
            s = self.ledger.checked()
            e = s['cases'][case_id]
            # Сначала восстановление неопределённого send любого case, даже при другом ID.
            uncertain = next((k for k,v in s['cases'].items() if v['status']=='in_flight'),None)
            if uncertain:
                self.ledger.stop(s,'unknown outcome after interrupted send',uncertain,'indeterminate')
                return self.report(s)
            if e['status'] in TERMINAL or s['stopped']:
                return self.report(s)
            case=self.cases[case_id]
            previous=list(self.cases)[:list(self.cases).index(case_id)]
            require(all(s['cases'][k]['status'] in ('pass','quality_fail') for k in previous),'case order violation')
            if case.get('requires_restart'):
                require(s['restart'] and s['restart']['status']=='restart_verified','restart verification required before S03')
            try:
                if e['status'] != 'response_recorded':
                    self.gate(s)
                if e['status']=='pending':
                    fixture=prepare(self.db,self.id,case)
                    agent=open_agent(self.db,self.id,case)
                    initial=snapshot(agent)
                    require(expected_initial(self.id,case,initial,s['cases']),'initial scope/state mismatch')
                    messages=agent.build_messages(case['question'])
                    for marker in case.get('context_forbidden',case['critical_forbidden']):
                        require(marker not in canonical(messages),'scope canary in payload')
                    blocks=[m for m in messages if m['role']=='system' and m['content'].startswith('ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ')]
                    require(len(blocks)==1 and blocks[0]==agent.store.load_profile().message(),'profile block mismatch')
                    without=[m for m in messages if m is not blocks[0]]
                    if case['group']=='profile':
                        peers=[c for c in self.cases.values() if c['group']=='profile' and c['paired_topic']==case['paired_topic'] and c['id'] in previous]
                        require(all(s['cases'][p['id']]['context_without_profile_hash']==digest(without) for p in peers),'paired prompt mismatch')
                    upper=sum(len(m['content'].encode())+64 for m in messages)+64
                    require(upper<=self.policy['max_prompt_tokens'],'prompt exceeds conservative bound')
                    request=agent.request_options(messages)
                    request['extra_body']['provider']={'only':['open-inference'],'allow_fallbacks':False,'require_parameters':True,
                                                       'max_price':{'prompt':float(self.policy['prompt_usd_per_million']),'completion':float(self.policy['completion_usd_per_million'])}}
                    e.update(status='prepared',campaign_id=self.id,case_id=case_id,group=case['group'],fixture=fixture,initial_state=initial,initial_state_hash=digest(initial),
                             request=request,request_hash=digest(request),messages_hash=digest(messages),profile=blocks[0],
                             profile_hash=digest(blocks[0]),context_without_profile_hash=digest(without),ordinal=len(previous)+1)
                    self.ledger.checkpoint(s,case_id+':prepared')
                if e['status']=='prepared':
                    require(snapshot(open_agent(self.db,self.id,case))==e['initial_state'],'state changed after preparation')
                    reserve=(self.policy['max_prompt_tokens']*decimal(self.policy['prompt_usd_per_million'])+256*decimal(self.policy['completion_usd_per_million']))/Decimal(1000000)
                    total=decimal(PRIOR_COST)+decimal(s['new_reported_cost_usd'])
                    if s['sent']>=24 or total+reserve>Decimal('0.02'):
                        self.ledger.stop(s,'global budget exhausted',case_id,'blocked_budget')
                        return self.report(s)
                    e.update(status='in_flight',sent=True,reserved_usd=str(reserve),started_at=utc())
                    s['sent']+=1
                    self.ledger.checkpoint(s,case_id+':in_flight')
                    started=time.monotonic()
                    response=raw(self.send(**e['request']))
                    e.update(status='response_recorded',response=response,response_hash=digest(response),latency_seconds=time.monotonic()-started,ended_at=utc())
                    # Сначала durable raw ответ, даже если provider/usage/cost некорректны.
                    self.ledger.checkpoint(s,case_id+':response_recorded')
                if e['status']=='response_recorded':
                    response=e['response']
                    if 'reported_cost_usd' not in e:
                        charge=decimal((response.get('usage') or {}).get('cost'))
                        e['reported_cost_usd']=str(charge)
                        s['new_reported_cost_usd']=str(decimal(s['new_reported_cost_usd'])+charge)
                        self.ledger.checkpoint(s,case_id+':cost_recorded')
                    total=decimal(PRIOR_COST)+decimal(s['new_reported_cost_usd'])
                    telemetry(response,decimal(e['reserved_usd']),total,self.policy)
                    e['telemetry']={'request_id':response['id'],'model':response['model'],'provider':response['provider'],
                                    'tokens':response['usage'],'cost_source':'provider usage.cost'}
                    choice=response['choices'][0]
                    grading=grade(case,choice['message'].get('content') or '',choice['finish_reason'])
                    grading['human_rubric']['response_hash']=e['response_hash']
                    e['grading']=grading
                    if grading['status']=='safety_fail':
                        self.ledger.stop(s,'response security predicate',case_id)
                    else:
                        agent=open_agent(self.db,self.id,case)
                        save_response(agent,self.id,case,response,e['latency_seconds'])
                        post=snapshot(agent)
                        require(post['notes']==e['initial_state']['notes'] and post['profile']==e['initial_state']['profile'],'unexpected state mutation')
                        expected=e['initial_state']['history']+[{'role':'user','content':case['question']},{'role':'assistant','content':choice['message'].get('content') or ''}]
                        require(post['history']==expected,'history persistence mismatch')
                        e.update(status=grading['status'],post_state=post,post_state_hash=digest(post),terminal_at=utc(),cumulative_total_usd=str(total))
                        self.ledger.checkpoint(s,case_id+':terminal')
            except BaseException as error:
                # Не сохраняем exception text: SDK может включить credential/header.
                status='indeterminate' if e['status']=='in_flight' else 'safety_fail'
                self.ledger.stop(s,'dispatch:'+type(error).__name__,case_id,status)
                if not isinstance(error,Exception): raise
            return self.report(s)


def owner_request(base,path,body=None):
    url=urlsplit(base)
    require(url.scheme=='http' and url.hostname=='127.0.0.1' and url.port is not None and not url.username and not url.password and url.path in ('','/'),'owner tunnel must use explicit loopback port')
    req=Request(base.rstrip('/')+path,data=canonical(body).encode() if body is not None else None,
                headers={'Content-Type':'application/json'})
    # urllib без retry; неопределённый HTTP исход восстанавливается только ledger GET.
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise BudgetStop('owner tunnel redirect denied')
    with build_opener(ProxyHandler({}), NoRedirect()).open(req,timeout=660) as result:
        return json.load(result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tunnel',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--restart-evidence',type=Path)
    args=p.parse_args()
    report=owner_request(args.tunnel,'/api/campaign/evidence')
    if args.restart_evidence:
        owner_request(args.tunnel,'/api/campaign/restart-verify',json.loads(args.restart_evidence.read_text()))
    for case in report['ledger']['manifest']['cases']:
        report=owner_request(args.tunnel,'/api/campaign/evidence')
        state=report['ledger']
        if state['stopped']: break
        if state['cases'][case['id']]['status'] in TERMINAL: continue
        if case.get('requires_restart') and (not state['restart'] or state['restart']['status']!='restart_verified'):
            owner_request(args.tunnel,'/api/campaign/restart-prepare',{})
            report=owner_request(args.tunnel,'/api/campaign/evidence')
            break
        report=owner_request(args.tunnel,'/api/campaign/dispatch',{'case_id':case['id']})
        _save_report(args.output,report)
    _save_report(args.output,report)
    print(canonical({'sent':report['ledger']['sent'],'stopped':report['ledger']['stopped'],'restart':(report['ledger']['restart'] or {}).get('status')}))


def _save_report(path,report):
    from live_budget import LiveBudget
    writer=object.__new__(LiveBudget); writer.path=path
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    writer.write(report)


if __name__=='__main__':
    main()
