"""Один путь вопроса: поиск, разрешение, резерв, генерация, проверка, сохранение."""
import fcntl
import hashlib
import json
import math
import re
import time
import uuid
import copy
from pathlib import Path
from common import API, MODEL, estimate, key_from_env, packed, payload, request, save, validate_answer, refresh_pricing
from answers import check_answer, refusal
from search import search
from conversation import build_context, prepare_generation
from task_contract import refusal_text, format_errors
from structured_evidence import check_response

STATES = {'verified': 'Цитаты проверены; смысл не проверен', 'no_context': 'Недостаточный контекст', 'model_refusal': 'Модель сообщает нехватку фактов', 'insufficient_context':'Недостаточно подтверждённых сторон сравнения', 'unverified': 'Непроверенный ответ', 'error': 'Техническая ошибка', 'not_authorized': 'Генерация не разрешена', 'interrupted': 'Операция прервана', 'unknown': 'Исход платного вызова неизвестен'}

def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default

class Service:
    def __init__(self, directory, search_fn=search, generate_fn=None, key_fn=key_from_env, pricing_fn=refresh_pricing):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.search_fn = search_fn
        self.generate_fn = generate_fn or (lambda body, key: request(API+'/chat/completions', body, key))
        self.key_fn = key_fn
        self.pricing_fn = pricing_fn
        self.ephemeral = {}
        with self.lock():
            ledger_path=self.directory/'ledger.json'
            ledger=read(ledger_path,{'entries':[]})
            ledger_changed=False
            for entry in ledger['entries']:
                if entry['status']=='inflight':
                    entry['status']='unknown'
                    ledger_changed=True
            if ledger_changed: save(ledger_path,ledger)
            for p in self.directory.glob('result-*.json'):
                item=read(p)
                stage=item.get('stage',item['status'])
                if stage in ('searching','selecting','generating','validating'):
                    entries=[e for e in ledger['entries'] if e['id']==item['id']]
                    paid_unknown=any(e['status']=='unknown' for e in entries)
                    pending=item.get('generation',{}).get('transmission') in ('pending','unknown')
                    item['status']='unknown' if paid_unknown or pending else 'interrupted'
                    if pending:item['generation']['transmission']='unknown'
                    item['error']='Процесс остановился; автоматического повтора нет.'
                    item['stage']='terminal'
                    item.setdefault('transitions',[]).append({'from':stage,'to':'terminal',
                        'outcome':item['status'],'at':time.time(),'reason':'restart'})
                    item.pop('answer',None)
                    save(p,item)

    def lock(self):
        return Lock(self.directory/'run.lock')

    def advance(self, item, path, target):
        stage=item.get('stage')
        transitions={'searching':{'selecting','terminal'},
                     'selecting':{'generating','terminal'},
                     'generating':{'validating','terminal'},
                     'validating':{'terminal'}, 'terminal':set()}
        if target not in transitions.get(stage,set()):raise ValueError('invalid_request_transition')
        changed=copy.deepcopy(item)
        changed['stage']=target
        if target=='terminal':
            if changed['status'] not in STATES:raise ValueError('invalid_terminal_status')
            if changed['status'] in ('verified','insufficient_context'):
                generation=changed.get('generation',{})
                chunks=generation.get('transmitted_chunks',[])
                checked=check_response(changed.get('raw_answer'),chunks,changed['question'],changed['task_state'])
                chunk_ids=[c['chunk_id'] for c in chunks]
                if (stage!='validating' or generation.get('transmission')!='confirmed'
                    or chunk_ids!=generation.get('transmitted_chunk_ids')
                    or chunk_ids!=generation.get('attempted_chunk_ids')
                    or checked.get('outcome')!=changed['status'] or not checked.get('structure_valid')
                    or checked.get('structured_evidence')!=changed.get('structured_evidence')
                    or checked['answer']!=changed.get('answer')
                    or changed.get('validation',{}).get('structure_valid') is not True):
                    raise ValueError('verified_invariant_failed')
        else: changed['status']=target
        event={'from':stage,'to':target,'at':time.time()}
        if target=='terminal':event['outcome']=changed['status']
        changed.setdefault('transitions',[]).append(event)
        save(path,changed)
        item.clear();item.update(changed)

    def path(self, ident):
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', ident):
            raise ValueError('invalid_id')
        return self.directory/('result-'+ident+'.json')

    def chat_path(self, chat_id):
        self.path(chat_id)
        return self.directory / ('chat-' + chat_id + '.json')

    def create_chat(self, title='', scope='all'):
        if not isinstance(title, str) or len(title) > 200 or scope not in ('all', 'public'):
            raise ValueError('invalid_chat')
        with self.lock():
            chat = {'chat_id': uuid.uuid4().hex, 'title': title, 'scope': scope,
                    'created_at': time.time(), 'task_state': {'version': 0, 'goal': '',
                    'clarifications': [], 'constraints': []}}
            save(self.chat_path(chat['chat_id']), chat)
            return chat

    def chats(self):
        return sorted([read(p) for p in self.directory.glob('chat-*.json')],
                      key=lambda c: c['created_at'], reverse=True)

    def chat(self, chat_id):
        chat = read(self.chat_path(chat_id))
        if not chat: raise ValueError('chat_not_found')
        return chat

    def update_task_state(self, chat_id, state, expected_version):
        if (not isinstance(state, dict) or set(state) != {'goal', 'clarifications', 'constraints'}
            or not isinstance(state['goal'], str) or len(state['goal']) > 4000
            or any(not isinstance(state[k], list) or len(state[k]) > 50
                   or any(not isinstance(v, str) or len(v) > 4000 for v in state[k])
                   for k in ('clarifications', 'constraints'))):
            raise ValueError('invalid_task_state')
        with self.lock():
            chat = self.chat(chat_id)
            if type(expected_version) is not int or expected_version != chat['task_state']['version']:
                raise ValueError('task_state_version_conflict')
            chat['task_state'] = copy.deepcopy(state)
            chat['task_state']['version'] = expected_version + 1
            save(self.chat_path(chat_id), chat)
            return chat

    def clear_task_state(self, chat_id, expected_version):
        return self.update_task_state(chat_id, {'goal': '', 'clarifications': [], 'constraints': []}, expected_version)

    def history(self, chat_id):
        self.chat(chat_id)
        return sorted([self.present(read(p)) for p in self.directory.glob('result-*.json')
                       if read(p).get('chat_id') == chat_id], key=lambda x: x.get('created_at', 0))

    def messages(self, chat_id):
        return self.messages_from_history(self.history(chat_id))

    @staticmethod
    def messages_from_history(history):
        messages = []
        for item in history:
            messages.append({'role': 'user', 'content': item['question'], 'request_id': item['id']})
            if item.get('answer'):
                messages.append({'role': 'assistant', 'content': item['answer']['answer'],
                                 'request_id': item['id'], 'status': item['status']})
        return messages

    @staticmethod
    def present(item):
        if not item:return item
        shown=copy.deepcopy(item)
        if shown.get('version')!='day25-chat-v3':
            shown.pop('structured_evidence',None)
            return shown
        if shown.get('status') in ('verified','insufficient_context'):
            generation=shown.get('generation',{})
            chunks=generation.get('transmitted_chunks',[])
            chunk_ids=[c['chunk_id'] for c in chunks]
            confirmed=(generation.get('transmission')=='confirmed' and chunk_ids==generation.get('transmitted_chunk_ids') and chunk_ids==generation.get('attempted_chunk_ids'))
            checked=check_response(shown.get('raw_answer'),chunks,shown['question'],shown['task_state'])
            if confirmed and checked.get('structure_valid') and checked.get('outcome')==shown['status'] and checked['answer']==shown.get('answer'):
                shown['structured_evidence']=checked['structured_evidence']
            else:
                shown.pop('answer',None);shown.pop('structured_evidence',None);shown['status']='unverified'
        else:shown.pop('structured_evidence',None)
        return shown

    def _get(self, ident):
        return self.present(self.ephemeral.get(ident) or read(self.path(ident)))

    def get(self, chat_id, ident):
        self.chat(chat_id)
        item = self._get(ident)
        if item and item.get('chat_id') != chat_id: raise ValueError('result_not_found')
        return item

    def feedback(self, chat_id, ident, marks, comment):
        if not isinstance(marks,list) or any(m not in ('не тот источник','неверный вывод','неполный ответ') for m in marks) or not isinstance(comment,str) or len(comment)>4000:
            raise ValueError('invalid_feedback')
        with self.lock():
            item=self.get(chat_id, ident)
            if not item: raise ValueError('result_not_found')
            item['feedback']={'marks':marks,'comment':comment,'at':time.time()}
            save(self.path(ident),item)
            return item

    def ask(self, chat_id, ident, question, scope):
        path=self.path(ident)
        if not isinstance(question,str) or not question.strip() or len(question.encode())>18000 or scope not in ('all','public'):
            raise ValueError('invalid_question_or_scope')
        question=question.strip()
        with self.lock():
            chat = self.chat(chat_id)
            if chat['scope'] != scope: raise ValueError('chat_scope_changed')
            old=self._get(ident)
            if old:
                if old.get('chat_id') != chat_id: raise ValueError('id_chat_changed')
                if old['question']!=question or old['scope']!=scope: raise ValueError('id_payload_changed')
                return old
            item={'chat_id':chat_id,'task_state':copy.deepcopy(chat['task_state']),'task_state_version':chat['task_state']['version'],'id':ident,'question':question,'scope':scope,'status':'searching','stage':'searching','transitions':[{'from':None,'to':'searching','at':time.time()}],'created_at':time.time(),'version':'day25-chat-v3','semantic_match':None,'cost':0,'generation':{'started':False,'transmitted_chunk_ids':[]},'feedback':None,'saved':True,'timings':{}}
            auth=read(self.directory/'authorization.json',{})
            history=self.history(chat_id)
            if auth.get('approved') is True:
                history=[old for old in history if self.allowed(auth, old['question'], scope,
                         old.get('search',{}).get('trace',{}).get('selected',[]),
                         old.get('search',{}).get('identity'))]
            item['conversation']=build_context(question, item['task_state'], history, scope)
            save(path,item)
            started=time.monotonic()
            try:
                result=self.search_fn(item['conversation']['search_query'],scope)
                item['conversation']['search_performed']=True
                item['search']=result
                trace=result['trace']
                self.advance(item,path,'selecting')
                trace=item['search']['trace']
                prepare_generation(question,item['conversation'],trace)
                item['timings']['search']=time.monotonic()-started
                if trace['empty']:
                    item.update(status='no_context',answer=refusal(),cost=0)
                    if trace.get('temporal',{}).get('enabled'):
                        item['reason']=trace['temporal'].get('error') or trace['temporal']['interpretation']
                        item['answer']['answer']='Не знаю: в указанном периоде недостаточно релевантного контекста. Уточни тему или период.'
                else:
                    allowed=self.allowed(auth,question,scope,trace['selected'],result.get('identity'))
                    if not allowed:
                        item.update(status='not_authorized',reason='Для этого вопроса, области или снимка индекса генерация не разрешена.')
                    else:
                        self.generate(item,path,auth,trace)
            except Exception as error:
                if item.get('ledger_save_error') or item.get('generation',{}).get('transmission') in ('pending','unknown'):
                    item['status']='unknown'
                else:item['status']='error'
                item.pop('answer',None)
                item['error']=str(error) if isinstance(error,ValueError) else type(error).__name__
            item['timings']['total']=time.monotonic()-started
            try: self.advance(item,path,'terminal')
            except Exception:
                if item['status'] in ('verified','insufficient_context'):
                    item.pop('answer',None);item.pop('structured_evidence',None)
                    item['status']='unverified'
                item.update(saved=False,save_error='Результат получен, но не сохранён надёжно.')
                self.ephemeral[ident]=item
            return item

    def allowed(self,auth,question,scope,chunks,identity=None):
        # AICODE-NOTE: свободный вопрос разрешён только в зафиксированном снимке корпуса.
        questions_ok = (auth.get('question_policy')=='arbitrary' and bool(auth.get('identity_sha256'))) or question in auth.get('questions',[])
        snapshot_ok = not auth.get('identity_sha256') or hashlib.sha256(packed(identity)).hexdigest()==auth['identity_sha256']
        return (auth.get('approved') is True and auth.get('model')==MODEL and auth.get('provider')=='deepinfra/fp8' and auth.get('retries')==0 and scope in auth.get('scopes',[]) and questions_ok and snapshot_ok and all(c['document_id'] in auth.get('document_ids',[]) for c in chunks))

    def cloud_state(self):
        auth=read(self.directory/'authorization.json',{})
        ledger=read(self.directory/'ledger.json',{'entries':[]})
        spent=sum(e['charged'] for e in ledger['entries'])
        blocked=any(e['status'] in ('inflight','unknown') or e.get('cost_unknown') for e in ledger['entries'])
        configured=(auth.get('approved') is True and auth.get('model')==MODEL and auth.get('provider')=='deepinfra/fp8' and auth.get('retries')==0)
        budget=auth.get('budget',0)
        enabled=configured and not blocked and type(budget) in (int,float) and budget>spent
        return {'enabled':enabled,'identity_sha256':auth.get('identity_sha256') if configured else None,'scopes':auth.get('scopes',[]) if enabled else [],'budget':budget if configured else None,'charged_or_reserved':spent,'question_policy':auth.get('question_policy','exact'),'text':('Поиск + DeepSeek · общий лимит $'+str(budget)+' · списано/зарезервировано $'+format(spent,'.6f')) if enabled else ('Генерация остановлена: требуется проверка неизвестного расхода. Поиск доступен.' if blocked else 'Сейчас доступен поиск без генерации: разрешение или бюджет отсутствуют.')}

    def generate(self,item,path,auth,trace):
        if item.get('stage')!='selecting':raise ValueError('invalid_request_transition')
        budget=auth.get('budget')
        if type(budget) not in (int,float) or not math.isfinite(budget) or budget<=0: raise ValueError('invalid_budget')
        ledger_path=self.directory/'ledger.json'
        ledger=read(ledger_path,{'entries':[]})
        if any(e['status'] in ('inflight','unknown') or e.get('cost_unknown') for e in ledger['entries']): raise ValueError('explicit_recovery_required')
        if any(e['id']==item['id'] for e in ledger['entries']):raise ValueError('request_ledger_already_exists')
        pricing=self.pricing_fn()
        if not isinstance(pricing,dict) or set(pricing)!={'prompt','completion'} or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in pricing.values()) or pricing['prompt']>.14/1e6 or pricing['completion']>.42/1e6: raise ValueError('invalid_pricing')
        reserve=estimate(trace['messages'],pricing)
        if sum(e['charged'] for e in ledger['entries'])+reserve>budget: raise ValueError('budget_exceeded')
        key=self.key_fn(None)
        entry={'id':item['id'],'chat_id':item['chat_id'],'task_state_version':item['task_state_version'],'status':'inflight','reserve':reserve,'charged':reserve,'at':time.time(),'payload_sha256':hashlib.sha256(packed(payload(trace['messages']))).hexdigest()}
        ledger['pricing']=pricing
        ledger['authorization_id']=auth.get('authorization_id')
        item['authorization']={'id':auth.get('authorization_id'),'budget':budget,'model':MODEL,'provider':'deepinfra/fp8','identity_sha256':auth.get('identity_sha256')}
        ledger['entries'].append(entry)
        self.advance(item,path,'generating')
        trace=item['search']['trace']
        transmitted=copy.deepcopy(trace['selected'])
        try:
            save(ledger_path,ledger)
        except Exception:
            item['status']='error'
            raise
        item['ledger']={'request_id':item['id'],'chat_id':item['chat_id'],'task_state_version':item['task_state_version'],'payload_sha256':entry['payload_sha256']}
        item['cost']=None
        item['generation']={'started':True,'transmission':'pending','attempted_chunk_ids':[c['chunk_id'] for c in trace['selected']],'transmitted_chunk_ids':[]}
        save(path,item)
        t=time.monotonic()
        try:
            raw=self.generate_fn(payload(trace['messages']),key)
            item['generation'].update(transmission='confirmed',transmitted_chunk_ids=item['generation']['attempted_chunk_ids'],transmitted_chunks=transmitted)
            item['raw_response']=raw
            actual=raw.get('usage',{}).get('cost')
            if type(actual) in (int,float) and math.isfinite(actual) and actual>=0:
                entry['charged']=actual
            cost=actual if type(actual) in (int,float) and math.isfinite(actual) and actual>=0 else None
            item['cost']=cost
            entry.update(status='completed',cost_unknown=cost is None)
            choices=raw.get('choices')
            choice=choices[0] if isinstance(choices,list) and choices and isinstance(choices[0],dict) else {}
            message=choice.get('message')
            content=message.get('content') if isinstance(message,dict) else None
            item['raw_answer']=content
            self.advance(item,path,'validating')
            try:
                validate_answer(raw)
            except (ValueError,KeyError,IndexError,TypeError) as error:
                reason=str(error) if isinstance(error,ValueError) else 'invalid_provider_response'
                item['status']='unverified'
                item['validation']={'valid':False,'errors':[reason],'semantic_match':None}
                item['reason']='Ответ провайдера получен, но не прошёл проверку: '+reason
                return
            checked=check_response(content,transmitted,item['question'],item['task_state'])
            contract_errors=format_errors(checked.get('answer'),item['task_state'])
            item['validation']=checked
            if checked.get('structure_valid'):
                item.update(status=checked['outcome'],answer=checked['answer'],structured_evidence=checked['structured_evidence'])
            else:
                # Без цитат отказ распознаётся только по точному контракту; прочее остаётся непроверенным.
                data=checked.get('answer')
                if not contract_errors and not any(e not in ('missing_sources','missing_quotes') for e in checked['errors']) and isinstance(data,dict) and {'answer','sources','quotes'}<=set(data)<= {'answer','sources','quotes','attributions','comparison'} and not data.get('attributions') and not data.get('comparison') and data['sources']==[] and data['quotes']==[] and bool(refusal_text(data)):
                    item.update(status='model_refusal',answer=data)
                else: item['status']='unverified'
        except Exception:
            if item['generation'].get('transmission')=='pending': item['generation']['transmission']='unknown'
            if item['generation'].get('transmission')!='confirmed':entry['status']='unknown'
            raise
        finally:
            item['timings']['generation']=time.monotonic()-t
            try:
                save(ledger_path,ledger)
            except Exception:
                item['ledger_save_error']='Журнал расходов не сохранён; новые вызовы заблокированы до проверки расхода.'
                raise ValueError('ledger_save_failed_recovery_required') from None

class Lock:
    def __init__(self,path): self.path=path
    def __enter__(self):
        self.file=open(self.path,'a');self.path.chmod(0o600)
        try: fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close();raise ValueError('request_in_progress')
        return self
    def __exit__(self,*args): self.file.close()
