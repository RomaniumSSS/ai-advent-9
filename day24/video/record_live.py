"""Живой вызов на публичном подмножестве одобренного контекста, без HTTP-сервера."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MODEL, key_from_env, messages, packed, save
from answers import check_answer, refusal
from evaluate import evaluate
from retrieval import Config, retrieve
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
HTML = r'''<!doctype html><html lang="ru"><meta charset="utf-8"><title>Day24</title><style>
body{background:#111927;color:#edf3fa;font:22px system-ui;margin:40px auto;max-width:1260px}h1{font-size:36px}h2{font-size:24px;color:#8edbd0}section{background:#1c293b;padding:22px;margin:16px 0;border-radius:14px}button{background:#8edbd0;color:#101b27;padding:12px;border:0;border-radius:8px;font-size:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:19px system-ui}.muted{color:#b4c2d8;font-size:17px}#source{max-height:180px;overflow:auto}</style>
<h1>Day24 · Ответ → источник → цитата</h1><p class="muted">Практический запуск · без озвучки · DeepSeek / DeepInfra</p>
<section><h2 id="question"></h2><p class="muted">Публичная демонстрация: только условие задания из найденных чанков. Полный поиск проверен отдельно на 10 вопросах.</p><pre id="source"></pre><button id="run">Получить новый ответ</button><p id="status">Готов к запуску</p></section>
<section id="result" hidden><h2>Ответ и доказательства</h2><pre id="answer"></pre><pre id="quote"></pre><p class="muted" id="refs"></p><p id="checks"></p></section>
<section id="unknown" hidden><h2>Режим «не знаю»</h2><p id="nquestion"></p><p class="muted">Повтор поиска на сохранённом векторе запроса, без облачного вызова</p><pre id="nresult"></pre></section>
<script>run.onclick=async()=>{run.disabled=true;statusText=document.getElementById('status');statusText.textContent='Выполняется реальный облачный запрос…';try{const r=await window.generate();answer.textContent=r.answer;quote.textContent='Цитата: «'+r.quotes.map(q=>q.text).join('»\n«')+'»';refs.textContent=r.sources.map(s=>s.source+' / '+s.chunk_id).join('\n');checks.textContent='Проверка приложения: источники и цитаты подлинные. Смысл проверяется отдельно.';result.hidden=false;statusText.textContent='Новый ответ получен. Общий расход Day24: $'+r.cost.toFixed(6)}catch(e){statusText.textContent='Ошибка запуска';throw e}};</script></html>'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--operate', action='store_true')
    p.add_argument('--env-file', required=True)
    a = p.parse_args()
    if not a.operate:
        raise SystemExit('Нужен --operate: запись выполняет платный вызов в общем бюджете.')
    prepared = json.loads((ROOT/'private/prepared.json').read_text())
    case = copy.deepcopy(next(c for c in prepared['cases'] if c['id'] == 'Q04'))
    selected = [c for c in case['traces']['rag']['selected'] if c['source'] == 'assignment']
    if not selected:
        raise ValueError('public_context_missing')
    context = '\n\n'.join(packed({'source':c['source'], 'chunk_id':c['chunk_id'], 'text':c['text']}).decode() for c in selected)
    job = {'model':MODEL, 'cases':[{'id':'VIDEO01', 'messages':{'rag':messages(case['question'],context)}}]}
    save(ROOT/'private/video-prepared.json', job)
    ledger_path=ROOT/'private/run-v1/ledger.json'
    if ledger_path.exists() and any(e['id']=='VIDEO01' for e in json.loads(ledger_path.read_text())['entries']):
        raise ValueError('video_already_attempted_use_saved_recording_or_review_resume')
    frames = ROOT/'private/video-frames'; frames.mkdir(parents=True, exist_ok=True, mode=0o700)
    def generate():
        ledger = evaluate(job, ROOT/'private/run-v1', key_from_env(a.env_file), budget=.10, max_retries=2)
        entry = next(e for e in reversed(ledger['entries']) if e['id']=='VIDEO01' and e['status']=='completed')
        raw = json.loads((ROOT/'private/run-v1'/entry['response_file']).read_text())
        content = json.loads(raw['body'])['choices'][0]['message']['content']
        checked = check_answer(content, selected)
        if not checked['valid']:
            raise ValueError('video_answer_invalid')
        save(ROOT/'private/video-checked.json', checked)
        return dict(checked['answer'], cost=sum(e['charged'] for e in ledger['entries']))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width':1440,'height':1100}, record_video_dir=str(frames), record_video_size={'width':1440,'height':1100})
        page = ctx.new_page(); page.expose_function('generate', generate); page.set_content(HTML)
        page.locator('#question').text_content()
        page.evaluate('(q)=>document.getElementById("question").textContent=q', case['question'])
        page.evaluate('(t)=>document.getElementById("source").textContent=t', selected[0]['text'])
        page.wait_for_timeout(4500); page.locator('#run').click()
        page.wait_for_function("document.getElementById('status').textContent.includes('Новый ответ получен') || document.getElementById('status').textContent.includes('Ошибка')", timeout=300000)
        if 'Ошибка' in page.locator('#status').inner_text():
            raise ValueError('video_generation_failed')
        page.locator('#result').scroll_into_view_if_needed(); page.wait_for_timeout(9500)
        page.screenshot(path=str(frames/'answer.png'))
        source = json.loads((ROOT/'private/refusal-preparation/prepared.json').read_text())
        n = source['cases'][0]
        trace = retrieve(source['chunks'],n['question'],n['query_vectors']['original'],Config())
        if not trace['empty']:
            raise ValueError('refusal_changed')
        result = refusal()
        page.evaluate('(v)=>{unknown.hidden=false;nquestion.textContent=v.q;nresult.textContent=v.text}',
                      {'q':n['question'],'text':f"Лучшая оценка: {max(c['mixed_score'] for c in trace['candidates']):.3f} < 0.35\n"+result['answer']+'\nИсточники: [] · Цитаты: [] · Облачных вызовов: 0'})
        page.locator('#unknown').scroll_into_view_if_needed(); page.wait_for_timeout(8500)
        page.screenshot(path=str(frames/'refusal.png'))
        video=page.video;ctx.close();video.save_as(str(frames/'live.webm'));browser.close()
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(frames/'live.webm'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(ROOT/'video/Day24-practical.mp4')],check=True)
    print('recorded: real cloud answer + local refusal; review before publication')


if __name__ == '__main__':
    main()
