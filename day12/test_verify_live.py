"""Verify runner sequencing and provenance against a local transport double."""
from copy import deepcopy
from unittest.mock import patch

from live_budget import MODEL, digest
from verify_live import run, PROFILES


class FakeTunnel:
    def __init__(self):
        self.ledger = {'attempts': [], 'stopped': None, 'reported_cost_usd': '0'}
        self.state = {'offline': False, 'model':'deepseek-v4-flash', 'history':[], 'notes':{}, 'profile':{}}
        self.saves = 0
        self.chats = 0

    def request(self, path, body=None):
        if path == 'evidence': return deepcopy(self.ledger)
        if path == 'state': return {'state':deepcopy(self.state)}
        if path == 'scope': return {'state':deepcopy(self.state)}
        if path == 'profile':
            self.saves += 1
            self.state['profile'] = deepcopy(body)
            return {}
        if path == 'chat':
            index = self.chats
            self.chats += 1
            assert set(body) == {'text'}, 'profile must not be transmitted with question'
            if index == 2: assert self.saves == 2
            profile = PROFILES[min(index, 1)].message()
            context = [{'role':'system','content':'role'}, {'role':'user','content':body['text']}]
            answer = '- A\n- B\n- C' if index == 0 else 'Explanation.\n\nHousehold analogy.'
            response = {'id':f'fake-{index}', 'model':MODEL, 'provider':'fake',
                        'usage':{'prompt_tokens':100,'completion_tokens':20,'cost':0.0001},
                        'choices':[{'message':{'content':answer}}]}
            self.ledger['attempts'].append({'status':'complete','request':{'model':MODEL,'messages':[context[0], profile, context[1]],'max_tokens':512},
                                            'response':response,'context_without_profile_hash':digest(context)})
            self.ledger['reported_cost_usd'] = str(self.chats * 0.0001)
            return {'message':answer,'ok':True,'saved':True}
        raise AssertionError(path)


def main():
    fake = FakeTunnel()
    report = {'cases':[]}
    run(fake, report, lambda: None)
    assert report['outcome'] == 'awaiting_human_rubric'
    assert fake.chats == 3 and fake.saves == 2 and report['automatic_profile_repeat']
    for altered in ('offline', 'used', 'provider_failure', 'format'):
        fake = FakeTunnel()
        if altered == 'offline': fake.state['offline'] = True
        if altered == 'used': fake.ledger['attempts'] = [{}]
        original = fake.request
        def request(path, body=None):
            value = original(path, body)
            if path == 'chat':
                if altered == 'provider_failure': fake.ledger['stopped'] = 'provider error'
                if altered == 'format':
                    value['message'] = 'bad format'
                    fake.ledger['attempts'][-1]['response']['choices'][0]['message']['content'] = 'bad format'
            return value
        fake.request = request
        try: run(fake, {'cases':[]}, lambda: None)
        except RuntimeError: pass
        else: raise AssertionError(altered)
        assert fake.chats <= 1
    print('ok: A/B/repeat sequencing, no retransmitted profile, provenance, early failure, no retry')


if __name__ == '__main__':
    with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
        main()
