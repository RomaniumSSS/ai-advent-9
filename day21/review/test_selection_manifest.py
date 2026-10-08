"""Synthetic coverage, context boundaries, quarantine, Unicode and immutable output."""
import copy
import tempfile
from pathlib import Path
from unittest.mock import patch
import build_selection_manifest as b
prep=b.prep

def msg(i,parent=None,text='Unicode 🧪 ``` <script>x</script> https://example.test'):
 record={'reply_to':parent,'text':text,'source_file':'synthetic','source_line':i}
 return {'message_id':i,'record':record,'source_key':'synthetic:'+str(i),'source_role':'discussion','version_hash':'v'+str(i),
         'text_sha256':prep.digest(text),'record_sha256':prep.digest(record),'reply':{'parent_id':parent,'parent_state':'available' if parent else 'none'},
         'attachment':{'attachment_presence':False,'attachment_type':'none','content_read':False}}
canonical={i:msg(i,parent) for i,parent in [(1,None),(2,1),(3,99),(4,None),(5,None)]}
output={'case_id':'synthetic','decisions':{'1':{'decision':'exclude','reason':'synthetic','flags':[]},'2':{'decision':'include','reason':'synthetic','flags':[]},'3':{'decision':'review','reason':'synthetic','flags':['mixed_content']}},
        'document_groups':[{'message_ids':[2],'context_ids':[],'reason':'synthetic'}],'review_groups':[{'message_ids':[3],'context_ids':[],'reason':'synthetic'}]}
requests=[{'case_id':'synthetic','owned_ids':[1,2,3],'body':{'max_tokens':1024},'body_sha256':prep.digest({'max_tokens':1024}),'input_token_conservative_bound':100,'output_token_cap':1024}]
attempts=[{'case_id':'synthetic','status':'complete','reserve':b.run.reserve(requests[0]),'actual_cost':.001}]
dispositions=[{'message_id':i,'packet_id':'synthetic','status':'request_owned' if i<4 else 'accepted_assignment_preserved' if i==4 else 'local_review_unread_media'} for i in canonical]
raw={'synthetic':{'body_sha256':requests[0]['body_sha256'],'http_status':200,'response_text':prep.encoded({'choices':[{'message':{'content':prep.encoded(output).decode()}}]}).decode()}}
with patch.object(b.policy,'classify',return_value=[]):result=b.build(canonical,requests,dispositions,attempts,raw,{})
assert len(result['rows'])==5 and result['summary']['statuses']['candidate_exclude']==1
assert result['groups'][0]['derived_context_references'][0]['parent_id']==1
assert result['rows'][0]['effective_proposed_status']=='candidate_exclude'
assert result['groups'][0]['context_references'][0]['effective_proposed_status']=='candidate_exclude'
assert result['groups'][1]['derived_context_references'][0]['parent_provenance'] is None
assert result['summary']['candidate_original_text_chars']==len(canonical[2]['record']['text'])
assert all(ref['id']!=1 for g in result['groups'] for ref in g['member_references'])
assert 'semantic_review' in result['review_inventory'][0]['categories'] and 'flag_mixed_content' in result['review_inventory'][0]['categories']
errors=['model_output_structural:review_groups_coverage'];quarantine={'synthetic':{'error_codes':errors,'owned_ids':[1,2,3]}}
bad_attempts=copy.deepcopy(attempts);bad_attempts[0]['status']='error'
with patch.object(b.policy,'classify',return_value=errors):bad=b.build(canonical,requests,dispositions,bad_attempts,raw,quarantine)
assert bad['groups']==[] and all(r['effective_proposed_status']=='invalid_model_review' for r in bad['rows'][:3])
assert output['decisions']['2']['decision']=='include'
for change in ['duplicate','rawhash','coverage','reserve']:
 req=copy.deepcopy(requests);r=copy.deepcopy(raw);a=copy.deepcopy(attempts);d=copy.deepcopy(dispositions)
 if change=='duplicate':req[0]['owned_ids'].append(1)
 elif change=='rawhash':r['synthetic']['body_sha256']='wrong'
 elif change=='reserve':a[0]['reserve']=0
 else:d.pop()
 try:
  with patch.object(b.policy,'classify',return_value=[]):b.build(canonical,req,d,a,r,{})
 except ValueError:pass
 else:raise AssertionError('drift accepted')
module=b.packets.load_parser(b.packets.SOL/'corpus.py');preview=module.inert_markdown(canonical[2]['record']['text'])
assert preview.startswith('````text\n') and canonical[2]['record']['text'] in preview
with tempfile.TemporaryDirectory() as directory:
 root=Path(directory)/'generation';identity={'synthetic':True}
 b.publish(root,identity,result,preview);before={p.name:p.read_bytes() for p in root.iterdir() if p.name!='.lock'}
 b.publish(root,identity,result,preview);assert all((root/n).read_bytes()==v for n,v in before.items())
 try:b.publish(root,{'changed':True},result,preview)
 except ValueError:pass
 else:raise AssertionError('immutable overwritten')
 assert root.stat().st_mode&0o777==0o700 and all(p.stat().st_mode&0o777==0o600 for p in root.iterdir())
print('PASS:full coverage,uniqueownership/groups,excludedparent notpromoted,missing provenance,invalidwholecase,Unicode exacttext/inertfence,sourcehash/reserve/drift,immutable repeat/private permissions;no API')
