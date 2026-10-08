"""Проверки контекстных metadata; вложения, holdout и сеть не читаются."""
import copy
import json
from pathlib import Path
from prepare_development_context import PRIVATE, RECHECK_CASES, attachment_metadata, sha256
from pilot_validation import diagnose_context, validate

assert attachment_metadata([]) == {'attachment_presence': False, 'attachment_type': 'none', 'content_read': False}
assert attachment_metadata(['media_new_type']) == {'attachment_presence': True, 'attachment_type': 'unknown', 'content_read': False}
assert attachment_metadata([], found=False) == {'attachment_presence': None, 'attachment_type': 'unknown', 'content_read': False}
for value in [1, None, 'false']:
    try: attachment_metadata([], found=value)
    except ValueError: pass
    else: raise AssertionError('non-boolean found')
for value in [True, [False], {'media_video': True}]:
    try: attachment_metadata(value)
    except ValueError: pass
    else: raise AssertionError('invalid classes')
for cls, kind in [('media_video', 'video'), ('photo_wrap', 'photo')]:
    assert attachment_metadata([cls])['attachment_type'] == kind

case = {'case_id': 'T', 'message_ids': [1, 2]}
messages = [{'id': 1, 'attachment_presence': True, 'content_read': False}, {'id': 2, 'reply_to': 1}]
output = {'case_id': 'T', 'decisions': [
    {'message_id': 1, 'decision': 'review', 'reason': 'непрочитано', 'flags': ['incomplete_context']},
    {'message_id': 2, 'decision': 'include', 'reason': 'ответ', 'flags': []}],
    'document_groups': [{'message_ids': [2], 'context_ids': [], 'reason': 'ответ'}],
    'review_groups': [{'message_ids': [1], 'context_ids': [], 'reason': 'контекст'}],
    'missing_context_ids': [], 'notes': ''}
assert not validate(case, output)
assert diagnose_context(case, messages, output) == ['2:unread_parent_missing_flag', '2:unread_parent_missing_context']
output['decisions'][1]['flags'] = ['incomplete_context']
output['document_groups'][0]['context_ids'] = [1]
assert not diagnose_context(case, messages, output)
# Exclude-родитель может сохраняться только как контекст, без include и слияния.
output['decisions'][0]['decision'] = 'exclude'; output['review_groups'] = []
assert not validate(case, output) and not diagnose_context(case, messages, output)
for value in [False, None, 1]:
    changed = copy.deepcopy(messages); changed[0]['attachment_presence'] = value
    bad = copy.deepcopy(output); bad['decisions'][1]['flags'] = []; bad['document_groups'][0]['context_ids'] = []
    assert diagnose_context(case, changed, bad) == (['context_input_attachment_type'] if type(value) is int else [])

source = PRIVATE / 'semantic-expanded-v2-development-input.json'
raw = source.read_bytes(); baseline = json.loads(raw)
full_path = PRIVATE / 'semantic-expanded-v3-development-input.json'
subset_path = PRIVATE / 'semantic-context-recheck-input.json'
full = json.loads(full_path.read_text()); subset = json.loads(subset_path.read_text())
a = {m['id']: m for m in baseline['messages']}; b = {m['id']: m for m in full['messages']}
assert a.keys() == b.keys() and len(a) == 39
for ident, original in a.items():
    assert b[ident]['text'].encode('utf-8') == original['text'].encode('utf-8')
    assert b[ident]['source_role'].encode('utf-8') == original['source_role'].encode('utf-8')
    assert all(b[ident][k] == v for k, v in original.items())
    assert type(b[ident]['attachment_presence']) is bool
    assert b[ident]['content_read'] is False
assert baseline['cases'] == full['cases']
assert {c['case_id'] for c in subset['cases']} == RECHECK_CASES
ids = {i for c in subset['cases'] for i in c['message_ids']}
assert ids == {m['id'] for m in subset['messages']} and len(ids) == 9
assert all(m == b[m['id']] for m in subset['messages'])
for ident, kind in [(765, 'video'), (3242, 'photo'), (4169, 'photo')]:
    assert b[ident]['attachment_presence'] is True and b[ident]['attachment_type'] == kind
assert b[4170]['reply_to'] == 4169
assert full['context_provenance']['input_sha256'] == sha256(raw)
assert source.read_bytes() == raw
assert PRIVATE.stat().st_mode & 0o777 == 0o700
assert all(p.stat().st_mode & 0o777 == 0o600 for p in [full_path, subset_path])
v2 = Path(__file__).with_name('semantic-rubric-v2.txt').read_bytes()
v3 = Path(__file__).with_name('semantic-rubric-v3.txt').read_bytes()
assert v3.startswith(v2)
assert full['rubric_sha256'] == sha256(v3)
print('ok: 39 unchanged IDs/texts/roles, four cases/nine IDs, media provenance, strict boolean/unknown, reply guard, rubric prefix, 0700/0600')
