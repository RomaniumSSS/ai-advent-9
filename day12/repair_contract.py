"""One narrowly pinned manual continuation; no provider or transport code."""
import re
from live_budget import BudgetStop, digest, decimal, MAX_COST

RUN_ID = 'proof-45691d23bd6f41dfa98d9a84bdc8c4d6'
REPORT_HASH = 'a430469b063a453d3bd26869c9188aac230eb5f8ffb2954ca90024c33a2c2a3e'
LEDGER_HASH = '93ff1ae56a4c74294608c8671de85ad93939af83ae9748a0b6cfbdec50dea653'
ANALYSIS = 'B finish_reason=length at max_tokens=512 with default reasoning; shorten profile B only'


def require(condition, message):
    if not condition:
        raise BudgetStop(message)


def source_check(report):
    require(digest(report) == REPORT_HASH and report['run_id'] == RUN_ID,
            'original live report changed')
    require(digest(report['ledger']) == LEDGER_HASH, 'original ledger changed')


def options(request):
    return {k: v for k, v in request.items() if k != 'messages'}


def short_format(text):
    paragraphs = re.split(r'\n\s*\n', text.strip())
    return (len(paragraphs) == 2 and len(text.split()) <= 60
            and not re.search(r'^\s*(?:[-*•]|\d+[.)])\s', text, re.M)
            and all(len(re.findall(r'[.!?]+(?:\s|$)', p)) == 1
                    and re.search(r'[.!?]$', p.strip()) for p in paragraphs))


def audit_check(state):
    audit = state['manual_resume']
    original = {k: v for k, v in state.items() if k != 'manual_resume'}
    original.update(attempts=state['attempts'][:2], reported_cost_usd='0.00010041',
                    stopped='empty or incomplete response')
    require(digest(original) == LEDGER_HASH, 'original attempts/policy changed')
    require(audit['run_id'] == RUN_ID and audit['source_report_hash'] == REPORT_HASH
            and audit['source_ledger_hash'] == LEDGER_HASH and audit['remaining_attempts'] == 2
            and audit['analysis'] == ANALYSIS and audit['approved_by'].strip()
            and audit['reason'].strip() and audit['authorized_at']
            and audit['original_stop'] == 'empty or incomplete response'
            and audit['original_cost'] == '0.00010041', 'invalid resume audit')
    require(2 <= len(state['attempts']) <= 4, 'resume attempt count changed')
    require(all('response' in a and a['response'].get('usage', {}).get('cost') is not None
                for a in state['attempts']), 'unknown outcome or usage; resume forbidden')
    total = sum((decimal(a['response']['usage']['cost']) for a in state['attempts']), decimal(0))
    require(total == decimal(state['reported_cost_usd']) and total <= MAX_COST,
            'resume cost mismatch')


def request_check(state, request):
    from verify_live import PROFILES
    audit_check(state)
    first = state['attempts'][0]
    expected = PROFILES[1].message()
    messages = request['messages']
    blocks = [m for m in messages if m['content'].startswith('ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ')]
    require(blocks == [expected], 'resume profile changed')
    require(digest([m for m in messages if m not in blocks]) == first['context_without_profile_hash'],
            'resume non-profile context changed')
    require(options(request) == options(first['request']), 'resume generation options changed')
    if len(state['attempts']) == 3:
        previous = state['attempts'][2]
        require(previous['status'] == 'complete' and
                short_format(previous['response']['choices'][0]['message']['content']),
                'B must pass before B-repeat')
