"""Приватный HTML сравнения; оценку ответов читает, но не придумывает."""
import argparse
import html
import json
import os
from pathlib import Path


def esc(value):
    return html.escape(str(value),quote=True)


def read(path):
    return json.loads(Path(path).read_text())


def private_output(path, private_root=None):
    path=Path(path).resolve()
    root=Path(private_root).resolve() if private_root is not None else (Path(__file__).resolve().parent/'private')
    if not path.is_relative_to(root):
        raise ValueError('output_must_be_private')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    root.chmod(0o700)
    parent=path.parent
    parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    parent.chmod(0o700)
    return path


def response_content(raw):
    if 'http_status' in raw:
        raw=json.loads(raw['body'])
    elif 'response' in raw:
        raw=raw['response']
    content=raw['choices'][0]['message']['content']
    if not isinstance(content,str):
        raise ValueError('invalid_response_content')
    return {'text':content,'model':raw.get('model'),'provider':raw.get('provider'),'usage':raw.get('usage',{})}


def inside(directory,filename):
    root=Path(directory).resolve();path=(root/filename).resolve()
    if not path.is_relative_to(root):raise ValueError('response_file_outside_ledger')
    return path


def load_answers(ledger_dir,baseline_dir,answer_ids):
    ledger=read(Path(ledger_dir)/'ledger.json')
    answers={}
    for entry in ledger['entries']:
        if entry.get('status')!='completed' or entry['id'] not in answer_ids or entry['mode'] not in ('A','E'):
            continue
        path=inside(ledger_dir,entry['response_file'])
        key=(entry['id'],entry['mode'])
        if key in answers:raise ValueError('duplicate_completed_answer')
        answers[key]={**response_content(read(path)),'provenance':'Новый Day23 ответ','charged':entry.get('charged',entry.get('reserve'))}
    for ident in answer_ids:
        if ident in {f'Q{i:02}' for i in range(1,11)}:
            if (ident,'A') in answers:raise ValueError('old_baseline_and_new_A_conflict')
            path=inside(baseline_dir,ident+'-rag.json')
            if path.exists():
                answers[(ident,'A')]={**response_content(read(path)),'provenance':'Сохранённый Day22 baseline; получен раньше'}
    return ledger,answers


def result_rows(label,results):
    rows=[]
    for mode,result in results.get('results',{}).items():
        for category,summary in result.get('summary',{}).items():
            values=[label,mode,category,summary.get('questions','—'),summary.get('answerable','—'),
                    summary.get('candidate_all_anchors','—'),summary.get('all_anchors','—'),
                    summary.get('all_documents','—'),summary.get('empty','—'),summary.get('context_bytes','—')]
            rows.append('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in values)+'</tr>')
    return rows


def trace_for(case,development,holdout,mode):
    results=(development if case['split']=='development' else holdout).get('results',{})
    name='E035' if mode=='E' and case['split']=='development' else mode
    return results.get(name,{}).get('traces',{}).get(case['id'])


def assessment_html(value,facts):
    if value is None:return '<p class="muted">Ручная оценка не внесена.</p>'
    marks=value.get('facts',[])
    if len(marks)!=len(facts) or any(mark not in ('full','partial','missing','contradicted') for mark in marks):
        raise ValueError('invalid_manual_fact_assessment')
    names={'full':'полностью','partial':'частично','missing':'нет','contradicted':'противоречит'}
    rows=''.join('<li>'+esc(fact)+' — <b>'+esc(names[mark])+'</b></li>' for fact,mark in zip(facts,marks))
    return '<h4>Ручная оценка фактов</h4><ul>'+rows+'</ul><p>Ошибка: '+esc(value.get('error','не указана'))+'</p><p>'+esc(value.get('notes',''))+'</p>'


def retrieval_html(trace):
    if trace is None:return '<p class="muted">Трасса поиска для этого режима отсутствует.</p>'
    selected=trace.get('selected',[])
    sources=list(dict.fromkeys(c['document_id'] for c in selected))
    counts=trace.get('counts',{})
    text='<p>Источники текущего поиска: '+esc(', '.join(sources) or 'пусто')+'</p>'
    text+='<p>Кандидаты: '+esc(counts.get('candidates','—'))+'; выбрано: '+esc(len(selected))+'; контекст: '+esc(trace.get('context_bytes','—'))+' байт.</p>'
    rows=[]
    for c in trace.get('candidates',[]):
        rows.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (c['document_id'],c['chunk_id'],c.get('cosine','—'),c.get('mixed_score','—'),c.get('exact_reason') or 'векторный поиск'))+'</tr>')
    return text+'<details><summary>Кандидаты и scores</summary><table><tr><th>Источник</th><th>Чанк</th><th>Cosine</th><th>Mixed</th><th>Правило</th></tr>'+''.join(rows)+'</table></details>'


def render(benchmark,development,holdout,ledger,answers,assessment=None):
    cases={c['id']:c for c in benchmark['cases']}
    ids=benchmark['answer_case_ids']
    if len(set(ids))!=len(ids) or any(ident not in cases for ident in ids):raise ValueError('invalid_answer_ids')
    assessments={c['id']:c for c in (assessment or {}).get('cases',[])}
    body=['<h1>Day23 · приватное сравнение</h1><p class="warning">Эталоны, обсуждения и ответы содержат приватные сведения. Не публиковать этот HTML.</p>',
          '<p>Метрики покрытия фрагментов показывают наличие опоры в контексте; это не precision и не автоматическая оценка правильности ответа. Отсутствующие данные обозначены явно.</p>',
          '<h2>Поиск · настройка и отложенная проверка</h2><div class="scroll"><table><tr><th>Часть</th><th>Режим</th><th>Категория</th><th>Вопросов</th><th>Answerable</th><th>Все опоры в кандидатах</th><th>Все опоры в контексте</th><th>Все документы в контексте</th><th>Пусто</th><th>Байт суммарно</th></tr>',
          *result_rows('Development',development),*result_rows('Holdout',holdout),'</table></div>',
          '<h2>Ответы · '+esc(len(ids))+' пар A/E</h2><p>Старые десять A — сохранённый Day22 baseline, поэтому сравнение не одновременное. Источники ниже относятся к текущей трассе поиска; они не восстанавливают контекст старого ответа. Оценки внесены отдельно проверяющим.</p>']
    for ident in ids:
        case=cases[ident];facts=case['expected_facts'];manual=assessments.get(ident,{})
        body.append('<section><h3>'+esc(ident)+' · '+esc(case['question'])+'</h3><p class="muted">'+esc(case['category'])+' · '+esc(case['split'])+'</p><h4>Ожидаемые факты</h4><ul>'+''.join('<li>'+esc(f)+'</li>' for f in facts)+'</ul><div class="pair">')
        for mode in ('A','E'):
            answer=answers.get((ident,mode));body.append('<article><h3>'+mode+'</h3>')
            if answer is None:body.append('<p class="missing">Ответ отсутствует: успешный завершённый вызов не найден.</p>')
            else:
                body.append('<p class="muted">'+esc(answer['provenance'])+' · '+esc(answer['model'])+' / '+esc(answer['provider'])+'</p><pre>'+esc(answer['text'])+'</pre>')
                usage=answer['usage'];body.append('<p>Вход/выход токенов: '+esc(usage.get('prompt_tokens','неизвестно'))+' / '+esc(usage.get('completion_tokens','неизвестно'))+'; usage.cost: '+esc(usage.get('cost','неизвестно'))+'</p>')
            body.append(assessment_html(manual.get(mode),facts));body.append(retrieval_html(trace_for(case,development,holdout,mode)));body.append('</article>')
        body.append('</div></section>')
    entries=ledger.get('entries',[])
    charged=sum(e.get('charged',e.get('reserve',0)) for e in entries)
    body.append('<h2>Общий бюджет Day23</h2><p>Попыток: '+esc(len(entries))+'; учтено с резервами: $'+esc(f'{charged:.8f}')+'; cap: $'+esc(ledger.get('budget','неизвестно'))+'. Включает записи видео и повторов, если они есть в этом едином журнале.</p>')
    return '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Day23 · private comparison</title><style>body{font:16px/1.5 system-ui;background:#101827;color:#edf2fa;margin:30px}h1,h2,h3{line-height:1.2}section,article{background:#1b293d;padding:18px;border-radius:10px;margin:15px 0}article{background:#24344a;margin:0;min-width:0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}.warning,.missing{color:#ffce83}.muted{color:#b4c3d7}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #52617a;text-align:left;padding:7px;overflow-wrap:anywhere}.scroll{overflow:auto}summary{cursor:pointer}@media(max-width:850px){.pair{grid-template-columns:1fr}}</style><main>'''+''.join(body)+'</main></html>'


def main():
    parser=argparse.ArgumentParser()
    for name in ('benchmark','development','holdout','ledger-dir','baseline-dir','output'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--assessment');args=parser.parse_args()
    output=private_output(args.output)
    benchmark=read(args.benchmark);ledger,answers=load_answers(args.ledger_dir,args.baseline_dir,benchmark['answer_case_ids'])
    document=render(benchmark,read(args.development),read(args.holdout),ledger,answers,read(args.assessment) if args.assessment else None)
    temporary=output.with_suffix(output.suffix+'.tmp')
    with open(temporary,'w',encoding='utf-8',opener=lambda path,flags:os.open(path,flags,0o600)) as stream:
        stream.write(document);stream.flush();os.fsync(stream.fileno())
    temporary.chmod(0o600);os.replace(temporary,output);output.chmod(0o600)
    print('private report written; no automatic grading')

if __name__=='__main__':main()
