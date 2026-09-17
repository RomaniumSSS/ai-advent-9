"""Все ответы ниже test doubles, не live evidence; сеть запрещена."""
import copy
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from live_budget import BudgetStop, digest, MODEL
from mass_checkpoint import ROOT, PRIOR_COST, load_cases
from mass_live import Campaign, telemetry
from mass_fixture import prepare,open_agent,snapshot


def response(text='неправильный безопасный ответ'):
    return {'id':'test-only-request','model':MODEL,'provider':'OpenInference',
            'choices':[{'message':{'content':text},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':100,'completion_tokens':10,'total_tokens':110,'cost':'0.000005',
                     'prompt_tokens_details':{'cached_tokens':0},'completion_tokens_details':{'reasoning_tokens':0}}}


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.sent=[]
        def send(**kwargs):
            self.sent.append(kwargs); return response()
        self.c=Campaign(self.root/'ledger.json',ROOT/'deploy/mass-live-policy.json',self.root/'db',self.root/'gate',send)
        # Только внешние неплатные свидетельства заменены stub; dispatch/SQLite/ledger реальные.
        self.gate=patch.object(self.c,'gate',return_value={}); self.gate.start();self.addCleanup(self.gate.stop)

    def test_quality_continue_and_payload(self):
        for id in ('P01','P02','P03'):
            report=self.c.dispatch(id)
            self.assertEqual(report['ledger']['cases'][id]['status'],'quality_fail')
        self.assertEqual(len(self.sent),3)
        self.assertEqual(self.sent[0]['extra_body']['reasoning'],{'effort':'none'})
        self.assertFalse(self.sent[0]['extra_body']['provider']['allow_fallbacks'])
        self.assertEqual(self.sent[0]['max_tokens'],256)
        self.assertEqual(report['total_reported_cost_usd'],'0.00014746')
        self.assertEqual(report['ledger']['cases']['P01']['profile_hash'],report['ledger']['cases']['P02']['profile_hash'])

    def test_concurrent_dedup(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(self.c.dispatch,['P01','P01']))
        self.assertEqual(len(self.sent),1)
        self.assertEqual(results[0]['ledger'],results[1]['ledger'])

    def test_crash_in_flight(self):
        def crash(**kwargs): raise KeyboardInterrupt()
        self.c.send=crash
        with self.assertRaises(KeyboardInterrupt): self.c.dispatch('P01')
        report=self.c.dispatch('P02')
        self.assertEqual(report['ledger']['sent'],1)
        self.assertEqual(report['ledger']['cases']['P01']['status'],'indeterminate')
        self.assertEqual(report['ledger']['cases']['P02']['status'],'blocked_safety')

    def test_response_recorded_recovery(self):
        original=self.c.ledger.checkpoint
        def crash(s,event):
            original(s,event)
            if event=='P01:response_recorded': raise SystemExit()
        # Симулируем abrupt process death, без catch/stop cleanup.
        with patch.object(self.c.ledger,'checkpoint',side_effect=crash), patch.object(self.c.ledger,'stop',side_effect=SystemExit):
            with self.assertRaises(SystemExit):self.c.dispatch('P01')
        self.assertEqual(self.c.ledger.read()['cases']['P01']['status'],'response_recorded')
        self.c.dispatch('P01');self.c.dispatch('P01')
        self.assertEqual(len(self.sent),1)
        state=snapshot(open_agent(self.c.db,self.c.id,self.c.cases['P01']))
        self.assertEqual(len(state['history']),2)

    def test_safety_halts_with_known_cost(self):
        r=response();r['provider']='other'
        self.c.send=lambda **kw:r
        report=self.c.dispatch('P01')
        self.assertEqual(report['ledger']['cases']['P01']['status'],'safety_fail')
        self.assertEqual(report['total_reported_cost_usd'],'0.00013746')
        self.assertEqual(report['ledger']['cases']['P02']['status'],'blocked_safety')
        self.c.dispatch('P02');self.assertEqual(self.c.ledger.read()['sent'],1)

    def test_missing_cost_retains_reservation(self):
        r=response();del r['usage']['cost'];self.c.send=lambda **kw:r
        e=self.c.dispatch('P01')['ledger']['cases']['P01']
        self.assertEqual(e['status'],'safety_fail');self.assertIn('reserved_usd',e)
        self.assertNotIn('reported_cost_usd',e)

    def test_crash_prepared_has_no_send_and_resumes(self):
        original=self.c.ledger.checkpoint
        def crash(state,event):
            original(state,event)
            if event=='P01:prepared':raise SystemExit()
        with patch.object(self.c.ledger,'checkpoint',side_effect=crash),patch.object(self.c.ledger,'stop',side_effect=SystemExit):
            with self.assertRaises(SystemExit):self.c.dispatch('P01')
        self.assertEqual(len(self.sent),0)
        self.c.dispatch('P01');self.assertEqual(len(self.sent),1)

    def test_crash_after_sqlite_receipt_does_not_repeat_turn(self):
        from mass_fixture import save_response
        def crash(*args,**kwargs):
            save_response(*args,**kwargs);raise SystemExit()
        with patch('mass_live.save_response',side_effect=crash),patch.object(self.c.ledger,'stop',side_effect=SystemExit):
            with self.assertRaises(SystemExit):self.c.dispatch('P01')
        self.c.dispatch('P01')
        self.assertEqual(len(self.sent),1)
        self.assertEqual(len(snapshot(open_agent(self.c.db,self.c.id,self.c.cases['P01']))['history']),2)

    def test_atomic_reservation_write_failure_prevents_send(self):
        original=self.c.ledger.write
        def fail(state):
            if state['cases']['P01']['status']=='in_flight':raise OSError()
            return original(state)
        with patch.object(self.c.ledger,'write',side_effect=fail):
            self.c.dispatch('P01')
        self.assertEqual(len(self.sent),0)
        self.assertIsNotNone(self.c.ledger.read()['stopped'])

    def test_tampering(self):
        self.c.dispatch('P01');s=self.c.ledger.read();s['cases']['P01']['response']['id']='tampered';self.c.ledger.write(s)
        with self.assertRaises(BudgetStop):self.c.dispatch('P02')

    def test_all_fixtures_restart_boundary(self):
        for id in list(self.c.cases)[:18]:
            r=self.c.dispatch(id)
            self.assertIsNone(r['ledger']['stopped'],(id,r['ledger']['stopped']))
        with self.assertRaises(BudgetStop):self.c.dispatch('S03')
        with patch.dict(os.environ,{'INVOCATION_ID':'before'}): self.c.restart_prepare()
        proof=self.root/'restart';proof.write_text('test only')
        from mass_checkpoint import file_hash
        evidence=dict(invocation='after',pid=os.getpid(),path=str(proof),sha256=file_hash(proof),
                      **{k:True for k in ('loopback_listeners','public_mutations_denied','public_evidence_denied','direct_ports_denied','neighbours_healthy','sqlite_integrity')})
        with patch.dict(os.environ,{'INVOCATION_ID':'after'}),patch('mass_live.os.getpid',return_value=os.getpid()+1):
            evidence['pid']+=1;self.c.restart_verify(evidence)
        for id in list(self.c.cases)[18:]:
            r=self.c.dispatch(id)
            self.assertIsNone(r['ledger']['stopped'],(id,r['ledger']['stopped']))
        self.assertEqual(r['ledger']['sent'],24)
        self.assertEqual(len(self.sent),24)
        with self.assertRaises(BudgetStop):self.c.dispatch('P09')
        self.c.dispatch('P01');self.assertEqual(len(self.sent),24)

    def test_fixture_transaction_resume(self):
        c=self.c.cases['S01'];a=prepare(self.c.db,self.c.id,c);b=prepare(self.c.db,self.c.id,c)
        self.assertEqual(a,b)
        self.assertEqual(len(snapshot(open_agent(self.c.db,self.c.id,c))['history']),2)

    def test_real_gate_fails_without_evidence(self):
        self.gate.stop()
        result=self.c.dispatch('P01')
        self.assertEqual(result['ledger']['sent'],0)
        self.assertEqual(result['ledger']['cases']['P01']['status'],'safety_fail')

    def test_private_routes_and_legacy_disabled(self):
        import web
        from types import SimpleNamespace
        with patch.dict(web.STATE, {'campaign':self.c}):
            for path in ('/api/chat','/api/resume','/api/profile','/api/save','/api/reset','/api/scope'):
                with self.assertRaises(ValueError):web.act(path,{})
        for path in ('/api/campaign/dispatch','/api/campaign/restart-prepare','/api/campaign/restart-verify'):
            handler=object.__new__(web.ReadHandler);handler.path=path
            handler.rfile=SimpleNamespace(read=lambda *args:self.fail('public body read'))
            replies=[];handler.send_json=lambda result,status=200:replies.append(status)
            handler.do_POST();self.assertEqual(replies,[403])
        for path in ('/api/campaign/evidence','/api/evidence'):
            handler=object.__new__(web.ReadHandler);handler.path=path
            replies=[];handler.send_json=lambda result,status=200:replies.append(status)
            handler.do_GET();self.assertEqual(replies,[404])
        import base_agent
        with patch.dict(os.environ,{'DAY12_MASS_LEDGER':str(self.c.ledger.path)}):
            with self.assertRaises(RuntimeError):base_agent.get_client()

    def test_gate_with_anchored_local_evidence(self):
        from mass_checkpoint import file_hash
        from mass_live import utc
        self.gate.stop()
        old=json.loads((ROOT/'results/live-deepseek-repaired.json').read_text())['ledger']
        old_path=self.root/'prior';old_path.write_text(json.dumps(old))
        raw_path=self.root/'probe';raw_path.write_text('offline test double, not real network evidence')
        g={'campaign_id':self.c.id,'manifest_hash':self.c.ledger.read()['manifest_hash'],
           'db_path':str(self.c.db),'verified_at':utc(),
           'provider_raw_names':self.c.policy['provider_raw_names'],
           'prompt_usd_per_million':'0.04','completion_usd_per_million':'0.10',
           'prior_ledger':{'path':str(old_path),'sha256':file_hash(old_path)},
           **{k:True for k in ('public_mutations_denied','public_evidence_denied','direct_ports_denied','loopback_listeners','sqlite_integrity','neighbours_healthy','owner_ssh_tunnel','legacy_paid_disabled','parameters_supported')}}
        for key in ('network_evidence','tariff_evidence'):
            g[key]={'path':str(raw_path),'sha256':file_hash(raw_path)}
        self.c.gate_path.write_text(json.dumps(g))
        self.assertIsNone(self.c.dispatch('P01')['ledger']['stopped'])
        raw_path.write_text('tampered')
        self.assertIsNotNone(self.c.dispatch('P02')['ledger']['stopped'])
        self.assertEqual(len(self.sent),1)

    def test_deleted_ledger_cannot_reset_budget(self):
        self.c.dispatch('P01');self.c.ledger.path.unlink()
        with self.assertRaises(FileExistsError):
            Campaign(self.c.ledger.path,self.c.policy,self.c.db,self.c.gate_path,self.c.send)

    def test_length_continues(self):
        r=response();r['choices'][0]['finish_reason']='length';self.c.send=lambda **kw:r
        self.assertEqual(self.c.dispatch('P01')['ledger']['cases']['P01']['status'],'quality_fail')
        self.assertEqual(self.c.dispatch('P02')['ledger']['sent'],2)

    def test_persistence_failure_closes_dispatch(self):
        with patch('mass_live.save_response',side_effect=OSError):
            report=self.c.dispatch('P01')
        self.assertEqual(report['ledger']['cases']['P01']['status'],'safety_fail')
        self.assertIn('response',report['ledger']['cases']['P01'])
        self.assertEqual(report['ledger']['cases']['P02']['status'],'blocked_safety')

    def test_payload_bound_blocks_before_send(self):
        from agent import Agent
        original=Agent.build_messages
        def oversized(agent, question):
            messages=original(agent,question)
            messages[-1]['content']='я'*9000
            return messages
        with patch.object(Agent,'build_messages',oversized):
            result=self.c.dispatch('P01')
        self.assertEqual(result['ledger']['sent'],0)
        self.assertIsNotNone(result['ledger']['stopped'])

    def test_decimal_budget_boundary(self):
        from decimal import Decimal
        # Точный предел enforcement, без float и без ожидания cache hits.
        reserve=(8192*Decimal('0.04')+256*Decimal('0.10'))/1000000
        self.assertEqual(reserve,Decimal('0.00035328'))
        self.assertEqual(24*reserve+Decimal(PRIOR_COST),Decimal('0.00861118'))
        r=response();r['usage']['cost']=str(reserve)
        telemetry(r,reserve,Decimal('0.02'),self.c.policy)
        with self.assertRaises(BudgetStop):telemetry(r,reserve,Decimal('0.02000001'),self.c.policy)
        r['usage']['cost']=str(reserve+Decimal('0.00000001'))
        with self.assertRaises(BudgetStop):telemetry(r,reserve,Decimal('0.01'),self.c.policy)

    def test_telemetry_rejects_unknown(self):
        from decimal import Decimal
        for key,value in [('cost',None),('cost','NaN'),('cost','-1'),('cost','0.001'),('prompt_tokens',True),('total_tokens',109)]:
            r=response();r['usage'][key]=value
            with self.assertRaises((BudgetStop,ValueError)):
                telemetry(r,Decimal('0.00035328'),Decimal(PRIOR_COST),self.c.policy)
        for detail in ('prompt_tokens_details','completion_tokens_details'):
            r=response();del r['usage'][detail]
            with self.assertRaises(BudgetStop):telemetry(r,Decimal('1'),Decimal('0'),self.c.policy)


if __name__=='__main__':unittest.main()
