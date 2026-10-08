"""Local risk-based inspection sample; no API, no semantic acceptance."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import prepare_selection_requests as prep
from run_local_sample import write

SEED=210124
SOURCE_SHA='076f2962bd221b659da1492691b4e1a8b85488c1aa6ba0e1327ee1fb588eb85a'
SAFE={'accepted_assignment','candidate_include'}


def prepare(rows,groups,canonical,max_ids=120,max_chars=60000):
    byid={r['message_id']:r for r in rows};rng=random.Random(SEED);inventory=[];candidates=[]
    def make(case_id,kind,members,context,labels):
        ids=set(members)|{i for i in context if i in canonical}
        return {'case_id':case_id,'stratum':kind,'member_ids':members,'context_ids':sorted(set(context)-set(members)),
                'labels':sorted(set(labels)),'unique_ids':sorted(ids),'chars':sum(len(canonical[i]['record']['text']) for i in ids),
                'member_chars':sum(len(canonical[i]['record']['text']) for i in members),'no_reply':all(canonical[i]['record']['reply_to'] is None for i in members)}
    for group in groups:
        if group['kind']!='document_groups':continue
        members=[r['id'] for r in group['member_references']]
        deps=group['context_references'];labels=[d['effective_proposed_status'] for d in deps if d['effective_proposed_status'] not in SAFE]
        if any('needs_fact_check' in (byid[i]['model_decision'] or {}).get('flags',[]) for i in members):labels.append('needs_fact_check_flag')
        if any('mixed_content' in (byid[i]['model_decision'] or {}).get('flags',[]) for i in members):labels.append('mixed_flag')
        disputed=any(d['effective_proposed_status'] not in SAFE for d in deps)
        kind='dependency' if disputed else 'clean_include'
        context=set(group['context_ids'])|{canonical[i]['record']['reply_to'] for i in members if canonical[i]['record']['reply_to'] is not None}
        candidate=make(group['draft_id'],kind,members,context,labels);candidate['model_group_proposal']=group['model_group'];candidates.append(candidate)
        if disputed:inventory.append({'case_id':group['draft_id'],'packet_id':group['packet_id'],'member_references':group['member_references'],
                                     'context_references':deps,'derived_context_references':group['derived_context_references'],'labels':candidate['labels'],'member_chars':candidate['member_chars']})
    for row in rows:
        if row['effective_proposed_status']!='candidate_exclude':continue
        ident=row['message_id'];parent=canonical[ident]['record']['reply_to'];reason=(row['model_decision'] or {}).get('reason','').casefold()
        # AICODE-NOTE: marker only stratifies the model's explanation; it does not prove a bot identity.
        labels=['model_reason_bot_marker'] if 'бот' in reason or 'bot' in reason else []
        candidates.append(make('exclude-'+str(ident),'exclude',[ident],[] if parent is None else [parent],labels))
    for c in sorted(candidates,key=lambda c:c['case_id']):c['tie']=rng.random()
    selected=[];selected_ids=set();rejected=[]
    def choose(pool,reason):
        for c in pool:
            if any(v['case_id']==c['case_id'] for v in selected):continue
            new=selected_ids|set(c['unique_ids']);chars=sum(len(canonical[i]['record']['text']) for i in new)
            if len(new)>max_ids or chars>max_chars:
                rejected.append({'case_id':c['case_id'],'reason':'whole_case_budget','prospective_ids':len(new),'prospective_chars':chars});continue
            selected.append(dict(c,sampling_reason=reason));selected_ids.update(c['unique_ids']);return True
        return False
    def ordered(kind,predicate=lambda _:True):return sorted([c for c in candidates if c['stratum']==kind and predicate(c)],key=lambda c:(c['tie'],c['case_id']))
    coverage=[]
    for label in ['candidate_exclude','semantic_review','unread_media_review','outside_or_missing','mixed_flag','needs_fact_check_flag']:
        pool=ordered('dependency',lambda c:label in c['labels'])
        if not pool:coverage.append({'label':label,'state':'not_available'});continue
        if any(label in c['labels'] for c in selected):coverage.append({'label':label,'state':'covered'});continue
        passed=choose(pool,'dependency_'+label);coverage.append({'label':label,'state':'covered' if passed else 'budget_unavailable'})
    while sum(c['stratum']=='dependency' for c in selected)<10:
        if not choose(ordered('dependency'),'seeded_dependency'):raise ValueError('insufficient_dependency_budget')
    for kind in ['clean_include','exclude']:
        if kind=='clean_include':choose(ordered(kind,lambda c:'mixed_flag' in c['labels']),'mixed_model_flag_inspection')
        choose(ordered(kind,lambda c:c['no_reply']),kind+'_no_reply')
        if kind=='exclude':choose(ordered(kind,lambda c:'model_reason_bot_marker' in c['labels']),'model_reason_marker_only')
        choose(sorted(ordered(kind),key=lambda c:(-c['member_chars'],c['tie'])),kind+'_longest_budget_fit')
        choose(sorted(ordered(kind),key=lambda c:(c['member_chars'],c['tie'])),kind+'_shortest')
        while sum(c['stratum']==kind for c in selected)<5:
            if not choose(ordered(kind),'seeded_'+kind):raise ValueError('insufficient_stratum_budget')
    if len(selected)!=20:raise ValueError('sample_count')
    cases=[]
    for c in selected:
        def record(i):
            m=canonical[i]
            return {'id':i,'text':m['record']['text'],'provenance':byid[i]['provenance'],'reply':m['reply'],
                    'source_role':m['source_role'],'media':m['attachment'],'proposed_status':byid[i]['effective_proposed_status'],'model_decision_proposal':byid[i]['model_decision'],'context_only':i not in c['member_ids']}
        cases.append({k:v for k,v in c.items() if k!='tie'}|{'members':[record(i) for i in c['member_ids']],
                    'context':[record(i) for i in c['context_ids'] if i in canonical],
                    'unavailable_context_ids':[i for i in c['context_ids'] if i not in canonical]})
    summary={'inventory_groups':len(inventory),'cases':len(cases),'strata':dict(Counter(c['stratum'] for c in cases)),
             'unique_message_ids':len(selected_ids),'unique_chars':sum(len(canonical[i]['record']['text']) for i in selected_ids),
             'case_text_chars_with_repeats':sum(c['chars'] for c in cases),'coverage':coverage,
             'sampled_labels':dict(Counter(label for c in cases for label in c['labels'])),
             'budget_rejected_unique_cases':len({r['case_id'] for r in rejected}),'cloud_authorized':False,'accepted_mutations':0}
    return {'inventory':inventory,'cases':cases,'selected_message_ids':sorted(selected_ids),'summary':summary,'selection_exclusions':rejected}


def publish(path,identity,result):
    if path.is_symlink():raise ValueError('symlink_generation')
    path.mkdir(mode=0o700,exist_ok=True);path.chmod(0o700)
    with (path/'.lock').open('a') as lock:
        (path/'.lock').chmod(0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        objects={'inventory.json':result['inventory'],'cases.json':result['cases'],'selected-message-ids.json':result['selected_message_ids']}
        hashes={name:hashlib.sha256((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest() for name,value in objects.items()}
        objects['manifest.json']={'version':3,'seed':SEED,'identity':identity,'artifacts':hashes,'summary':result['summary'],'selection_exclusions':result['selection_exclusions']}
        for name,value in objects.items():
            p=path/name;raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
            if p.is_symlink() or p.exists() and p.read_bytes()!=raw:raise ValueError('changed_generation')
        for name,value in objects.items():
            if not (path/name).exists():write(path/name,value)


def main():
    os.umask(0o077);cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--run-name',default='selection-review-v3');args=cli.parse_args()
    if Path(args.run_name).name!=args.run_name:raise ValueError('private_directory_only')
    source=prep.PRIVATE/'selection-proposals-v3';manifest= json.loads((source/'manifest.json').read_text())
    if prep.file_hash(source/'manifest.json')!=SOURCE_SHA:raise ValueError('proposal_manifest_changed')
    protected={str(source/name):sha for name,sha in manifest['artifacts'].items()}|manifest['identity']['accepted_guard_sha256']
    protected[str(source/'manifest.json')]=SOURCE_SHA
    if any(prep.file_hash(Path(p))!=sha for p,sha in protected.items()):raise ValueError('source_changed')
    _,canonical,_=prep.load_packets(prep.PRIVATE/'selection-packets-v1')
    rows=[json.loads(s) for s in (source/'rows.jsonl').read_text().splitlines()];groups=json.loads((source/'groups.json').read_text())
    for row in rows:
        m=canonical[row['message_id']]
        if row['provenance']['version_hash']!=m['version_hash'] or row['provenance']['text_sha256']!=m['text_sha256']:raise ValueError('provenance_changed')
    result=prepare(rows,groups,canonical)
    if any(prep.file_hash(Path(p))!=sha for p,sha in protected.items()):raise ValueError('source_changed_during_build')
    identity={'source_manifest_sha256':SOURCE_SHA,'preparer_sha256':prep.file_hash(Path(__file__)),'packet_manifest_sha256':manifest['identity']['packet_manifest_sha256'],'protected_sha256':protected,'max_ids':120,'max_chars':60000}
    publish(prep.PRIVATE/args.run_name,identity,result)
    print(json.dumps({'summary':result['summary'],'manifest_sha256':prep.file_hash(prep.PRIVATE/args.run_name/'manifest.json')}))

if __name__=='__main__':main()
