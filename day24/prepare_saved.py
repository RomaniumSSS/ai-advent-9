"""Повторить поиск на сохранённых векторах без сети и доступа к эталонам."""
import argparse
import json
from pathlib import Path
from common import MODEL, save
from retrieval import Config, retrieve
from answers import refusal


def prepare(data, ids):
    lookup = {c['id']: c for c in data['cases']}
    if len(set(ids)) != len(ids) or any(i not in lookup for i in ids):
        raise ValueError('invalid_case_selection')
    cases = []
    for ident in ids:
        old = lookup[ident]
        trace = retrieve(data['chunks'], old['question'], old['query_vectors']['original'], Config())
        cases.append({'id': ident, 'question': old['question'], 'traces': {'rag': trace},
                      'messages': {} if trace['empty'] else {'rag': trace['messages']},
                      'local_result': refusal() if trace['empty'] else None})
    return {'version': 1, 'model': MODEL, 'identity': data['identity'], 'cases': cases,
            'origin': 'saved_query_vectors_no_network'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--saved', required=True)
    p.add_argument('--ids', nargs='+', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    result = prepare(json.loads(Path(a.saved).read_text()), a.ids)
    save(a.output, result)
    print(json.dumps({'cases': len(result['cases']), 'cloud_jobs': sum(bool(c['messages']) for c in result['cases']), 'network_calls': 0}))
