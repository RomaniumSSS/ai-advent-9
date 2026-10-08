"""Offline plan from local runtime limits; no pricing endpoint or provider calls."""
from decimal import Decimal
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from common import MAX_OUTPUT_TOKENS, MODEL, packed
from conversation import MESSAGES_BYTES


def proposal(scenarios):
    calls=sum(len(s['turns']) for s in scenarios['scenarios'])
    prompt=Decimal('0.14')/Decimal(1000000)
    completion=Decimal('0.42')/Decimal(1000000)
    reserve=(Decimal(MESSAGES_BYTES)+Decimal(MAX_OUTPUT_TOKENS))*prompt+Decimal(MAX_OUTPUT_TOKENS)*completion
    by_scope={s['scope']:sum(len(x['turns']) for x in scenarios['scenarios'] if x['scope']==s['scope']) for s in scenarios['scenarios']}
    global_policy=scenarios.get('budget_policy',{})
    global_mode=global_policy.get('kind')=='global_sequential'
    existing_all=global_policy.get('kind')=='reuse_existing_all_ledger'
    report={'scenario_sha256':__import__('hashlib').sha256(packed(scenarios)).hexdigest(), 'scopes':list(by_scope), 'frozen_identity_sha256':scenarios['frozen_identity_sha256'],
            'scope_breakdown':{scope:{'user_messages':count,'maximum_provider_calls':count,
                'reserve_upper_estimate_usd':str(reserve*count),'proposed_scope_budget_usd':(global_policy['initial_public_cap_usd'] if scope=='public' else 'global cap minus actual public charge') if global_mode else ('remaining existing all ledger; no reset' if existing_all else '0.06'),
                'documents':['assignment:18'] if scope=='public' else 'entire approved frozen index-release-v1; RAG days21–24 and course discussions; raw results private'} for scope,count in by_scope.items()},
            'scenario_count':len(scenarios['scenarios']), 'user_messages':calls,
            'maximum_new_searches':calls,'maximum_provider_calls':calls,
            'extra_video_provider_calls':0,'model_from_local_code':MODEL,'provider':'deepinfra/fp8',
            'retries':0,'messages_bytes_cap':MESSAGES_BYTES,'max_output_tokens':MAX_OUTPUT_TOKENS,
            'prompt_rate_cap_per_million':str(prompt*1000000),
            'completion_rate_cap_per_million':str(completion*1000000),
            'reserve_upper_estimate_per_call_usd':str(reserve),
            'reserve_upper_estimate_total_usd':str(reserve*calls),
            'proposed_new_budget_usd':global_policy['global_usd'] if global_mode else ('0; reuse existing cap' if existing_all else '0.12'), 'approval_status':'NOT_GRANTED',
            'basis':'Local service rate ceilings and byte reserve; not a fetched price or measured charge.'}
    if global_mode:report.update(budget_policy=global_policy,worst_case_all_calls_guaranteed=reserve*calls<=Decimal(global_policy['global_usd']),manual_uses_same_all_ledger=True,stop_before_insufficient_reserve=True)
    if existing_all:report.update(budget_policy=global_policy,worst_case_all_calls_guaranteed=False,manual_uses_same_all_ledger=True,stop_before_insufficient_reserve=True,sequential_scenario_reserve=True)
    return report


if __name__=='__main__':
    scenarios=json.loads(Path(__file__).with_name('scenarios.json').read_text())
    print(json.dumps(proposal(scenarios),ensure_ascii=False,indent=2))
