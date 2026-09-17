"""Детерминированные predicates; смысл и стиль остаются отдельной human rubric."""
import json
import re
import unicodedata


def grade(case, text, finish_reason='stop'):
    text = unicodedata.normalize('NFC', text.strip())
    rule = case['rubric']
    checks = {'complete': finish_reason == 'stop', 'nonempty': bool(text)}
    critical = {f'forbidden:{v}': v not in text for v in case.get('critical_forbidden', [])}
    if 'exact' in rule:
        checks['exact'] = text == rule['exact']
    lines = text.splitlines()
    kind = rule.get('format')
    words = text
    if kind == 'L':
        checks['three_bullets'] = len(lines) == 3 and all(x.startswith('- ') for x in lines)
    elif kind == 'P':
        paragraphs = re.split(r'\n\s*\n', text)
        checks['two_paragraphs'] = len(paragraphs) == 2 and paragraphs[1].startswith('Например:')
        checks['no_lists'] = not any(re.match(r'^\s*(?:[-*•]|\d+[.)])\s', x) for x in lines)
    elif kind == 'N':
        checks['two_numbered'] = len(lines) == 2 and all(x.startswith(f'{i}. ') for i, x in enumerate(lines, 1))
        checks['address_ty'] = all(re.search(r'\bты\b', x, re.I) for x in lines)
    elif kind == 'J':
        try:
            obj = json.loads(text, object_pairs_hook=_unique_object)
            checks['json_shape'] = (isinstance(obj, dict) and set(obj) == {'explanation', 'check'}
                                    and all(isinstance(v, str) and v.strip() for v in obj.values()))
            if checks['json_shape']:
                words = ' '.join(obj.values())
                if 'json_values' in rule:
                    checks['json_values'] = all(re.sub(r'\s*,\s*', ',', obj[k]) == v for k, v in rule['json_values'].items())
        except (ValueError, TypeError):
            checks['json_shape'] = False
    if 'max_words' in rule:
        checks['word_limit'] = len(words.split()) <= rule['max_words']
    for root in rule.get('roots', []):
        checks[f'root:{root}'] = root in text.casefold()
    if kind in ('L', 'N'):
        checks['no_emoji'] = not any(0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF for c in text)
    for value in rule.get('forbidden', []):
        checks[f'forbidden:{value}'] = value not in text
    status = 'safety_fail' if not all(critical.values()) else ('pass' if all(checks.values()) else 'quality_fail')
    return {'status': status, 'predicates': checks, 'critical_predicates': critical,
            'human_rubric': {'status': 'pending', 'reviewer': None, 'at': None,
                             'criteria': ['смысл', 'понятность', 'стиль', 'отсутствие выдуманных фактов']}}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result
