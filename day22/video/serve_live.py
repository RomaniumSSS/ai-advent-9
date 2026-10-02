"""Панель съёмки: реальный поиск на VPS, ранее полученные ответы без новых API-вызовов."""
import inspect,json,sys,tempfile,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import rag
from prepare_remote import prepare_remote
ROOT=Path(__file__).resolve().parents[1]
QUESTION=json.loads((ROOT/'questions.json').read_text())['cases'][0]['question']
PAGE='''<!doctype html><html lang="ru"><meta charset="utf-8"><title>Day22 — практическая проверка</title><style>
body{margin:0;background:#111a29;color:#eef3fa;font:20px/1.45 system-ui}main{max-width:1280px;margin:auto;padding:26px}h1{font-size:30px;margin:0 0 6px}h2{font-size:23px;margin:14px 0}p{margin:8px 0}.muted{color:#acbfd7;font-size:17px}button,input{font:inherit;border-radius:8px;padding:10px 15px;border:1px solid #526581}button{background:#28405c;color:white;cursor:pointer}button:disabled{opacity:.5}input{background:#1c2b40;color:white;width:96%;box-sizing:border-box}section{background:#1b2a3f;border:1px solid #405674;border-radius:12px;padding:18px;margin:14px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:18px/1.45 ui-monospace,monospace;margin:10px 0}.bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.good{color:#76e4cc}table{border-collapse:collapse;width:100%;font-size:17px}td,th{padding:7px;border-bottom:1px solid #405674;text-align:left}summary{cursor:pointer;color:#76e4cc}#answer{font:21px/1.55 system-ui}.hidden{display:none}
</style><main><h1>Day22 · Проверка работающего RAG</h1><p class="muted">Поиск выполняется сейчас на VPS. Ответы — из сохранённого реального прогона DeepSeek.</p>
<section><div class="bar"><button id="codebtn">Код поиска</button><button id="back" class="hidden">К вопросу</button></div><pre id="code" class="hidden"></pre><div id="controls"><h2>1. Задаём вопрос</h2><input id="question" aria-label="Вопрос" value=""><p><button id="search">Запустить поиск на VPS</button></p><p id="status" class="good">Готов к запуску · платных вызовов здесь нет</p></div></section>
<section id="searchresult" class="hidden"><h2>2. Найденные чанки · Structure SQLite · top-5</h2><p id="timing" class="muted"></p><table><thead><tr><th>№</th><th>Источник</th><th>Cosine</th></tr></thead><tbody id="rows"></tbody></table><details id="source"><summary>Открыть найденный текст assignment:7</summary><pre id="chunk"></pre></details><p class="muted">Тексты обсуждений скрыты из видеозаписи; поиск выполняется по всему индексу.</p></section>
<section id="responses" class="hidden"><h2>3. Сравниваем ответы на этот вопрос</h2><p class="muted">Чтение сохранённых ответов OpenRouter. Сейчас LLM не вызывается.</p><div class="bar"><button id="plain">Без RAG</button><button id="rag">С RAG</button><button id="summary">Итоги 10 вопросов</button></div><p id="model" class="muted"></p><div id="answer"></div></section><section id="totals" class="hidden"><h2>10 вопросов · 20 реальных ответов</h2><pre id="totaltext"></pre><p>Ограничения: нужные документы найдены в 5/10 вопросов. В Q10 ответ противоречит правильному контексту.</p></section></main>
<script>
const el=id=>document.getElementById(id);let data;
el('codebtn').onclick=async()=>{el('code').textContent=await(await fetch('/code')).text();el('code').classList.remove('hidden');el('controls').classList.add('hidden');el('back').classList.remove('hidden')};el('back').onclick=()=>{el('code').classList.add('hidden');el('controls').classList.remove('hidden');el('back').classList.add('hidden')};
el('search').onclick=async()=>{el('search').disabled=true;el('status').textContent='Выполняется: SSH → Qwen embedding → SQLite → cosine top-5…';try{const r=await fetch('/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:el('question').value})});data=await r.json();if(!r.ok)throw Error(data.error);el('timing').textContent=`Реальный запуск: ${data.seconds.toFixed(2)} с · размерность ${data.dimensions} · контекст совпал с исходным прогоном`;el('rows').replaceChildren();data.hits.forEach((x,i)=>{const tr=document.createElement('tr');[i+1,x.source,x.score.toFixed(4)].forEach(t=>{const td=document.createElement('td');td.textContent=t;tr.append(td)});el('rows').append(tr)});el('chunk').textContent=data.assignment;el('status').textContent='Поиск завершён. Найден исходный текст задания.';el('searchresult').classList.remove('hidden');el('responses').classList.remove('hidden')}catch(e){el('status').textContent='Ошибка: '+e.message}finally{el('search').disabled=false}};
for(const mode of ['plain','rag'])el(mode).onclick=()=>{const x=data.answers[mode];el('model').textContent=`${mode==='plain'?'БЕЗ RAG':'С RAG'} · ${x.model} / ${x.provider} · вход ${x.input}, выход ${x.output} токенов · $${x.cost}`;el('answer').textContent=x.text;el('responses').scrollIntoView({behavior:'smooth',block:'start'})};
el('summary').onclick=()=>{el('totaltext').textContent=data.totals;el('totals').classList.remove('hidden');el('totals').scrollIntoView({behavior:'smooth'})};
</script></html>'''
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,body,kind='application/json'):
  self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.end_headers();self.wfile.write(body.encode())
 def do_GET(self):
  if self.path=='/':return self.send(200,PAGE,'text/html')
  if self.path=='/code':return self.send(200,inspect.getsource(rag.rank)+'\n'+inspect.getsource(rag.messages),'text/plain')
  self.send(404,'{}')
 def do_POST(self):
  if self.path!='/search':return self.send(404,'{}')
  if self.headers.get('Origin')!='http://127.0.0.1:8052':return self.send(403,'{}')
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n>4096:raise ValueError('size')
   question=json.loads(self.rfile.read(n))['question']
   if question!=QUESTION:raise ValueError('Для сопоставления с записанным ответом используйте вопрос Q01')
   began=time.monotonic()
   with tempfile.TemporaryDirectory(dir=ROOT/'private') as tmp:
    inp=Path(tmp)/'questions.json';out=Path(tmp)/'prepared.json';rag.save(inp,{'cases':[{'id':'Q01','question':question}]})
    prepare_remote('crm-agent','/opt/day21/private/index-release-v1','/opt/day21/pipeline-venv/bin/python',inp,out)
    prepared=json.loads(out.read_text());case=prepared['cases'][0]
    rag.save(ROOT/'private/video-live-search.json',prepared)
   reference=json.loads((ROOT/'private/prepared.json').read_text())['cases'][0]
   assert [(r['chunk_id'],r['text']) for r in case['retrieved']]==[(r['chunk_id'],r['text']) for r in reference['retrieved']]
   answers={}
   for mode in ['plain','rag']:
    original=json.loads((ROOT/f'private/run-v1/Q01-{mode}.json').read_text());r=original['response'];rag.validate_answer(r)
    answers[mode]={'model':r['model'],'provider':r['provider'],'input':r['usage']['prompt_tokens'],'output':r['usage']['completion_tokens'],'cost':r['usage']['cost'],'text':r['choices'][0]['message']['content']}
   ledger=json.loads((ROOT/'private/run-v1/ledger.json').read_text());done=[e for e in ledger['entries'] if e['status']=='completed']
   totals='\n'.join(f'Q{i:02}: без RAG — сохранён; с RAG — сохранён' for i in range(1,11))
   totals+=f"\n\nПроверено ответов: {len(done)} / 20. Попыток: {len(ledger['entries'])}.\nИзвестная стоимость: ${sum(e['cost'] for e in done):.8f}."
   result={'seconds':time.monotonic()-began,'dimensions':len(case['query_vector']),'hits':[{'source':r['document_id'] if r['document_id'].startswith('assignment:') else 'Обсуждение (текст скрыт)','score':r['score']} for r in case['retrieved']], 'assignment':next(r['text'] for r in case['retrieved'] if r['document_id']=='assignment:7'),'answers':answers,'totals':totals}
   rag.save(ROOT/'private/video-safe-result.json',result);self.send(200,json.dumps(result,ensure_ascii=False))
  except Exception as e:self.send(500,json.dumps({'error':type(e).__name__}))
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8052),Handler).serve_forever()
