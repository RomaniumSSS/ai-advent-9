"""Записать экран с живым состоянием приватного Telegram-прогона на VPS."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
VIDEO = HERE / "telegram-live.mp4"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
REMOTE = '''import json, sqlite3
from pathlib import Path
db = sqlite3.connect('/var/lib/day20/day20.db')
db.row_factory = sqlite3.Row
requests = [dict(row) for row in db.execute(
    "SELECT id, origin_message_id, parent_request_id, user_text, state, fullness, "
    "trace_path, created_utc FROM requests WHERE state!='superseded' ORDER BY created_utc")]
outbox = [dict(row) for row in db.execute(
    "SELECT request_id, kind, status, message_id, text FROM outbox ORDER BY created_utc")]
for request in requests:
    raw_path = request.pop('trace_path')
    request['calls'] = []
    if raw_path and (path := Path(raw_path)).is_relative_to(Path('/var/lib/day20')) and path.is_file():
        trace = json.loads(path.read_text())
        request['calls'] = [
            {'server': call['server'], 'tool': call['tool'], 'status': call['status'],
             'elapsed_ms': call.get('elapsed_ms')}
            for call in trace.get('calls', [])]
print(json.dumps({'requests': requests, 'outbox': outbox}, ensure_ascii=False))
'''
HTML = """<!doctype html><html lang="ru"><meta charset="utf-8"><style>
body{margin:0;background:#101727;color:#e8edf7;font:20px/1.45 system-ui,sans-serif}
main{padding:42px 58px}h1{font-size:32px;margin:0 0 8px}h2{font-size:22px;margin:30px 0 10px}
.sub{color:#9eb3d1}.card{background:#1b2740;border:1px solid #385072;border-radius:12px;
padding:18px 22px;margin:12px 0}.tag{color:#74d6b5;font-weight:700}.muted{color:#a7b7d0}
.row{padding:4px 0;border-bottom:1px solid #34435b}.answer{max-height:145px;overflow:hidden;
white-space:pre-wrap;font-size:15px}.live{color:#ffca73}code{font:16px ui-monospace,monospace}
</style><main><h1>Day 20 · живой Telegram-прогон</h1>
<div class="sub">Приватный чат → Habr MCP + GitHub MCP → ответ бота</div>
<div id="status" class="card live">Ожидаю запрос в Telegram…</div>
<div id="content"></div></main><script>
const escapeHtml=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
window.render=s=>{
 const r=s.requests, o=s.outbox;
 document.querySelector('#status').textContent=r.length?`Получено запросов: ${r.length} · доставлено ответов: ${o.filter(x=>x.kind==='answer'&&x.status==='delivered').length}`:'Ожидаю запрос в Telegram…';
 document.querySelector('#content').innerHTML=r.map((x,i)=>{
  const messages=o.filter(y=>y.request_id===x.id);
  const calls=x.calls.filter(c=>c.status==='ok').slice(0,4).map(c=>`<div class="row"><code>${escapeHtml(c.server)} MCP · ${escapeHtml(c.tool)} · ${escapeHtml(c.status)}</code></div>`).join('');
  const answer=messages.find(y=>y.kind==='answer');
  return `<section class="card"><div class="tag">${i?'FOLLOW-UP':'ЗАПРОС'} · ${escapeHtml(x.state)} · ${escapeHtml(x.fullness||'обработка')}</div>
  <div>${escapeHtml(x.user_text)}</div>${calls?`<h2>Вызовы MCP</h2>${calls}`:''}
  ${answer?`<h2>Ответ бота · ${escapeHtml(answer.status)}${answer.message_id?' · message_id получен':''}</h2><div class="answer">${escapeHtml(answer.text)}</div>`:''}</section>`;
 }).join('');
};
</script></html>"""


def snapshot() -> dict:
    command = "runuser -u day20 -- /opt/day20-agent/.venv/bin/python -c " + shlex.quote(REMOTE)
    result = subprocess.run(["ssh", "crm-agent", command], capture_output=True,
                            text=True, check=True, timeout=15)
    return json.loads(result.stdout)


def main() -> None:
    baseline = {request["id"] for request in snapshot()["requests"]}
    timeout = int(os.environ.get("DAY20_RECORD_WAIT_SECONDS", "900"))
    HERE.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="day20-live-video-") as temporary:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, executable_path=str(CHROME) if CHROME.is_file() else None)
            context = browser.new_context(viewport={"width": 1440, "height": 900},
                                          record_video_dir=temporary,
                                          record_video_size={"width": 1440, "height": 900})
            page = context.new_page()
            page.set_content(HTML)
            page.evaluate("window.render", {"requests": [], "outbox": []})
            started = time.monotonic()
            observed: list[dict] = []
            completed = False
            while time.monotonic() - started < timeout:
                all_state = snapshot()
                requests = [request for request in all_state["requests"]
                            if request["id"] not in baseline]
                ids = {request["id"] for request in requests}
                current = {"requests": requests,
                           "outbox": [item for item in all_state["outbox"]
                                      if item["request_id"] in ids]}
                page.evaluate("window.render", current)
                observed.append({"at": time.time(), "request_count": len(current["requests"]),
                                 "calls": [len(r["calls"]) for r in current["requests"]],
                                 "delivered": sum(o["status"] == "delivered" for o in current["outbox"])})
                if any(item["kind"] == "answer" and item["status"] == "delivered"
                       for item in current["outbox"]):
                    servers = {call["server"] for request in requests for call in request["calls"]
                               if call["status"] == "ok"}
                    if not {"habr", "github"}.issubset(servers):
                        raise RuntimeError("live_answer_without_two_mcp")
                    page.wait_for_timeout(8000)
                    completed = True
                    break
                time.sleep(2)
            if not completed:
                raise TimeoutError("telegram_request_not_completed")
            raw = page.video
            context.close()
            browser.close()
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-i", raw.path(), "-c:v", "libx264", "-crf", "22",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(VIDEO)],
                           check=True)
            (HERE / "live-capture.json").write_text(
                json.dumps(observed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"video": str(VIDEO), "snapshots": len(observed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
