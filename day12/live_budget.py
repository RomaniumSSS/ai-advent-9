"""Fail-closed live-call boundary. No network outside the wrapped create()."""
import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace

from models import MODELS

MODEL = MODELS['deepseek-v4-flash']['id']
MAX_CALLS = 4
MAX_COST = Decimal('0.02')


class BudgetStop(RuntimeError):
    pass


def decimal(value):
    if value is None or isinstance(value, bool):
        raise ValueError('unknown monetary value')
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError('invalid monetary value') from error
    if not result.is_finite() or result < 0:
        raise ValueError('invalid monetary value')
    return result


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def raw(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, SimpleNamespace):
        return {k: raw(v) for k, v in vars(value).items()}
    if isinstance(value, dict):
        return {k: raw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [raw(v) for v in value]
    return value


class LiveBudget:
    def __init__(self, ledger, policy):
        self.path = Path(ledger)
        self.policy = json.loads(Path(policy).read_text()) if not isinstance(policy, dict) else dict(policy)
        p = self.policy
        if p.get('model') != MODEL or not isinstance(p.get('provider'), str) or not p['provider'].strip():
            raise ValueError('exact DeepSeek model and verified provider required')
        # AICODE-NOTE: no guessed default tariffs. Validation supplies a verified
        # upper bound; max_price also constrains OpenRouter provider routing.
        for key in ('price_source', 'verified_at'):
            if not isinstance(p.get(key), str) or not p[key].strip():
                raise ValueError(f'{key} required')
        self.input_price = decimal(p.get('prompt_usd_per_million'))
        self.output_price = decimal(p.get('completion_usd_per_million'))
        if min(self.input_price, self.output_price) <= 0:
            raise ValueError('positive price ceilings required')
        for key, ceiling in [('max_prompt_tokens', 16384), ('max_tokens', 1024)]:
            if type(p.get(key)) is not int or not 1 <= p[key] <= ceiling:
                raise ValueError(f'invalid {key}')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.locked():
            if not self.path.exists():
                self.write({'version': 1, 'policy_hash': digest(p), 'policy': p,
                            'attempts': [], 'reported_cost_usd': '0', 'stopped': None})
            state = self.read()
            if state['policy_hash'] != digest(p):
                raise BudgetStop('ledger policy changed; original ledger must be retained')
            if any(a['status'] == 'in_flight' for a in state['attempts']):
                state['stopped'] = 'unknown outcome after interrupted call'
                self.write(state)

    @contextmanager
    def locked(self):
        fd = os.open(str(self.path) + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def read(self):
        return json.loads(self.path.read_text())

    def write(self, state):
        # The separate lock inode survives atomic replacement of the journal.
        temporary = self.path.with_name(self.path.name + '.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(canonical(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
        directory = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def snapshot(self):
        with self.locked():
            return self.read()

    def authorize_resume(self, report, approved_by, reason):
        from repair_contract import source_check, require, RUN_ID, REPORT_HASH, LEDGER_HASH, ANALYSIS
        source_check(report)
        require(isinstance(approved_by, str) and 0 < len(approved_by.strip()) <= 100
                and isinstance(reason, str) and 0 < len(reason.strip()) <= 1000,
                'manual reviewer and analysis reason required')
        with self.locked():
            state = self.read()
            require(digest(state) == LEDGER_HASH, 'resume requires exact original stopped ledger')
            state['manual_resume'] = {
                'run_id': RUN_ID, 'source_report_hash': REPORT_HASH,
                'source_ledger_hash': LEDGER_HASH, 'remaining_attempts': 2,
                'original_stop': state['stopped'], 'original_cost': state['reported_cost_usd'],
                'analysis': ANALYSIS, 'approved_by': approved_by, 'reason': reason,
                'authorized_at': datetime.now(timezone.utc).isoformat()}
            state['stopped'] = None
            self.write(state)
            return state

    def wrap(self, client):
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=lambda **kwargs: self.create(client.chat.completions.create, **kwargs))))

    def create(self, send, **kwargs):
        with self.locked():
            state = self.read()
            if state['policy_hash'] != digest(self.policy):
                raise BudgetStop('ledger policy mismatch')
            if any(a['status'] == 'in_flight' for a in state['attempts']):
                state['stopped'] = 'unknown outcome after interrupted call'
            if state['stopped']:
                self.write(state)
                raise BudgetStop(state['stopped'])
            total = decimal(state['reported_cost_usd'])
            reserve = (self.policy['max_prompt_tokens'] * self.input_price +
                       self.policy['max_tokens'] * self.output_price) / Decimal(1000000)
            reason = None
            if len(state['attempts']) >= MAX_CALLS:
                reason = 'call limit reached'
            elif total + reserve > MAX_COST:
                reason = 'insufficient remaining reserve'
            if reason:
                state['stopped'] = reason
                self.write(state)
                raise BudgetStop(reason)
            if kwargs.get('model') != MODEL or type(kwargs.get('max_tokens')) is not int or not 1 <= kwargs['max_tokens'] <= self.policy['max_tokens']:
                raise BudgetStop('request exceeds model/output policy')
            messages = kwargs.get('messages', [])
            if not messages or any(set(m) != {'role', 'content'} or not isinstance(m['content'], str) for m in messages):
                raise BudgetStop('only plain text messages supported')
            # Byte upper bound is deliberately larger than local token estimates.
            upper = sum(len(m['content'].encode('utf-8')) + 64 for m in messages) + 64
            if upper > self.policy['max_prompt_tokens']:
                raise BudgetStop('prompt exceeds conservative input bound')
            blocks = [m for m in messages if m['role'] == 'system' and m['content'].startswith('ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ')]
            if len(blocks) != 1:
                raise BudgetStop('exactly one automatic profile required')
            if set(kwargs) - {'model', 'messages', 'max_tokens', 'temperature', 'extra_body'}:
                raise BudgetStop('unsupported request options')
            supplied_extra = kwargs.get('extra_body')
            kwargs['extra_body'] = {'usage': {'include': True}, 'provider': {
                'only': [self.policy['provider']], 'allow_fallbacks': False,
                'require_parameters': True, 'max_price': {
                    'prompt': float(self.input_price), 'completion': float(self.output_price)}}}
            if 'manual_resume' in state:
                from repair_contract import request_check, require
                try:
                    # The base client supplies its default routing; the budget
                    # replaces it with the same pinned routing used for A.
                    require(supplied_extra in (None, kwargs['extra_body'],
                            {'provider': {'allow_fallbacks': True}, 'usage': {'include': True}}),
                            'resume extra options changed')
                    request_check(state, kwargs)
                except (BudgetStop, KeyError, TypeError, ValueError):
                    state['stopped'] = 'resume preflight mismatch'
                    self.write(state)
                    raise BudgetStop(state['stopped']) from None
            attempt = {'number': len(state['attempts']) + 1, 'status': 'in_flight',
                       'started_at': datetime.now(timezone.utc).isoformat(),
                       'reserved_usd': str(reserve), 'request': kwargs,
                       'profile': blocks[0], 'context_without_profile_hash': digest([m for m in messages if m is not blocks[0]])}
            state['attempts'].append(attempt)
            self.write(state)  # Durable reservation BEFORE the sole network call.
            try:
                response = send(**kwargs)
            except BaseException as error:
                # Do not store exception text: SDK exceptions can include secrets.
                attempt.update(status='provider_error', error_type=type(error).__name__)
                state['stopped'] = 'first provider error'
                self.write(state)
                raise BudgetStop(state['stopped']) from None
            attempt['response'] = raw(response)
            usage = getattr(response, 'usage', None)
            try:
                charge = decimal(getattr(usage, 'cost', None))
                # Account known cost even when other usage fields are malformed.
                total += charge
                state['reported_cost_usd'] = str(total)
                for key in ('prompt_tokens', 'completion_tokens'):
                    value = getattr(usage, key, None)
                    if type(value) is not int or value < 0:
                        raise ValueError('missing or invalid token usage')
                if usage.prompt_tokens > self.policy['max_prompt_tokens'] or usage.completion_tokens > kwargs['max_tokens']:
                    raise ValueError('provider exceeded token reservation')
                if charge > reserve or total > MAX_COST:
                    raise ValueError('provider cost exceeded reservation')
                if getattr(response, 'model', None) != MODEL:
                    raise ValueError('unexpected response model')
                choices = getattr(response, 'choices', [])
                if not choices or not choices[0].message.content or choices[0].finish_reason != 'stop':
                    raise ValueError('empty or incomplete response')
                if 'manual_resume' in state:
                    from repair_contract import short_format
                    if not short_format(choices[0].message.content):
                        raise ValueError('resume B format failed')
            except (ValueError, AttributeError, TypeError) as error:
                attempt['status'] = 'invalid_response'
                state['stopped'] = str(error)
            else:
                attempt['status'] = 'complete'
                if total >= MAX_COST or len(state['attempts']) >= MAX_CALLS:
                    state['stopped'] = 'budget reached'
            self.write(state)
            if attempt['status'] != 'complete':
                raise BudgetStop(state['stopped'])
            return response
