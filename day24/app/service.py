"""Один путь вопроса: поиск, разрешение, резерв, генерация, проверка, сохранение."""
import fcntl
import hashlib
import json
import math
import re
import time
from pathlib import Path
from common import API, MODEL, estimate, key_from_env, packed, payload, request, save, validate_answer, refresh_pricing
from answers import check_answer, refusal
from search import search

STATES = {'verified': 'Цитаты проверены; смысл не проверен', 'no_context': 'Недостаточный контекст', 'model_refusal': 'Модель сообщает нехватку фактов', 'unverified': 'Непроверенный ответ', 'error': 'Техническая ошибка', 'not_authorized': 'Генерация не разрешена', 'interrupted': 'Операция прервана', 'unknown': 'Исход платного вызова неизвестен'}

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
            for p in self.directory.glob('result-*.json'):
                item = read(p)
                if item['status'] in ('searching', 'generating'):
                    item['status'] = 'unknown' if item['status']=='generating' else 'interrupted'
                    if item.get('generation',{}).get('transmission')=='pending': item['generation']['transmission']='unknown'
                    item['error'] = 'Процесс остановился; автоматического повтора нет.'
                    save(p, item)

    def lock(self):
        return Lock(self.directory/'run.lock')

    def path(self, ident):
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', ident):
            raise ValueError('invalid_id')
        return self.directory/('result-'+ident+'.json')

    def history(self):
        return sorted([read(p) for p in self.directory.glob('result-*.json')], key=lambda x:x.get('created_at',0), reverse=True)

    def get(self, ident):
        return self.ephemeral.get(ident) or read(self.path(ident))

    def feedback(self, ident, marks, comment):
        if not isinstance(marks,list) or any(m not in ('не тот источник','неверный вывод','неполный ответ') for m in marks) or not isinstance(comment,str) or len(comment)>4000:
            raise ValueError('invalid_feedback')
        with self.lock():
            item=self.get(ident)
            if not item: raise ValueError('result_not_found')
            item['feedback']={'marks':marks,'comment':comment,'at':time.time()}
            save(self.path(ident),item)
            return item

    def ask(self, ident, question, scope):
        path=self.path(ident)
        if not isinstance(question,str) or not question.strip() or len(question.encode())>18000 or scope not in ('all','public'):
            raise ValueError('invalid_question_or_scope')
        question=question.strip()
        with self.lock():
            old=self.get(ident)
            if old:
                if old['question']!=question or old['scope']!=scope: raise ValueError('id_payload_changed')
                return old
            item={'id':ident,'question':question,'scope':scope,'status':'searching','created_at':time.time(),'version':'mentor-v2-quality-20261003','semantic_match':None,'cost':0,'generation':{'started':False,'transmitted_chunk_ids':[]},'feedback':None,'saved':True,'timings':{}}
            save(path,item)
            started=time.monotonic()
            try:
                result=self.search_fn(question,scope)
                item['search']=result
                trace=result['trace']
                item['timings']['search']=time.monotonic()-started
                if trace['empty']:
                    item.update(status='no_context',answer=refusal(),cost=0)
                    if trace.get('temporal',{}).get('enabled'):
                        item['reason']=trace['temporal'].get('error') or trace['temporal']['interpretation']
                        item['answer']['answer']='Не знаю: в указанном периоде недостаточно релевантного контекста. Уточни тему или период.'
                else:
                    auth=read(self.directory/'authorization.json',{})
                    allowed=self.allowed(auth,question,scope,trace['selected'],result.get('identity'))
                    if not allowed:
                        item.update(status='not_authorized',reason='Для этого вопроса, области или снимка индекса генерация не разрешена.')
                    else:
                        self.generate(item,path,auth,trace)
            except Exception as error:
                if item['status']=='generating': item['status']='unknown'
                elif not item.get('ledger_save_error'): item['status']='error'
                item['error']=str(error) if isinstance(error,ValueError) else type(error).__name__
            item['timings']['total']=time.monotonic()-started
            try: save(path,item)
            except Exception:
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
        return {'enabled':enabled,'scopes':auth.get('scopes',[]) if enabled else [],'budget':budget if configured else None,'charged_or_reserved':spent,'question_policy':auth.get('question_policy','exact'),'text':('Поиск + DeepSeek · общий лимит $'+str(budget)+' · списано/зарезервировано $'+format(spent,'.6f')) if enabled else ('Генерация остановлена: требуется проверка неизвестного расхода. Поиск доступен.' if blocked else 'Сейчас доступен поиск без генерации: разрешение или бюджет отсутствуют.')}

    def generate(self,item,path,auth,trace):
        budget=auth.get('budget')
        if type(budget) not in (int,float) or not math.isfinite(budget) or budget<=0: raise ValueError('invalid_budget')
        ledger_path=self.directory/'ledger.json'
        ledger=read(ledger_path,{'entries':[]})
        if any(e['status'] in ('inflight','unknown') or e.get('cost_unknown') for e in ledger['entries']): raise ValueError('explicit_recovery_required')
        pricing=self.pricing_fn()
        if not isinstance(pricing,dict) or set(pricing)!={'prompt','completion'} or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in pricing.values()) or pricing['prompt']>.14/1e6 or pricing['completion']>.42/1e6: raise ValueError('invalid_pricing')
        reserve=estimate(trace['messages'],pricing)
        if sum(e['charged'] for e in ledger['entries'])+reserve>budget: raise ValueError('budget_exceeded')
        key=self.key_fn(None)
        entry={'id':item['id'],'status':'inflight','reserve':reserve,'charged':reserve,'at':time.time(),'payload_sha256':hashlib.sha256(packed(payload(trace['messages']))).hexdigest()}
        ledger['pricing']=pricing
        ledger['authorization_id']=auth.get('authorization_id')
        item['authorization']={'id':auth.get('authorization_id'),'budget':budget,'model':MODEL,'provider':'deepinfra/fp8','identity_sha256':auth.get('identity_sha256')}
        ledger['entries'].append(entry)
        item['status']='generating'
        save(path,item)
        try:
            save(ledger_path,ledger)
        except Exception:
            item['status']='error'
            raise
        item['cost']=None
        item['generation']={'started':True,'transmission':'pending','attempted_chunk_ids':[c['chunk_id'] for c in trace['selected']],'transmitted_chunk_ids':[]}
        save(path,item)
        t=time.monotonic()
        try:
            raw=self.generate_fn(payload(trace['messages']),key)
            item['generation'].update(transmission='confirmed',transmitted_chunk_ids=item['generation']['attempted_chunk_ids'])
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
            try:
                validate_answer(raw)
            except (ValueError,KeyError,IndexError,TypeError) as error:
                reason=str(error) if isinstance(error,ValueError) else 'invalid_provider_response'
                item['status']='unverified'
                item['validation']={'valid':False,'errors':[reason],'semantic_match':None}
                item['reason']='Ответ провайдера получен, но не прошёл проверку: '+reason
                return
            checked=check_answer(content,trace['selected'])
            item['validation']=checked
            if checked['valid']:
                item.update(status='verified',answer=checked['answer'])
            else:
                # Без цитат отказ распознаётся только по точному контракту; прочее остаётся непроверенным.
                data=checked.get('answer')
                if isinstance(data,dict) and set(data)=={'answer','sources','quotes'} and data['sources']==[] and data['quotes']==[] and isinstance(data['answer'],str) and data['answer'].startswith('Не знаю:') and 'уточн' in data['answer'].lower():
                    item.update(status='model_refusal',answer=data)
                else: item['status']='unverified'
        except Exception:
            if item['generation'].get('transmission')=='pending': item['generation']['transmission']='unknown'
            entry['status']='unknown'
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
