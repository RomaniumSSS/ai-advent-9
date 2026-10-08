"""Offline global-cap transitions; fake ledgers, no search/provider."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from budget import proposal
from common import save
from global_session import activate_public,activate_all,manual_ready,balance

ROOT=Path(__file__).resolve().parents[1]/'private'


class GlobalTest(unittest.TestCase):
    def setUp(self):
        ROOT.mkdir(exist_ok=True,mode=0o700);self.tmp=tempfile.TemporaryDirectory(dir=ROOT,prefix='global-unit-');self.root=Path(self.tmp.name)
        self.profile={'phase':'PLANNED','approved':True,'global_cap_usd':'0.10','initial_public_cap_usd':'0.07','scenario_sha256':'test','scopes':{}}
        for scope,port in [('public',8056),('all',8057)]:
            directory=self.root/scope;run=self.root/(scope+'-run');directory.mkdir();run.mkdir()
            save(directory/'authorization.json',{'approved':False,'budget':0,'scopes':[scope]});save(directory/'ledger.json',{'entries':[]})
            self.profile['scopes'][scope]={'data_dir':str(directory),'run_dir':str(run),'url':'http://127.0.0.1:'+str(port)}
        self.path=self.root/'profile.json';save(self.path,self.profile)
        self.listener=patch('global_session.no_listener');self.listener.start()
        self.provider=patch('requests.Session.request',side_effect=AssertionError('provider forbidden'));self.provider.start()

    def tearDown(self):self.provider.stop();self.listener.stop();self.tmp.cleanup()

    def complete(self,scope,cost):
        phase=self.profile['scopes'][scope]
        save(Path(phase['data_dir'])/'ledger.json',{'entries':[{'id':scope+str(i),'status':'completed','charged':cost,'cost_unknown':False} for i in range(15)]})
        save(Path(phase['run_dir'])/'run.json',{'status':'MECHANICAL_RUN_COMPLETE','current_action':None,'scenario_sha256':'test','results':[{'scope':scope,'generation_started':True} for _ in range(15)]})

    def test_exact_remainder_and_manual_same_ledger(self):
        activate_public(self.path);self.complete('public',.0002);activate_all(self.path)
        all_dir=Path(self.profile['scopes']['all']['data_dir']);auth=json.loads((all_dir/'authorization.json').read_text())
        self.assertEqual(Decimal(str(auth['budget'])),Decimal('.0970'))
        self.complete('all',.0003);before=(all_dir/'ledger.json').read_bytes();value=manual_ready(self.path)
        self.assertEqual(value['remaining_global_usd'],'0.0925');self.assertEqual((all_dir/'ledger.json').read_bytes(),before)
        state=json.loads(self.path.read_text());chat=json.loads((all_dir/('chat-'+state['manual_chat_id']+'.json')).read_text())
        self.assertEqual(chat['title'],'Мой чат');self.assertEqual(chat['task_state']['goal'],'')
        self.assertFalse(json.loads((Path(self.profile['scopes']['public']['data_dir'])/'authorization.json').read_text())['approved'])

    def test_unknown_and_live_public_prevent_transfer(self):
        activate_public(self.path);self.complete('public',.0002)
        ledger=Path(self.profile['scopes']['public']['data_dir'])/'ledger.json';value=json.loads(ledger.read_text());value['entries'][0]['status']='unknown';save(ledger,value)
        with self.assertRaisesRegex(ValueError,'ambiguous_spend'):activate_all(self.path)
        self.complete('public',.0002)
        with patch('global_session.no_listener',side_effect=ValueError('previous_paid_server_must_be_stopped')):
            with self.assertRaisesRegex(ValueError,'must_be_stopped'):activate_all(self.path)
        self.assertFalse(json.loads((Path(self.profile['scopes']['all']['data_dir'])/'authorization.json').read_text())['approved'])

    def test_zero_charge_existing_entry_not_fresh_and_cap_overflow(self):
        ledger=Path(self.profile['scopes']['public']['data_dir'])/'ledger.json';save(ledger,{'entries':[{'status':'completed','charged':0}]})
        with self.assertRaisesRegex(ValueError,'fresh_ledgers'):activate_public(self.path)
        profile=copy.deepcopy(self.profile);profile['global_cap_usd']='0.11';save(self.path,profile)
        with self.assertRaisesRegex(ValueError,'invalid_global_caps'):activate_public(self.path)

    def test_insufficient_worst_reserve_stop_and_changed_manual_cap(self):
        activate_public(self.path);self.complete('public',.003)
        with self.assertRaisesRegex(ValueError,'insufficient_all_phase'):activate_all(self.path)
        self.complete('public',.0002);activate_all(self.path);self.complete('all',.0003)
        auth_path=Path(self.profile['scopes']['all']['data_dir'])/'authorization.json';auth=json.loads(auth_path.read_text());auth['budget']=.10;save(auth_path,auth)
        with self.assertRaisesRegex(ValueError,'all_cap_changed'):manual_ready(self.path)

    def test_existing_zero_all_entry_and_ambiguous_phase_stop(self):
        activate_public(self.path);self.complete('public',.0002)
        all_ledger=Path(self.profile['scopes']['all']['data_dir'])/'ledger.json'
        save(all_ledger,{'entries':[{'id':'old-zero','status':'completed','charged':0,'cost_unknown':False}]})
        with self.assertRaisesRegex(ValueError,'fresh_all_ledger'):activate_all(self.path)
        save(all_ledger,{'entries':[]})
        manifest=Path(self.profile['scopes']['public']['run_dir'])/'run.json';run=json.loads(manifest.read_text());run['current_action']='ambiguous';save(manifest,run)
        with self.assertRaisesRegex(ValueError,'ambiguous_phase'):activate_all(self.path)

    def test_global_proposal_30_calls_not_guaranteed_at_worst_case(self):
        data=json.loads(Path(__file__).with_name('session15_scenarios.json').read_text());plan=proposal(data)
        self.assertEqual(plan['user_messages'],30);self.assertEqual(plan['proposed_new_budget_usd'],'0.10')
        self.assertEqual(plan['reserve_upper_estimate_total_usd'],'0.13520640');self.assertFalse(plan['worst_case_all_calls_guaranteed'])
        self.assertTrue(plan['manual_uses_same_all_ledger'])


if __name__=='__main__':unittest.main()
