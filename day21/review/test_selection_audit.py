"""Synthetic offline derived-context and immutable model output checks."""
import copy
import json
from unittest.mock import patch
import audit_selection_proposals as a
canonical={i:{'record':{'reply_to':parent},'version_hash':str(i),'text_sha256':str(i)} for i,parent in [(2,1),(3,99),(1,None)]}
output={'decisions':{'1':{'decision':'exclude'},'2':{'decision':'include'}},'document_groups':[{'message_ids':[2,3],'context_ids':[]}],'review_groups':[]}
raw={'http_status':200,'response_text':json.dumps({'choices':[{'message':{'content':json.dumps(output)}}]})}
before=copy.deepcopy(output)
with patch.object(a.run,'process',return_value=output):result=a.audit({'case_id':'synthetic'},raw,canonical)
assert result['model_output']==before and result['model_valid']
refs=result['derived_context_references'];assert refs[0]['parent_model_decision']=='exclude' and refs[1]['parent_state']=='missing'
with patch.object(a.run,'process',side_effect=ValueError('output_validation')),patch.object(a.run,'context_guard',return_value=['included_reply_unread_parent:2']):result=a.audit({'case_id':'synthetic'},raw,canonical)
assert result['model_output']==before and not result['model_valid'] and result['local_disposition']=='review_required'
assert a.audit({'case_id':'synthetic'},{'response_text':'bad'},canonical)['local_disposition']=='review_required'
print('PASS: excluded/missing direct-parent provenance, unchanged model output, context/strict failure review_required, malformed input')
