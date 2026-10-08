#!/usr/bin/env python3
"""Подготовка на VPS через stdin SSH; результат сохраняется только локально."""
import argparse
import base64
import json
from pathlib import Path
import shlex
import subprocess
import rag


def prepare_remote(host, root, python, questions, output, strategy='structure'):
    if not host or host.startswith('-') or any(char.isspace() for char in host):
        raise ValueError('invalid_ssh_host')
    if not python.startswith('/') or not root.startswith('/'):
        raise ValueError('remote_paths_must_be_absolute')
    if strategy not in ('structure', 'fixed'):
        raise ValueError('invalid_strategy')
    source = base64.b64encode(Path(rag.__file__).read_bytes()).decode('ascii')
    questions_data = json.loads(Path(questions).read_text())
    settings = base64.b64encode(json.dumps({'root':root, 'questions':questions_data,
        'strategy':strategy}, ensure_ascii=False).encode()).decode('ascii')
    # Вставляются только base64-строки: содержимое корпуса не становится кодом.
    wrapper = f'''import base64, json
namespace = {{"__name__": "remote_prepare"}}
exec(compile(base64.b64decode({source!r}), "rag.py", "exec"), namespace)
settings = json.loads(base64.b64decode({settings!r}))
try:
    result = namespace["prepare"](settings["root"], settings["questions"], "http://127.0.0.1:11434", settings["strategy"])
    print(json.dumps(result, ensure_ascii=False))
except Exception as error:
    print(json.dumps({{"error_type": type(error).__name__}}))
    raise SystemExit(1)
'''
    remote_command = shlex.quote(python) + ' -'
    completed = subprocess.run(['ssh', '-o', 'BatchMode=yes', host, remote_command],
        input=wrapper.encode(), capture_output=True, timeout=600, check=False)
    if completed.returncode:
        # stderr SSH и удалённого Python могут раскрыть пути и приватные данные.
        raise RuntimeError('remote_prepare_failed')
    result = json.loads(completed.stdout)
    if result.get('model') != rag.MODEL or not isinstance(result.get('cases'), list):
        raise ValueError('invalid_remote_result')
    rag.save(output, result)
    return {'status':'prepared', 'cases':len(result['cases']), 'paid_requests':0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='crm-agent')
    parser.add_argument('--root', default='/opt/day21/private/index-release-v1')
    parser.add_argument('--python', default='/opt/day21/pipeline-venv/bin/python')
    parser.add_argument('--questions', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--strategy', choices=('structure','fixed'), default='structure')
    args = parser.parse_args()
    try:
        print(json.dumps(prepare_remote(args.host,args.root,args.python,args.questions,args.output,args.strategy)))
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__}))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
