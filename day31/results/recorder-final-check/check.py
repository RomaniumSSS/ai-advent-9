"""Офлайн-доказательство прокрутки: настоящий MCP, длинный контрольный текст без LLM."""
from pathlib import Path
from types import SimpleNamespace
import json
import subprocess
import sys
import tempfile
import threading
from day31.config import build_assistant
from day31.provider import OfflineProvider, ProviderResult
from day31.web import make_server

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]

class LongOfflineProvider(OfflineProvider):
    def generate(self, question,sources,git_context,trace_id):
        text='Контрольный офлайн-текст для проверки длинного экрана. Это не ответ LLM.\n\n'
        text+='\n'.join(f'{i:03d}. Контрольная строка для чтения и проверки непрерывной прокрутки.' for i in range(1,81))
        text+='\nКОНЕЦ КОНТРОЛЬНОГО ОФЛАЙН-ТЕКСТА'
        return ProviderResult(json.dumps({'status':'ok','text':text,'source_ids':[sources[0]['id']]},ensure_ascii=False),None)

with tempfile.TemporaryDirectory(prefix='day31-recorder-') as temp:
    app=build_assistant(SimpleNamespace(repo=ROOT,data_dir=Path(temp),live=False,budget_usd=None,env_file=None))
    server=make_server(app,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_address[1]}'
    try:
        for kind,folder,long_text in [('dry-run','normal-dry',False),('record','long-offline-record',True)]:
            if long_text: app.provider=LongOfflineProvider()
            command=[sys.executable,'-m','day31.recorder.run_demo','--'+kind,'--url',url,'--output',str(BASE/folder),'--hold-seconds','1']
            subprocess.run(command,cwd=ROOT,check=True)
        events=[json.loads(line) for line in (BASE/'long-offline-record/events.jsonl').read_text().splitlines()]
        frames=[e for e in events if e['event']=='reading_frame']
        for i in (1,2):
            answer_frames=[e for e in frames if e['index']==i and e['section']=='answer']
            assert len(answer_frames)>1
            assert answer_frames[0]['scroll_y']<answer_frames[-1]['scroll_y']
        for event in (e for e in frames if e['section']=='mcp_result'):
            assert event['pre_scroll_top']>0
            assert event['visible_result_keys']=={'branch':True,'head':True}
        dry=json.loads((BASE/'normal-dry/manifest.json').read_text())
        assert dry['hold_seconds_effective']==0
        report={'mode':'offline only: no OpenRouter client or ledger; real stdio MCP',
            'checks':['normal offline dry-run','long offline record: multiple overlapping answer frames','MCP call + internally scrolled branch/head in all 3 answers','no API wait truncation; raw JSON unchanged; screenshot+trace preserved','dry-run no reading holds'],
            'long_answer_frames':{str(i):len([e for e in frames if e['index']==i and e['section']=='answer']) for i in (1,2)},
            'mcp_result_visibility':[e for e in frames if e['section']=='mcp_result']}
        (BASE/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
