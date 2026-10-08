"""Только приватная dry-generation запросов; отправки и принятия решений нет."""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
from prepare_selection_packets import PRIVATE, digest, encoded, file_hash
from run_openrouter_sample import request_body
from run_local_sample import RUBRIC, output_schema, normalized
from pilot_validation import validate

MODEL = 'deepseek/deepseek-v4.1-flash'
PROVIDER = 'deepinfra/fp8'
VERSION = 2
EXPECTED_PACKET_MANIFEST = '0159dd0bf7285564682f2d19773eb59cad42c5295522538af6c62fc28451104f'
ADAPTER = '''
Адаптер формата selection-owned-context v1 (предложения, без применения):
Входные ID для решений — ТОЛЬКО case.owned_message_ids. Верни decisions как объект,
ключи — строковые owned ID; значение содержит decision, reason, flags, без message_id.
Решение ровно одно для каждого owned ID. context_messages — только читаемый контекст:
не создавай для них решения и не включай их в message_ids document_groups/review_groups.
Context-only ID можно указывать в context_ids. Ссылки missing_references не содержат
прочитанного сообщения; их ID можно отметить в missing_context_ids. Переданные
context_messages физически присутствуют: не объявляй их missing_context_ids.
Группы состоят только из owned ID. Их происхождение сохранено локально по ID/version,
не возвращай имена, пути или собственную переоценку source_role. Смысловые границы
транспортного пакета не заданы; не объединяй все его сообщения автоматически.
Причины до 80 Unicode символов, notes до 160 символов; без цитат и персональных данных.
Пустые непрочитанные медиа и уже принятые условия могут быть context-only; локальные
решения о review и принятый корпус не изменяй. Соблюдай приложенную JSON Schema.
'''


def load_packets(directory):
    if file_hash(directory / 'manifest.json') != EXPECTED_PACKET_MANIFEST:
        raise ValueError('approved_packet_manifest_hash')
    manifest = json.loads((directory / 'manifest.json').read_text())
    identity = json.loads((directory / 'identity.json').read_text())
    if manifest['identity'] != identity or identity['version'] != 1:
        raise ValueError('packet_identity_version')
    rows = {}
    for name in ['messages.jsonl', 'packets.jsonl']:
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['artifacts'][name]:
            raise ValueError('packet_artifact_hash')
        rows[name] = [json.loads(line) for line in raw.splitlines()]
    messages = {m['message_id']: m for m in rows['messages.jsonl']}
    owners = [i for p in rows['packets.jsonl'] for i in p['owned_message_ids']]
    expected = {c['message_id'] for c in manifest['coverage'] if c['input_status'] == 'eligible'}
    if len(messages) != len(rows['messages.jsonl']) or set(owners) != expected or len(owners) != len(set(owners)) or messages.keys() != expected:
        raise ValueError('packet_ownership')
    for ident, message in messages.items():
        if message['version_hash'] != identity['record_versions'][str(ident)] or message['record_sha256'] != digest(message['record']):
            raise ValueError('source_record_version')
        if message['text_sha256'] != hashlib.sha256(message['record']['text'].encode()).hexdigest():
            raise ValueError('source_text_hash')
    return manifest, messages, rows['packets.jsonl']


def minimal_message(message):
    return {'id': message['message_id'], 'text': message['record']['text'],
            'reply_to': message['record']['reply_to'], 'source_role': message['source_role'],
            **message['attachment']}


def selection_schema(case_id, owned, context, missing):
    schema = output_schema({'case_id': case_id, 'message_ids': owned})
    fields = schema['properties']
    for value in fields['decisions']['properties'].values():
        value['properties']['reason']['maxLength'] = 80
        value['properties']['flags']['maxItems'] = 3
    available = sorted(set(owned) | set(context) | set(missing))
    for field in ['document_groups', 'review_groups']:
        fields[field]['maxItems'] = len(owned)
        group = fields[field]['items']['properties']
        group['message_ids']['maxItems'] = len(owned)
        group['context_ids'].update(maxItems=len(available), items={'type': 'integer', 'enum': available})
        group['reason']['maxLength'] = 80
    fields['missing_context_ids']['maxItems'] = len(missing)
    if missing: fields['missing_context_ids']['items']['enum'] = missing
    fields['notes']['maxLength'] = 160
    return schema


def output_cap(case_id, owned, context, missing):
    # AICODE-NOTE: operational spending cap, not a guarantee for every schema-valid output.
    # A future sender must stop for manual review on length, without hidden retries.
    if not 1 <= len(owned) <= 16:
        raise ValueError('owned_count_outside_transport_limit')
    return max(1024, 512 + 256 * len(owned))


def validate_selection_output(spec, output):
    """Owned coverage отдельно от readable context; прежний validate адаптирован."""
    if not isinstance(output, dict): return ['output_type']
    if isinstance(output.get('decisions'), dict):
        try: output = normalized(output)
        except (ValueError, TypeError, KeyError): return ['schema_decisions_type']
    adjusted = copy.deepcopy(output)
    context = set(spec['context_ids'])
    for field in ['document_groups', 'review_groups']:
        groups = adjusted.get(field)
        if isinstance(groups, list):
            for group in groups:
                if isinstance(group, dict) and isinstance(group.get('context_ids'), list):
                    group['context_ids'] = [i for i in group['context_ids'] if type(i) is not int or i not in context]
    errors = validate({'case_id': spec['case_id'], 'message_ids': spec['owned_ids']}, adjusted)
    missing = output.get('missing_context_ids')
    if isinstance(missing, list) and any(type(i) is not int or i not in spec['missing_ids'] for i in missing):
        errors.append('invalid_missing_reference')
    return sorted(set(errors))


def generate(messages, packets, rubric):
    dispositions, requests = [], []
    for packet in packets:
        owned = []
        for ident in packet['owned_message_ids']:
            message = messages[ident]
            if message['source_role'] == 'assignment' and message['accepted_version_state'] == 'matched':
                state, decision, flags = 'accepted_assignment_preserved', None, []
            elif not message['record']['text'] and message['attachment']['attachment_presence'] is True and message['attachment']['content_read'] is False:
                state, decision, flags = 'local_review_unread_media', 'review', ['incomplete_context']
            elif packet['transport_status'] != 'ready':
                state, decision, flags = 'deferred_needs_segmentation', None, []
            else:
                state, decision, flags = 'request_owned', None, []; owned.append(ident)
            dispositions.append({'message_id': ident, 'packet_id': packet['packet_id'], 'status': state,
                                 'decision_proposal': decision, 'flags': flags, 'applied': False,
                                 'version_hash': message['version_hash'], 'text_sha256': message['text_sha256']})
        if not owned: continue
        context = {r['message_id'] for r in packet['context_references'] if r['message_id'] in messages}
        context.update(set(packet['owned_message_ids']) - set(owned))
        context -= set(owned)
        missing = [r['message_id'] for r in packet['context_references'] if r['message_id'] not in messages]
        case_id = packet['packet_id']
        owned_records = [minimal_message(messages[i]) for i in owned]
        context_records = [minimal_message(messages[i]) for i in sorted(context)]
        payload = {'case': {'case_id': case_id, 'owned_message_ids': owned,
                           'transport_part_index': packet['part_index'], 'transport_part_count': packet['part_count'],
                           'forced_transport_break': packet['forced_transport_break']},
                   'owned_messages': owned_records, 'context_messages': context_records,
                   'missing_references': [{'id': r['message_id'], 'state': r['state']} for r in packet['context_references'] if r['message_id'] in missing]}
        body = request_body(MODEL, PROVIDER, {'case_id': case_id, 'message_ids': owned}, owned_records, rubric)
        body['messages'][0]['content'] = rubric + ADAPTER
        body['messages'][1]['content'] = encoded(payload).decode()
        schema = selection_schema(case_id, owned, sorted(context), missing)
        body['response_format']['json_schema']['schema'] = schema
        body['max_tokens'] = output_cap(case_id, owned, sorted(context), missing)
        body_bytes = len(encoded(body))
        owned_text = sum(len(m['text'].encode()) for m in owned_records)
        context_text = sum(len(m['text'].encode()) for m in context_records)
        requests.append({'case_id': case_id, 'owned_ids': owned, 'context_ids': sorted(context), 'missing_ids': missing,
                         'body': body, 'body_sha256': digest(body), 'full_utf8_bytes': body_bytes,
                         'owned_text_utf8_bytes': owned_text, 'context_text_utf8_bytes': context_text,
                         'nontext_request_overhead_bytes': body_bytes - owned_text - context_text,
                         'system_prompt_utf8_bytes': len((rubric + ADAPTER).encode()), 'schema_utf8_bytes': len(encoded(schema)),
                         'input_token_conservative_bound': body_bytes + 8192, 'output_token_cap': body['max_tokens'],
                         'owned_provenance': [{'id': i, 'version_hash': messages[i]['version_hash'], 'text_sha256': messages[i]['text_sha256']} for i in owned],
                         'context_provenance': [{'id': i, 'version_hash': messages[i]['version_hash'], 'text_sha256': messages[i]['text_sha256']} for i in sorted(context)],
                         'proposal_only': True})
    return dispositions, requests


def pricing_estimate(requests, snapshot):
    entry = next(r for r in snapshot if r['model'] == MODEL and r['endpoint'] == PROVIDER)
    inputs = sum(r['input_token_conservative_bound'] for r in requests)
    outputs = sum(r['output_token_cap'] for r in requests)
    return {'label': 'estimate_not_actual_not_budget_authorization', 'input_token_upper': inputs, 'output_token_cap_total': outputs,
            'enforced_max_price_upper_usd': inputs * .20 / 1e6 + outputs * .60 / 1e6,
            'saved_snapshot_upper_estimate_usd': inputs * float(entry['pricing']['prompt']) + outputs * float(entry['pricing']['completion']),
            'saved_prompt_price_per_token': entry['pricing']['prompt'], 'saved_completion_price_per_token': entry['pricing']['completion'],
            'cache_discount_assumed': False}


def publish_requests(directory, identity, requests, manifest):
    if directory.is_symlink(): raise ValueError('symlink_generation')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True); directory.chmod(0o700)
    lock_path = directory / '.prepare.lock'
    if lock_path.is_symlink(): raise ValueError('symlink_lock')
    with lock_path.open('a') as lock:
        lock_path.chmod(0o600)
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('another_generation_active')
        payload = b''.join(encoded(request) + b'\n' for request in requests)
        manifest = dict(manifest, identity=identity, artifacts={'requests.jsonl': hashlib.sha256(payload).hexdigest()})
        artifacts = [('identity.json', encoded(identity) + b'\n'), ('requests.jsonl', payload), ('manifest.json', encoded(manifest) + b'\n')]
        for name, raw in artifacts:
            path = directory / name
            if path.is_symlink(): raise ValueError('symlink_artifact')
            if path.exists() and path.read_bytes() != raw: raise ValueError('changed_generation_refused')
        # Identity до payload, manifest после него: interruption можно восполнить.
        for name, raw in artifacts:
            path = directory / name
            if path.exists(): path.chmod(0o600); continue
            import tempfile
            fd, temporary = tempfile.mkstemp(prefix=name + '.', suffix='.tmp', dir=directory)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally: Path(temporary).unlink(missing_ok=True)
        return manifest


def main():
    os.umask(0o077)
    cli = argparse.ArgumentParser(description=__doc__); cli.add_argument('--run-name', default='selection-requests-v2')
    args = cli.parse_args()
    if Path(args.run_name).name != args.run_name or args.run_name in ('.', '..'): cli.error('private/ directory name only')
    source = PRIVATE / 'selection-packets-v1'
    before = {name: file_hash(source / name) for name in ['identity.json', 'manifest.json', 'messages.jsonl', 'packets.jsonl']}
    packet_manifest, messages, packets = load_packets(source)
    source_identity = packet_manifest['identity']
    for path, expected in source_identity['accepted_guard_sha256'].items():
        if file_hash(Path(path)) != expected: raise ValueError('accepted_source_changed')
    parser_path = Path(__file__).resolve().parents[2].parent / 'day21-sol-high/day21/corpus.py'
    if file_hash(parser_path) != source_identity['parser_sha256']: raise ValueError('source_parser_changed')
    rubric_path = RUBRIC.with_name('semantic-rubric-v3.txt'); rubric_bytes = rubric_path.read_bytes()
    if hashlib.sha256(rubric_bytes).hexdigest() != '7c80878682472e328428c36c34a0b7d1dee8f157f5342666c58d6cead3317076':
        raise ValueError('frozen_rubric_changed')
    dispositions, requests = generate(messages, packets, rubric_bytes.decode())
    snapshot_path = PRIVATE / 'semantic-openrouter-provider-snapshot.json'
    snapshot = json.loads(snapshot_path.read_text())
    owned = [i for r in requests for i in r['owned_ids']]
    if len(owned) != len(set(owned)) or {d['message_id'] for d in dispositions} != messages.keys(): raise ValueError('request_ownership')
    summary = {'source_packets': len(packets), 'calls': len(requests), 'eligible_ids': len(messages),
               'request_owned_ids': len(owned), 'unique_context_ids': len({i for r in requests for i in r['context_ids']}),
               'context_id_occurrences': sum(len(r['context_ids']) for r in requests),
               'dispositions': dict(__import__('collections').Counter(d['status'] for d in dispositions)),
               'full_utf8_bytes_total': sum(r['full_utf8_bytes'] for r in requests),
               'full_utf8_bytes_max': max((r['full_utf8_bytes'] for r in requests), default=0),
               'prompt_schema_overhead_bytes_total': sum(r['system_prompt_utf8_bytes'] + r['schema_utf8_bytes'] for r in requests),
               'nontext_request_overhead_bytes_total': sum(r['nontext_request_overhead_bytes'] for r in requests),
               'output_cap_max': max((r['output_token_cap'] for r in requests), default=0),
               'pricing_estimate': pricing_estimate(requests, snapshot), 'sent_requests': 0}
    identity = {'version': VERSION, 'source_manifest_sha256': file_hash(source / 'manifest.json'),
                'source_artifact_sha256': packet_manifest['artifacts'], 'source_input_sha256': packet_manifest['identity']['input_sha256'],
                'source_parser_sha256': packet_manifest['identity']['parser_sha256'], 'rubric_sha256': hashlib.sha256(rubric_bytes).hexdigest(),
                'adapter_sha256': hashlib.sha256(ADAPTER.encode()).hexdigest(), 'preparer_sha256': file_hash(Path(__file__)),
                'pricing_snapshot_sha256': file_hash(snapshot_path), 'model': MODEL, 'provider': PROVIDER}
    if any(file_hash(source / name) != value for name, value in before.items()): raise ValueError('source_generation_changed')
    manifest = publish_requests(PRIVATE / args.run_name, identity, requests,
                                {'summary': summary, 'dispositions': dispositions, 'proposal_only': True,
                                 'personal_data_in_text_possible': True, 'sent_requests': 0})
    print(json.dumps({'summary': summary, 'manifest_sha256': file_hash(PRIVATE / args.run_name / 'manifest.json'),
                      'adapter_sha256': identity['adapter_sha256'], 'private_modes': '0700/0600'}, ensure_ascii=False))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'error_type': type(error).__name__}), flush=True)
        raise SystemExit(1)
