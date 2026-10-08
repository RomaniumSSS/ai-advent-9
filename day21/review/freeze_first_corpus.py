"""Первая ограниченная версия корпуса; исходное accepted-хранилище не изменяется."""
import json
import os
import sqlite3
from collections import Counter
from pathlib import Path
import prepare_selection_requests as prep
import prepare_selection_packets as packets
from run_local_sample import write

SOURCE_SHA='615d53241afc38a2a17cf27ba2c93919febfc9a5a6c62aa634748806543d7392'
REVIEW_SHA='2d9b28175b642f424e331b1fad8c4673f16f635971a9d2d890fb07d38071d07c'

def main():
    os.umask(0o077)
    base=prep.PRIVATE;source=base/'selection-reviewed-proposals-v2'
    assert prep.file_hash(source/'manifest.json')==SOURCE_SHA
    manifest=json.loads((source/'manifest.json').read_text())
    review_path=base/'selection-semantic-review-v1.json';assert prep.file_hash(review_path)==REVIEW_SHA
    review=json.loads(review_path.read_text())
    guards=manifest['protected_sha256']
    assert all(prep.file_hash(Path(p))==v for p,v in guards.items())
    assert all(prep.file_hash(source/n)==v for n,v in manifest['artifacts'].items())
    rows={r['message_id']:r for r in json.loads((source/'rows.json').read_text())}
    groups=[g for g in json.loads((source/'groups.json').read_text()) if g['kind']=='document_groups']
    _,canonical,_=prep.load_packets(base/'selection-packets-v1')
    keep={r['case_id'] for r in review['reviews'] if r['verdict']=='keep'}
    owners={r['id']:g['draft_id'] for g in groups for r in g['member_references']}
    held={g['draft_id']:'unresolved_context' for g in groups if g['draft_id'] not in keep and any(d['effective_proposed_status'] not in ['candidate_include','accepted_assignment'] for d in g['context_references'])}
    while True:
        extra={g['draft_id']:'context_group_deferred' for g in groups if g['draft_id'] not in keep and g['draft_id'] not in held and any(owners.get(d['id']) in held for d in g['context_references'])}
        if not extra:break
        held.update(extra)
    conn=sqlite3.connect((packets.SOL/'private/corpus.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    days={json.loads(raw)['message_id']:day for raw,day in conn.execute("SELECT a.record_json,d.day FROM accepted a JOIN decisions d ON a.source_key=d.source_key WHERE d.day IS NOT NULL")}
    notes=json.loads((base/'selection-proposals-v3/accepted-notes.json').read_text())['active_notes'];docs=[];selected=set()
    def document(doc_id,ids,kind,day=None,group=None):
        text='';members=[];sections=[]
        for ident in ids:
            m=canonical[ident];r=m['record'];start=len(text);separator='\n\n' if text else '';text+=separator+r['text']
            member=rows[ident]['provenance']|{k:r[k] for k in ['author','date','reply_to','links']};member['message_id']=ident;members.append(member)
            sections.append({'start_char':start,'end_char':len(text),'text_start_char':start+len(separator),'message_id':ident,'member_ids':[ident],'source_keys':[m['source_key']],'reply_to':r['reply_to']})
            assert ident not in selected;selected.add(ident)
        return {'document_id':doc_id,'source':kind,'title':f'Day {day}' if kind=='assignment' else f'Обсуждение {ids[0]}','day':day,'text':text,'members':members,'sections':sections,'context_references':group['context_references'] if group else [],'related_continuation_references':group.get('related_continuation_references',[]) if group else [],'source_group_id':group['draft_id'] if group else None,'context_reviewed_self_contained':bool(group and group['draft_id'] in keep),'release':'corpus-release-v1'}
    for ident,day in sorted(days.items(),key=lambda x:x[1]):
        assert rows[ident]['effective_proposed_status']=='accepted_assignment'
        docs.append(document('assignment:'+str(day),[ident],'assignment',day))
    for g in groups:
        if g['draft_id'] in held:continue
        ids=[r['id'] for r in g['member_references']]
        linked={canonical[i]['assignment_context_id'] for i in ids}-{None}
        day=days.get(next(iter(linked))) if len(linked)==1 else None
        docs.append(document('discussion:'+g['draft_id'],ids,'discussion',day,g))
    for n in notes:
        r=n['record'];docs.append({'document_id':'personal-note:understanding','source':'personal_note','title':r['section'],'day':None,'text':r['text'],'members':[{'source_key':n['source_key'],'version_hash':n['version_hash'],'source_file':r['source']}],'sections':[{'start_char':0,'end_char':len(r['text']),'member_ids':[],'source_keys':[n['source_key']],'reply_to':None}],'release':'corpus-release-v1'})
    chars=sum(len(d['text']) for d in docs);assert len(docs)==663 and len(selected)==1314 and len(notes)==1
    inventory=[{'message_id':i,'release_status':'selected' if i in selected else 'deferred_context' if r['effective_proposed_status']=='candidate_include' else r['effective_proposed_status'],'version_hash':r['provenance']['version_hash']} for i,r in sorted(rows.items())]
    summary={'documents':len(docs),'source_records':len(selected)+len(notes),'discussion_messages':len(selected)-len(days),'assignments':len(days),'notes':len(notes),'discussion_documents':len(docs)-len(days)-len(notes),'deferred_candidate_groups':len(held),'deferred_candidate_messages':sum(x['release_status']=='deferred_context' for x in inventory),'characters':chars,'page_estimate_method':'Unicode characters / 1800; A4 12pt line spacing1.5; estimate, not rendered pagination','estimated_pages':round(chars/1800,2),'minimum_30_pages_obvious':chars>=30*1800*1.2,'source_inventory':dict(Counter(x['release_status'] for x in inventory)),'old_accepted_store_mutated':False}
    objects={'documents.json':docs,'inventory.json':inventory,'deferred-groups.json':held,'volume.json':summary}
    hashes={n:prep.digest(v) for n,v in objects.items()}
    result={'version':1,'selection_policy':'include groups without unresolved dependencies; cascade deferral; reviewed self-contained keep cases exempt; accepted assignments and note preserved','authorization':'User accepted first limited corpus and main Day21 chain: да давай; doubtful records retained for future review','source_manifest_sha256':SOURCE_SHA,'review_sha256':REVIEW_SHA,'builder_sha256':prep.file_hash(Path(__file__)),'logical_hashes':hashes,'summary':summary,'source_guard_sha256':guards}
    objects['manifest.json']=result;target=base/'corpus-release-v1';target.mkdir(mode=0o700,exist_ok=True)
    for name,value in objects.items():
        path=target/name
        if path.exists():assert json.loads(path.read_text())==value,'immutable release changed'
        else:write(path,value)
    assert all(prep.file_hash(Path(p))==v for p,v in guards.items())
    print(json.dumps(summary,ensure_ascii=False));print('documents_file_sha256',prep.file_hash(target/'documents.json'))
if __name__=='__main__':main()
