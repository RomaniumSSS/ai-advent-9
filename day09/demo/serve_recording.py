"""Подготовка панели из 8 реальных ходов: 9-й вопрос и summary вызываются вживую."""
import argparse
import json
import sys
import tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from base_agent import Reply
from experiment import BudgetLedger, MeasuredClient, real_client
from store import SqliteStore
import web

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--env-file',type=Path,required=True)
parser.add_argument('--report',type=Path,default=Path(__file__).resolve().parents[1]/'results/final/project-r1.json')
parser.add_argument('--port',type=int,default=8049)
args=parser.parse_args();load_dotenv(args.env_file)
report=json.loads(args.report.read_text())
(Path(__file__).parent/'recording-source.json').write_text(json.dumps({'source_report':str(args.report),'seeded_turns':8,'live_turn':9},ensure_ascii=False,indent=2)+'\n')
if not report['complete']:raise SystemExit('нужен завершённый реальный прогон')
ledger=BudgetLedger()
with tempfile.TemporaryDirectory(prefix='day09-video-') as tmp:
    db=Path(tmp)/'video.db'
    for side,key in [('left','full'),('right','compressed')]:
        store=SqliteStore(db,side)
        store.remember_config(report['config']['model'],report['config']['system_prompt'])
        for turn in report['turns'][:8]:
            fields=dict(turn['sides'][key]['reply']);fields['budget']=None
            reply=Reply(**fields)
            store.append_call(reply)
            store.append_turn(turn['question'],reply)
    web.build_panels(db,{'left':'left','right':'right'})
    for side,agent in web.PANELS.items():
        agent.config=web.AgentConfig(**report['config'])
        agent.client=MeasuredClient(real_client(),ledger,'video:'+side,
            Path(__file__).parent/(side+'-calls.json'))
    server=ThreadingHTTPServer(('127.0.0.1',args.port),web.Handler)
    print(f'Панель записи: http://127.0.0.1:{args.port}; первые 8 ходов из {args.report}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        state=web.state()
        (Path(__file__).parent/'panel-results.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
        (Path(__file__).parent.parent/'results/budget-report.json').write_text(json.dumps(ledger.report(),ensure_ascii=False,indent=2)+'\n')
