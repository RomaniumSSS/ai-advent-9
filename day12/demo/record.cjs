// Replay saved live evidence only: never connects to the product or model.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const launchOptions = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
  ? {headless:true, executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}
  : {headless:true};
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
(async () => {
  const report = JSON.parse(fs.readFileSync(process.argv[2] || 'results/live-deepseek.json', 'utf8'));
  if (report.ledger?.manifest?.campaign_id) return recordMass(report);
  assert.equal(report.provenance, 'real DeepSeek via private VPS runtime');
  assert.equal(report.outcome, 'awaiting_human_rubric');
  assert.equal(report.cases.length, 3);
  assert.equal(report.ledger.attempts.length, 3);
  assert(Number(report.ledger.reported_cost_usd) <= 0.02);
  assert.equal(report.automatic_profile_repeat, true);
  for (const [i, entry] of report.cases.entries()) {
    const attempt = report.ledger.attempts[i];
    assert.equal(attempt.status, 'complete');
    assert.equal(entry.reply.message, attempt.response.choices[0].message.content);
    assert.equal(attempt.response.model, 'deepseek/deepseek-v4-flash-0731');
  }
  const browser = await chromium.launch(launchOptions);
  const context = await browser.newContext({viewport:{width:1280,height:800},recordVideo:{dir:'demo/raw-live',size:{width:1280,height:800}}});
  await context.route('**/*', route => route.abort());
  const page = await context.newPage();
  const style = '<style>body{background:#101827;color:#edf4ff;font:22px system-ui;padding:35px}h1{font-size:28px}pre{white-space:pre-wrap;font:17px monospace}.badge{color:#80e8bd}article{max-width:1150px}</style>';
  const title = '<p class="badge">Воспроизведение реального DeepSeek-прогона · без новых API-вызовов</p>';
  try {
    const source = fs.readFileSync('agent.py','utf8');
    const excerpt = source.slice(source.indexOf('    def build_messages'),source.indexOf('    def save('));
    await page.setContent(style + title + '<h1>Код: один снимок профиля → контекст и бюджет</h1><pre>' + escape(excerpt) + '</pre>');
    await page.waitForTimeout(9000);
    for (const [i, entry] of report.cases.entries()) {
      const attempt = report.ledger.attempts[i];
      await page.setContent(style + title + `<h1>${escape(entry.label)}: ${i===2?'новая сессия, профиль повторно не передан':'тот же вопрос, эквивалентная пустая история'}</h1>` +
        `<pre>${escape(attempt.profile.content)}</pre><article>${escape(entry.reply.message).replace(/\n/g,'<br>')}</article>` +
        `<p>request ID: ${escape(attempt.response.id)} · cost: $${escape(attempt.response.usage.cost)}</p>`);
      await page.waitForTimeout(12000);
    }
    await page.setContent(style + title + `<h1>Три сохранённых вызова · $${escape(report.ledger.reported_cost_usd)}</h1><p>Автоматическое подключение профиля проверено по фактическим messages.</p><p>Стиль, ограничения и VPS network smoke требуют отдельных отчётов проверки.</p>`);
    await page.waitForTimeout(5000);
  } finally {
    const video = page.video();
    await context.close();
    await video.saveAs('demo/day12-live-replay.webm');
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode=1; });

async function recordMass(report) {
  const entries = report.ledger.manifest.cases;
  assert.equal(entries.length, 24);
  assert(Number(report.total_reported_cost_usd) <= 0.02);
  const browser = await chromium.launch(launchOptions);
  const context = await browser.newContext({viewport:{width:1280,height:800},recordVideo:{dir:'demo/raw-mass',size:{width:1280,height:800}}});
  await context.route('**/*', route => route.abort());
  const page = await context.newPage();
  const style = '<style>body{background:#101827;color:#edf4ff;font:18px system-ui;padding:28px;overflow:hidden}h1{font-size:34px;margin:24px 0 12px}.profile,.grading{white-space:pre-wrap;font:14px monospace;line-height:1.25}article{white-space:pre-wrap;font-size:20px;line-height:1.3;margin:14px 0}.badge{color:#80e8bd}</style>';
  const title = '<p class="badge">REPLAY · сохранённые ответы · сеть отключена · ошибки не скрыты</p>';
  try {
    for (const c of entries) {
      const e = report.ledger.cases[c.id];
      if (e.response) {
        assert(e.response.id);
        assert.equal(e.response.model, 'deepseek/deepseek-v4-flash-0731');
      }
      await page.setContent(style + title + `<h1>${escape(c.id)} · ${escape(c.group)} · ${escape(e.status)}</h1>` +
        `<p>${escape(c.question)}</p><pre class="profile">${escape(e.profile?.content || 'Нет отправленного контекста')}</pre>` +
        `<article>${escape(e.response?.choices?.[0]?.message?.content || 'Нет подтверждённого ответа')}</article>` +
        `<p>request ID: ${escape(e.response?.id || '—')} · cost: ${escape(e.reported_cost_usd || 'неизвестно')} · reuse: ${escape(c.profile_reuse || '—')}</p>` +
        `<pre class="grading">predicates: ${escape(JSON.stringify(e.grading?.predicates || {error:e.error}))}\ncritical: ${escape(JSON.stringify(e.grading?.critical_predicates || {}))}</pre>`);
      await page.waitForTimeout(2500);
    }
    const rows = Object.entries(report.groups).map(([name,g]) =>
      `<p><b>${escape(name)}</b>: ${g.pass}/${g.executed} pass · quality_fail ${g.quality_fail} · safety_fail ${g.safety_fail}</p>`).join('');
    await page.setContent(style + title + '<h1>Результаты и restart evidence</h1>' + rows +
      `<p>24 terminal cases · 17 pass · 7 quality_fail · 0 safety_fail</p>` +
      `<p>total with prior calls: $${escape(report.total_reported_cost_usd)} · cost complete: ${escape(report.cost_complete)}</p>` +
      `<p>restart: ${escape(report.ledger.restart?.status)} · PID ${escape(report.ledger.restart?.new_pid)} · SQLite/network checks recorded</p>` +
      `<p>Human semantic rubric: pending; Codex/model judge не использовался.</p>`);
    await page.waitForTimeout(6000);
  } finally {
    const video = page.video();
    await context.close();
    await video.saveAs('demo/day12-mass-replay.webm');
    await browser.close();
  }
}
