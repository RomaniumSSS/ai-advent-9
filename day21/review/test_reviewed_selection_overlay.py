"""Synthetic proposal changes preserve source model output and ownership."""
import copy,tempfile
from pathlib import Path
import build_reviewed_selection_overlay as b

rows=[];canonical={}
for i in range(1,7):
 p={'id':i,'version_hash':str(i),'text_sha256':'t'+str(i)}
 rows.append({'message_id':i,'provenance':p,'effective_proposed_status':'candidate_include','decision_origin':'model_valid_proposal','model_decision':{'decision':'include','reason':'synthetic','flags':[]},'media':{},'reply_reference':{'parent_id':1 if i==2 else None}})
 canonical[i]={'record':{'reply_to':1 if i==2 else None},'reply':{'parent_state':'available'}}
def group(ident,ids):return {'draft_id':ident,'kind':'document_groups','member_references':[rows[i-1]['provenance'] for i in ids],'model_group':{'message_ids':ids,'context_ids':[],'reason':'synthetic original'},'context_ids':[]}
groups=[group('replace',[1,2]),group('remove',[3,4]),group('keep',[5,6])]
review={'proposed_status_changes':[{'message_id':3,'from':'candidate_include','proposed_to':'semantic_review','provenance':rows[2]['provenance'],'case_id':'s','reason':'synthetic','applied':False},
 {'message_id':4,'from':'candidate_include','proposed_to':'candidate_exclude','provenance':rows[3]['provenance'],'case_id':'s','reason':'synthetic','applied':False}],
 'proposed_group_replacement':{'original_case_id':'replace','groups':[{'member_ids':[1],'context_ids':[]},{'member_ids':[2],'context_ids':[1],'related_continuation_ids':[5]}]}}
before=copy.deepcopy((rows,groups));new_rows,new_groups,summary=b.overlay(rows,groups,review,canonical,'syntheticsha')
assert (rows,groups)==before and summary['status_changes']==2
assert new_rows[2]['model_decision']==rows[2]['model_decision'] and new_rows[2]['effective_proposed_status']=='semantic_review'
assert all(4 not in [r['id'] for r in g['member_references']] for g in new_groups)
assert any(g['kind']=='review_groups' and g['origin']=='root_review_proposal' for g in new_groups)
assert all(g['model_group']==groups[0]['model_group'] for g in new_groups if g.get('source_group_references',[{}])[0].get('draft_id')=='replace')
assert any(g.get('related_continuation_references',[{}])[0].get('reference_only') for g in new_groups if g.get('related_continuation_references'))
bad=copy.deepcopy(review);bad['proposed_status_changes'][0]['provenance']={'wrong':True}
try:b.overlay(rows,groups,bad,canonical,'sha')
except ValueError:pass
else:raise AssertionError('provenance drift')
with tempfile.TemporaryDirectory() as d:
 root=Path(d)/'overlay';objects={'rows.json':new_rows,'groups.json':new_groups,'diff-summary.json':summary}
 b.publish(root,objects);before={p.name:p.read_bytes() for p in root.iterdir() if p.name!='.lock'};b.publish(root,objects)
 assert all((root/n).read_bytes()==v for n,v in before.items())
 try:b.publish(root,{'rows.json':[]})
 except ValueError:pass
 else:raise AssertionError('overwrite')
 assert root.stat().st_mode&0o777==0o700 and all(p.stat().st_mode&0o777==0o600 for p in root.iterdir())
print('PASS:changedstatuses/rootreviewgroups,fullownership/uniquegroupcoverage,rawmodelgroupsunchanged,continuationonlyref,provenancedrift,repeat/immutable/privacy;no API')

paired=copy.deepcopy(review)
paired['proposed_status_changes'][1]['proposed_to']='semantic_review'
with_explicit=copy.deepcopy(groups);with_explicit[1]['context_ids']=[1]
new_rows,new_groups,summary=b.overlay(rows,with_explicit,paired,canonical,'sha')
reviewgroups=[g for g in new_groups if g['kind']=='review_groups']
assert len(reviewgroups)==1 and [r['id'] for r in reviewgroups[0]['member_references']]==[3,4]
assert 1 in reviewgroups[0]['context_ids']
assert reviewgroups[0]['model_group']==groups[1]['model_group']
assert 5 not in reviewgroups[0]['context_ids'] and 6 not in reviewgroups[0]['context_ids']
print('PASS:movedpair stays same sourcegroup,explicit ancestor context preserved,no unrelated thread context')
