"""Local evaluation with explicit input, checkpoints and optional constrained IDs.

Outputs remain proposals in private/. No corpus decisions are applied here.
"""
import argparse
import hashlib
import json
import os
import time
import tempfile
import urllib.request
from pathlib import Path

from pilot_validation import validate, diagnose_context, input_context_errors

PRIVATE = Path(__file__).resolve().parents[1] / 'private'
RUBRIC = Path(__file__).with_name('semantic-rubric-v2.txt')
MODEL = 'qwen3:8b'
BASE = 'http://127.0.0.1:11435'


def api(endpoint, payload=None):
    request = urllib.request.Request(
        BASE + endpoint,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.load(response)


def write(path, data):
    descriptor, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_output(raw):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique_object)


def resume(previous, meta):
    if not isinstance(previous, dict):
        raise ValueError('Invalid checkpoint object')
    for key in meta.keys() - {'cases'}:
        if previous.get(key) != meta[key]:
            raise ValueError('Incompatible checkpoint: ' + key)
    records = previous.get('cases')
    if not isinstance(records, list):
        raise ValueError('Invalid checkpoint cases')
    ids = [r.get('case_id') if isinstance(r, dict) else None for r in records]
    if any(i not in meta['case_ids'] for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Invalid checkpoint case IDs')
    return records


def object_schema(properties):
    return {'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False}


def output_schema(case):
    decision = object_schema({
        'decision': {'type': 'string', 'enum': ['include', 'exclude', 'review']},
        'reason': {'type': 'string', 'minLength': 1},
        'flags': {'type': 'array', 'items': {'type': 'string', 'enum': [
            'needs_fact_check', 'mixed_content', 'incomplete_context']}},
    })
    ids = case['message_ids']
    group = object_schema({
        'message_ids': {'type': 'array', 'minItems': 1,
                        'items': {'type': 'integer', 'enum': ids}},
        'context_ids': {'type': 'array', 'items': {'type': 'integer'}},
        'reason': {'type': 'string', 'minLength': 1},
    })
    # Обязательный ключ каждого ID препятствует незаметному пропуску сообщения.
    # Согласованность групп по-прежнему проверяет отдельный валидатор.
    return object_schema({
        'case_id': {'type': 'string', 'enum': [case['case_id']]},
        'decisions': object_schema({str(i): decision for i in ids}),
        'document_groups': {'type': 'array', 'items': group},
        'review_groups': {'type': 'array', 'items': group},
        'missing_context_ids': {'type': 'array', 'items': {'type': 'integer'}},
        'notes': {'type': 'string'},
    })


def normalized(output):
    if not isinstance(output, dict) or not isinstance(output.get('decisions'), dict):
        raise ValueError('schema_decisions_type')
    for key, value in output['decisions'].items():
        if not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key or not isinstance(value, dict) or 'message_id' in value:
            raise ValueError('schema_decision_type')
    result = dict(output)
    result['decisions'] = [dict(value, message_id=int(key))
                           for key, value in output['decisions'].items()]
    return result


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Filename within private/')
    parser.add_argument('--output', required=True, help='Filename within private/')
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--schema', action='store_true')
    parser.add_argument('--rubric', help='Filename within review/; default semantic-rubric-v2.txt')
    args = parser.parse_args()
    if any(Path(name).name != name for name in [args.input, args.output]):
        parser.error('Use private/ filenames, not paths')
    if args.input == args.output:
        parser.error('Input and output must differ')
    source = PRIVATE / args.input
    target = PRIVATE / args.output
    data = json.loads(source.read_text())
    cases = [c for c in data['cases'] if not args.cases or c['case_id'] in args.cases]
    if args.cases and set(args.cases) != {c['case_id'] for c in cases}:
        parser.error('Unknown case ID')
    for case in cases:
        errors = input_context_errors(case, data['messages'])
        if errors:
            raise ValueError('Invalid case input: ' + ','.join(errors))
    messages = {m['id']: m for m in data['messages']}
    rubric_path = RUBRIC
    if args.rubric:
        if Path(args.rubric).name != args.rubric or args.rubric in ('.', '..'):
            parser.error('Use review/ rubric filename, not paths')
        rubric_path = Path(__file__).with_name(args.rubric)
    rubric_bytes = rubric_path.read_bytes()
    rubric = rubric_bytes.decode('utf-8')
    if args.schema:
        rubric += ('\nЕдинственное изменение формата: decisions — объект, '
                   'ключи которого — все входные ID как строки. Значение '
                   'каждого ключа содержит decision, reason, flags, без message_id. '
                   'Смысловые правила прежние. Соблюдай приложенную JSON Schema.\n')
    tags = api('/api/tags')
    model = next(m for m in tags['models'] if m['name'] == MODEL)
    meta = {'model': MODEL, 'digest': model['digest'], 'think': False,
            'num_ctx': 8192, 'num_predict': 2048, 'temperature': 0,
            'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'rubric_sha256': hashlib.sha256(rubric_bytes).hexdigest(),
            'schema_mode': args.schema, 'runner_version': 3, 'rubric_file': rubric_path.name, 'case_ids': [c['case_id'] for c in cases],
            'system_prompt': rubric, 'cases': []}
    if target.exists():
        previous = json.loads(target.read_text())
        meta['cases'] = resume(previous, meta)
    completed = {c['case_id'] for c in meta['cases']}
    write(target, meta)
    try:
        for case in cases:
            if case['case_id'] in completed:
                continue
            schema = output_schema(case) if args.schema else 'json'
            payload = {'case': case, 'messages': [messages[i] for i in case['message_ids']]}
            if args.schema:
                payload['output_schema'] = schema
            started = time.monotonic()
            record = {'case_id': case['case_id']}
            try:
                response = api('/api/chat', {
                    'model': MODEL, 'messages': [
                        {'role': 'system', 'content': rubric},
                        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
                    'format': schema, 'think': False, 'stream': False,
                    'keep_alive': '60s', 'options': {'num_ctx': 8192,
                                                   'num_predict': 2048, 'temperature': 0},
                })
                record.update(done_reason=response.get('done_reason'),
                              usage={k: response.get(k) for k in ['prompt_eval_count', 'eval_count', 'total_duration', 'load_duration']})
                raw = response.get('message', {}).get('content', '')
                record['raw_output'] = raw
                parsed = parse_output(raw)
                output = normalized(parsed) if args.schema else parsed
                errors = validate(case, output)
                if response.get('done_reason') == 'length':
                    errors.append('truncated_output')
                record.update(output=output, validation_errors=errors,
                              context_diagnostics=diagnose_context(case, data['messages'], output),
                              valid_coverage=not errors, done_reason=response.get('done_reason'),
                              usage={k: response.get(k) for k in [
                                  'prompt_eval_count', 'eval_count', 'total_duration', 'load_duration']})
            except Exception as error:
                record.update(error_type=type(error).__name__, valid_coverage=False,
                              validation_errors=['malformed_output' if isinstance(error, (ValueError, TypeError, KeyError, AttributeError)) else 'request_error'])
                if record.get('done_reason') == 'length':
                    record['validation_errors'].append('truncated_output')
            record['elapsed_seconds'] = round(time.monotonic() - started, 3)
            meta['cases'].append(record)
            write(target, meta)
            print(json.dumps({k: record.get(k) for k in [
                'case_id', 'valid_coverage', 'done_reason', 'elapsed_seconds',
                'validation_errors', 'context_diagnostics', 'error_type']}), flush=True)
    finally:
        try:
            api('/api/generate', {'model': MODEL, 'keep_alive': 0})
        except Exception as error:
            print(json.dumps({'unload_error_type': type(error).__name__}), flush=True)


if __name__ == '__main__':
    main()
