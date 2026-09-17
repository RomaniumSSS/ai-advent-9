"""Three real calls through an owner SSH tunnel; never retries an HTTP request."""
import argparse
import http.client
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from live_budget import MODEL, MAX_COST, decimal, digest
from profile import UserProfile

QUESTION = 'Объясни, как работает резервное копирование и как проверить восстановление'
PROFILES = [
    UserProfile('Деловой, краткий', 'Ровно три коротких маркированных пункта', 'Без аналогий'),
    UserProfile('Обучающий, для начинающего', 'Ровно два очень коротких абзаца, по одному предложению',
                'Весь ответ не более 60 слов; ровно одна бытовая аналогия; без списков'),
]


def rubric(text, index):
    bullets = re.findall(r'^\s*[-*•]\s+.+', text, flags=re.M)
    paragraphs = [p for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]
    return {'format_pass': len(bullets) == 3 and len(text.splitlines()) == 3 if index == 0
            else len(paragraphs) == 2 and not re.search(r'^\s*(?:[-*•]|\d+[.)])\s', text, re.M),
            'human_style_constraints': 'pending: brevity/no analogy for A; teaching/household analogy for B'}


class Tunnel:
    def __init__(self, url):
        parts = urlsplit(url)
        if parts.scheme != 'http' or parts.hostname != '127.0.0.1' or not parts.port or parts.path not in ('', '/') or parts.query or parts.fragment or parts.username:
            raise ValueError('use http://127.0.0.1:PORT through an authenticated owner tunnel')
        self.port = parts.port

    def request(self, path, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=650)
        try:
            payload = None if body is None else json.dumps(body, ensure_ascii=False)
            connection.request('GET' if body is None else 'POST', '/api/' + path,
                               body=payload.encode() if payload else None,
                               headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            value = json.loads(response.read())
            if response.status != 200:
                raise RuntimeError(f'HTTP {response.status}; stopped without retry')
            return value
        finally:
            connection.close()


def run(tunnel, report, save):
    initial = tunnel.request('evidence')
    report['ledger_before'] = initial
    save()
    if initial['attempts'] or initial['stopped']:
        raise RuntimeError('proof requires an unused ledger; do not reset an existing run')
    state = tunnel.request('state')['state']
    if state['offline'] or state['model'] != 'deepseek-v4-flash':
        raise RuntimeError('real DeepSeek runtime required')
    run_id = 'proof-' + uuid4().hex
    report['run_id'] = run_id
    previous = initial
    for index, label in enumerate(('A', 'B', 'B-repeat')):
        scoped = tunnel.request('scope', {'session': f'{run_id}-{label}', 'task': run_id, 'user': run_id})['state']
        if scoped['history'] or any(scoped['notes'].values()):
            raise RuntimeError('equivalent empty history/memory required')
        if index < 2:
            tunnel.request('profile', PROFILES[index].to_dict())
        # Third call changes only session; profile is loaded by the agent from SQLite.
        current = tunnel.request('state')['state']
        if current['profile'] != PROFILES[min(index, 1)].to_dict():
            raise RuntimeError('profile persistence failed')
        if tunnel.request('evidence') != previous:
            raise RuntimeError('concurrent model request detected')
        reply = tunnel.request('chat', {'text': QUESTION})
        ledger = tunnel.request('evidence')
        report['ledger'] = ledger
        report['cases'].append({'label': label, 'reply': reply})
        save()
        if len(ledger['attempts']) != index + 1 or ledger['stopped']:
            raise RuntimeError('unexpected attempt count or budget stop')
        attempt = ledger['attempts'][-1]
        expected = PROFILES[min(index, 1)].message()
        messages = attempt['request']['messages']
        blocks = [m for m in messages if m['content'].startswith('ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ')]
        if blocks != [expected] or messages[-1] != {'role': 'user', 'content': QUESTION}:
            raise RuntimeError('actual request profile/question mismatch')
        other = [m for m in messages if m not in blocks]
        if attempt['context_without_profile_hash'] != digest(other):
            raise RuntimeError('context hash mismatch')
        if index and attempt['context_without_profile_hash'] != ledger['attempts'][0]['context_without_profile_hash']:
            raise RuntimeError('A/B histories or parameters differ')
        options = {k: v for k, v in attempt['request'].items() if k != 'messages'}
        first_options = {k: v for k, v in ledger['attempts'][0]['request'].items() if k != 'messages'}
        if options != first_options or attempt['status'] != 'complete' or not reply['ok'] or not reply['saved']:
            raise RuntimeError('incomplete or unsaved real response')
        response = attempt['response']
        if response['model'] != MODEL or not response.get('id') or not response.get('provider'):
            raise RuntimeError('model/request ID/provider evidence missing')
        if response['choices'][0]['message']['content'] != reply['message']:
            raise RuntimeError('response provenance mismatch')
        if decimal(ledger['reported_cost_usd']) > MAX_COST:
            raise RuntimeError('reported cost exceeds budget')
        report['cases'][-1]['rubric'] = rubric(reply['message'], index)
        save()
        if not report['cases'][-1]['rubric']['format_pass']:
            raise RuntimeError('format rubric failed; no further paid requests')
        previous = ledger
    if report['cases'][0]['reply']['message'] == report['cases'][1]['reply']['message']:
        raise RuntimeError('A/B responses are identical')
    report['outcome'] = 'awaiting_human_rubric'
    report['automatic_profile_repeat'] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    tunnel = Tunnel(args.url)
    report = {'provenance': 'real DeepSeek via private VPS runtime', 'outcome': 'running', 'cases': [],
              'human_acceptance': None, 'vps_network_acceptance': None}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    # Refuse accidental resume/overwrite. The service ledger persists separately.
    with args.report.open('x') as stream:
        json.dump(report, stream)
    def save():
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    try:
        run(tunnel, report, save)
    except Exception as error:
        report.update(outcome='fail', error_type=type(error).__name__, error=str(error))
        save()
        raise SystemExit('Live proof stopped; inspect report and server ledger, do not retry') from None
    finally:
        save()


if __name__ == '__main__':
    main()
