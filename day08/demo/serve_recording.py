"""Настоящая панель для записи: отдельная временная база и явный лимит защиты."""
import argparse
import sys
import tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--env-file', type=Path)
args = parser.parse_args()
if args.env_file:
    load_dotenv(args.env_file)
else:
    load_dotenv()
import web
from test_live import MeasuredClient

with tempfile.TemporaryDirectory(prefix='day08-recording-') as tmp:
    web.build_panels(Path(tmp)/'demo.db', {'left':'видео-диалог','right':'видео-защита'}, context_limit=6000)
    for name, agent in list(web.PANELS.items()):
        agent = agent.with_config(model='gpt-oss-20b', max_tokens=1500,
            system_prompt='Отвечай кратко по-русски, одним предложением. Запоминай факты разговора.')
        agent.client = MeasuredClient(0.03, 'coreweave')
        web.PANELS[name] = agent
    server=ThreadingHTTPServer(('127.0.0.1',8048),web.Handler)
    print('Recording panel ready: http://127.0.0.1:8048',flush=True)
    server.serve_forever()
