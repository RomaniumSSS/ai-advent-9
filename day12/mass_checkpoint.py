"""Durable server ledger: отдельный lock inode, atomic replace, fsync, 0600."""
import hashlib
import json
import os
import re
from pathlib import Path

from live_budget import LiveBudget, BudgetStop, digest, decimal

PRIOR_COST = '0.00013246'
PRIOR_HASHES = {
 'live-deepseek.json':'6ceda57d5240adc52573308c6b078a4135eb22281e047ede62e0f51fb37ffd66',
 'live-deepseek-repaired.json':'49b5076594188e7b2b64fa8cddb979d7bf4a60f0ead43838c606b2217bcbd21f',
 'live-deepseek-transport-failure.json':'3eeffe9ec94504187e7dcc5b01cf94f911e2c3ddde9653984d06fa403e969974'}
PRIOR_LEDGER = 'ed53feaa730396e661674be327d5208a362bbdd73b258afaac77da9c1ad198d7'
TERMINAL = {'pass','quality_fail','safety_fail','indeterminate','blocked_safety','blocked_budget'}
ROOT = Path(__file__).resolve().parent
CODE_FILES = ('mass_cases.json','mass_checkpoint.py','mass_fixture.py','mass_grade.py','mass_live.py','agent.py','base_agent.py','store.py','profile.py','live_budget.py','web.py','models.py','tokens.py')


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prior_check(directory=ROOT/'results'):
    for name, expected in PRIOR_HASHES.items():
        if file_hash(Path(directory)/name) != expected:
            raise BudgetStop('immutable prior report changed')
    old = json.loads((Path(directory)/'live-deepseek-repaired.json').read_text())['ledger']
    if digest(old) != PRIOR_LEDGER or len(old['attempts']) != 3 or decimal(old['reported_cost_usd']) != decimal(PRIOR_COST):
        raise BudgetStop('prior ledger mismatch')
    return old


def load_cases():
    cases = json.loads((ROOT/'mass_cases.json').read_text())['cases']
    expected = [f'{p}{i:02}' for p,n in [('P',8),('M',8),('S',4),('A',4)] for i in range(1,n+1)]
    if [c['id'] for c in cases] != expected or any(not c['question'] or not c['rubric'] for c in cases):
        raise BudgetStop('case manifest invalid')
    return cases


class Checkpoint(LiveBudget):
    def __init__(self, path, policy, campaign_id):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',campaign_id):
            raise ValueError('invalid campaign namespace')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.policy = policy
        cases = load_cases()
        prior_check()
        self.manifest = {'version':1,'campaign_id':campaign_id,'policy':policy,
                         'cases':cases,'code_hashes':{p:file_hash(ROOT/p) for p in CODE_FILES},
                         'prior':{'calls':3,'reported_cost_usd':PRIOR_COST,'reports':PRIOR_HASHES,'ledger_hash':PRIOR_LEDGER}}
        with self.locked():
            seal = self.path.with_name(self.path.name + '.created')
            if not self.path.exists():
                # Удаление ledger не должно выдавать новый бюджет тому же campaign.
                fd = os.open(seal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    stream.write(digest(self.manifest)); stream.flush(); os.fsync(stream.fileno())
                self.write({'manifest':self.manifest,'manifest_hash':digest(self.manifest),
                            'cases':{c['id']:{'status':'pending'} for c in cases},
                            'new_reported_cost_usd':'0','sent':0,'stopped':None,'restart':None,'events':[]})
            self.checked()

    def checked(self):
        state = self.read()
        if state['manifest'] != self.manifest or state['manifest_hash'] != digest(self.manifest):
            raise BudgetStop('manifest/code/policy mismatch')
        if set(state['cases']) != {c['id'] for c in self.manifest['cases']}:
            raise BudgetStop('case set changed')
        events = state['events']
        for i, event in enumerate(events):
            if event['number'] != i + 1 or event['previous'] != (digest(events[i-1]) if i else None):
                raise BudgetStop('checkpoint chain corrupt')
        if events and (events[-1]['cases_hash'] != digest(state['cases']) or events[-1]['sent'] != state['sent'] or events[-1]['new_reported_cost_usd'] != state['new_reported_cost_usd']):
            raise BudgetStop('checkpoint final state corrupt')
        entries = list(state['cases'].values())
        if any(e['status'] not in TERMINAL | {'pending','prepared','in_flight','response_recorded'} for e in entries):
            raise BudgetStop('invalid case status')
        if state['sent'] != sum(bool(e.get('sent')) for e in entries) or state['sent'] > 24:
            raise BudgetStop('send counter corrupt')
        total = sum((decimal(e['reported_cost_usd']) for e in entries if 'reported_cost_usd' in e),decimal('0'))
        if total != decimal(state['new_reported_cost_usd']):
            raise BudgetStop('cost counter corrupt')
        for e in entries:
            for key in ('request','response','initial_state','post_state'):
                if key in e and e.get(key+'_hash') != digest(e[key]):
                    raise BudgetStop('checkpoint evidence changed')
        prior_check()
        return state

    def checkpoint(self,state,event):
        previous = digest(state['events'][-1]) if state['events'] else None
        state['events'].append({'number':len(state['events'])+1,'event':event,'previous':previous,
                                'cases_hash':digest(state['cases']),'sent':state['sent'],
                                'new_reported_cost_usd':state['new_reported_cost_usd']})
        self.write(state)

    def stop(self,state,reason,case_id=None,status='safety_fail'):
        state['stopped'] = reason
        if case_id:
            state['cases'][case_id].update(status=status,error=reason)
        for e in state['cases'].values():
            if e['status'] not in TERMINAL:
                e.update(status='blocked_budget' if status=='blocked_budget' else 'blocked_safety',error=reason)
        self.checkpoint(state,'stop:'+reason)
        return state
