"""Статичный показ только сохранённого и проверенного реального trace."""
from __future__ import annotations
import html
import json
from pathlib import Path
from day19.evals.audit import audit_trace

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def e(value):return html.escape(str(value),quote=True)

def main():
    trace_path=HERE/'live-trace.json'
    # AICODE-NOTE: старый демонстрационный отчёт содержал верные только для
    # RSS-выдержки отрицания; новая запись показывает текст, сверенный со статьями.
    t=audit_trace(trace_path)
    if t['status'] != 'saved' or len(t['tool_calls']) != 3:
        raise ValueError('demo_requires_successful_three_call_trace')
    cli=json.loads((HERE/'live-cli-output.json').read_text(encoding='utf-8'))
    if (cli['run_id'] != t['run_id'] or cli['status'] != t['status']
            or cli['tool_calls'] != len(t['tool_calls'])
            or cli['model_calls'] != len(t['model_calls'])
            or abs(cli['reported_cost_usd'] - t['reported_cost_usd']) > 0.000000001):
        raise ValueError('demo_cli_trace_mismatch')
    a,b,c=t['tool_calls']
    report=(ROOT/c['result']['path']).read_text(encoding='utf-8')
    source_cards=''.join(f'<div class="source"><b>{e(r["article_id"])}</b><span>{e(r["title"])}</span><small>{e(r["url"])}</small></div>'
                         for r in a['result']['model_seen'])
    draft_cards=''.join(f'<div class="source"><b>{e(x["category"])}</b><span>{e(x["summary"])}</span>'
                        f'<small>observation_id: {e(x["observation_id"])}</small></div>'
                        for x in b['arguments']['draft']['entries'])
    html_doc=f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Day 19 — verified MCP trace</title><style>
:root{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#e9f2f7;background:#08121c}}
*{{box-sizing:border-box}}body{{margin:0;width:100vw;height:100vh;background:radial-gradient(circle at 77% 13%,#194a5b 0,#0d2232 30%,#08121c 68%);overflow:hidden}}
main{{width:100%;height:100%;padding:54px 84px;position:relative}}.top{{display:flex;justify-content:space-between;align-items:center;color:#8fb0bf;font-size:18px;letter-spacing:.08em;text-transform:uppercase}}
.brand{{font-weight:800;color:#d9fff1}}.badge{{border:1px solid #3a6876;background:#123342;padding:10px 18px;border-radius:99px;color:#b2f9df;font-size:15px}}
.slide{{display:none;height:calc(100% - 105px);align-content:center}}.slide.active{{display:block}}
h1{{font-size:56px;line-height:1.08;letter-spacing:-.045em;margin:10px 0 28px;max-width:1150px}}h2{{font-size:30px;margin:0 0 14px;color:#c7e6ef}}
.kicker{{font-size:18px;color:#79e3bf;text-transform:uppercase;letter-spacing:.18em;font-weight:750}}.lead{{font-size:28px;line-height:1.4;color:#c8d9e1;max-width:1080px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:34px}}.card{{border:1px solid #315262;background:#102938dd;border-radius:24px;padding:28px;box-shadow:0 18px 54px #0003}}
.card.big{{padding:34px}}.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere;color:#b6d7e2;font-size:19px;line-height:1.6}}
.tag{{display:inline-block;background:#135743;color:#c5ffe7;border-radius:8px;padding:6px 11px;font-size:17px;font-weight:750;margin-bottom:12px}}
.source{{display:grid;grid-template-columns:210px minmax(0,1fr);gap:5px 14px;padding:14px 0;border-bottom:1px solid #36515e;font-size:19px}}.source:last-child{{border-bottom:0}}.source b{{color:#81e7c0;font-size:16px}}.source small{{grid-column:2;color:#a9c3cf;font-size:15px;overflow-wrap:anywhere}}
.steps{{display:flex;gap:14px;margin-top:25px}}.step{{flex:1;background:#102938;border:1px solid #315262;border-radius:18px;padding:20px;font-size:19px}}.step strong{{color:#7ee0bd;display:block;margin-bottom:8px}}
pre{{white-space:pre-wrap;font:21px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;margin:0;color:#e9f2f7}}.report{{max-height:555px;overflow:hidden}}
.foot{{position:absolute;bottom:30px;left:84px;right:84px;display:flex;justify-content:space-between;color:#82a5b5;font-size:15px}}.line{{height:4px;background:#1e3a47;position:absolute;bottom:0;left:0;width:100%}}.progress{{height:100%;width:0;background:#7de8bc;transition:width .35s}}
</style></head><body><main>
<div class="top"><div class="brand">AI ADVENT / DAY 19</div><div class="badge">DeepSeek V4.1 Flash · DeepInfra · локальный MCP</div></div>
<section class="slide active" id="s1"><div class="kicker">Локальный агент · реальный запрос</div><h1>{e(t['request'])}</h1><div class="card"><span class="tag">Запуск через CLI</span><div class="mono">$ uv run python -m day19.cli<br>RSS: day19/evals/fixtures/mixed_fact_noise.xml · DeepSeek V4.1 Flash</div></div><p class="lead">Команда воспроизведения и сохранённый вывод — в README. Модель получает схемы трёх инструментов и сама выбирает каждый вызов.</p></section>
<section class="slide" id="s2"><div class="kicker">Каталог для каждого хода</div><h1>Три инструмента. Один агентный цикл.</h1><div class="steps"><div class="step"><strong>01 · поиск</strong>collect_habr_agent_cases</div><div class="step"><strong>02 · обработка</strong>prepare_report_preview</div><div class="step"><strong>03 · запись</strong>save_report</div></div><p class="lead">model → проверка аргументов → локальный MCP → observation с тем же call ID → model</p></section>
<section class="slide" id="s3"><div class="kicker">Вызов 1 / 3 · выбрала модель</div><h1>Поиск вернул batch и исходные записи</h1><div class="grid"><div class="card"><span class="tag">{e(a['result']['status'])}</span><div class="mono">call_id: {e(a['call_id'])}<br>batch_id: {e(a['result']['batch_id'])}<br>model_seen: {len(a['result']['model_seen'])}<br>coverage: {e(a['result']['coverage']['kind'])}</div></div><div class="card">{source_cards}</div></div></section>
<section class="slide" id="s4"><div class="kicker">Вызов 2 / 3 · после observation 1</div><h1>Модель передала ID найденного batch и draft</h1><div class="grid"><div class="card"><span class="tag">{e(b['result']['status'])}</span><div class="mono">call_id: {e(b['call_id'])}<br>batch_id: {e(b['arguments']['batch_id'])}<br>preview_id: {e(b['result']['preview_id'])}<br>sha256: {e(b['result']['sha256'])}</div></div><div class="card">{draft_cards}</div></div></section>
<section class="slide" id="s5"><div class="kicker">Вызов 3 / 3 · после observation 2</div><h1>Сервер сохранил только проверенный preview</h1><div class="card big"><span class="tag">{e(c['result']['status'])}</span><div class="mono">call_id: {e(c['call_id'])}<br>preview_id из шага 2: {e(c['arguments']['preview_id'])}<br>sha256 из шага 2: {e(c['arguments']['sha256'])}<br>путь назначил сервер: {e(c['result']['path'])}</div></div><p class="lead">Путь и содержимое файла не передавались моделью в save_report.</p></section>
<section class="slide" id="s6"><div class="kicker">Ответ локального агента · фактический CLI-вывод</div><h1>Агент завершил запрос после трёх вызовов</h1><div class="card big"><span class="tag">{e(cli['status'])}</span><div class="mono">run_id: {e(cli['run_id'])}<br>вызовов модели: {e(cli['model_calls'])}<br>вызовов MCP: {e(cli['tool_calls'])}<br>файл: {e(c['result']['path'])}<br>стоимость по usage: ${e(f'{cli["reported_cost_usd"]:.8f}')}</div></div><p class="lead">Поля взяты из сохранённого stdout; три вызова и путь проверены по trace.</p></section>
<section class="slide" id="s7"><div class="kicker">Результат · файл проверен</div><h1>Две ссылки на исходные статьи</h1><div class="card report"><pre>{e(report)}</pre></div><p class="lead" style="font-size:19px">SHA-256 файла совпадает с preview · {e(f'{t["reported_cost_usd"]:.6f}')} USD по usage провайдера</p></section>
<div class="foot"><span>Реальный CLI-прогон, визуализация его trace · {e(t['started_utc'])}</span><span id="slide-number">1 / 7</span></div><div class="line"><div class="progress" id="progress"></div></div>
</main><script>function show(n){{document.querySelectorAll('.slide').forEach(s=>s.classList.remove('active'));document.getElementById('s'+n).classList.add('active');document.getElementById('slide-number').textContent=n+' / 7';document.getElementById('progress').style.width=(n/7*100)+'%'}}show(1);</script></body></html>'''
    target=HERE/'evidence.html'
    target.write_text(html_doc,encoding='utf-8')
    print(json.dumps({'html':str(target),'slides':7},ensure_ascii=False))

if __name__=='__main__':main()
