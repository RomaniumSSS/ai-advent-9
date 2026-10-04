"""Offline planning and evidence checks; no UI/provider/SSH or auth/ledger writes."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from budget import proposal
from scenario_runner import validate_scenarios, mechanical_check, SCENARIOS, preflight
from common import MODEL, estimate, packed
from privacy import private_output
import tempfile
from conversation import MESSAGES_BYTES


class PreparationTest(unittest.TestCase):
    def setUp(self):self.plan=validate_scenarios(json.loads(SCENARIOS.read_text()))

    def test_two_distinct_twelve_turn_scenarios_and_memory_changes(self):
        self.assertEqual([len(x['turns']) for x in self.plan['scenarios']],[12,12])
        a,b=self.plan['scenarios']
        self.assertNotEqual(a['initial_state']['goal'],b['initial_state']['goal'])
        self.assertEqual((a['scope'],b['scope']),('public','all'))
        self.assertTrue(any(t.get('restart_after') for s in self.plan['scenarios'] for t in s['turns']))
        for scenario in self.plan['scenarios']:
            self.assertGreaterEqual(len({t['intent'] for t in scenario['turns']}),8)
            self.assertEqual(len({t['question'] for t in scenario['turns']}),12)
            self.assertIn('absent_fact',{t['intent'] for t in scenario['turns']})
            self.assertIn('source_quote_check',{t['intent'] for t in scenario['turns']})
            changes=[t['state_before'] for t in scenario['turns'] if 'state_before' in t]
            self.assertTrue(any(c['goal']!=scenario['initial_state']['goal'] for c in changes))
            self.assertTrue(any(c['clarifications']!=scenario['initial_state']['clarifications'] for c in changes))
            self.assertTrue(any(c['constraints']!=scenario['initial_state']['constraints'] for c in changes))
            self.assertTrue(any(t.get('refresh_after') for t in scenario['turns']))

    def test_budget_is_conservative_under_runtime_reserve_cap(self):
        estimate_plan=proposal(self.plan)
        self.assertEqual(estimate_plan['maximum_provider_calls'],24)
        self.assertEqual(estimate_plan['extra_video_provider_calls'],0)
        self.assertEqual(estimate_plan['reserve_upper_estimate_total_usd'],'0.10816512')
        self.assertGreaterEqual(Decimal(estimate_plan['proposed_new_budget_usd']),Decimal(estimate_plan['reserve_upper_estimate_total_usd']))
        msgs=[{'role':'user','content':''}]
        msgs[0]['content']='x'*(MESSAGES_BYTES-len(packed(msgs)))
        actual=estimate(msgs,{'prompt':.14/1e6,'completion':.42/1e6})
        self.assertAlmostEqual(actual,float(estimate_plan['reserve_upper_estimate_per_call_usd']))
        self.assertEqual(estimate_plan['approval_status'],'NOT_GRANTED')

    def test_nonpublic_or_incomplete_plan_rejected(self):
        wrong=copy.deepcopy(self.plan);wrong['scenarios'][0]['allowed_document_ids']=['private:note']
        with self.assertRaisesRegex(ValueError,'only_public'):validate_scenarios(wrong)
        wrong=copy.deepcopy(self.plan);wrong['scenarios'][0]['turns']=wrong['scenarios'][0]['turns'][:9]
        with self.assertRaisesRegex(ValueError,'scenario_length'):validate_scenarios(wrong)

    def result(self):
        state={'version':1,'goal':'Понять требования дня 18','clarifications':[],'constraints':[]}
        chunk={'chunk_id':'c1','document_id':'assignment:18','source':'assignment','text':'Факт задания.'}
        answer={'answer':'Факт задания.','sources':[{'source':'assignment','chunk_id':'c1'}],
                'quotes':[{'chunk_id':'c1','text':'Факт задания.'}]}
        return {'id':'r1','chat_id':'own','scope':'public','stage':'terminal','status':'verified','saved':True,
                'cost':.00001,'task_state':state,'conversation':{'search_performed':True,'history':[]},
                'search':{'trace':{'selected':[chunk], 'candidates':[chunk], 'removed':[]}},
                'generation':{'started':True,'transmission':'confirmed','transmitted_chunk_ids':['c1'],'transmitted_chunks':[chunk]},
                'raw_answer':json.dumps(answer),'answer':answer}

    def test_private_output_rejects_outside_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'private';root.mkdir()
            outside=Path(temporary)/'public';outside.mkdir()
            (root/'escape').symlink_to(outside,target_is_directory=True)
            self.assertEqual(private_output(root/'safe',root),(root/'safe').resolve())
            for path in (outside/'raw',root/'..'/'raw',root/'escape'/'raw',root):
                with self.assertRaisesRegex(ValueError,'output_must_be_inside'):
                    private_output(path,root)

    def test_read_only_preflight_checks_both_identities_before_post(self):
        expected='a'*64
        class Request:
            def __init__(inner,bad_scope=None):inner.calls=[];inner.bad_scope=bad_scope
            def get(inner,url):
                inner.calls.append(('GET',url))
                scope='public' if ':8054/' in url else 'all'
                state={'public_only':scope=='public','test_fixture':False,'cloud':{
                    'enabled':True,'scopes':[scope],'budget':.06,'charged_or_reserved':0,
                    'identity_sha256':'b'*64 if scope==inner.bad_scope else expected}}
                class Response:
                    status=200
                    def json(self):return state
                return Response()
            def post(inner,*args,**kwargs):inner.calls.append(('POST',args));raise AssertionError('preflight attempted POST')
        urls={'public':'http://127.0.0.1:8054','all':'http://127.0.0.1:8053'}
        for scope in ('public','all'):
            request=Request(scope)
            with self.assertRaisesRegex(ValueError,'preflight_frozen_identity_mismatch'):
                preflight(request,urls,'live',expected,self.plan,[])
            self.assertTrue(all(method=='GET' for method,_ in request.calls))
        request=Request()
        self.assertEqual(set(preflight(request,urls,'live',expected,self.plan,[])),{'public','all'})
        self.assertEqual([method for method,_ in request.calls],['GET','GET'])

    def test_full_scope_requires_exact_frozen_identity(self):
        item=self.result();item['scope']='all';item['search']['identity']={'frozen':'synthetic'}
        digest=__import__('hashlib').sha256(packed(item['search']['identity'])).hexdigest()
        item['authorization']={'identity_sha256':digest}
        item['search']['trace']['selected'][0]['document_id']='discussion:synthetic'
        self.assertEqual(mechanical_check(item,'own',set(),item['task_state'],'all',digest)['mechanical'],'PASS')
        with self.assertRaisesRegex(ValueError,'frozen_identity_mismatch'):
            mechanical_check(item,'own',set(),item['task_state'],'all','0'*64)
        item['authorization']['identity_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'authorization_identity_mismatch'):
            mechanical_check(item,'own',set(),item['task_state'],'all',digest)

    def test_evidence_never_claims_semantic_pass(self):
        item=self.result()
        verdict=mechanical_check(item,'own',set(),item['task_state'])
        self.assertEqual(verdict,{'mechanical':'PASS','semantic':'NOT_REVIEWED'})

    def test_unknown_wrong_sources_foreign_history_and_stale_memory_rejected(self):
        for change,error in ((lambda x:x.update(status='unknown'),'stop_and_audit_unknown'),
             (lambda x:x['generation'].update(transmitted_chunk_ids=['other']),'invalid_verified_evidence'),
             (lambda x:x['search']['trace']['candidates'].append({'document_id':'private:note'}),'private_document'),
             (lambda x:x['conversation']['history'].append({'request_id':'foreign'}),'foreign_history'),
             (lambda x:x['task_state'].update(goal='OLD'),'wrong_task_snapshot')):
            item=self.result();expected=copy.deepcopy(item['task_state']);change(item)
            with self.assertRaisesRegex(ValueError,error):mechanical_check(item,'own',set(),expected)


if __name__=='__main__':
    with patch('requests.Session.request',side_effect=AssertionError('offline network forbidden')), patch('subprocess.run',side_effect=AssertionError('no external command in preparation tests')):
        unittest.main()
