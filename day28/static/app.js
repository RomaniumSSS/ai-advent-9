const $ = s => document.querySelector(s);
function node(tag,text,cls){const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;return el;}
async function api(path,options){const r=await fetch(path,options);const d=await r.json();if(!r.ok)throw Error(d.error||r.status);return d;}
function show(r){$('#result').dataset.state=r.status;$('#result').dataset.requestId=r.request_id;$('#result').dataset.metrics=JSON.stringify(r.metrics||null);
 $('#request').textContent=`run ${r.run_id} · request ${r.request_id}`;
 const names={running:'Выполняется локальный запрос…',done:'Ответ получен · источники проверены',unknown:'Сведений недостаточно',error:'Запрос завершился ошибкой'};
 $('#status').textContent=names[r.status]||r.status;if(r.status==='running')return;
 $('#answer').textContent=r.answer?.answer||`${r.error?.phase}: ${r.error?.message}`;$('#sources').replaceChildren();$('#metrics').replaceChildren();
 for(const [key,title] of Object.entries({embedding:'Embedding',retrieval:'Поиск',generation:'Генерация',total:'Всего'})){
  const seconds=r.times?.[key];$('#metrics').append(node('span',`${title}: ${seconds==null?'не измерено':seconds.toFixed(2)+' с'}`));}
 $('#metrics').append(node('span',`Вход / выход: ${r.metrics?.prompt_eval_count??'—'} / ${r.metrics?.eval_count??'—'} токенов`));
 $('#metrics').append(node('span','Смысловая обоснованность: требует оценки'));
 if(r.citation_mode==='source_references_original_text'){
  if(r.answer?.sources?.length>0)$('#metrics').append(node('span','Модель выбрала источники; приложение показывает их оригинальный текст'));
  else{
   $('#metrics').append(node('span','Подтверждающих источников нет'));
   if(r.selected?.length>0)$('#metrics').append(node('span','Поиск нашёл контекст; модель не использовала его как подтверждение'));
  }
 }
 for(const source of r.answer?.sources||[]){const c=r.selected.find(c=>c.chunk_id===source.chunk_id);const div=node('div','', 'source');div.id='chunk-'+c.chunk_id;
  const link=node('a',`${c.source_ref||c.chunk_id.slice(0,12)} · ${source.source}`);link.href='#'+div.id;div.append(link);
  const details=node('details','');details.append(node('summary','Показать исходный фрагмент'));
  for(const q of r.answer.quotes.filter(q=>q.chunk_id===c.chunk_id))details.append(node('blockquote',q.text));
  div.append(details);$('#sources').append(div);}
 // Найденное поиском отделено от источников, которые модель выбрала для ответа.
 const uncited=(r.selected||[]).filter(c=>!(r.answer?.sources||[]).some(s=>s.chunk_id===c.chunk_id));
 if(uncited.length>0)$('#sources').append(node('h3','Найденный поиском контекст'));
 for(const c of uncited){const details=node('details','', 'source');details.append(node('summary',`${c.document_id} · найден поиском, не процитирован моделью`),node('pre',c.text));$('#sources').append(details);}
}
$('#form').addEventListener('submit',async event=>{event.preventDefault();$('#send').disabled=true;$('#answer').textContent='Ожидаем настоящий ответ модели…';$('#metrics').replaceChildren();$('#sources').replaceChildren();
 try{let r=await api('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('#question').value})});show(r);const id=r.request_id;
  while(r.status==='running'){await new Promise(resolve=>setTimeout(resolve,700));r=await api('/api/requests/'+id);show(r);}}
 catch(e){$('#result').dataset.state='error';$('#status').textContent='Ошибка: '+e.message;}finally{$('#send').disabled=false;}});
api('/api/state').then(s=>{$('#identity').textContent=`${s.model} · ${s.embedding_model} · индекс ${s.index.generation?.slice(0,12)||'fixture'} · окно ${s.generation_options.num_ctx}. Identity моделей проверяется при запросе.`;}).catch(e=>{$('#identity').textContent=e.message;});
function showSummary(s){
 const summary=$('#summary');summary.replaceChildren();
 const meta=node('div','','evaluation-meta');
 meta.append(node('p',`E2E · отдельный run ${s.e2e_run_id||'не подтверждён'}`),
  node('p',`Исторический replay · отдельный run ${s.replay_run_id||'не подтверждён'}`));
 const statuses=node('div','','release-statuses');
 statuses.append(node('span',s.code_checked===true?'Код проверен':s.code_checked===false?'Код требует проверки':'Код: проверка не подтверждена','badge'),
  node('span',s.video_status==='checking'?'Видео проверяется':s.video_status==='verified'?'Видео проверено':'Видео: проверка не подтверждена','badge'),
  node('span',s.published===false?'Не опубликовано':s.published===true?'Опубликовано':'Публикация: статус неизвестен','badge'));
 summary.append(meta,statuses,node('div',s.message||'Подтверждённая сводка пока недоступна.','evaluation-message'));
 $('#preparation').textContent=s.preparation?.index_transferred===true && s.preparation?.vectors_recomputed===false?
  'Индекс перенесён без пересчёта векторов. Снимок и модели получены на этапе подготовки.':
  'Происхождение индекса: подтверждение пока недоступно.';
}
api('/api/summary').then(showSummary).catch(e=>{$('#summary').textContent=e.message;$('#preparation').textContent='Происхождение индекса: подтверждение пока недоступно.';});
