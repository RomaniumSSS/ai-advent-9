"""Офлайн: границы отказа, поддельные доказательства и полный цикл на подставном HTTP."""
import copy
import json
import math
from pathlib import Path
import tempfile
from answers import check_answer, refusal
from common import MODEL
from evaluate import evaluate
from prepare_saved import prepare
from report import collect, render
from retrieval import Config, retrieve


def chunk(cosine, text='Проверенный фрагмент', cid='c1'):
    return {'source': 'assignment', 'document_id': 'd21', 'day': 21,
            'chunk_id': cid, 'text': text, 'vector': [cosine, math.sqrt(1-cosine*cosine)]}


def main():
    question = 'Какие требования Day21?'
    for score, expected in ((.349, 0), (.35, 1), (.351, 1)):
        t = retrieve([chunk(score/.8)], question, [1., 0.], Config())
        assert len(t['selected']) == expected, (score, t)
        assert t['metadata_rule']['assignment_intent']
    empty = retrieve([], question, [1., 0.], Config())
    assert empty['empty'] and empty['selected'] == []
    data = {'identity': {}, 'chunks': [chunk(.8)], 'cases': [
        {'id': 'Q1', 'question': question, 'query_vectors': {'original': [1., 0.]}}]}
    prepared = prepare(data, ['Q1'])
    assert '"source":"assignment"' in prepared['cases'][0]['traces']['rag']['context']
    good = {'answer': 'Проверенный фрагмент', 'sources': [{'source': 'assignment', 'chunk_id': 'c1'}],
            'quotes': [{'chunk_id': 'c1', 'text': 'Проверенный фрагмент'}]}
    selected = prepared['cases'][0]['traces']['rag']['selected']
    assert check_answer(json.dumps(good), selected)['valid']
    for change, expected in (
        (lambda a: a['sources'][0].update(source='discussion'), 'source_not_in_context'),
        (lambda a: a['quotes'][0].update(text='Придуманная цитата'), 'quote_not_in_context'),
        (lambda a: a['sources'][0].update(chunk_id='unknown'), 'source_not_in_context'),
        (lambda a: a.update(quotes=[]), 'missing_quotes'),
        (lambda a: a.update(answer=''), 'empty_answer'),
    ):
        bad = copy.deepcopy(good); change(bad)
        assert expected in check_answer(json.dumps(bad), selected)['errors']
    assert not check_answer('not json', selected)['valid']
    contradiction = copy.deepcopy(good); contradiction['answer'] = 'Неподтверждённый вывод'
    check = check_answer(json.dumps(contradiction), selected)
    assert check['valid'] and check['semantic_match'] is None
    with tempfile.TemporaryDirectory() as d:
        calls = []
        def fake(url, body, key):
            calls.append(body)
            return {'model': MODEL, 'provider': 'DeepInfra', 'usage': {'cost': .0001},
                    'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(good)}}]}
        pricing = {'prompt': .14/1e6, 'completion': .42/1e6}
        evaluate(prepared, d, 'fake', budget=.1, pricing=pricing, dispatch_fn=fake)
        evaluate(prepared, d, 'fake', budget=.1, pricing=pricing, dispatch_fn=fake)
        report = collect(prepared, d)
        assert len(calls) == 1 and report['rows'][0]['status'] == 'valid_citations'
        assert report['rows'][0]['semantic_match'] is None
        data['chunks'] = []
        local = prepare(data, ['Q1'])
        assert not local['cases'][0]['messages']
        result = collect(local, d)['rows'][0]
        assert result['status'] == 'no_context' and result['answer'] == refusal()
        assert 'Уточни' in result['answer']['answer']
        assert result['answer']['sources'] == result['answer']['quotes'] == []
        result['question'] = '<script>alert(1)</script>'
        assert '<script>' not in render({'rows': [result], 'notice': ''})
    print('ok: threshold boundaries + metadata, empty context, citations, semantics limitation, mock HTTP/resume, report escaping')


if __name__ == '__main__':
    main()
