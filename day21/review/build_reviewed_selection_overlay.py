"""Corrected proposal overlay only; root review is not corpus approval."""
import copy
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import prepare_selection_requests as prep
import build_selection_manifest as source_builder
from run_local_sample import write

REVIEW_SHA='2d9b28175b642f424e331b1fad8c4673f16f635971a9d2d890fb07d38071d07c'
SOURCE_SHA='076f2962bd221b659da1492691b4e1a8b85488c1aa6ba0e1327ee1fb588eb85a'


def overlay(rows,groups,review,canonical,review_sha):
    result_rows=copy.deepcopy(rows);byid={r['message_id']:r for r in result_rows};changes={}
    if len(byid)!=len(rows) or set(byid)!=set(canonical):raise ValueError('row_coverage')
    for change in review['proposed_status_changes']:
        ident=change['message_id'];row=byid[ident]
        if ident in changes or row['effective_proposed_status']!=change['from'] or row['provenance']!=change['provenance'] or change['applied'] is not False:raise ValueError('status_change_source')
        if change['proposed_to'] not in ['semantic_review','candidate_exclude']:raise ValueError('unsupported_status_change')
        changes[ident]=change;row['effective_proposed_status']=change['proposed_to'];row['decision_origin']='root_review_proposal'
        row['review_overlay']={'review_sha256':review_sha,'case_id':change['case_id'],'reason':change['reason'],'previous_proposed_status':change['from'],'accepted':False}
    replacement=review['proposed_group_replacement'];original=next(g for g in groups if g['draft_id']==replacement['original_case_id'])
    def make(group,members,kind,explicit,proposal,related=()):
        output=copy.deepcopy(group);output['kind']=kind
        output['source_group_references']=[{'draft_id':group['draft_id'],'source_generation':'selection-proposals-v3'}]
        output['source_model_group']=copy.deepcopy(group.get('model_group'))
        output['member_references']=[byid[i]['provenance'] for i in members]
        output['sections']=[{'section_index':n,'original_text_ref':byid[i]['provenance'],'text_transform':'none'} for n,i in enumerate(members)]
        output['origin']='root_review_proposal';output['review_overlay']={'review_sha256':review_sha,'proposal':proposal,'accepted':False}
        output['draft_id']='reviewed-'+prep.digest({'source':group['draft_id'],'review':review_sha,'kind':kind,'members':output['member_references'],'proposal':proposal})[:24]
        output['context_ids']=sorted(set(explicit)-set(members));output['related_continuation_references']=[{'id':i,'provenance':byid[i]['provenance'],'effective_proposed_status':byid[i]['effective_proposed_status'],'reference_only':True,'promoted':False} for i in related]
        return output
    result_groups=[]
    for group in groups:
        members=[r['id'] for r in group['member_references']]
        if group['draft_id']==replacement['original_case_id']:
            new_members=[i for g in replacement['groups'] for i in g['member_ids']]
            expected=[i for i in members if byid[i]['effective_proposed_status']=='candidate_include']
            if set(new_members)!=set(expected) or len(new_members)!=len(set(new_members)):raise ValueError('replacement_coverage')
            for proposed in replacement['groups']:
                result_groups.append(make(group,proposed['member_ids'],'document_groups',proposed['context_ids'],proposed,proposed.get('related_continuation_ids',[])))
        else:
            remaining=[i for i in members if i not in changes]
            if remaining:
                result_groups.append(copy.deepcopy(group) if remaining==members else make(group,remaining,group['kind'],group['context_ids'],{'operation':'remove_changed_members'}))
        moved_review=[i for i in members if i in changes and byid[i]['effective_proposed_status']=='semantic_review']
        if moved_review:
            result_groups.append(make(group,moved_review,'review_groups',group['context_ids'],
                                      {'operation':'review_changed_members','ids':moved_review}))
    for group in result_groups:
        members=[r['id'] for r in group['member_references']];derived=[]
        for ident in members:
            parent=canonical[ident]['record']['reply_to']
            if parent is not None and parent not in members:
                message=canonical.get(parent)
                derived.append({'child_id':ident,'parent_id':parent,'relation':'source_direct_reply','state':canonical[ident]['reply']['parent_state'],
                                'child_provenance':byid[ident]['provenance'],'parent_provenance':byid[parent]['provenance'] if message else None})
        context=(set(group['context_ids'])|{d['parent_id'] for d in derived})-set(members)
        group['derived_context_references']=derived;group['context_ids']=sorted(context)
        group['context_references']=[{'id':i,'provenance':byid[i]['provenance'] if i in byid else None,'state':'canonical' if i in byid else 'outside_or_missing',
            'effective_proposed_status':byid[i]['effective_proposed_status'] if i in byid else 'outside_or_missing',
            'media':byid[i]['media'] if i in byid else None,'reply_reference':byid[i]['reply_reference'] if i in byid else None,
            'derived_parent_states':sorted({d['state'] for d in derived if d['parent_id']==i}),'promoted':False} for i in sorted(context)]
    for kind,status in [('document_groups','candidate_include'),('review_groups','semantic_review')]:
        members=[r['id'] for g in result_groups if g['kind']==kind for r in g['member_references']]
        expected={i for i,r in byid.items() if r['effective_proposed_status']==status}
        if set(members)!=expected or len(members)!=len(set(members)):raise ValueError('group_coverage')
    summary={'eligible_ids':len(result_rows),'statuses':dict(Counter(r['effective_proposed_status'] for r in result_rows)),
             'groups':dict(Counter(g['kind'] for g in result_groups)),'status_changes':len(changes),
             'status_changes_by_target':dict(Counter(c['proposed_to'] for c in changes.values())),
             'replacement_groups':len(replacement['groups']),'replacement_member_ids':sum(len(g['member_ids']) for g in replacement['groups']),
             'candidate_groups_with_review_dependencies':sum(any(d['effective_proposed_status'] not in ['candidate_include','accepted_assignment'] for d in g['context_references']) for g in result_groups if g['kind']=='document_groups'),
             'related_continuation_references':sum(len(g.get('related_continuation_references',[])) for g in result_groups),'accepted_mutations':0}
    return result_rows,result_groups,summary


def publish(directory,objects):
    if directory.is_symlink():raise ValueError('symlink_generation')
    directory.mkdir(mode=0o700,exist_ok=True);directory.chmod(0o700)
    with (directory/'.lock').open('a') as lock:
        (directory/'.lock').chmod(0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for name,value in objects.items():
            path=directory/name;raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
            if path.is_symlink() or path.exists() and path.read_bytes()!=raw:raise ValueError('changed_generation')
        for name,value in objects.items():
            if not (directory/name).exists():write(directory/name,value)


def main():
    os.umask(0o077);source=prep.PRIVATE/'selection-proposals-v3';review_path=prep.PRIVATE/'selection-semantic-review-v1.json'
    if prep.file_hash(source/'manifest.json')!=SOURCE_SHA or prep.file_hash(review_path)!=REVIEW_SHA:raise ValueError('input_manifest_changed')
    manifest=json.loads((source/'manifest.json').read_text());review=json.loads(review_path.read_text())
    if review['proposal_manifest_sha256']!=SOURCE_SHA:raise ValueError('review_source_mismatch')
    protected={str(source/name):sha for name,sha in manifest['artifacts'].items()}|manifest['identity']['accepted_guard_sha256']
    protected[str(source/'manifest.json')]=SOURCE_SHA;protected[str(review_path)]=REVIEW_SHA
    if review['accepted_guard_sha256']!=manifest['identity']['accepted_guard_sha256']:raise ValueError('accepted_guard_mismatch')
    if any(prep.file_hash(Path(p))!=sha for p,sha in protected.items()):raise ValueError('input_changed')
    _,canonical,_=prep.load_packets(prep.PRIVATE/'selection-packets-v1')
    rows=[json.loads(s) for s in (source/'rows.jsonl').read_text().splitlines()];groups=json.loads((source/'groups.json').read_text())
    output_rows,output_groups,summary=overlay(rows,groups,review,canonical,REVIEW_SHA)
    objects={'rows.json':output_rows,'groups.json':output_groups,'diff-summary.json':summary}
    artifact_sha={name:hashlib.sha256((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest() for name,value in objects.items()}
    objects['manifest.json']={'version':2,'source_manifest_sha256':SOURCE_SHA,'review_sha256':REVIEW_SHA,'builder_sha256':prep.file_hash(Path(__file__)),
                             'protected_sha256':protected,'artifacts':artifact_sha,'summary':summary,'source_preview_ref':'selection-proposals-v3/preview.md','accepted':False}
    if any(prep.file_hash(Path(p))!=sha for p,sha in protected.items()):raise ValueError('input_changed_during_build')
    target=prep.PRIVATE/'selection-reviewed-proposals-v2';publish(target,objects)
    print(json.dumps({'summary':summary,'manifest_sha256':prep.file_hash(target/'manifest.json')}))

if __name__=='__main__':main()
