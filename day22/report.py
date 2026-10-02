"""Локальный просмотр сохранённых результатов без сетевых запросов."""
import argparse
from html import escape
import json
from pathlib import Path


def build(prepared_path, run_dir, output):
    prepared = json.loads(Path(prepared_path).read_text())
    directory = Path(run_dir)
    ledger = json.loads((directory / 'ledger.json').read_text())
    assessment_path = directory / 'assessment.json'
    assessments = json.loads(assessment_path.read_text()) if assessment_path.exists() else {}
    cards = []
    all_found = 0
    found_total = 0
    expected_total = 0
    for case in prepared['cases']:
        expected = set(case['expected_document_ids'])
        found = {r['document_id'] for r in case['retrieved']}
        hits = expected & found
        all_found += expected <= found
        found_total += len(hits)
        expected_total += len(expected)
        answers = []
        for mode, title in [('plain', 'Без RAG'), ('rag', 'С RAG')]:
            path = directory / f"{case['id']}-{mode}.json"
            if path.exists():
                data = json.loads(path.read_text())
                response = data['response']
                answer = response['choices'][0]['message'].get('content') or '(пустой ответ)'
                usage = response.get('usage', {})
                cost = usage.get('cost')
                details = f"{data['elapsed_seconds']:.1f} с · вход {usage.get('prompt_tokens', '?')} / выход {usage.get('completion_tokens', '?')} токенов · ${cost if cost is not None else '?'}"
            else:
                entry = next((e for e in ledger['entries'] if e['id'] == case['id'] and e['mode'] == mode), {})
                answer = 'Ответ не получен: ' + entry['status'] if entry else 'Ответ ещё не сохранён'
                details = entry.get('error_type', '')
            grade = assessments.get(case['id'], {}).get(mode, {})
            note = grade.get('note', 'Разбор ещё не выполнен')
            answers.append(f'<section><h3>{title}</h3><small>{escape(details)}</small><pre>{escape(answer)}</pre><p class="note">{escape(note)}</p></section>')
        sources = ''.join(
            f'<details><summary>{escape(r["document_id"])} · cosine {r["score"]:.3f}</summary>'
            f'<small>{escape(r["chunk_id"])}</small><pre>{escape(r["text"])}</pre></details>'
            for r in case['retrieved'])
        facts = ''.join(f'<li>{escape(f)}</li>' for f in case['expected_facts'])
        cards.append(f'<article id="{case["id"]}"><h2>{case["id"]}. {escape(case["question"])}</h2>'
                     f'<p>Ожидаемые источники: {escape(", ".join(sorted(expected)))}. Найдены: {len(hits)}/{len(expected)}.</p>'
                     f'<details><summary>Ожидаемые факты</summary><ul>{facts}</ul></details>'
                     f'<div class="answers">{"".join(answers)}</div><details><summary>Переданные чанки ({len(case["retrieved"])})</summary>{sources}</details></article>')
    entries = ledger['entries']
    known_cost = sum(e['cost'] for e in entries if e['status'] == 'completed')
    summary = {'completed': sum(e['status'] == 'completed' for e in entries),
               'known_cost': known_cost, 'all_expected_sources_found_cases': all_found,
               'cases': len(prepared['cases']), 'expected_sources_found': found_total,
               'expected_sources_total': expected_total, 'network_calls': 0}
    nav = ''.join(f'<a href="#{c["id"]}">{c["id"]}</a>' for c in prepared['cases'])
    page = '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Day22 — сравнение ответов</title><style>
body{margin:0;background:#101827;color:#edf2fa;font:16px/1.6 system-ui,sans-serif}main{max-width:1300px;margin:auto;padding:28px}
h1,h2,h3{line-height:1.3}h2{font-size:22px}small{color:#a9bbd4}article{background:#182438;border:1px solid #33445f;border-radius:14px;padding:24px;margin:22px 0;scroll-margin-top:70px}
.answers{display:grid;grid-template-columns:1fr 1fr;gap:24px}.answers section{min-width:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}
summary{cursor:pointer;color:#6be2ca}details{margin:12px 0}.note{border-left:3px solid #6be2ca;padding-left:12px;color:#cbd8e9}
nav{position:sticky;top:0;background:#101827;padding:12px;display:flex;gap:16px;flex-wrap:wrap}a{color:#6be2ca}
@media(max-width:800px){.answers{grid-template-columns:1fr}main{padding:12px}article{padding:16px}}
</style><main><h1>Day22: без RAG / с RAG</h1><p>Локальный приватный отчёт. Страница не отправляет данные в сеть.</p>'''
    page += f'<p>Ответов: {summary["completed"]}/20 · известная цена: ${known_cost:.8f} · все ожидаемые источники: {all_found}/{len(prepared["cases"])} вопросов.</p>'
    page += '<p>Источник найден — ещё не значит, что ответ правильный. Разбор выполнен агентом, не является человеческой приёмкой.</p>'
    page += f'<nav>{nav}</nav>{"".join(cards)}</main></html>'
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.parent.chmod(0o700)
    output.touch(mode=0o600, exist_ok=True)
    output.chmod(0o600)
    output.write_text(page)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepared', required=True)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    build(args.prepared, args.run_dir, args.output)
