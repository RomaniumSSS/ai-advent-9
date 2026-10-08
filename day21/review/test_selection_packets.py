"""Stdlib-проверки механической упаковки; только синтетические сообщения."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import prepare_selection_packets as prep


def record(ident, parent=None, text='Текст 🧪', date='2026-09-01T10:00:00+01:00', service=False):
    return {'message_id': ident, 'reply_to': parent, 'text': text, 'date': date, 'service': service,
            'source_file': 'synthetic.html', 'source_line': ident, 'links': [{'href': 'https://example.invalid', 'label': 'пример'}],
            'author': 'Участник', 'forwarded': []}


def build(records, assignments=(), max_messages=2, max_bytes=4000):
    identity = {'input_sha256': prep.digest(records), 'record_versions': {str(r['message_id']): prep.digest(r) for r in records},
                'max_messages': max_messages, 'max_bytes': max_bytes}
    media = {r['message_id']: {'attachment_presence': False, 'attachment_type': 'none', 'content_read': False} for r in records}
    return prep.build(records, [], media, assignments, {}, identity, max_messages, max_bytes)

records = [record(1), record(2, 1), record(3, 2), record(4, 3), record(5, 4),
           record(6, 999), record(7, text='🌍' * 2000), record(8, date='2026-08-01'), record(9, service=True)]
result = build(records)
assert result['summary']['input_ids'] == 9 and result['summary']['eligible_ids'] == 7
owners = [i for p in result['packets'] for i in p['owned_message_ids']]
assert len(owners) == len(set(owners)) == 7
assert result['summary']['transport_statuses']['needs_segmentation'] == 1
assert next(m for m in result['canonical_messages'] if m['message_id'] == 7)['record']['text'] == '🌍' * 2000
assert next(m for m in result['canonical_messages'] if m['message_id'] == 6)['reply']['parent_state'] == 'missing'
assert any(r['message_id'] == 999 and r['state'] == 'missing' for p in result['packets'] for r in p['context_references'])
branch = [p for p in result['packets'] if p['branch_root_id'] == 1]
assert len(branch) == 3 and all(p['forced_transport_break'] for p in branch)
assert branch[0]['next_packet_id'] == branch[1]['packet_id'] and branch[1]['previous_packet_id'] == branch[0]['packet_id']
assert any(r['message_id'] == 2 for r in branch[1]['context_references'])
assert result == build(records)
assert all(m['record']['links'] == records[m['message_id'] - 1]['links'] for m in result['canonical_messages'])
# Проверенное условие остаётся отдельно от двух самостоятельных вопросов под ним.
assignment = build([record(1), record(2, 1), record(3, 1), record(4, 2)], assignments={1})
assert {p['branch_root_id'] for p in assignment['packets']} == {1, 2, 3}
assert next(m for m in assignment['canonical_messages'] if m['message_id'] == 1)['source_role'] == 'assignment'
cycle = build([record(1, 2), record(2, 1), record(3, 2)])
assert all(m['reply_cycle_ids'] == [1, 2] for m in cycle['canonical_messages'])
assert cycle['summary']['branches'] == 1
orphan = build([record(1, date='2026-08-01'), record(2, 1)])
assert orphan['canonical_messages'][0]['reply']['parent_state'] == 'outside_eligible'
# Непрочитанное медиа не теряется из-за пустого текста.
media_records = [record(1, text='')]
identity = {'input_sha256': prep.digest(media_records), 'record_versions': {'1': prep.digest(media_records[0])}}
media = {1: {'attachment_presence': True, 'attachment_type': 'photo', 'content_read': False}}
photo = prep.build(media_records, [], media, {}, {}, identity)
assert photo['canonical_messages'][0]['payload_kind'] == 'metadata_only'
assert photo['canonical_messages'][0]['media_status'] == 'unread'
assert photo['summary']['owned_ids'] == 1
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / 'run'
    published = prep.publish(root, result)
    first = {name: (root / name).read_bytes() for name in ['identity.json', 'messages.jsonl', 'packets.jsonl', 'manifest.json']}
    prep.publish(root, build(records))
    assert all((root / name).read_bytes() == raw for name, raw in first.items())
    changed = copy.deepcopy(records); changed[0]['text'] += '!'
    try: prep.publish(root, build(changed))
    except ValueError: pass
    else: raise AssertionError('changed input overwritten')
    assert all((root / name).read_bytes() == raw for name, raw in first.items())
    assert root.stat().st_mode & 0o777 == 0o700
    assert all((root / name).stat().st_mode & 0o777 == 0o600 for name in first)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / 'run'; original = prep.os.replace
    def interrupt(source, target):
        if Path(target).name == 'packets.jsonl': raise OSError('synthetic interruption')
        return original(source, target)
    with patch.object(prep.os, 'replace', interrupt):
        try: prep.publish(root, result)
        except OSError: pass
        else: raise AssertionError('interruption missing')
    assert not (root / 'manifest.json').exists()
    assert (root / 'messages.jsonl').exists()
    prep.publish(root, result)
    assert json.loads((root / 'manifest.json').read_text())['artifacts'] == published['artifacts']
print('ok: no-reply/orphan/cycle, independent assignment branches, long branch/huge Unicode message, links, media-only, deterministic repeat, changed-input refusal, interrupted publication recovery, 0700/0600')
