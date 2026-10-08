"""Offline derived reply context; model output and paid records remain immutable."""
import json
from collections import Counter
from pathlib import Path
import run_selection_requests as run
import prepare_selection_requests as prep


def audit(spec, raw, canonical):
    result={'case_id':spec['case_id'],'paid_response_received':raw.get('http_status')==200,
            'model_output':None,'model_valid':False,'local_disposition':'review_required',
            'validation_errors':[],'derived_context_references':[],'manual_notes':[]}
    try:
        envelope=run.strict_json(raw['response_text'])
        result['model_output']=run.strict_json(envelope['choices'][0]['message']['content'])
    except (ValueError,KeyError,IndexError,TypeError):
        result['validation_errors'].append('output_parse_error');return result
    output=result['model_output']
    try:run.process(spec,raw)
    except Exception as error:
        result['validation_errors'].append(str(error) if isinstance(error,ValueError) else type(error).__name__)
        try:result['validation_errors'].extend(run.context_guard(spec,output))
        except (KeyError,TypeError,ValueError):pass
    else:
        result['model_valid']=True;result['local_disposition']='proposal_pending_manual_review'
    if not isinstance(output,dict):return result
    decisions=output.get('decisions',{})
    for field in ['document_groups','review_groups']:
        groups=output.get(field,[])
        if not isinstance(groups,list):continue
        for index,group in enumerate(groups):
            if not isinstance(group,dict) or not isinstance(group.get('message_ids'),list):continue
            members=group['message_ids']
            for ident in members:
                if type(ident) is not int:continue
                message=canonical.get(ident)
                if not message:continue
                parent=message['record']['reply_to']
                if parent is None or parent in members:continue
                record=canonical.get(parent)
                decision=decisions.get(str(parent),{}) if isinstance(decisions,dict) else {}
                result['derived_context_references'].append({
                    'group_kind':field,'group_index':index,'child_id':ident,'parent_id':parent,
                    'relation':'source_direct_reply','parent_state':'canonical' if record else 'missing',
                    'parent_model_decision':decision.get('decision') if isinstance(decision,dict) else None,
                    'already_explicit':parent in (group.get('context_ids') if isinstance(group.get('context_ids'),list) else []),
                    'child_provenance':{'version_hash':message['version_hash'],'text_sha256':message['text_sha256']},
                    'parent_provenance':({'version_hash':record['version_hash'],'text_sha256':record['text_sha256']} if record else None)})
    return result


def main():
    rows=run.load();byid={r['case_id']:r for r in rows}
    _,canonical,_=prep.load_packets(prep.PRIVATE/'selection-packets-v1')
    ledger_path=run.ROOT/'ledger.json';ledger=run.strict_json(ledger_path.read_text())
    raw_paths=[run.ROOT/(a['case_id']+'.json') for a in ledger['attempts']]
    protected=[ledger_path]+raw_paths
    before={p.name:prep.file_hash(p) for p in protected if p.exists()}
    cases=[]
    for attempt in ledger['attempts']:
        path=run.ROOT/(attempt['case_id']+'.json')
        if path.exists():case=audit(byid[attempt['case_id']],run.strict_json(path.read_text()),canonical)
        else:case={'case_id':attempt['case_id'],'model_valid':False,'local_disposition':'review_required','validation_errors':['missing_response'],'derived_context_references':[],'model_output':None,'manual_notes':[],'paid_response_received':False}
        case['attempt_status']=attempt['status'];cases.append(case)
    after={p.name:prep.file_hash(p) for p in protected if p.exists()}
    if before!=after:raise ValueError('paid_records_changed')
    summary={'attempts':len(cases),'attempt_statuses':dict(Counter(c['attempt_status'] for c in cases)),
             'paid_response_received':sum(c['paid_response_received'] for c in cases),
             'model_valid':sum(c['model_valid'] for c in cases),
             'local_dispositions':dict(Counter(c['local_disposition'] for c in cases)),
             'derived_references':sum(len(c['derived_context_references']) for c in cases),
             'raw_and_ledger_unchanged':True}
    target=prep.PRIVATE/'selection-pilot-audit-v1.json'
    run.write(target,{'version':1,'request_manifest_sha256':run.EXPECTED,'auditor_sha256':prep.file_hash(Path(__file__)),
                      'protected_hashes_before':before,'protected_hashes_after':after,'summary':summary,'cases':cases,'accepted_proposals':False})
    print(json.dumps({'summary':summary,'audit_sha256':prep.file_hash(target)}))

if __name__=='__main__':main()
