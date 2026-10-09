'use strict';
const history = [];
let busy = false;
let requestCounter = 0;
const messages = document.querySelector('#messages');
const prompt = document.querySelector('#prompt');
const status = document.querySelector('#status');
const send = document.querySelector('#send');
const newChat = document.querySelector('#new-chat');

function addMessage(role, text) {
  document.querySelector('#empty')?.remove();
  const article = document.createElement('article');
  article.className = `message ${role}`;
  const name = document.createElement('div');
  name.className = 'role'; name.textContent = role === 'user' ? 'ВЫ' : 'QWEN3';
  const body = document.createElement('div'); body.className = 'text'; body.textContent = text;
  const meta = document.createElement('div'); meta.className = 'meta';
  article.append(name, body, meta); messages.append(article);
  messages.scrollTop = messages.scrollHeight;
  return {article, body, meta};
}
function setBusy(value) {
  busy = value; send.disabled = value; newChat.disabled = value; prompt.disabled = value;
}
function metric(value, scale = 1) {
  return typeof value === 'number' ? (value / scale).toLocaleString('ru-RU', {maximumFractionDigits: 2}) : '—';
}
async function submit(event) {
  event.preventDefault();
  if (busy || !prompt.value.trim()) return;
  const question = prompt.value.trim();
  const requestId = ++requestCounter;
  const user = addMessage('user', question);
  const reply = addMessage('assistant', '');
  reply.article.classList.add('pending');
  reply.article.dataset.requestId = String(requestId);
  reply.article.dataset.state = 'streaming';
  reply.meta.textContent = 'Модель отвечает…'; status.textContent = 'Генерация ответа…';
  prompt.value = ''; setBusy(true);
  let answer = ''; let completed = false; let done = null;
  try {
    const response = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({messages:[...history, {role:'user', content:question}]})});
    if (!response.ok) {
      const error = await response.json(); throw new Error(error.error || `Ошибка HTTP ${response.status}`);
    }
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
    function consume(line) {
      if (!line.trim()) return;
      const item = JSON.parse(line);
      if (completed) throw new Error('Получены данные после завершения ответа.');
      if (item.type === 'error') throw new Error(item.error);
      if (item.type === 'delta' && typeof item.content === 'string') {
        answer += item.content; reply.body.textContent = answer; messages.scrollTop = messages.scrollHeight;
      } else if (item.type === 'done') {completed = true; done = item;}
      else throw new Error('Неверный формат потока ответа.');
    }
    try {
      while (true) {
        const {value, done: streamDone} = await reader.read();
        buffer += decoder.decode(value, {stream:!streamDone});
        const lines = buffer.split('\n'); buffer = lines.pop(); lines.forEach(consume);
        if (streamDone) break;
      }
      if (buffer.trim()) consume(buffer);
    } finally { await reader.cancel().catch(() => {}); }
    if (!completed || !answer.trim()) throw new Error('Поток оборвался до завершения ответа.');
    // AICODE-NOTE: незавершённый ответ не должен стать успешной памятью следующего запроса.
    history.push({role:'user', content:question}, {role:'assistant', content:answer});
    if (history.length > 16) history.splice(0, history.length - 16);
    reply.article.dataset.state = 'done';
    reply.article.dataset.metrics = JSON.stringify(done);
    reply.meta.textContent = `Завершено · ${done.done_reason ?? 'причина не передана'} · ${metric(done.total_duration, 1e9)} с · вход ${metric(done.prompt_eval_count)} токенов · ответ ${metric(done.eval_count)} токенов`;
    status.textContent = 'Ответ получен';
  } catch (error) {
    reply.article.classList.add('failed'); reply.article.dataset.state = 'error';
    if (!answer) reply.body.textContent = 'Ответ не получен.';
    reply.meta.textContent = `${error.message} Этот обмен не добавлен в память чата.`;
    user.article.classList.add('failed'); status.textContent = 'Ошибка — можно повторить вопрос'; prompt.value = question;
  } finally {reply.article.classList.remove('pending'); setBusy(false); prompt.focus();}
}
document.querySelector('#composer').addEventListener('submit', submit);
prompt.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {event.preventDefault(); document.querySelector('#composer').requestSubmit();}
});
newChat.addEventListener('click', () => {
  if (busy) return;
  history.length = 0; messages.replaceChildren(); prompt.value = '';
  status.textContent = 'Новый чат · память очищена'; prompt.focus();
});
async function checkHealth() {
  try {
    const data = await (await fetch('/api/health')).json();
    document.querySelector('#connection').textContent = data.message;
    document.querySelector('#connection-dot').classList.toggle('ready', data.ready);
  } catch {document.querySelector('#connection').textContent = 'Приложение недоступно';}
}
checkHealth();
