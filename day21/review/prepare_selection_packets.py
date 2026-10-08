"""Локальные транспортные пакеты; не смысловой отбор и не изменение корпуса."""
import argparse
import collections
import hashlib
import fcntl
import json
import os
from pathlib import Path
import sqlite3
from prepare_development_context import load_parser, metadata_parser
from run_local_sample import write

PROJECT = Path(__file__).resolve().parents[2]
PRIVATE = PROJECT / 'day21/private'
SOL = PROJECT.parent / 'day21-sol-high/day21'
VERSION = 1


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def branch_for(ident, eligible, records, assignments):
    current, path = ident, []
    while True:
        if current in path:
            cycle = path[path.index(current):]
            return min(cycle), 'reply_cycle', sorted(cycle), None
        path.append(current)
        if current in assignments:
            return current, 'assignment', [], None
        parent = records[current]['reply_to']
        if parent in assignments:
            return current, 'discussion', [], parent
        if parent not in eligible:
            return current, 'discussion', [], None
        current = parent


def build(records, source_files, media, verified_assignments, accepted_versions, identity, max_messages=16, max_bytes=24000,
          start_date='2026-08-31', end_date='2026-10-01'):
    if type(max_messages) is not int or max_messages < 1 or type(max_bytes) is not int or max_bytes < 1:
        raise ValueError('invalid_transport_limits')
    all_records = {}
    for record in records:
        ident = record['message_id']
        if type(ident) is not int or ident in all_records:
            raise ValueError('duplicate_or_invalid_input_id')
        if record.get('reply_to') is not None and type(record['reply_to']) is not int:
            raise ValueError('invalid_reply_id')
        all_records[ident] = record
    coverage, eligible = [], set()
    for ident, record in all_records.items():
        if record['service']:
            state = 'service'
        elif not isinstance(record.get('date'), str):
            raise ValueError('missing_record_date')
        elif not start_date <= record['date'][:10] <= end_date:
            state = 'outside_period'
        else:
            state = 'eligible'; eligible.add(ident)
        coverage.append({'message_id': ident, 'input_status': state, 'source_file': record['source_file'], 'source_line': record['source_line']})
    assignments = set(verified_assignments) & eligible
    order = lambda ident: (all_records[ident]['date'], ident)
    canonical, branches = {}, collections.defaultdict(list)
    for ident in sorted(eligible, key=order):
        record = all_records[ident]
        metadata = media.get(ident, {'attachment_presence': None, 'attachment_type': 'unknown', 'content_read': False})
        root, kind, cycle, assignment = branch_for(ident, eligible, all_records, assignments)
        version = identity['record_versions'][str(ident)]
        accepted = accepted_versions.get('telegram:' + str(ident))
        parent = record['reply_to']
        parent_state = ('none' if parent is None else 'missing' if parent not in all_records else
                        'outside_eligible' if parent not in eligible else
                        'unread_media' if media.get(parent, {}).get('attachment_presence') is True else
                        'nontext' if not all_records[parent]['text'] else 'available')
        canonical[ident] = {'message_id': ident, 'source_key': 'telegram:' + str(ident),
                           'version_hash': version, 'record_sha256': digest(record), 'text_sha256': hashlib.sha256(record['text'].encode()).hexdigest(),
                           'source_role': 'assignment' if ident in assignments else 'discussion',
                           'accepted_version_hash': accepted,
                           'accepted_version_state': 'absent' if accepted is None else 'matched' if accepted == version else 'changed_proposal_only',
                           'record': record, 'attachment': {k: metadata[k] for k in ['attachment_presence', 'attachment_type', 'content_read']},
                           'media_status': 'unread' if metadata['attachment_presence'] is True else 'unknown' if metadata['attachment_presence'] is None else 'absent',
                           'payload_kind': 'metadata_only' if not record['text'] and metadata['attachment_presence'] is not False else 'text_and_metadata',
                           'reply': {'parent_id': parent, 'parent_state': parent_state},
                           'branch_root_id': root, 'branch_kind': kind, 'reply_cycle_ids': cycle,
                           'assignment_context_id': assignment,
                           'semantic_decision': None,
                           'mixed_content_proposal': {'status': 'not_evaluated', 'offset_unit': 'unicode_codepoint',
                               'interval': 'half_open', 'text_sha256': hashlib.sha256(record['text'].encode()).hexdigest(),
                               'proposed_ranges': [], 'requires_review': True, 'applied': False}}
        branches[root].append(ident)
    packets = []
    for root in sorted(branches, key=order):
        branch = sorted(branches[root], key=order)
        pieces, current, current_bytes = [], [], 0
        for ident in branch:
            size = len(encoded(canonical[ident]))
            if size > max_bytes:
                if current: pieces.append((current, 'ready')); current, current_bytes = [], 0
                pieces.append(([ident], 'needs_segmentation')); continue
            if current and (len(current) >= max_messages or current_bytes + size > max_bytes):
                pieces.append((current, 'ready')); current, current_bytes = [], 0
            current.append(ident); current_bytes += size
        if current: pieces.append((current, 'ready'))
        for index, (ids, state) in enumerate(pieces):
            owned = set(ids)
            context = {all_records[i]['reply_to'] for i in ids if all_records[i]['reply_to'] is not None and all_records[i]['reply_to'] not in owned}
            if root not in owned: context.add(root)
            context.update(canonical[i]['assignment_context_id'] for i in ids if canonical[i]['assignment_context_id'] is not None and canonical[i]['assignment_context_id'] not in owned)
            references = []
            for ident in sorted(context):
                references.append({'message_id': ident,
                                   'state': 'missing' if ident not in all_records else 'canonical' if ident in eligible else 'outside_eligible_metadata_only',
                                   'version_hash': identity['record_versions'].get(str(ident)),
                                   'source_file': all_records[ident]['source_file'] if ident in all_records else None,
                                   'source_line': all_records[ident]['source_line'] if ident in all_records else None})
            packet = {'packet_id': 'p-' + digest({'identity': identity['input_sha256'], 'root': root, 'index': index, 'owned': ids})[:20],
                      'branch_root_id': root, 'branch_kind': canonical[root]['branch_kind'],
                      'part_index': index, 'part_count': len(pieces), 'owned_message_ids': ids,
                      'context_references': references, 'transport_status': state,
                      'owned_payload_bytes': sum(len(encoded(canonical[i])) for i in ids),
                      'forced_transport_break': len(pieces) > 1,
                      'previous_packet_id': None, 'next_packet_id': None,
                      'reply_references': [{'message_id': i, **canonical[i]['reply']} for i in ids],
                      'semantic_boundary': 'not_evaluated', 'decisions_applied': False}
            packets.append(packet)
        local = packets[-len(pieces):]
        for index, packet in enumerate(local):
            packet['previous_packet_id'] = local[index - 1]['packet_id'] if index else None
            packet['next_packet_id'] = local[index + 1]['packet_id'] if index + 1 < len(local) else None
    ownership = {i: p['packet_id'] for p in packets for i in p['owned_message_ids']}
    for item in coverage:
        ident = item['message_id']; item['owner_packet_id'] = ownership.get(ident)
        item['version_hash'] = identity['record_versions'][str(ident)]
    summary = {'input_ids': len(records), 'eligible_ids': len(eligible), 'owned_ids': len(ownership),
               'input_statuses': dict(collections.Counter(c['input_status'] for c in coverage)),
               'packets': len(packets), 'branches': len(branches), 'assignment_ids': len(assignments),
               'transport_statuses': dict(collections.Counter(p['transport_status'] for p in packets)),
               'split_branches': len({p['branch_root_id'] for p in packets if p['forced_transport_break']}),
               'parent_states': dict(collections.Counter(m['reply']['parent_state'] for m in canonical.values())),
               'attachment_types': dict(collections.Counter(m['attachment']['attachment_type'] for m in canonical.values())),
               'accepted_version_states': dict(collections.Counter(m['accepted_version_state'] for m in canonical.values())),
               'eligible_text_utf8_bytes': sum(len(m['record']['text'].encode()) for m in canonical.values()),
               'semantic_decisions': 0}
    result = {'identity': identity, 'source_files': source_files, 'summary': summary, 'coverage': sorted(coverage, key=lambda c: c['message_id']),
              'canonical_messages': list(canonical.values()), 'packets': packets}
    validate_preparation(result, records)
    return result


def validate_preparation(result, originals):
    originals = {r['message_id']: r for r in originals}
    canonical = {m['message_id']: m for m in result['canonical_messages']}
    eligible = {c['message_id'] for c in result['coverage'] if c['input_status'] == 'eligible'}
    owners = [i for p in result['packets'] for i in p['owned_message_ids']]
    if len(owners) != len(set(owners)) or set(owners) != eligible or canonical.keys() != eligible:
        raise ValueError('ownership_coverage')
    if {c['message_id'] for c in result['coverage']} != originals.keys():
        raise ValueError('input_coverage')
    for ident, message in canonical.items():
        if message['record'] != originals[ident]: raise ValueError('record_changed')
        if message['attachment']['content_read'] is not False: raise ValueError('attachment_read')
    for packet in result['packets']:
        owned = set(packet['owned_message_ids'])
        references = {r['message_id'] for r in packet['context_references']}
        for ident in owned:
            parent = originals[ident]['reply_to']
            if parent is not None and parent not in owned and parent not in references:
                raise ValueError('reply_reference_lost')


def publish_unlocked(directory, result):
    if directory.is_symlink(): raise ValueError('symlink_run_directory')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True); directory.chmod(0o700)
    state = directory / 'identity.json'
    if state.is_symlink(): raise ValueError('symlink_identity')
    if state.exists() and json.loads(state.read_text()) != result['identity']:
        raise ValueError('changed_input_or_configuration')
    if not state.exists(): write(state, result['identity'])
    messages = b''.join(encoded(m) + b'\n' for m in result['canonical_messages'])
    packets = b''.join(encoded(p) + b'\n' for p in result['packets'])
    manifest = {k: v for k, v in result.items() if k not in ['canonical_messages', 'packets']}
    manifest['artifacts'] = {name: hashlib.sha256(raw).hexdigest() for name, raw in [('messages.jsonl', messages), ('packets.jsonl', packets)]}
    # Manifest публикуется последним: его наличие означает проверенный комплект.
    for name, raw in [('messages.jsonl', messages), ('packets.jsonl', packets), ('manifest.json', encoded(manifest) + b'\n')]:
        path = directory / name
        if path.is_symlink(): raise ValueError('symlink_artifact')
        if path.exists():
            if path.read_bytes() != raw: raise ValueError('different_existing_artifact')
            path.chmod(0o600); continue
        import tempfile
        descriptor, temporary = tempfile.mkstemp(prefix=name + '.', suffix='.tmp', dir=directory)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return manifest


def publish(directory, result):
    if directory.is_symlink(): raise ValueError('symlink_run_directory')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True); directory.chmod(0o700)
    lock_path = directory / '.prepare.lock'
    if lock_path.is_symlink(): raise ValueError('symlink_lock')
    with lock_path.open('a') as lock:
        os.chmod(lock_path, 0o600)
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('another_preparation_active')
        return publish_unlocked(directory, result)


def main():
    os.umask(0o077)
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-dir', type=Path, default=Path('/Users/ramanpazharytski/Downloads/Telegram Desktop/ChatExport_2026-10-01'))
    cli.add_argument('--run-name', default='selection-packets-v1')
    cli.add_argument('--max-messages', type=int, default=16)
    cli.add_argument('--max-bytes', type=int, default=24000)
    args = cli.parse_args()
    if Path(args.run_name).name != args.run_name or args.run_name in ('.', '..'):
        cli.error('run-name must be a private/ directory name')
    protected = [SOL / 'private/corpus.sqlite3', SOL / 'private/selection-manifest.json']
    before = {str(path): file_hash(path) for path in protected}
    with sqlite3.connect((SOL / 'private/corpus.sqlite3').resolve().as_uri() + '?mode=ro', uri=True) as conn:
        accepted = dict(conn.execute('SELECT source_key,version_hash FROM accepted'))
    parser_path = SOL / 'corpus.py'; module = load_parser(parser_path)
    records, files = module.parse_export(args.source_dir)
    media = {}
    for source in files:
        parser = metadata_parser(module, source['name'], {r['message_id'] for r in records if r['source_file'] == source['name']})
        parser.feed((args.source_dir / source['name']).read_bytes().decode('utf-8-sig')); parser.close()
        if parser.stack: raise ValueError('incomplete_media_parse')
        for item in parser.records:
            if item['id'] in media: raise ValueError('duplicate_media_id')
            media[item['id']] = item
    if media.keys() != {r['message_id'] for r in records}: raise ValueError('missing_media_metadata')
    identity = {'version': VERSION, 'parser_sha256': file_hash(parser_path), 'parser_revision': module.PARSER_REVISION,
                'preparer_sha256': file_hash(Path(__file__)), 'metadata_preparer_sha256': file_hash(Path(__file__).with_name('prepare_development_context.py')),
                'source_sha256': {f['name']: f['sha256'] for f in files}, 'input_sha256': digest(files),
                'source_kind': 'fresh_five_part_export', 'start_date': module.START_DATE, 'end_date': '2026-10-01',
                'max_messages': args.max_messages, 'max_bytes': args.max_bytes, 'accepted_guard_sha256': before,
                'record_versions': {str(r['message_id']): module.content_digest(r) for r in records},
                'verified_assignment_ids': sorted(module.ASSIGNMENT_BY_ID)}
    result = build(records, files, media, module.ASSIGNMENT_BY_ID, accepted, identity, args.max_messages, args.max_bytes)
    if any(file_hash(args.source_dir / f['name']) != f['sha256'] for f in files): raise ValueError('source_changed_during_preparation')
    if any(file_hash(Path(path)) != sha for path, sha in before.items()): raise ValueError('accepted_store_changed')
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True); PRIVATE.chmod(0o700)
    manifest = publish(PRIVATE / args.run_name, result)
    if any(file_hash(Path(path)) != sha for path, sha in before.items()): raise ValueError('accepted_store_changed')
    print(json.dumps({'summary': manifest['summary'], 'input_sha256': identity['input_sha256'],
                      'manifest_sha256': file_hash(PRIVATE / args.run_name / 'manifest.json'),
                      'artifact_sha256': manifest['artifacts'], 'accepted_guard_unchanged': True}, ensure_ascii=False))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'error_type': type(error).__name__}), flush=True)
        raise SystemExit(1)
