"""Prepare a reproducible, private sample without printing source text."""
import collections
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
from datetime import date
from pathlib import Path

os.umask(0o077)
PROJECT = Path(__file__).resolve().parents[2]
PRIVATE = PROJECT / 'day21/private'
SOURCE = Path('/Users/ramanpazharytski/Downloads/Telegram Desktop/ChatExport_2026-10-01')
spec = importlib.util.spec_from_file_location('sol_corpus', PROJECT.parent / 'day21-sol-high/day21/corpus.py')
parser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)
records, files = parser.parse_export(SOURCE)
course = {r['message_id']: r for r in records
          if not r['service'] and r['date'][:10] >= '2026-08-31'}
assignments = {i: parser.assignment_day(r) for i, r in course.items() if parser.assignment_day(r)}
pilot = json.loads((PRIVATE / 'semantic-pilot-v2-input.json').read_text())
pilot_ids = {r['id'] for r in pilot['messages']}
groups = collections.defaultdict(list)
for ident in course:
    if ident in assignments:
        continue
    current, seen = ident, set()
    while current not in seen:
        seen.add(current)
        parent = course[current]['reply_to']
        if parent in assignments or parent not in course:
            break
        current = parent
    groups[current].append(ident)
eligible, omitted = {}, collections.Counter()
for root, ids in groups.items():
    if set(ids) & pilot_ids:
        omitted['overlaps_initial_pilot'] += 1
    elif len(ids) > 12 or sum(len(course[i]['text']) for i in ids) > 9000:
        # Full branch is omitted, never silently truncated to fit the pilot.
        omitted['oversize_branch'] += 1
    else:
        eligible[root] = sorted(ids, key=lambda i: (course[i]['date'], i))
rng = random.Random(210124)
chosen = []

def take(roots, count, kind, split):
    available = sorted(set(roots) - {r for r, _, _ in chosen})
    rng.shuffle(available)
    if len(available) < count:
        raise ValueError('Insufficient candidates: ' + kind)
    chosen.extend((r, kind, split) for r in available[:count])

# Ordinary samples cover four periods, equally in development and holdout.
start = date(2026, 8, 31)
periods = collections.defaultdict(list)
for root in eligible:
    week = min((date.fromisoformat(course[root]['date'][:10]) - start).days // 7, 3)
    periods[week].append(root)
for week in range(4):
    for split in ['development', 'holdout']:
        take(periods[week], 3, f'ordinary_period_{week + 1}', split)

stress = {
    'short_answer_branch': [r for r, ids in eligible.items() if any(
        course[i]['reply_to'] is not None and 0 < len(course[i]['text']) <= 40 for i in ids)],
    'long_text_branch': [r for r, ids in eligible.items() if any(len(course[i]['text']) >= 1400 for i in ids)],
    'attachment_context': [r for r, ids in eligible.items() if len(ids) > 1 and any(not course[i]['text'] for i in ids)],
    'standalone_text': [r for r, ids in eligible.items() if len(ids) == 1 and len(course[r]['text']) > 120],
}
for kind, roots in stress.items():
    for split in ['development', 'holdout']:
        take(roots, 2, kind, split)

cases, messages = [], {}
for number, (root, kind, split) in enumerate(chosen, 1):
    ids = eligible[root]
    parent = course[root]['reply_to']
    cases.append({'case_id': f'E{number:02d}', 'split': split,
                  'candidate_type': kind, 'anchor_id': root, 'message_ids': ids,
                  'context_may_need_expansion': parent is not None,
                  'assignment_context_id': parent if parent in assignments else None,
                  'known_missing_parent_ids': [parent] if parent is not None and parent not in ids else []})
    for ident in ids:
        record = course[ident]
        text = re.sub(r'(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|\d{6,12}:[A-Za-z0-9_-]{25,})\b',
                      '[REDACTED_TOKEN]', record['text'])
        messages[ident] = {'id': ident, 'date': record['date'], 'reply_to': record['reply_to'],
                           'source_role': 'discussion', 'text': text,
                           'source': {'export': 'ChatExport_2026-10-01/' + record['source_file'],
                                      'line': record['source_line']}}
dev = {i for c in cases if c['split'] == 'development' for i in c['message_ids']}
holdout = {i for c in cases if c['split'] == 'holdout' for i in c['message_ids']}
assert not dev & holdout and not (dev | holdout) & pilot_ids
rubric = (PROJECT / 'day21/review/semantic-rubric-v2.txt').read_bytes()
result = {'scope': 'Approved test sample only. Holdout stays unused during prompt tuning.',
          'seed': 210124, 'rubric_version': 'v2', 'rubric_sha256': hashlib.sha256(rubric).hexdigest(),
          'source_files': files, 'omitted_branch_counts': dict(omitted),
          'selection_limit': {'max_messages_per_full_branch': 12, 'max_characters_per_full_branch': 9000},
          'sampling_limitations': ['Branches are structural, not semantic ground truth.',
                                   'Oversize branches omitted, conclusions do not cover them.',
                                   'Root conditions are referenced, not copied; missing context may require review.'],
          'cases': cases, 'messages': list(messages.values())}
path = PRIVATE / 'semantic-expanded-v2-input.json'
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
path.chmod(0o600)
print(json.dumps({'cases': len(cases), 'messages': len(messages),
                  'characters': sum(len(m['text']) for m in messages.values()),
                  'splits': dict(collections.Counter(c['split'] for c in cases)),
                  'omitted_branch_counts': dict(omitted)}, ensure_ascii=False))
