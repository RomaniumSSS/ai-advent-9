"""Local inert proposal manifest and review inventory; never accepts corpus."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import prepare_selection_requests as prep
import prepare_selection_packets as packets
import run_selection_requests as run
import run_selection_context_review as policy

VERSION=3


def provenance(message):
    record=message['record']
    return {'id':message['message_id'],'source_key':message['source_key'],'version_hash':message['version_hash'],
            'text_sha256':message['text_sha256'],'record_sha256':message['record_sha256'],
            'source_file':record['source_file'],'source_line':record['source_line']}


def build(canonical, requests, dispositions, attempts, raw_results, review_queue, transport_authorizations=None):
    transport_authorizations=transport_authorizations or {}
    byid={r['case_id']:r for r in requests};owned={i:r['case_id'] for r in requests for i in r['owned_ids']}
    if len(owned)!=sum(len(r['owned_ids']) for r in requests):raise ValueError('duplicate_ownership')
    if len({a['case_id'] for a in attempts})!=len(attempts) or set(byid)!={a['case_id'] for a in attempts}:raise ValueError('attempt_coverage')
    local={d['message_id']:d for d in dispositions}
    if set(local)!=set(canonical) or len(local)!=len(dispositions):raise ValueError('disposition_coverage')
    decisions={};groups=[];all_context=set();raw_hashes={}
    for attempt in attempts:
        case_id=attempt['case_id'];spec=byid[case_id];raw=raw_results[case_id]
        if attempt['reserve']!=run.reserve(spec):raise ValueError('reservation_mismatch')
        if raw['body_sha256']!=spec['body_sha256']:raise ValueError('raw_request_hash')
        if spec['body_sha256']!=prep.digest(spec['body']):raise ValueError('request_body_hash')
        raw_hashes[case_id]=prep.digest(raw)
        if raw.get('http_status') is None:
            if case_id not in transport_authorizations:raise ValueError('unacknowledged_transport')
            if raw.get('transport_error')!='ConnectionError' or attempt['status']!='error' or attempt.get('actual_cost') is not None:raise ValueError('transport_state')
            for ident in spec['owned_ids']:decisions[ident]={'status':'transport_unresolved','origin':'transport','reason_category':'unknown_paid_transport','model_decision':None}
            continue
        errors=policy.classify(spec,raw)
        if errors:
            queue=review_queue.get(case_id)
            if not queue or queue['error_codes']!=errors or queue['owned_ids']!=spec['owned_ids'] or attempt['status']!='error':raise ValueError('review_queue_consistency')
            for ident in spec['owned_ids']:decisions[ident]={'status':'invalid_model_review','origin':'whole_case_quarantine','reason_category':errors,'model_decision':None}
            continue
        if attempt['status']!='complete' or case_id in review_queue:raise ValueError('valid_attempt_state')
        envelope=run.strict_json(raw['response_text']);output=run.strict_json(envelope['choices'][0]['message']['content'])
        for ident in spec['owned_ids']:
            decision=output['decisions'][str(ident)]
            decisions[ident]={'status':{'include':'candidate_include','exclude':'candidate_exclude','review':'semantic_review'}[decision['decision']],
                              'origin':'model_valid_proposal','reason_category':decision['decision'],'model_decision':decision}
        for kind in ['document_groups','review_groups']:
            for index,group in enumerate(output[kind]):
                members=group['message_ids'];derived=[]
                for ident in members:
                    parent=canonical[ident]['record']['reply_to']
                    if parent is not None and parent not in members:
                        source=canonical.get(parent)
                        derived.append({'child_id':ident,'parent_id':parent,'relation':'source_direct_reply',
                                        'state':canonical[ident]['reply']['parent_state'],
                                        'child_provenance':provenance(canonical[ident]),'parent_provenance':provenance(source) if source else None})
                context=set(group['context_ids'])|{r['parent_id'] for r in derived};all_context.update(context)
                identifier='draft-'+prep.digest({'case_id':case_id,'kind':kind,'index':index,'members':[provenance(canonical[i]) for i in members]})[:24]
                groups.append({'draft_id':identifier,'packet_id':case_id,'kind':kind,'model_group':group,
                               'member_references':[provenance(canonical[i]) for i in members],
                               'sections':[{'section_index':n,'original_text_ref':provenance(canonical[i]),'text_transform':'none'} for n,i in enumerate(members)],
                               'derived_context_references':derived,'context_ids':sorted(context),
                               'context_references':[{'id':i,'provenance':provenance(canonical[i]) if i in canonical else None,'state':'canonical' if i in canonical else 'outside_or_missing','promoted':False} for i in sorted(context)],'accepted':False})
    if set(review_queue)-set(byid):raise ValueError('unknown_review_case')
    rows=[];inventory=[]
    for ident,message in sorted(canonical.items()):
        state=decisions.get(ident)
        if state is None:
            disposition=local[ident]['status']
            mapping={'accepted_assignment_preserved':('accepted_assignment','accepted_store'),'local_review_unread_media':('unread_media_review','deterministic_metadata')}
            if disposition not in mapping:raise ValueError('unhandled_eligible_id')
            status,origin=mapping[disposition];state={'status':status,'origin':origin,'reason_category':disposition,'model_decision':None}
        row={'message_id':ident,'provenance':provenance(message),'source_role':message['source_role'],
             'decision_origin':state['origin'],'model_decision':state['model_decision'],'effective_proposed_status':state['status'],
             'reason_category':state['reason_category'],'packet_id':local[ident]['packet_id'],
             'reply_reference':message['reply'],'media':message['attachment'],'original_text_ref':provenance(message),'accepted_mutation':False}
        rows.append(row)
        if state['status'] in ['semantic_review','invalid_model_review','unread_media_review','transport_unresolved']:
            categories=[state['status']]
            if message['reply']['parent_state'] not in ['none','canonical']:categories.append('parent_'+message['reply']['parent_state'])
            if message['attachment']['attachment_presence'] is True:categories.append('unread_attachment')
            if state['model_decision']:
                categories.extend('flag_'+f for f in state['model_decision']['flags'])
            inventory.append({'message_id':ident,'categories':categories,'packet_id':row['packet_id'],'text_ref':row['original_text_ref']})
    rows_by_id={r['message_id']:r for r in rows}
    for group in groups:
        for dependency in group['context_references']:
            ident=dependency['id'];parent=rows_by_id.get(ident)
            dependency['effective_proposed_status']=parent['effective_proposed_status'] if parent else 'outside_or_missing'
            dependency['media']=parent['media'] if parent else None
            dependency['reply_reference']=parent['reply_reference'] if parent else None
            dependency['derived_parent_states']=sorted({r['state'] for r in group['derived_context_references'] if r['parent_id']==ident})
    include_ids={r['message_id'] for r in rows if r['effective_proposed_status']=='candidate_include'}
    review_ids={r['message_id'] for r in rows if r['effective_proposed_status']=='semantic_review'}
    for kind,expected in [('document_groups',include_ids),('review_groups',review_ids)]:
        members=[ref['id'] for g in groups if g['kind']==kind for ref in g['member_references']]
        if set(members)!=expected or len(members)!=len(set(members)):raise ValueError('group_coverage')
    review_owned={r['message_id'] for r in inventory}
    summary={'eligible_ids':len(rows),'statuses':dict(Counter(r['effective_proposed_status'] for r in rows)),
             'groups':dict(Counter(g['kind'] for g in groups)),'candidate_original_text_chars':sum(len(canonical[i]['record']['text']) for i in include_ids),
             'review_original_text_chars':sum(len(canonical[i]['record']['text']) for i in review_owned),
             'candidate_text_utf8_bytes':sum(len(canonical[i]['record']['text'].encode()) for i in include_ids),
             'deduplicated_context_ids':len(all_context),'deduplicated_context_chars':sum(len(canonical[i]['record']['text']) for i in all_context if i in canonical),
             'candidate_groups_with_review_dependencies':sum(any(d['effective_proposed_status'] not in ['accepted_assignment','candidate_include'] for d in g['context_references']) for g in groups if g['kind']=='document_groups'),
             'candidate_context_occurrences_by_status':dict(Counter(d['effective_proposed_status'] for g in groups if g['kind']=='document_groups' for d in g['context_references'])),
             'review_categories':dict(Counter(c for r in inventory for c in r['categories'])),'accepted_mutations':0}
    return {'rows':rows,'groups':groups,'review_inventory':inventory,'summary':summary,'raw_content_hashes':raw_hashes}


def publish(directory,identity,result,preview):
    manifest={'version':VERSION,'identity':identity,'summary':result['summary'],'accepted_mutations':False}
    content={'rows.jsonl':b''.join(prep.encoded(r)+b'\n' for r in result['rows']),
             'groups.json':prep.encoded(result['groups'])+b'\n','review-inventory.json':prep.encoded(result['review_inventory'])+b'\n',
             'preview.md':preview.encode(),'accepted-notes.json':prep.encoded(result.get('notes',{}))+b'\n'}
    manifest['artifacts']={k:hashlib.sha256(v).hexdigest() for k,v in content.items()}
    content['manifest.json']=prep.encoded(manifest)+b'\n'
    if directory.is_symlink():raise ValueError('symlink_generation')
    directory.mkdir(mode=0o700,exist_ok=True);directory.chmod(0o700)
    with (directory/'.lock').open('a') as lock:
        (directory/'.lock').chmod(0o600)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for name,raw in content.items():
            path=directory/name
            if path.is_symlink() or path.exists() and path.read_bytes()!=raw:raise ValueError('changed_generation')
        for name,raw in content.items():
            path=directory/name
            if path.exists():continue
            fd,temp=tempfile.mkstemp(dir=directory)
            try:
                with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                os.replace(temp,path)
            finally:Path(temp).unlink(missing_ok=True)
    return manifest


def main():
    os.umask(0o077);cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--run-name',default='selection-proposals-v3');args=cli.parse_args()
    if Path(args.run_name).name!=args.run_name:raise ValueError('private_directory_only')
    evidence_path=prep.PRIVATE/'selection-final-verification.json';evidence=run.strict_json(evidence_path.read_text())
    ledger_path=run.ROOT/'ledger.json';queue_path=policy.QUEUE
    if not evidence['coverage_verified'] or evidence['request_manifest_sha256']!=run.EXPECTED or evidence['ledger_sha256']!=prep.file_hash(ledger_path) or evidence['queue_sha256']!=prep.file_hash(queue_path):raise ValueError('final_evidence_mismatch')
    requests=run.load();source,canonical,_=prep.load_packets(prep.PRIVATE/'selection-packets-v1')
    protected={path:prep.file_hash(Path(path)) for path in source['identity']['accepted_guard_sha256']}
    if protected!=source['identity']['accepted_guard_sha256']:raise ValueError('accepted_snapshot_changed')
    request_manifest=run.strict_json((prep.PRIVATE/'selection-requests-v2/manifest.json').read_text())
    ledger_sha=prep.file_hash(ledger_path);queue_sha=prep.file_hash(queue_path)
    ledger=run.strict_json(ledger_path.read_text());queue=run.strict_json(queue_path.read_text());raw_paths={a['case_id']:run.ROOT/(a['case_id']+'.json') for a in ledger['attempts']}
    raw_sha={i:prep.file_hash(p) for i,p in raw_paths.items()}
    for ident,entry in queue['cases'].items():
        if entry['raw_sha256']!=raw_sha.get(ident):raise ValueError('queue_raw_hash')
    raws={i:run.strict_json(p.read_text()) for i,p in raw_paths.items()}
    transport_authorizations={}
    for event in ledger.get('transport_deferrals',[]):
        ack=event['acknowledgment'];ident=ack['case_id']
        expected={'case_id':ident,'request_manifest_sha256':run.EXPECTED,'raw_sha256':raw_sha[ident],'transport_error':'ConnectionError','http_status':None,'disposition':'transport_unresolved','no_retry':True}
        if ack!=expected or ack['no_retry'] is not True:raise ValueError('transport_ack_mismatch')
        transport_authorizations[ident]=ack
    result=build(canonical,requests,request_manifest['dispositions'],ledger['attempts'],raws,queue['cases'],transport_authorizations)
    module=packets.load_parser(packets.SOL/'corpus.py')
    with sqlite3.connect((packets.SOL/'private/corpus.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as conn:
        notes=[]
        for key,version,record_json in conn.execute('SELECT source_key,version_hash,record_json FROM accepted'):
            record=json.loads(record_json)
            if record.get('source_kind')=='note' or str(key).startswith('note:'):
                notes.append({'source_key':key,'version_hash':version,'record':record,'proposal':False,'state':'active_accepted'})
        inactive=conn.execute('SELECT COUNT(*) FROM accepted_history').fetchone()[0]
        inactive_note_versions=conn.execute('SELECT COUNT(*) FROM note_versions n LEFT JOIN accepted a ON n.source_key=a.source_key AND n.version_hash=a.version_hash WHERE a.source_key IS NULL').fetchone()[0]
        result['notes']={'active_notes':notes,'inactive_accepted_history_count':inactive,'inactive_note_versions_count':inactive_note_versions,'proposal':False}
    preview=['# Inert proposal preview\n\nКорпус не принят. Context отдельно; исходные тексты без изменения.\n']
    for group in result['groups']:
        preview.append('\n## '+group['draft_id']+' / '+group['kind']+'\n')
        for ref in group['member_references']:
            preview.append('\n### ID '+str(ref['id'])+'\n'+module.inert_markdown(canonical[ref['id']]['record']['text'])+'\n')
    for group in result['groups']:
        if group['context_references']:preview.append('\n## '+group['draft_id']+' context (not candidate text)\n')
        for dependency in group['context_references']:
            ident=dependency['id'];preview.append('\n'+module.inert_markdown(prep.encoded(dependency).decode())+'\n')
            if ident in canonical:preview.append(module.inert_markdown(canonical[ident]['record']['text'])+'\n')
    for note in result['notes']['active_notes']:
        preview.append('\n## Active accepted note (not a Telegram proposal)\n'+module.inert_markdown(note['record'].get('text',''))+'\n')
    if prep.file_hash(ledger_path)!=ledger_sha or prep.file_hash(queue_path)!=queue_sha:raise ValueError('run_state_changed')
    if protected!={path:prep.file_hash(Path(path)) for path in protected} or raw_sha!={i:prep.file_hash(p) for i,p in raw_paths.items()}:raise ValueError('inputs_changed')
    identity={'builder_sha256':prep.file_hash(Path(__file__)),'verification_sha256':prep.file_hash(evidence_path),'request_manifest_sha256':run.EXPECTED,
              'packet_manifest_sha256':prep.file_hash(prep.PRIVATE/'selection-packets-v1/manifest.json'),'ledger_sha256':prep.file_hash(ledger_path),'queue_sha256':prep.file_hash(queue_path),'raw_sha256':raw_sha,'accepted_guard_sha256':protected}
    publish(prep.PRIVATE/args.run_name,identity,result,'\n'.join(preview))
    print(json.dumps({'summary':result['summary'],'active_notes':len(result['notes']['active_notes']),'inactive_history':inactive,'inactive_note_versions':inactive_note_versions,'manifest_sha256':prep.file_hash(prep.PRIVATE/args.run_name/'manifest.json')}))

if __name__=='__main__':main()
