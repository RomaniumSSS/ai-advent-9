"""Synthetic stratification, exact text, context boundary and immutable repeat."""
import tempfile
from pathlib import Path
import prepare_selection_review as p

canonical={};rows=[];groups=[]
for i in range(1,46):
 text=('🧪 ``` <script> synthetic\n'*(i%5+1))
 canonical[i]={'record':{'text':text,'reply_to':None},'reply':{'parent_id':None,'parent_state':'none'},'source_role':'discussion','attachment':{'attachment_presence':False,'content_read':False}}
 status='candidate_include' if i<=20 else 'candidate_exclude' if i<=35 else 'semantic_review'
 if i==38:status='unread_media_review'
 rows.append({'message_id':i,'provenance':{'id':i,'text_sha256':p.prep.digest(text),'version_hash':str(i)},'effective_proposed_status':status,'model_decision':{'flags':['mixed_content'] if i==15 else [],'reason':'bot model explanation' if i==21 else 'synthetic'}})
for i in range(1,21):
 deps=[]
 if i<=10:
  ident=36+(i%3);status={36:'semantic_review',37:'candidate_exclude',38:'unread_media_review'}[ident]
  deps=[{'id':ident,'effective_proposed_status':status}]
  if i==1:deps.append({'id':99,'effective_proposed_status':'outside_or_missing'})
 groups.append({'draft_id':'g'+str(i),'packet_id':'p'+str(i),'kind':'document_groups','member_references':[{'id':i}],
                'model_group':{'message_ids':[i],'context_ids':[],'reason':'synthetic proposal'},'context_ids':[d['id'] for d in deps],'context_references':deps,'derived_context_references':[]})
a=p.prepare(rows,groups,canonical);assert a==p.prepare(rows,groups,canonical)
assert a['summary']['strata']=={'dependency':10,'clean_include':5,'exclude':5}
assert a['summary']['unique_message_ids']<=120 and a['summary']['unique_chars']<=60000
assert any(c['sampling_reason']=='mixed_model_flag_inspection' for c in a['cases'])
def has_text_key(value):
 if isinstance(value,dict):return 'text' in value or any(has_text_key(v) for v in value.values())
 if isinstance(value,list):return any(has_text_key(v) for v in value)
 return False
assert not has_text_key(a['inventory'])
for c in a['cases']:
 for m in c['members']+c['context']:assert m['text']==canonical[m['id']]['record']['text']
 assert all(m['context_only'] for m in c['context'])
 assert all(not m['context_only'] for m in c['members'])
with tempfile.TemporaryDirectory() as d:
 root=Path(d)/'sample';p.publish(root,{'sha':'synthetic'},a)
 before={x.name:x.read_bytes() for x in root.iterdir() if x.name!='.lock'};p.publish(root,{'sha':'synthetic'},a)
 assert all((root/n).read_bytes()==v for n,v in before.items())
 try:p.publish(root,{'sha':'changed'},a)
 except ValueError:pass
 else:raise AssertionError('changed source overwritten')
 assert root.stat().st_mode&0o777==0o700 and all(x.stat().st_mode&0o777==0o600 for x in root.iterdir())
print('PASS:seeded20 strata/categorycoverage,wholetextUnicode,contextnotpromoted,refs-only inventory,limits,repeat/sourceidentitydrift/private permissions;no API')
import copy
oversized=copy.deepcopy(canonical);oversized[11]['record']['text']='X'*70000
limited=p.prepare(rows,groups,oversized)
assert all(11 not in c['member_ids'] for c in limited['cases']) and limited['summary']['budget_rejected_unique_cases']>0
assert len(limited['cases'])==20 and limited['summary']['unique_chars']<=60000
assert any(c.get('model_group_proposal',{}).get('reason')=='synthetic proposal' for c in a['cases'])
assert all('model_decision_proposal' in m for c in a['cases'] for m in c['members'])
print('PASS:oversized wholecase skipped without truncation,model reasons/flags preserved')
