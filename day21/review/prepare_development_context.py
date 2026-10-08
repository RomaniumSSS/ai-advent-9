"""Добавить только метаданные вложений разрешённой development-выборки."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

from run_local_sample import write

PROJECT = Path(__file__).resolve().parents[2]
PRIVATE = PROJECT / 'day21/private'
RECHECK_CASES = {'E03', 'E07', 'E33', 'E34'}
MEDIA_TYPES = {
    'media_video': 'video', 'video_file': 'video', 'photo_wrap': 'photo',
    'media_photo': 'photo', 'media_voice_message': 'voice',
    'media_audio_file': 'audio', 'media_file': 'file',
    'media_sticker': 'sticker', 'media_animation': 'animation',
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def attachment_metadata(classes, found=True):
    if type(found) is not bool:
        raise ValueError('found must be boolean')
    if not found:
        return {'attachment_presence': None, 'attachment_type': 'unknown', 'content_read': False}
    if not isinstance(classes, (list, set, tuple)) or any(not isinstance(c, str) for c in classes):
        raise ValueError('classes must contain strings')
    types = sorted({MEDIA_TYPES[c] for c in classes if c in MEDIA_TYPES})
    media_present = bool(types) or any(c.startswith('media_') or c == 'media' for c in classes)
    return {'attachment_presence': media_present,
            'attachment_type': types[0] if len(types) == 1 else 'multiple' if types else 'unknown' if media_present else 'none',
            'content_read': False}


def load_parser(path):
    spec = importlib.util.spec_from_file_location('development_sol_corpus', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def metadata_parser(module, filename, allowed):
    class MetadataParser(module.TelegramParser):
        def handle_data(self, data):
            # Тексты, имена и подписи не нужны для metadata и не накапливаются.
            pass

        def _record(self, root):
            raw_id = root.attrs.get('id', '')
            if not raw_id.startswith('message') or not raw_id[7:].isdecimal():
                return None
            ident = int(raw_id[7:])
            if ident not in allowed:
                return None
            classes = {c for node in module.walk(root) for c in node.classes
                       if c in MEDIA_TYPES or c.startswith('media_') or c == 'media'}
            return {'id': ident, 'line': root.line, 'classes': sorted(classes),
                    **attachment_metadata(classes)}
    return MetadataParser(filename)


def build(data, input_hash, source_root, parser_path, split="development"):
    expected_messages = {"development": 39, "holdout": 51}[split]
    if len(data['cases']) != 20 or len(data['messages']) != expected_messages or any(c.get('split') != split for c in data['cases']):
        raise ValueError('Invalid approved split size')
    messages = {m['id']: m for m in data['messages']}
    if len(messages) != expected_messages or any(type(i) is not int for i in messages):
        raise ValueError('Invalid development IDs')
    case_ids = {c['case_id'] for c in data['cases']}
    if len(case_ids) != 20 or (split == "development" and not RECHECK_CASES <= case_ids):
        raise ValueError('Invalid development case IDs')
    if {i for c in data['cases'] for i in c['message_ids']} != messages.keys():
        raise ValueError('Input case/message coverage mismatch')
    expected_hashes = {f['name']: f['sha256'] for f in data['source_files']}
    files = {}
    for message in messages.values():
        source = message['source']
        ref = Path(source['export'])
        if len(ref.parts) != 2 or ref.parts[0] != source_root.name or ref.name not in expected_hashes:
            raise ValueError('Invalid source reference')
        files.setdefault(ref.name, set()).add(message['id'])
    module = load_parser(parser_path)
    metadata, hashes = {}, {}
    for filename, allowed in sorted(files.items()):
        raw = (source_root / filename).read_bytes()
        digest = sha256(raw)
        if digest != expected_hashes[filename]:
            raise ValueError('Source hash changed: ' + filename)
        parser = metadata_parser(module, filename, allowed)
        parser.feed(raw.decode('utf-8'))
        parser.close()
        for record in parser.records:
            ident = record['id']
            if ident in metadata or record['line'] != messages[ident]['source']['line']:
                raise ValueError('Duplicate ID or changed source line')
            metadata[ident] = record
        hashes[filename] = digest
    if metadata.keys() != messages.keys():
        raise ValueError('Missing source metadata; absence must not be inferred')
    result = copy.deepcopy(data)
    result.update(rubric_version='v3', rubric_sha256=sha256(Path(__file__).with_name('semantic-rubric-v3.txt').read_bytes()),
                  parent_input_sha256=input_hash,
                  context_provenance={'input_sha256': input_hash,
                                      'parser_sha256': sha256(parser_path.read_bytes()),
                                      'preparer_sha256': sha256(Path(__file__).read_bytes()),
                                      'source_sha256': hashes,
                                      'method': 'TelegramParser Node classes only; no attachment content read'})
    for message in result['messages']:
        record = metadata[message['id']]
        message.update({k: record[k] for k in ['attachment_presence', 'attachment_type', 'content_read']})
        message['attachment_provenance'] = {'source_sha256': hashes[Path(message['source']['export']).name],
                                             'line': record['line'], 'media_classes': record['classes']}
    subset = copy.deepcopy(result)
    subset['cases'] = [c for c in subset['cases'] if c['case_id'] in RECHECK_CASES]
    ids = {i for c in subset['cases'] for i in c['message_ids']}
    subset['messages'] = [m for m in subset['messages'] if m['id'] in ids]
    subset['scope'] = 'Four development cases for context recheck only; no holdout.'
    return result, subset if split == 'development' else None


def select_holdout(data):
    result = copy.deepcopy(data)
    development_ids = {i for c in data['cases'] if c['split'] == 'development' for i in c['message_ids']}
    result['cases'] = [c for c in data['cases'] if c['split'] == 'holdout']
    ids = {i for c in result['cases'] for i in c['message_ids']}
    pilot = json.loads((PRIVATE / 'semantic-pilot-v2-input.json').read_text())
    pilot_ids = {m['id'] for m in pilot['messages']}
    if ids & (development_ids | pilot_ids):
        raise ValueError('Holdout overlaps development/pilot')
    result['messages'] = [m for m in data['messages'] if m['id'] in ids]
    result['scope'] = 'Frozen-rubric holdout evaluation only; no prompt tuning.'
    return result


def main():
    os.umask(0o077)
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, default=Path('/Users/ramanpazharytski/Downloads/Telegram Desktop/ChatExport_2026-10-01'))
    cli.add_argument('--parser-path', type=Path, default=PROJECT.parent / 'day21-sol-high/day21/corpus.py')
    cli.add_argument('--split', choices=['development', 'holdout'], default='development')
    args = cli.parse_args()
    source = PRIVATE / ('semantic-expanded-v2-input.json' if args.split == 'holdout' else 'semantic-expanded-v2-development-input.json')
    raw = source.read_bytes()
    data = json.loads(raw)
    if args.split == 'holdout':
        data = select_holdout(data)
    full, subset = build(data, sha256(raw), args.source_root, args.parser_path, args.split)
    if source.read_bytes() != raw:
        raise ValueError('Input changed during preparation')
    targets = [(PRIVATE / 'semantic-expanded-v3-development-input.json', full),
               (PRIVATE / 'semantic-context-recheck-input.json', subset)]
    if args.split == 'holdout':
        targets = [(PRIVATE / 'semantic-expanded-v3-holdout-input.json', full)]
    for target, result in targets:
        if target.exists() and json.loads(target.read_text()) != result:
            raise ValueError('Refusing to overwrite a different prepared artifact')
    for target, result in targets:
        write(target, result)
    print(json.dumps({'split': args.split, 'cases': len(full['cases']), 'messages': len(full['messages']),
                      'output_sha256': sha256(targets[0][0].read_bytes()),
                      'attachment_counts': {kind: sum(m['attachment_type'] == kind for m in full['messages'])
                                            for kind in sorted({m['attachment_type'] for m in full['messages']})},
                      'input_sha256': sha256(raw)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
