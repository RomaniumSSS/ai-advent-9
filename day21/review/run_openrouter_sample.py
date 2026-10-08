"""Последовательная holdout-оценка двух pinned-моделей; dry-run по умолчанию."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import requests
import certifi

from run_local_sample import PRIVATE, RUBRIC, output_schema, normalized, parse_output, write
from pilot_validation import validate, diagnose_context, input_context_errors

VERSION = 1
EXPECTED_INPUT = '166d9f119ac0f357b7e2526f5558b068ace64c96b0312dbbb3298fb40298c00e'
INPUT = 'semantic-expanded-v3-holdout-input.json'
ENV_FILE = Path('/Users/ramanpazharytski/Projects/ai-advent-9/.env')
ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
MODELS = [
    ('deepseek/deepseek-v4.1-flash', 'deepinfra/fp8', 'semantic-holdout-deepseek.json'),
    ('z-ai/glm-5.3-flash', 'deepinfra/fp4', 'semantic-holdout-glm.json'),
]
FORMAT_INSTRUCTION = ('\nЕдинственное изменение формата: decisions — объект, '
                      'ключи которого — все входные ID как строки. Значение '
                      'каждого ключа содержит decision, reason, flags, без message_id. '
                      'Смысловые правила прежние. Соблюдай приложенную JSON Schema.\n')
CAP = 1.0


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def serialize(payload):
    return json.dumps(payload, ensure_ascii=False).encode('utf-8')


def request_body(model, provider, case, messages, rubric):
    schema = output_schema(case)
    payload = {'case': case, 'messages': messages, 'output_schema': schema}
    return {'model': model, 'messages': [
        {'role': 'system', 'content': rubric + FORMAT_INSTRUCTION},
        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
        'provider': {'only': [provider], 'allow_fallbacks': False,
                     'require_parameters': True, 'data_collection': 'deny',
                     'max_price': {'prompt': 0.20, 'completion': 0.60}},
        'reasoning': {'effort': 'low'} if model == 'z-ai/glm-5.3-flash' else {'enabled': False}, 'temperature': 0, 'max_tokens': 2048,
        'stream': False, 'response_format': {'type': 'json_schema',
            'json_schema': {'name': 'case_decisions', 'strict': True, 'schema': schema}}}


def reserve_upper(body):
    return (len(body) + 8192) * 0.20 / 1e6 + 2048 * 0.60 / 1e6


def money(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def charged(attempt):
    actual = attempt.get('actual_cost')
    return actual if actual is not None else attempt['reserve']


def spent(ledger):
    return sum(charged(a) for a in ledger['attempts'])


def ensure_ledger(ledger, meta, valid_keys):
    if not isinstance(ledger, dict) or ledger.get('meta') != meta or not isinstance(ledger.get('attempts'), list):
        raise ValueError('unsafe_ledger_metadata')
    seen = set()
    for item in ledger['attempts']:
        if not isinstance(item, dict): raise ValueError('unsafe_ledger_record')
        key = (item.get('model'), item.get('case_id'))
        if key not in valid_keys or key in seen or not money(item.get('reserve')) or item['reserve'] <= 0:
            raise ValueError('unsafe_ledger_record')
        if isinstance(valid_keys, dict) and item['reserve'] != valid_keys[key]:
            raise ValueError('unsafe_ledger_reserve')
        if item.get('status') not in ('pending', 'complete', 'error'):
            raise ValueError('unsafe_ledger_status')
        if item.get('actual_cost') is not None and not money(item['actual_cost']):
            raise ValueError('unsafe_ledger_cost')
        if item['status'] == 'pending' and item.get('actual_cost') is not None:
            raise ValueError('unsafe_pending_cost')
        seen.add(key)
    return seen


def reserve(ledger, key, upper):
    if not money(upper) or upper <= 0 or spent(ledger) + upper > CAP:
        raise ValueError('budget_cap')
    if any((a['model'], a['case_id']) == key for a in ledger['attempts']):
        raise ValueError('attempt_already_reserved')
    record = {'model': key[0], 'case_id': key[1], 'reserve': upper, 'actual_cost': None, 'status': 'pending'}
    ledger['attempts'].append(record)
    return record


def api_key():
    value = os.environ.get('OPENROUTER_API_KEY')
    if value: return value
    for line in ENV_FILE.read_text().splitlines():
        key, separator, raw = line.strip().partition('=')
        if separator and key == 'OPENROUTER_API_KEY':
            value = raw.strip().strip('\"\'')
            if value: return value
    raise ValueError('missing_api_key')


def prepare():
    raw = (PRIVATE / INPUT).read_bytes()
    if digest(raw) != EXPECTED_INPUT: raise ValueError('input_hash_mismatch')
    data = json.loads(raw)
    if len(data['cases']) != 20 or len(data['messages']) != 51 or any(c.get('split') != 'holdout' for c in data['cases']):
        raise ValueError('holdout_scope')
    for case in data['cases']:
        if input_context_errors(case, data['messages']): raise ValueError('malformed_input')
    rubric_path = RUBRIC.with_name('semantic-rubric-v3.txt')
    rubric_bytes = rubric_path.read_bytes()
    if digest(rubric_bytes) != data['rubric_sha256']: raise ValueError('rubric_hash_mismatch')
    messages = {m['id']: m for m in data['messages']}
    jobs = []
    for model, provider, filename in MODELS:
        for case in data['cases']:
            body = serialize(request_body(model, provider, case, [messages[i] for i in case['message_ids']], rubric_bytes.decode()))
            jobs.append({'model': model, 'filename': filename, 'case': case,
                         'body': body, 'reserve': reserve_upper(body)})
    meta = {'version': VERSION, 'code_sha256': digest(Path(__file__).read_bytes()),
            'input_sha256': digest(raw), 'rubric_sha256': digest(rubric_bytes),
            'cap': CAP, 'request_sha256': [digest(j['body']) for j in jobs]}
    return data, jobs, meta


def process_response(case, messages, response, model):
    record = {'case_id': case['case_id'], 'valid_coverage': False}
    stop = None
    if not isinstance(response, dict): return dict(record, error_type='response_type'), 'response_type'
    record['usage'] = response.get('usage')
    record['provider'] = response.get('provider')
    record['model'] = response.get('model')
    if response.get('model') != model or not isinstance(response.get('provider'), str) or response['provider'].casefold() != 'deepinfra':
        stop = 'unexpected_provider_or_model'
    try:
        choice = response['choices'][0]
        raw = choice['message']['content']
        record.update(raw_output=raw, finish_reason=choice.get('finish_reason'))
        output = normalized(parse_output(raw))
        errors = validate(case, output)
        if choice.get('finish_reason') == 'length': errors.append('truncated_output')
        record.update(output=output, validation_errors=errors, valid_coverage=not errors,
                      context_diagnostics=diagnose_context(case, messages, output))
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        record.update(error_type=type(error).__name__, validation_errors=['malformed_output'])
        if record.get('finish_reason') == 'length': record['validation_errors'].append('truncated_output')
        if 'choices' not in response: stop = stop or 'response_envelope'
    return record, stop


def live(data, jobs, meta):
    ledger_path = PRIVATE / 'semantic-openrouter-budget.json'
    valid_keys = {(j['model'], j['case']['case_id']): j['reserve'] for j in jobs}
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'meta': meta, 'attempts': []}
    attempted = ensure_ledger(ledger, meta, valid_keys)
    if any(a['status'] == 'pending' for a in ledger['attempts']): raise ValueError('pending_attempt_requires_review')
    if ledger.get('stop_reason'): raise ValueError('stopped_batch_requires_review')
    runs = {}
    for model, _, filename in MODELS:
        path = PRIVATE / filename
        run = json.loads(path.read_text()) if path.exists() else {'meta': meta, 'model': model, 'cases': []}
        if run.get('meta') != meta or run.get('model') != model or not isinstance(run.get('cases'), list):
            raise ValueError('unsafe_checkpoint')
        keys = [(model, r.get('case_id')) for r in run['cases'] if isinstance(r, dict)]
        expected = {key for key in attempted if key[0] == model}
        if len(keys) != len(run['cases']) or len(keys) != len(set(keys)) or set(keys) != expected:
            raise ValueError('checkpoint_ledger_mismatch')
        ledger_records = {(a['model'], a['case_id']): a for a in ledger['attempts']}
        for record in run['cases']:
            attempt = ledger_records[(model, record['case_id'])]
            if record.get('reserved_cost') != attempt['reserve'] or record.get('actual_cost') != attempt['actual_cost']:
                raise ValueError('checkpoint_cost_mismatch')
        runs[model] = run
    key = api_key()
    for job in jobs:
        ident = (job['model'], job['case']['case_id'])
        if ident in attempted: continue
        attempt = reserve(ledger, ident, job['reserve'])
        write(ledger_path, ledger)  # Резерв durable до отправки: неизвестная стоимость не ноль.
        import time
        started = time.monotonic()
        record, stop = {'case_id': ident[1], 'valid_coverage': False}, None
        try:
            response = requests.post(ENDPOINT, data=job['body'],
                headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                timeout=600, verify=certifi.where())
            if response.status_code != 200:
                record.update(error_type='http_error', http_status=response.status_code)
                stop = 'http_error'
            else:
                record, stop = process_response(job['case'], data['messages'], response.json(), ident[0])
        except (requests.RequestException, ValueError) as error:
            record['error_type'] = type(error).__name__
            stop = 'transport_or_response_error'
        record['elapsed_seconds'] = round(time.monotonic() - started, 3)
        usage = record.get('usage')
        actual = usage.get('cost') if isinstance(usage, dict) else None
        if actual is not None and not money(actual): stop = stop or 'invalid_usage_cost'; actual = None
        record.update(reserved_cost=attempt['reserve'], actual_cost=actual)
        attempt.update(actual_cost=actual, status='error' if stop else 'complete')
        if actual is not None and actual > attempt['reserve']: stop = 'actual_exceeds_reserve'
        runs[ident[0]]['cases'].append(record)
        write(PRIVATE / job['filename'], runs[ident[0]])
        if stop: ledger['stop_reason'] = stop
        write(ledger_path, ledger)
        print(json.dumps({'model': ident[0], 'case_id': ident[1], 'valid_coverage': record.get('valid_coverage'),
                          'seconds': record['elapsed_seconds'], 'error_type': record.get('error_type'),
                          'stop_reason': stop, 'budget_charged': spent(ledger)}), flush=True)
        if stop: return


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    data, jobs, meta = prepare()
    if not args.live:
        print(json.dumps({'dry_run': True, 'calls': len(jobs), 'models': [m[0] for m in MODELS],
                          'reserve_upper_total': sum(j['reserve'] for j in jobs), 'cap': CAP}))
        return
    with (PRIVATE / 'semantic-openrouter-budget.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('another_runner_active')
        live(data, jobs, meta)


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'error_type': type(error).__name__}), flush=True)
        raise SystemExit(1)
