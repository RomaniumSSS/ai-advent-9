"""Приватный отчёт: автоматическая подлинность отдельно от оценки смысла."""
import argparse
import html
import json
from pathlib import Path
from answers import check_answer
from common import save


def collect(prepared, run_dir):
    directory = Path(run_dir)
    ledger = json.loads((directory/'ledger.json').read_text()) if (directory/'ledger.json').exists() else {'entries': []}
    rows = []
    for case in prepared['cases']:
        trace = case['traces']['rag']
        row = {'id': case['id'], 'question': case['question'], 'selected': trace['selected'],
               'semantic_match': None, 'refusal_correct': None}
        if trace['empty']:
            row.update(status='no_context', answer=case['local_result'], sources_present=False,
                       quotes_present=False, expected_empty_evidence=True, refusal_correct=True)
        else:
            matches = [e for e in ledger['entries'] if e['id'] == case['id'] and e['mode'] == 'rag' and e['status'] == 'completed']
            if not matches:
                row.update(status='pending')
            else:
                raw = json.loads((directory/matches[-1]['response_file']).read_text())
                body = json.loads(raw['body']) if 'body' in raw else raw
                check = check_answer(body['choices'][0]['message']['content'], trace['selected'])
                row.update(check)
                row.update(status='valid_citations' if check['valid'] else 'invalid_answer',
                           raw_content=body['choices'][0]['message']['content'])
        rows.append(row)
    return {'rows': rows, 'charged': sum(e['charged'] for e in ledger['entries']),
            'notice': 'Подлинность цитат не доказывает смысл; semantic_match заполняется после разбора.'}


def render(report):
    esc = lambda v: html.escape(str(v))
    cards = []
    for row in report['rows']:
        cards.append('<article><h2>'+esc(row['id'])+' — '+esc(row['question'])+'</h2><pre>'+
                     esc(json.dumps(row, ensure_ascii=False, indent=2))+'</pre></article>')
    return '<!doctype html><meta charset="utf-8"><title>Day24 — приватная проверка</title><style>body{font:16px system-ui;max-width:1000px;margin:30px auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #aaa;padding:15px}</style><h1>Day24: источники и цитаты</h1><p>'+esc(report['notice'])+'</p>'+''.join(cards)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--prepared', required=True)
    p.add_argument('--run-dir', required=True)
    p.add_argument('--assessment', help='Отдельная смысловая оценка по источникам')
    p.add_argument('--output', required=True, help='JSON; HTML сохраняется рядом, оба файла приватные')
    a = p.parse_args()
    result = collect(json.loads(Path(a.prepared).read_text()), a.run_dir)
    if a.assessment:
        assessment = json.loads(Path(a.assessment).read_text())
        grades = {c['id']: c for c in assessment['cases']}
        if len(grades) != len(assessment['cases']) or set(grades) != {r['id'] for r in result['rows']}:
            raise ValueError('assessment_cases_mismatch')
        for row in result['rows']:
            grade = grades[row['id']]
            row.update({k: grade[k] for k in ('semantic_match', 'answers_question', 'notes')})
        result['semantic_reviewer'] = assessment['reviewer']
        result['human_acceptance'] = assessment.get('human_acceptance', False)
    save(a.output, result)
    dest = Path(a.output).with_suffix('.html')
    import os
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(render(result))
    dest.chmod(0o600)
    print(json.dumps({'rows': len(result['rows']), 'charged': result['charged']}))
