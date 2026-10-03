"""Подлинность ссылок и цитат не доказывает смысловую правильность ответа."""
import json


def refusal():
    return {'answer': 'Не знаю: недостаточно релевантных сведений. Уточни день задания или тему вопроса.',
            'sources': [], 'quotes': [], 'status': 'no_context'}


def check_answer(content, selected):
    """Возвращает наблюдаемые ошибки, не исправляя слова модели задним числом."""
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return {'valid': False, 'errors': ['invalid_json'], 'answer': None}
    if not isinstance(data, dict) or set(data) != {'answer', 'sources', 'quotes'}:
        return {'valid': False, 'errors': ['invalid_fields'], 'answer': data}
    errors = []
    if not isinstance(data['answer'], str) or not data['answer'].strip():
        errors.append('empty_answer')
    if not isinstance(data['sources'], list) or not isinstance(data['quotes'], list):
        return {'valid': False, 'errors': errors + ['invalid_lists'], 'answer': data}
    if not data['sources']:
        errors.append('missing_sources')
    if not data['quotes']:
        errors.append('missing_quotes')
    chunks = {c['chunk_id']: c for c in selected}
    source_ids, quote_ids = set(), set()
    for source in data['sources']:
        if (not isinstance(source, dict) or set(source) != {'source', 'chunk_id'}
                or not all(isinstance(source[k], str) and source[k] for k in source)):
            errors.append('invalid_source')
            continue
        cid = source['chunk_id']
        if cid in source_ids:
            errors.append('duplicate_source')
        source_ids.add(cid)
        if cid not in chunks or source['source'] != chunks[cid]['source']:
            errors.append('source_not_in_context')
    for quote in data['quotes']:
        if (not isinstance(quote, dict) or set(quote) != {'chunk_id', 'text'}
                or not all(isinstance(quote[k], str) and quote[k].strip() for k in quote)):
            errors.append('invalid_quote')
            continue
        cid = quote['chunk_id']
        quote_ids.add(cid)
        if cid not in chunks or quote['text'] not in chunks[cid]['text']:
            errors.append('quote_not_in_context')
        if cid not in source_ids:
            errors.append('quote_without_source')
    if source_ids - quote_ids:
        errors.append('source_without_quote')
    return {'valid': not errors, 'errors': sorted(set(errors)), 'answer': data,
            'sources_present': bool(data['sources']), 'quotes_present': bool(data['quotes']),
            'semantic_match': None}
