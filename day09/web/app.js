
let states={},busy=false,pending=null,steps={project:0,personal:0},scenarios={};
const $=id=>document.getElementById(id),num=x=>x==null?'?':x.toLocaleString('ru-RU');
for(const side of ['left','right']){$('panels').insertAdjacentHTML('beforeend',`<section class="panel"><div class="panel-head"><h2>${side==='left'?'Полная история':'Со сжатием'}</h2><p>${side==='left'?'Весь разговор отправляется каждый раз':'Старая часть заменяется краткой памятью'}</p><div class="metrics" id="metrics-${side}"></div><div class="details" id="details-${side}"></div></div><div class="history" id="history-${side}"></div><div class="status" id="status-${side}" role="status"></div><details class="memory" ${side==='right'?'open':''}><summary>${side==='right'?'Что сохранено в summary':'Как устроен контекст'}</summary><pre id="memory-${side}"></pre></details></section>`)}
async function api(path,data){const r=await fetch('/api/'+path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const result=await r.json();if(!r.ok)throw Error(result.error||'Ошибка сервера');return result}
function render(side,s){states[side]=s;const u=s.usage;$('metrics-'+side).innerHTML=`<div class="metric">Учтено токенов<strong>${num(u.total.tokens)}</strong></div><div class="metric">Из них на summary<strong>${num(u.summary.tokens)}</strong></div><div class="metric">Оценка входа<strong>${num(s.budget.prompt)}</strong></div>`;$('details-'+side).textContent=`Ходов: ${s.turns} · Свежих сообщений: ${s.active_messages} · Покрыто summary: ${s.covered} · Вход / выход API: ${num(u.total.prompt_tokens)} / ${num(u.total.completion_tokens)}`;const h=$('history-'+side);h.replaceChildren();if(!s.history.length){const e=document.createElement('div');e.className='empty';e.textContent='Здесь появится разговор';h.append(e)}for(const m of s.history){const e=document.createElement('div');e.className='message '+m.role;const role=document.createElement('span');role.className='role';role.textContent=m.role==='user'?'Вы':'DeepSeek';e.append(role,document.createTextNode(m.content));h.append(e)}h.scrollTop=h.scrollHeight;$('memory-'+side).textContent=side==='left'?'Системная роль + весь архив сообщений + новый вопрос.':s.summary||'Сжатия ещё не было. Оно начнётся перед следующим вопросом после накопления 16 сообщений.';const event=s.compression_event;if(event){$('status-'+side).textContent=event.error||`Сжатие: оценка контекста ${num(event.before_estimate)} → ${num(event.after_estimate)}`;$('status-'+side).classList.toggle('error',!!event.error)}compare()}
function compare(){if(!states.left||!states.right)return;const a=states.left.usage.total.tokens,b=states.right.usage.total.tokens;const matched=JSON.stringify(states.left.history.filter(m=>m.role==='user').map(m=>m.content))===JSON.stringify(states.right.history.filter(m=>m.role==='user').map(m=>m.content));$('comparison').textContent=!matched?'Истории вопросов различаются: сравнение пока не является парным.':a>0&&b!=null?`Учтённый расход: ${num(a)} / ${num(b)} токенов. ${a>=b?'Со сжатием меньше':'Со сжатием больше'} на ${Math.abs((a-b)/a*100).toFixed(1)}%. Ответы моделей могут различаться.`:'Расход появится после первых ответов.'}
function lock(v){busy=v;for(const id of ['send','reset','next','scenario'])$(id).disabled=v||((id==='next'||id==='scenario')&&!!pending);$('question').disabled=v||!!pending;$('send').textContent=pending?'Повторить только неудавшиеся':'Отправить в оба режима'}
$('chat').onsubmit = async e => {
  e.preventDefault();
  if (busy) return;
  const text = pending?.text || $('question').value.trim();
  if (!text) return;
  const sides = pending?.sides || ['left', 'right'];
  const ids = pending?.ids || Object.fromEntries(sides.map(side => [side, crypto.randomUUID()]));
  lock(true);
  const failed = [];
  const nextIds = {};
  await Promise.all(sides.map(async side => {
    const status = $('status-' + side);
    status.classList.remove('error');
    status.textContent = 'Ожидаем ответ; при необходимости создаётся summary…';
    try {
      const r = await api('chat', {panel: side, text, request_id: ids[side]});
      render(side, r.state);
      if (r.error || r.empty) {
        // Ответ получен: повтор модели — новый запрос, только для этой стороны.
        failed.push(side);
        nextIds[side] = crypto.randomUUID();
        status.textContent = r.error || 'Пустой ответ. Можно повторить эту сторону.';
        status.classList.add('error');
      } else if (r.store_error) {
        status.textContent = 'Ответ получен, но не сохранён: ' + r.store_error;
        status.classList.add('error');
      } else if (r.truncated) {
        status.textContent = 'Ответ обрезан по лимиту; сохранён как есть.';
      } else if (!r.state.compression_event) {
        status.textContent = `Ответ за ${r.elapsed} с`;
      }
    } catch (err) {
      // При обрыве HTTP тот же ID возвращает записанный результат без нового API.
      failed.push(side);
      nextIds[side] = ids[side];
      status.textContent = err.message;
      status.classList.add('error');
    }
  }));
  pending = failed.length ? {text, sides: failed, ids: nextIds} : null;
  if (!pending) $('question').value = '';
  lock(false);
};
$('reset').onclick=async()=>{if(!confirm('Удалить обе истории, summary и расход этого эксперимента?'))return;lock(true);try{for(const panel of ['left','right'])await api('reset',{panel});pending=null;steps={project:0,personal:0};for(const side of ['left','right'])$('status-'+side).textContent='';await refresh()}catch(e){alert(e.message)}finally{lock(false)}};
$('next').onclick=()=>{if(pending)return;const key=$('scenario').value,items=scenarios[key]?.questions||[];if(steps[key]>=items.length){$('step').textContent='Все вопросы подставлены';return}$('question').value=items[steps[key]++];$('step').textContent=`Вопрос ${steps[key]} / ${items.length}`};
async function refresh(){const s=await api('state');for(const side of ['left','right'])render(side,s.panels[side])}
fetch('/api/scenarios').then(r=>r.json()).then(s=>scenarios=s).catch(()=>{});refresh().catch(e=>$('comparison').textContent=e.message);

api('results').then(rows => {
  const box = $('saved-results');
  box.replaceChildren();
  if (!rows.length) { box.textContent = 'Завершённых сравнений пока нет.'; return; }
  const table = document.createElement('table');
  const addRow = (values, header = false) => {
    const tr = document.createElement('tr');
    for (const value of values) {
      const td = document.createElement(header ? 'th' : 'td');
      td.textContent = value; tr.append(td);
    }
    table.append(tr);
  };
  addRow(['Сценарий', 'Прогон', 'Полная история', 'Со сжатием', 'Экономия токенов', 'Попыток без usage'], true);
  for (const row of rows) addRow([row.scenario === 'project' ? 'Проект' : 'Беседа', row.repeat,
    num(row.full_tokens), num(row.compressed_tokens), row.savings_percent.toFixed(1) + '%', row.failed_attempts_without_usage]);
  box.append(table);
  const note = document.createElement('p'); note.className = 'table-note';
  note.textContent = 'Токены успешных API-ответов вместе с summary. Ошибки без usage отмечены отдельно. Отрицательная экономия означает больший расход.';
  box.append(note);
}).catch(e => $('saved-results').textContent = e.message);
