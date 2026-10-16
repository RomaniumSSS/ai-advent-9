"""Панель только чтения. Недоверенный текст выводится через textContent."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from review import Store, dumps

PAGE='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Day32 · Ревью PR</title><link rel="icon" href="data:,">
<style>body{margin:0;background:#101820;color:#dce6e8;font:16px system-ui}main{max-width:1180px;margin:auto;padding:38px}header{display:flex;justify-content:space-between;align-items:center}h1{font-size:38px;margin:8px 0}small,.muted{color:#9cabb1}button,select{background:#223640;color:#dce6e8;padding:12px;border:1px solid #42555d;border-radius:8px}article{background:#17252e;border:1px solid #344550;border-radius:14px;padding:24px;margin:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.65 ui-monospace;background:#0c161c;padding:18px;border-radius:10px;max-height:520px;overflow:auto}summary{padding:15px 0;cursor:pointer;color:#8fe0c3}.badge{display:inline-block;padding:6px 10px;background:#234a41;color:#a3f1d7;border-radius:20px}.finding{border-left:3px solid #e3b76a;padding:4px 18px;margin:24px 0}h2{font-size:21px}#empty{padding:70px;text-align:center}a{color:#8fe0c3}@media(max-width:600px){main{padding:20px 14px}header{display:block}header .badge{margin:10px 0}h1{font-size:30px}article{padding:16px}pre{padding:12px}}</style>
<main><header><div><small>AI ADVENT / DAY 32</small><h1>Ревью изменений PR</h1><p class="muted">Git → diff и файлы → FTS5 → один запрос → проверка ссылок</p></div><span class="badge">localhost · только чтение</span></header><article id="demo" hidden></article><select id="runs"></select><div id="view"></div></main>
<script>
const el=(tag,text,cls)=>{let n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
function detail(parent,title,value){let d=el('details');d.append(el('summary',title),el('pre',typeof value==='string'?value:JSON.stringify(value,null,2)));parent.append(d)}
const labels={complete:'Готово',limited:'Неполное ревью',error:'Ошибка',claimed:'Зарезервировано',budget_blocked:'Бюджет исчерпан',bug:'Ошибки',architecture:'Архитектура',recommendation:'Рекомендации',snapshot:'Снимок Git','diff/files':'Diff и файлы',FTS5:'Поиск FTS5',prompt:'Контекст',reserved:'Резерв бюджета','one model call':'Один вызов модели',validated:'Ссылки проверены','error; no retry':'Ошибка, без повтора'};const label=x=>labels[x]||x;let rows=[];async function render(){let row=rows.find(r=>r.id===document.querySelector('#runs').value),v=document.querySelector('#view');v.replaceChildren();if(!row){v.append(el('p','Пока нет отчётов. Запустите offline fixture или разрешённый watcher.'));return}let r=row.report,a=el('article');v.append(a);a.append(el('span',label(row.status),'badge'));if(!r){a.append(el('h2',row.status==='budget_blocked'?'Лимит бюджета: вызов не выполнен':'Запуск зарезервирован; автоматический повтор запрещён'));return}a.append(el('h2',r.snapshot.repository+' · PR #'+r.snapshot.number),el('p',r.provider+' · режим '+r.mode),el('p',r.stages.map(label).join(' → '),'muted'));detail(a,'Закреплённые SHA',{base:r.snapshot.base_sha,head:r.snapshot.head_sha,merge_base:r.snapshot.merge_base});a.append(el('p','Время: '+r.elapsed_seconds+' с · резерв $'+r.cost.reserved_usd.toFixed(5)+' · факт '+(r.cost.actual_usd===null?'не сообщён':'$'+r.cost.actual_usd)));if(r.provider==='offline fixture')a.append(el('p','OFFLINE FIXTURE — статический учебный ответ; качество Qwen и live-trigger не проверены.','badge'));if(r.error)a.append(el('pre',r.error));if(r.limitations.length)detail(a,'Ограничения: неполное ревью',r.limitations);a.append(el('h2','Результат'));for(let cat of ['bug','architecture','recommendation']){a.append(el('h3',label(cat)));let fs=r.findings.filter(f=>f.category===cat);if(!fs.length)a.append(el('p','Замечаний нет.','muted'));for(let f of fs){let d=el('div',undefined,'finding');d.append(el('strong',f.path+':'+f.line+' ('+f.version+')'),el('p',f.evidence),el('p',f.suggestion),el('small','Источники: '+(f.source_ids.join(', ')||'нет')));a.append(d)}}detail(a,'Diff',r.snapshot.diff);detail(a,'Изменённые файлы',r.snapshot.changed_files);detail(a,'Содержимое файлов',r.snapshot.files);detail(a,'Источники docs + code (FTS5/BM25)',r.sources);detail(a,'Стоимость и reported tokens',r.cost);let data=await fetch('/api/run/'+row.id+'/messages').then(x=>x.json());detail(a,'Точный модельный контекст',data);detail(a,'Полный отчёт',r)}
async function narrative(){let d=await fetch('/api/demo').then(x=>x.json());let n=document.querySelector('#demo');n.hidden=!d;if(d){n.replaceChildren(el('h2',d.title),el('p',d.text),el('small',d.legend));}}setInterval(narrative,1000);narrative();let lastRows='';async function refresh(){let old=document.querySelector('#runs').value;let fresh=await fetch('/api/runs').then(x=>x.json());let signature=JSON.stringify(fresh);if(signature===lastRows)return;lastRows=signature;rows=fresh;let s=document.querySelector('#runs');s.replaceChildren();for(let r of rows){let o=el('option',r.id.slice(0,8)+' · '+label(r.status)+(r.report?' · '+r.report.mode:''));o.value=r.id;s.append(o)}if(rows.some(r=>r.id===old))s.value=old;await render()}document.querySelector('#runs').onchange=render;refresh();setInterval(refresh,5000);
</script></html>'''


def serve(root, port=8072):
    root=Path(root)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path=urlparse(self.path).path
            if path=='/': body=PAGE.encode(); kind='text/html; charset=utf-8'
            elif path=='/api/demo':
                f=root/'demo.json';body=f.read_bytes() if f.exists() else b'null';kind='application/json; charset=utf-8'
            elif path=='/api/runs':
                store=Store(root); body=dumps(store.reports()).encode();store.db.close();kind='application/json; charset=utf-8'
            elif path.startswith('/api/run/') and path.endswith('/messages'):
                ident=path.split('/')[3]
                if len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident): self.send_error(404);return
                f=root/ident/'messages.json';body=f.read_bytes() if f.exists() else b'null';kind='application/json; charset=utf-8'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Day32: http://127.0.0.1:{port}',flush=True)
    server.serve_forever()
