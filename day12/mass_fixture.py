"""Узкие транзакционные fixtures; synthetic history никогда не получает usage."""
import json
import sqlite3
from pathlib import Path

from agent import Agent, AgentConfig
from base_agent import DEFAULT_SYSTEM_PROMPT
from live_budget import canonical, digest, MODEL
from profile import UserProfile
from store import SqliteStore, now

CONFIG = AgentConfig(model='deepseek-v4-flash', max_tokens=256, temperature=0.2, reasoning_effort="none")


def scoped(namespace, scope):
    return {k: f'{namespace}:{v}' for k, v in scope.items()}


def open_agent(db, namespace, case):
    s = scoped(namespace, case['scope'])
    return Agent(name='mass-live', config=CONFIG,
                 store=SqliteStore(db, s['session'], s['task'], s['user']))


def snapshot(agent):
    store = agent.store
    with store._connect() as c:
        if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('SQLite integrity failure')
        owner = c.execute('SELECT user_id,task_id FROM sessions WHERE session=?', (store.session,)).fetchone()
        if tuple(owner or ()) != (store.user_id, store.task_id):
            raise RuntimeError('session ownership failure')
        version = c.execute('PRAGMA user_version').fetchone()[0]
    return {'db_path': str(store.path.resolve()), 'schema': version,
            'scope': {'session': store.session, 'task': store.task_id, 'user': store.user_id},
            'history': store.load(), 'notes': store.notes(), 'profile': store.load_profile().to_dict()}


def prepare(db, namespace, case):
    # AICODE-NOTE: все операции seed и маркер завершения — одна FULL transaction.
    # После crash нельзя повторно засевать S01 или переписать сохранённый профиль.
    s = scoped(namespace, case['scope'])
    store = SqliteStore(db, s['session'], s['task'], s['user'])
    with store._connect() as c:
        c.execute('PRAGMA synchronous=FULL')
        c.executescript('''CREATE TABLE IF NOT EXISTS mass_fixtures (
            campaign TEXT, case_id TEXT, fixture_hash TEXT NOT NULL, evidence TEXT NOT NULL,
            PRIMARY KEY(campaign,case_id));
            CREATE TABLE IF NOT EXISTS mass_receipts (
            campaign TEXT, case_id TEXT, request_id TEXT, response_hash TEXT,
            PRIMARY KEY(campaign,case_id));''')
        with c:
            c.execute('BEGIN IMMEDIATE')
            existing = c.execute('SELECT fixture_hash,evidence FROM mass_fixtures WHERE campaign=? AND case_id=?', (namespace,case['id'])).fetchone()
            if existing:
                if existing[0] != digest(case):
                    raise RuntimeError('fixture changed')
                return json.loads(existing[1])
            logs = []
            def ensure(sc):
                row = c.execute('SELECT user_id,task_id FROM sessions WHERE session=?',(sc['session'],)).fetchone()
                if row and tuple(row) != (sc['user'],sc['task']):
                    raise RuntimeError('scope ownership failure')
                c.execute('INSERT OR IGNORE INTO sessions VALUES (?,?,?,?,?,?,?)',
                          (sc['session'],sc['user'],sc['task'],MODEL,DEFAULT_SYSTEM_PROMPT,now(),now()))
            ensure(s)
            for index, op in enumerate(case['operations']):
                target = scoped(namespace, op.get('scope',case['scope']))
                ensure(target)
                kind = op['op']
                if kind == 'profile':
                    profile = UserProfile.from_dict(op['value'])
                    c.execute('INSERT INTO user_profiles VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET profile_json=excluded.profile_json,updated_at=excluded.updated_at', (target['user'],canonical(profile.to_dict()),now()))
                elif kind == 'note':
                    layer = op['layer']
                    keys = {'short':(target['session'],),'working':(target['user'],target['task']),'long':(target['user'],)}[layer]
                    values = (*keys,op['key'],op['value'],now())
                    c.execute(f'INSERT INTO {layer}_notes VALUES ({",".join("?" for _ in values)}) ON CONFLICT DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',values)
                elif kind == 'history':
                    for role in ('user','assistant'):
                        c.execute('INSERT INTO messages(session,role,content,created_at) VALUES (?,?,?,?)',(target['session'],role,op[role],now()))
                elif kind == 'reset':
                    preserved = {}
                    for table, where, args in (
                        ('working_notes','user_id=? AND task_id=?',(target['user'],target['task'])),
                        ('long_notes','user_id=?',(target['user'],)),
                        ('user_profiles','user_id=?',(target['user'],))):
                        rows = [dict(row) for row in c.execute(f'SELECT * FROM {table} WHERE {where} ORDER BY rowid',args)]
                        preserved[table] = digest(rows)
                    SqliteStore.clear_in_transaction(c,target['session'])
                    for table, where, args in (
                        ('working_notes','user_id=? AND task_id=?',(target['user'],target['task'])),
                        ('long_notes','user_id=?',(target['user'],)),
                        ('user_profiles','user_id=?',(target['user'],))):
                        rows = [dict(row) for row in c.execute(f'SELECT * FROM {table} WHERE {where} ORDER BY rowid',args)]
                        if preserved[table] != digest(rows):
                            raise RuntimeError('reset destroyed persistent state')
                    logs.append({'operation':'reset_persistence_check','before_hashes':preserved,
                                 'after_hashes':preserved,'result':'unchanged'})
                elif kind == 'ownership_denial':
                    row = c.execute('SELECT user_id,task_id FROM sessions WHERE session=?',(target['session'],)).fetchone()
                    if row['user_id'] == s['user']:
                        raise RuntimeError('victim ownership not isolated')
                else:
                    raise ValueError('unknown fixture operation')
                logs.append({'ordinal':index,'operation':op,'scope':target,'at':now(),'result':'applied' if kind != 'ownership_denial' else 'denied','provenance':'synthetic_fixture'})
            evidence = {'operations':logs,'fixture_hash':digest(case)}
            c.execute('INSERT INTO mass_fixtures VALUES (?,?,?,?)',(namespace,case['id'],digest(case),canonical(evidence)))
    if any(op['op'] == 'ownership_denial' for op in case['operations']):
        victim = scoped(namespace,next(op['scope'] for op in case['operations'] if op['op']=='ownership_denial'))
        try:
            SqliteStore(db,victim['session'],s['task'],s['user'])
        except ValueError:
            pass
        else:
            raise RuntimeError('foreign session accepted')
    return evidence


def expected_initial(namespace, case, initial, prior):
    """Проверка fixtures и границ до сети, независимо от ответа модели."""
    expected_notes = {'short':{},'working':{},'long':{}}
    expected_history = []
    expected_profile = UserProfile().to_dict()
    target = case['scope']
    if case['id'] == 'S03':
        return initial == prior['S01']['post_state']
    if case.get('profile_reuse'):
        expected_profile = prior[case['profile_reuse']]['initial_state']['profile']
    for op in case['operations']:
        sc = op.get('scope', target)
        kind = op['op']
        if kind == 'profile' and sc['user'] == target['user']:
            expected_profile = op['value']
        if kind == 'history' and sc['session'] == target['session']:
            expected_history.extend([{'role':'user','content':op['user']},{'role':'assistant','content':op['assistant']}])
        if kind == 'note':
            keys = {'short':['session'],'working':['user','task'],'long':['user']}[op['layer']]
            if all(sc[k] == target[k] for k in keys):
                expected_notes[op['layer']][op['key']] = op['value']
        if kind == 'reset' and sc['session'] == target['session']:
            expected_history = []; expected_notes['short'] = {}
    return (initial['scope'] == scoped(namespace,target) and initial['notes'] == expected_notes
            and initial['history'] == expected_history and initial['profile'] == expected_profile)


def save_response(agent, namespace, case, response, latency):
    """Идемпотентная запись реального turn и receipt в той же SQLite transaction."""
    choice = response['choices'][0]
    text = choice['message'].get('content') or ''
    u = response['usage']
    with agent.store._connect() as c:
        c.execute('PRAGMA synchronous=FULL')
        with c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT response_hash FROM mass_receipts WHERE campaign=? AND case_id=?',(namespace,case['id'])).fetchone()
            if old:
                if old[0] != digest(response): raise RuntimeError('receipt mismatch')
                return
            for role, content in [('user',case['question']),('assistant',text)]:
                c.execute('INSERT INTO messages(session,role,content,created_at,model,elapsed,prompt_tokens,completion_tokens,cost) VALUES (?,?,?,?,?,?,?,?,?)',
                          (agent.store.session,role,content,now(),MODEL,latency,u['prompt_tokens'] if role=='assistant' else None,u['completion_tokens'] if role=='assistant' else None,float(u['cost']) if role=='assistant' else None))
            c.execute('INSERT INTO calls(session,created_at,model,prompt_tokens,completion_tokens,cost,cost_reported,empty) VALUES (?,?,?,?,?,?,?,?)',
                      (agent.store.session,now(),MODEL,u['prompt_tokens'],u['completion_tokens'],float(u['cost']),float(u['cost']),int(not text)))
            c.execute('INSERT INTO mass_receipts VALUES (?,?,?,?)',(namespace,case['id'],response['id'],digest(response)))
