"""Read saved private evidence and rebuild context/prompt; never run retrieval/provider."""
import argparse
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from common import packed, save
from conversation import build_context, prepare_generation, MESSAGES_BYTES
from answers import check_answer
from task_contract import format_errors
from privacy import private_output


def replay(run_dir,output):
    output=private_output(output)
    run_dir=private_output(run_dir)
    run=json.loads((run_dir/'run.json').read_text())
    history={}
    rows=[]
    for row in run['results']:
        name=row['scenario']+'-'+str(row['turn']).zfill(2)+'.json'
        item=json.loads((run_dir/name).read_text())
        own=history.setdefault(item['chat_id'],[])
        ctx=build_context(item['question'],item['task_state'],own,item['scope'])
        trace=copy.deepcopy(item['search']['trace'])
        prepare_generation(item['question'],ctx,trace)
        assert len(packed(trace['messages']))<=MESSAGES_BYTES
        assert all(m['request_id'] in {x['id'] for x in own} for m in ctx['history'])
        if name in ('learn-scheduler-05.json','rag-course-review-05.json','rag-course-review-12.json'):
            assert item['task_state']['goal'] in ctx['search_query']
        snapshots=item['generation'].get('transmitted_chunks',[])
        checked=check_answer(item.get('raw_answer',''),snapshots) if snapshots else None
        if name=='learn-scheduler-08.json' and item['status']=='unverified':
            assert checked and not checked['valid'] and 'source_not_in_context' in checked['errors']
        rows.append({'evidence_file':name,'scope':item['scope'],'original_status':item['status'],
                     'search_query_changed':ctx['search_query']!=item['conversation']['search_query'],
                     'new_search_rule':ctx['search_rule'],'task_state_version':ctx['task_state']['version'],
                     'messages_bytes':len(packed(trace['messages'])),
                     'saved_answer_validation':checked['valid'] if checked else None,
                     'saved_task_format_errors':format_errors(item.get('answer'),item['task_state']),
                     'new_context':ctx,'new_messages':trace['messages']})
        own.append(item)
    save(output,{'kind':'offline-context-prompt-replay','new_searches':0,'new_provider_calls':0,
                 'new_answer_semantics':'NOT_PROVEN','saved_answers_not_rewritten':True,'rows':rows})
    return {'turns':len(rows),'queries_changed':sum(r['search_query_changed'] for r in rows),
            'new_searches':0,'new_provider_calls':0,'new_answer_semantics':'NOT_PROVEN'}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with patch('requests.Session.request',side_effect=AssertionError('replay network forbidden')), patch('subprocess.run',side_effect=AssertionError('replay SSH forbidden')):
        print(json.dumps(replay(args.run_dir,args.output)))
