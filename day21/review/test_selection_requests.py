"""Синтетический dry-run: owned/context, минимальные поля, schema и бюджет."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import prepare_selection_requests as prep


def message(ident, role='discussion', text='Пример 🧪\nстрока', parent=None, attachment=False):
    return {'message_id': ident, 'source_role': role, 'accepted_version_state': 'matched' if role == 'assignment' else 'absent',
            'version_hash': 'version-' + str(ident), 'text_sha256': 'hash-' + str(ident),
            'record': {'text': text, 'reply_to': parent, 'author': 'DO_NOT_SEND_NAME', 'date': 'DO_NOT_SEND_DATE', 'source_file': 'DO_NOT_SEND_PATH'},
            'attachment': {'attachment_presence': attachment, 'attachment_type': 'photo' if attachment else 'none', 'content_read': False}}


def packet(ids, context=()):
    return {'packet_id': 'synthetic', 'owned_message_ids': ids,
            'context_references': [{'message_id': i, 'state': 'canonical' if i != 999 else 'missing'} for i in context],
            'transport_status': 'ready', 'part_index': 0, 'part_count': 1, 'forced_transport_break': False}

messages = {1: message(1, 'assignment'), 2: message(2, parent=1), 3: message(3, text='', attachment=True), 4: message(4, parent=3)}
dispositions, requests = prep.generate(messages, [packet([1]), packet([2, 3, 4], [1, 999])], 'frozen rubric')
assert len(requests) == 1
spec = requests[0]
assert spec['owned_ids'] == [2, 4] and spec['context_ids'] == [1, 3] and spec['missing_ids'] == [999]
assert [d['status'] for d in dispositions] == ['accepted_assignment_preserved', 'request_owned', 'local_review_unread_media', 'request_owned']
body = spec['body']; payload = json.loads(body['messages'][1]['content'])
assert body['messages'][0]['content'] == 'frozen rubric' + prep.ADAPTER
assert body['model'] == prep.MODEL and body['provider']['only'] == ['deepinfra/fp8'] and body['provider']['allow_fallbacks'] is False
assert body['response_format']['json_schema']['strict'] is True
schema = body['response_format']['json_schema']['schema']
assert schema['properties']['decisions']['required'] == ['2', '4']
assert set(schema['properties']['decisions']['properties']) == {'2', '4'}
assert schema['properties']['document_groups']['items']['properties']['message_ids']['items']['enum'] == [2, 4]
assert all(m['text'].encode() == messages[m['id']]['record']['text'].encode() for m in payload['owned_messages'] + payload['context_messages'])
assert all(set(m) == {'id', 'text', 'reply_to', 'source_role', 'attachment_presence', 'attachment_type', 'content_read'} for m in payload['owned_messages'] + payload['context_messages'])
assert all(value not in json.dumps(payload) for value in ['DO_NOT_SEND_NAME', 'DO_NOT_SEND_DATE', 'DO_NOT_SEND_PATH'])
output = {'case_id': 'synthetic', 'decisions': {str(i): {'decision': 'include', 'reason': 'пример', 'flags': []} for i in [2, 4]},
          'document_groups': [{'message_ids': [2, 4], 'context_ids': [1, 3, 999], 'reason': 'пример'}],
          'review_groups': [], 'missing_context_ids': [999], 'notes': ''}
assert not prep.validate_selection_output(spec, output)
extra = copy.deepcopy(output); extra['decisions']['1'] = {'decision': 'include', 'reason': 'пример', 'flags': []}
assert 'decision_coverage' in prep.validate_selection_output(spec, extra)
extra = copy.deepcopy(output); extra['document_groups'][0]['message_ids'].append(1)
assert prep.validate_selection_output(spec, extra)
extra = copy.deepcopy(output); extra['missing_context_ids'].append(3)
assert 'invalid_missing_reference' in prep.validate_selection_output(spec, extra)
assert prep.generate(messages, [packet([1]), packet([3])], 'rubric')[1] == []
large = {i: message(i) for i in range(1, 17)}
_, sixteen = prep.generate(large, [packet(list(large))], 'rubric')
assert sixteen[0]['output_token_cap'] == 4608
caps = [prep.output_cap('synthetic', list(range(n)), [], []) for n in range(1, 17)]
assert caps == sorted(caps) and min(caps) == 1024 and max(caps) <= 4608
assert caps == [max(1024, 512 + 256 * n) for n in range(1, 17)]
assert sixteen[0]['full_utf8_bytes'] == len(prep.encoded(sixteen[0]['body']))
assert sixteen[0]['input_token_conservative_bound'] == sixteen[0]['full_utf8_bytes'] + 8192
assert prep.generate(messages, [packet([2, 3, 4], [1, 999])], 'frozen rubric') == prep.generate(messages, [packet([2, 3, 4], [1, 999])], 'frozen rubric')
snapshot = [{'model': prep.MODEL, 'endpoint': prep.PROVIDER, 'pricing': {'prompt': '0.00000014', 'completion': '0.00000042'}}]
estimate = prep.pricing_estimate(requests, snapshot)
assert estimate['output_token_cap_total'] == sum(r['body']['max_tokens'] for r in requests)
assert abs(estimate['enforced_max_price_upper_usd'] - (sum(r['input_token_conservative_bound'] for r in requests) * .20 + sum(r['body']['max_tokens'] for r in requests) * .60) / 1e6) < 1e-10
assert abs(estimate['saved_snapshot_upper_estimate_usd'] - estimate['enforced_max_price_upper_usd'] * .7) < 1e-10
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / 'run'
    manifest = {'summary': {}, 'sent_requests': 0}
    prep.publish_requests(root, {'version': 1}, requests, manifest)
    before = {n: (root / n).read_bytes() for n in ['identity.json', 'requests.jsonl', 'manifest.json']}
    prep.publish_requests(root, {'version': 1}, requests, manifest)
    assert all((root / n).read_bytes() == value for n, value in before.items())
    try: prep.publish_requests(root, {'version': 2}, requests, manifest)
    except ValueError: pass
    else: raise AssertionError('changed generation overwritten')
    assert all((root / n).stat().st_mode & 0o777 == 0o600 for n in before)
    assert root.stat().st_mode & 0o777 == 0o700
print('ok: owned-only schema/decisions/groups, accepted/media skip, context/missing distinction, untouched Unicode text, minimal metadata, cap/byte/cost bound, deterministic immutable private generation')

# Проверка hash/version source на синтетическом immutable комплекте.
import prepare_selection_packets as packets_module
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / 'packets'
    record = {'message_id': 7, 'reply_to': None, 'text': 'Синтетика', 'date': '2026-09-01',
              'service': False, 'source_file': 'synthetic.html', 'source_line': 1, 'links': []}
    identity = {'version': 1, 'input_sha256': packets_module.digest([record]),
                'record_versions': {'7': packets_module.digest(record)}}
    result = packets_module.build([record], [], {}, {}, {}, identity)
    packets_module.publish(root, result)
    approved = prep.file_hash(root / 'manifest.json')
    with patch.object(prep, 'EXPECTED_PACKET_MANIFEST', approved):
        manifest, canonical, source_packets = prep.load_packets(root)
        assert set(canonical) == {7}
        path = root / 'messages.jsonl'; path.write_bytes(path.read_bytes() + b'\n')
        try: prep.load_packets(root)
        except ValueError: pass
        else: raise AssertionError('tampered artifact accepted')
    try: prep.load_packets(root)
    except ValueError: pass
    else: raise AssertionError('different approved manifest accepted')
print('ok: pinned source manifest, source version/hash, corrupted immutable artifact rejected')
