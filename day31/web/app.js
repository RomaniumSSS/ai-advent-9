'use strict';
const $ = id => document.getElementById(id);
let config;
const node = (tag, text, className) => {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
};
async function init() {
  const response = await fetch('/api/config');
  if (!response.ok) throw new Error('Не удалось получить конфигурацию');
  config = await response.json();
  $('mode').textContent = config.live ? `${config.model} · ${config.provider}` : 'Офлайн · без генерации LLM';
  $('root').textContent = config.git_root;
}
function render(value) {
  $('answer').textContent = value.text;
  $('answer').classList.remove('muted');
  $('status').textContent = {ok: 'Ответ получен', unknown: 'Нет данных', error: 'Ошибка'}[value.status];
  $('status').className = `tag ${value.status}`;
  if (value.git_context) {
    const git = value.git_context;
    $('branch').textContent = `Ветка: ${git.branch || 'detached HEAD'} · HEAD ${git.head}`;
  } else $('branch').textContent = 'Git-контекст не получен';
  const usage = value.usage;
  const cost = usage && usage.cost_usd !== null ? `$${usage.cost_usd}` : 'неизвестна';
  $('metrics').textContent = `${value.elapsed_seconds.toFixed(2)} с · ${value.model} / ${value.provider} · ${usage ? `токены ${usage.prompt_tokens ?? '?'} → ${usage.completion_tokens ?? '?'} · стоимость ${cost}` : 'usage отсутствует'}`;
  $('run').textContent = `Trace: ${value.trace_id}`;
  $('sources').replaceChildren();
  $('citations').replaceChildren();
  $('source-count').textContent = `${value.sources.length} фрагментов`;
  for (const source of value.sources) {
    const used = value.source_ids.includes(source.id);
    const details = node('details', undefined, used ? 'used' : '');
    details.id = `source-${source.id}`;
    details.append(node('summary', `${source.path}:${source.start_line}–${source.end_line} · ${source.section}${used ? ' · ссылка в ответе' : ' · найдено поиском'}`));
    const lines = source.text.split('\n').map((line, index) => `${source.start_line + index}  ${line}`).join('\n');
    details.append(node('pre', lines));
    details.append(node('div', `ID ${source.id} · SHA256 ${source.sha256}`, 'source-meta'));
    $('sources').append(details);
    if (used) {
      const link = node('a', `${source.path}:${source.start_line}–${source.end_line}`);
      link.href = `#${details.id}`;
      link.addEventListener('click', () => { details.open = true; });
      $('citations').append(link);
    }
  }
  if (!value.sources.length) $('sources').append(node('p', 'Поиск не нашёл подходящих фрагментов.', 'muted small'));
  $('stages').replaceChildren();
  const labels = {search: 'Поиск по документации', mcp: 'Git через MCP', model: 'Ответ модели'};
  value.stages.forEach((stage, index) => {
    const row = node('div', undefined, `stage ${stage.status}`);
    row.append(node('span', String(index + 1), 'number'));
    const body = node('div');
    body.append(node('h3', labels[stage.name] || stage.name));
    const state = {ok: 'Выполнено', error: 'Ошибка', skipped: 'Пропущено'}[stage.status];
    body.append(node('p', `${state}${stage.seconds !== undefined ? ` · ${stage.seconds.toFixed(2)} с` : ''}${stage.count !== undefined ? ` · найдено ${stage.count}` : ''}`));
    if (stage.reason) body.append(node('p', stage.reason));
    const details = node('details');
    details.append(node('summary', 'Фактические данные'));
    details.append(node('pre', JSON.stringify(stage, null, 2)));
    body.append(details); row.append(body); $('stages').append(row);
  });
}
$('form').addEventListener('submit', async event => {
  event.preventDefault();
  const question = $('question').value.trim();
  if (!question || !config) return;
  $('send').disabled = true; $('send').textContent = 'Выполняется запрос…';
  $('response').setAttribute('aria-busy', 'true');
  $('status').textContent = 'Выполняется'; $('status').className = 'tag';
  $('answer').textContent = 'Поиск документов → настоящий MCP → один ответ. Ожидаем результат этого запроса.';
  $('sources').replaceChildren(); $('citations').replaceChildren(); $('stages').replaceChildren();
  $('source-count').textContent = '…'; $('metrics').textContent = ''; $('run').textContent = 'Новый запуск…';
  try {
    const response = await fetch('/api/answer', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-DevHelper-Token': config.token}, body: JSON.stringify({question})});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'Ошибка HTTP');
    render(value);
  } catch (error) {
    $('answer').textContent = error.message || 'Сетевая ошибка';
    $('status').textContent = 'Ошибка'; $('status').className = 'tag error';
    $('branch').textContent = 'Результат текущего запроса не получен';
  } finally {
    $('send').disabled = false; $('send').textContent = 'Спросить помощника ↗';
    $('response').setAttribute('aria-busy', 'false');
  }
});
document.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => {
  $('question').value = button.dataset.question;
  $('question').focus();
}));
init().catch(error => { $('mode').textContent = error.message; $('send').disabled = true; });
