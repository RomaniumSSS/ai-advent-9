import copy
import fcntl
from contextlib import contextmanager, nullcontext, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
import full_chat_core as chat
import quality_eval as q
from test_quality_eval_protocol import ACCEPT, REPAIR, FakeClient, FakeEngine, draft


class ProtocolFailures(unittest.TestCase):
    def test_uncited_factual_repair_cannot_be_promoted_by_recheck(self):
        client=FakeClient([REPAIR,{'answer':'Факт без подтверждённой ссылки.','source_refs':[]},ACCEPT])
        result=q.execute_pair(FakeEngine(),{'question':'Макет?'},[],client)
        self.assertEqual(result['B']['status'],'unavailable')
        self.assertEqual(result['B']['failed_stage'],'repair')
        self.assertEqual(result['B']['reason'],'uncited_answer_without_unknown')
        self.assertEqual(len(client.calls),2);self.assertEqual(result['generation_calls'],3)
        self.assertEqual(len(client.answers),1)

    def test_uncited_correct_unknown_repair_uses_baseline_rule(self):
        client=FakeClient([REPAIR,{'answer':'Не знаю по переданному контексту: недостаточно сведений.','source_refs':[]},ACCEPT])
        result=q.execute_pair(FakeEngine(),{'question':'Макет?'},[],client)
        self.assertEqual(result['B']['status'],'accepted_by_recheck')
        self.assertEqual(result['B']['answer']['source_refs'],[])
        self.assertEqual(result['B']['quality'],'NOT_CHECKED')
        self.assertEqual(len(client.calls),3)

    def test_one_repair_recheck_no_second_repair(self):
        client=FakeClient([REPAIR,{'answer':'Полка.','source_refs':['S1']},REPAIR])
        result=q.execute_pair(FakeEngine(),{'question':'Макет?','gold':'PRIVATE'},[],client)
        self.assertEqual(result['B']['status'],'unverified')
        self.assertEqual(result['generation_calls'],4)
        self.assertEqual(len(client.calls),3)
        self.assertEqual(result['B']['answer']['answer'],'Полка.')
        original=json.loads(draft()['messages'][1]['content'])
        for _,payload in client.calls:
            body=json.loads(payload['messages'][1]['content'])
            for key in original:self.assertEqual(body[key],original[key])
            self.assertNotIn('PRIVATE',json.dumps(payload))
            self.assertEqual(payload['model'],core.MODEL);self.assertIs(payload['think'],False)
            self.assertEqual(payload['options']['temperature'],0)
        recheck=json.loads(client.calls[-1][1]['messages'][1]['content'])
        self.assertNotIn('issues',recheck);self.assertNotIn('verdict',recheck)

    def test_no_sources_unknown_and_baseline_error(self):
        for status,expected in [('unknown','not_applicable'),('error','dependency_blocked')]:
            a=draft();a.update(status=status,generation_called=False);client=FakeClient([])
            result=q.execute_pair(FakeEngine(a),{'question':'Макет?'},[],client)
            self.assertEqual(result['B']['status'],expected);self.assertEqual(client.calls,[])

    def test_insufficient_evidence_is_not_accept(self):
        value={'verdict':'insufficient_evidence','issues':[{'type':'answerability','claim':'Неизвестно','reason':'Недостаточно','source_refs':[]}]}
        result=q.execute_pair(FakeEngine(),{'question':'Макет?'},[],FakeClient([value]))
        self.assertEqual(result['B']['status'],'unavailable')
        self.assertNotIn('answer',result['B'])

    def test_invalid_json_length_refs_timeout_never_fallback_to_a(self):
        for response in [TimeoutError('invented transport'),{**ACCEPT,'issues':REPAIR['issues']},
                         {**REPAIR,'issues':[{**REPAIR['issues'][0],'source_refs':['S8']}]}]:
            with self.subTest(response=type(response).__name__):
                client=FakeClient([response]);result=q.execute_pair(FakeEngine(),{'question':'Макет?'},[],client)
                self.assertEqual(result['B']['status'],'unavailable');self.assertNotIn('answer',result['B'])
                self.assertEqual(len(client.calls),1);self.assertEqual(result['generation_calls'],2)
        payload=q.critique_payload(draft(),draft()['answer'])
        for change in ({'done_reason':'length'},{'message':{'content':'{'}},{'prompt_eval_count':None},
                       {'message':{'content':'{"verdict":"accept","verdict":"repair","issues":[]}'}}):
            raw=FakeClient([ACCEPT]).request('/api/chat',payload);raw.update(change)
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):q.validate_response(raw,payload,{'S1'})

    def test_budget_rejection_calls_zero_without_clipping(self):
        a=draft();body=json.loads(a['messages'][1]['content']);body['sources'][0]['parts'][0]['text']='z'*12000
        a['messages'][1]['content']=core.packed(body).decode();client=FakeClient([])
        result=q.execute_pair(FakeEngine(a),{'question':'Макет?'},[],client)
        self.assertEqual(result['B']['reason'],'stage_budget_rejected');self.assertEqual(client.calls,[])
        self.assertEqual(result['A']['messages'],a['messages'])


def synthetic_matrix():
    matrix=q.mock_matrix();matrix['cases']=matrix['cases'][:3];matrix['order']=[c['id'] for c in matrix['cases']]
    a,b,c=matrix['cases'];b.update(dependency=a['id'],new_conversation=False,semantic_group=a['semantic_group'],question='А что именно?')
    return matrix


class FakeNet(q.MockOllama):
    def __init__(self,critiques=None,fail=None):self.calls=[];self.critiques=list(critiques or []);self.fail=fail
    def request(self,path,payload=None):
        self.calls.append((path,copy.deepcopy(payload)))
        if path==self.fail:raise TimeoutError('synthetic timeout')
        if path=='/api/chat' and payload['format']==q.CRITIC_SCHEMA and self.critiques:
            value=self.critiques.pop(0)
            if isinstance(value,BaseException):raise value
            raw=super().request(path,payload);raw['message']['content']=json.dumps(value);return raw
        return super().request(path,payload)


def chunk():return {'chunk_id':'invented','document_id':'mock','source':'discussion','text':'Макет хранится на полке.',
                    'vector':[1.0]+[0.0]*1023,'start_char':0,'end_char':len('Макет хранится на полке.')}


class DurableTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.input=self.root/'matrix.json';core.save_private(self.input,synthetic_matrix())
        self.run=q.prepare(self.input,self.root/'runs');self.net=FakeNet()
        self.lock_patch=patch.object(core,'generation_lock',nullcontext);self.lock_patch.start();self.addCleanup(self.lock_patch.stop)
        self.output=io.StringIO();self.output_patch=redirect_stdout(self.output);self.output_patch.__enter__();self.addCleanup(self.output_patch.__exit__,None,None,None)

    def runner(self,net=None,factory=None,lock=nullcontext):
        return q.Runner(self.run,factory or (lambda client:chat.ChatEngine([chunk()],{'synthetic':True},client)),net or self.net,lock_factory=lock)

    def test_completed_resume_no_regeneration_and_baseline_only_prefix(self):
        r=self.runner();summary=r.run();calls=len(self.net.calls)
        self.assertEqual(summary['completed_pairs'],3);self.assertEqual(summary['counters']['generation_calls'],6)
        self.assertEqual(summary['counters']['embedding_calls'],3);self.assertEqual(summary['counters']['service_calls'],24)
        again=self.runner();self.assertEqual(again.run()['completed_pairs'],3);self.assertEqual(len(self.net.calls),calls)
        b=again.state['cases']['P02'];self.assertEqual(b['prefix'],[again.state['cases']['P01']['stages']['A']['result']])
        self.assertNotIn('gold',json.dumps(self.net.calls));self.assertNotIn('Секретный',json.dumps(self.net.calls))
        for path in self.run.rglob('*'):
            self.assertEqual(path.stat().st_mode&0o777,0o700 if path.is_dir() else 0o600)
        self.assertNotIn('Макет',self.output.getvalue())

    def test_timeout_pause_requires_operator_idle_no_replay_dependency(self):
        net=FakeNet(fail='/api/chat');r=self.runner(net);summary=r.run()
        self.assertTrue(summary['paused']);self.assertEqual(summary['counters']['generation_calls'],1)
        self.assertEqual(r.state['cases']['P01']['stages']['A']['status'],'interrupted_unknown')
        calls=len(net.calls);again=self.runner(net)
        with self.assertRaisesRegex(ValueError,'idle_confirmation'):again.run()
        self.assertEqual(len(net.calls),calls)
        again.confirm_idle('Оператор подтвердил idle вне /api/ps');net.fail=None;again.run()
        self.assertEqual(again.state['cases']['P02']['status'],'dependency_blocked')
        self.assertEqual(sum(p=='/api/chat' and payload['format']==core.SOURCE_SCHEMA for p,payload in net.calls),2)
        self.assertTrue(again.state['idle_confirmations'])

    def test_crash_after_critic_dispatch_never_replayed(self):
        net=FakeNet(critiques=[SystemExit('synthetic crash')]);r=self.runner(net)
        with self.assertRaises(SystemExit):r.run()
        again=self.runner(net);self.assertTrue(again.state['paused'])
        self.assertEqual(again.state['cases']['P01']['stages']['critic']['status'],'interrupted_unknown')
        again.confirm_idle('Подтверждена остановка');again.run()
        first=[e for e in again.state['events'] if e['case_id']=='P01' and e['path']=='/api/chat']
        self.assertEqual(len(first),2);self.assertEqual(again.state['cases']['P01']['B']['status'],'unavailable')

    def test_completed_critic_resume_before_repair_only_dispatches_remaining(self):
        r=self.runner();r.case_id='P01';r.stage='A'
        a=draft();r.state['cases']['P01']={'stages':{'A':{'status':'done','result':a},
            'critic':{'status':'done','payload':q.critique_payload(a,a['answer']),'validated':REPAIR}}}
        r.save();self.net.critiques=[ACCEPT];again=self.runner();again.run()
        events=[e for e in again.state['events'] if e['case_id']=='P01' and e['path']=='/api/chat']
        self.assertEqual(len(events),2);self.assertEqual(again.state['cases']['P01']['B']['status'],'accepted_by_recheck')

    def test_resume_latency_includes_previous_completed_stage_no_guess_overhead(self):
        r=self.runner();a=draft();r.state['cases']['P01']={'stages':{'A':{'status':'done','result':a},
            'critic':{'status':'done','payload':q.critique_payload(a,a['answer']),'validated':REPAIR,'seconds':10}}}
        r.save();summary=self.runner().run();row=summary['cases'][0]
        self.assertGreaterEqual(row.get('B_latency_observed_lower_bound',row['B_latency']),12)
        self.assertIsNone(row['B_latency']);self.assertIsNone(row['pair_observed_seconds'])
        self.assertEqual(row['latency_measurement'],'observed_lower_bound_missing_orchestration')

    def test_resume_multiple_completed_stages_never_double_counts(self):
        r=self.runner();a=draft();candidate={'answer':'Полка.','source_refs':['S1']}
        stages={'A':{'status':'done','result':a},
            'critic':{'status':'done','payload':q.critique_payload(a,a['answer']),'validated':REPAIR,'seconds':10},
            'repair':{'status':'done','payload':q.critique_payload(a,a['answer'],REPAIR['issues'],'repair'),'validated':candidate,'seconds':7},
            'recheck':{'status':'done','payload':q.critique_payload(a,candidate,stage='recheck'),'validated':ACCEPT,'seconds':5}}
        r.state['cases']['P01']={'stages':stages};r.save();summary=self.runner().run();row=summary['cases'][0]
        self.assertEqual(row.get('B_latency_observed_lower_bound',row['B_latency']),24)
        self.assertIsNone(row['B_latency']);self.assertEqual(row['added_stage_seconds'],22)
        first_events=[e for e in json.loads((self.run/'checkpoint.json').read_text())['events'] if e['case_id']=='P01']
        self.assertEqual(first_events,[])
        again=self.runner().run();self.assertEqual(again['cases'][0]['B_latency_observed_lower_bound'],24)

    def test_crashed_continuous_flags_do_not_prove_whole_resumed_latency(self):
        r=self.runner();a=draft();r.state['cases']['P01']={'b_timing_complete':True,'pair_timing_complete':True,
            'stages':{'A':{'status':'done','result':a},'critic':{'status':'done','payload':q.critique_payload(a,a['answer']),
                     'validated':REPAIR,'seconds':10}}}
        r.save();row=self.runner().run()['cases'][0]
        self.assertIsNone(row['B_latency']);self.assertIsNone(row['pair_observed_seconds'])
        self.assertGreaterEqual(row['B_latency_observed_lower_bound'],12)

    def test_missing_previous_stage_duration_keeps_headline_null(self):
        r=self.runner();a=draft();r.state['cases']['P01']={'stages':{'A':{'status':'done','result':a},
            'critic':{'status':'done','payload':q.critique_payload(a,a['answer']),'validated':ACCEPT,'seconds':None}}}
        r.save();row=self.runner().run()['cases'][0]
        self.assertIsNone(row['B_latency']);self.assertEqual(row['missing_added_stage_times'],1)
        self.assertEqual(row['B_latency_observed_lower_bound'],2)

    def test_immutability_inputs_protocol_code_and_audit(self):
        r=self.runner();r.inputs['cases'][0]['question']='Изменён вопрос';core.save_private(self.run/'inputs.json',r.inputs)
        with self.assertRaisesRegex(ValueError,'immutable'):self.runner()
        audit={'approved':True,'cases_file_sha256':'wrong','audit_kind':'independent_agent_source_audit','human_acceptance':False}
        path=self.root/'audit.json';core.save_private(path,audit)
        with self.assertRaisesRegex(ValueError,'audit'):q.prepare(self.input,self.root/'runs',path)

    def test_busy_no_dispatch_and_wrong_digest_pauses(self):
        @contextmanager
        def busy():raise ValueError('local_generation_busy');yield
        r=self.runner(lock=busy);r.run()
        self.assertEqual(r.state['cases']['P01']['B']['status'],'unavailable')
        self.assertEqual(sum(p=='/api/chat' for p,_ in self.net.calls),3)
        class WrongDigest(FakeNet):
            def request(self,path,payload=None):
                raw=super().request(path,payload)
                if path=='/api/tags':raw['models'][0]['digest']='wrong'
                return raw
        self.run=q.prepare(self.input,self.root/'runs');net=WrongDigest();r=self.runner(net);r.run()
        self.assertTrue(r.state['paused']);self.assertFalse(any(p in ('/api/embed','/api/chat') for p,_ in net.calls))

    def test_missing_metrics_are_null_not_zero_cost(self):
        class MissingMetrics(FakeNet):
            def request(self,path,payload=None):
                raw=super().request(path,payload)
                if path=='/api/chat':raw.pop('eval_count',None);raw['prompt_eval_count']=100
                return raw
        r=self.runner(MissingMetrics());summary=r.run()
        self.assertIsNone(summary['counters'].get('output_tokens_total',0))
        self.assertEqual(summary['counters']['missing_generation_metrics'],6)

    def test_full_model_schema_and_payload_budget_before_a_dispatch(self):
        r=self.runner();r.case_id='P01';r.stage='A'
        payload=core.profile_payload(chat.PROFILE,[{'role':'system','content':chat.SYSTEM},{'role':'user','content':'x'*8000}])
        with self.assertRaisesRegex(ValueError,'budget'):r.client.request('/api/chat',payload)
        self.assertEqual(self.net.calls,[]);self.assertEqual(r.state['events'],[])

    def test_stage_trace_rejected_budget_preserves_candidate_no_dispatch(self):
        r=self.runner();a=draft();a['answer']['answer']='x'*12000
        class LargeDraft(FakeEngine):
            pass
        r=self.runner(factory=lambda client:LargeDraft(a));r.run()
        stage=r.state['cases']['P01']['stages']['critic']
        self.assertEqual(stage['status'],'budget_rejected');self.assertEqual(stage['dispatch_count'],0)
        self.assertEqual(self.net.calls,[])

    def test_identity_and_code_protection_reject_before_network(self):
        manifest=json.loads((self.run/'manifest.json').read_text());manifest['code_hashes']['full_chat_core.py']='bad'
        core.save_private(self.run/'manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'immutable'):self.runner()
        self.assertEqual(self.net.calls,[])

    def test_dependency_invalid_order_group_split_and_private_symlink(self):
        matrix=synthetic_matrix();matrix['order'].reverse()
        with self.assertRaisesRegex(ValueError,'dependency'):q.validate_matrix(matrix)
        matrix=synthetic_matrix();matrix['cases'][1]['split']='holdout'
        with self.assertRaises(ValueError):q.validate_matrix(matrix)
        target=self.root/'link';target.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):q.private_dir(target/'nested')

    def test_no_global_time_or_call_limit_in_protocol(self):
        self.assertIsNone(q.protocol()['walltime_limit']);self.assertIsNone(q.protocol()['call_cap'])
        self.assertEqual(q.protocol()['transport_timeout'],300)

    def test_wall_time_and_error_latency_not_fast_b(self):
        class SlowClient(FakeNet):
            def request(self,path,payload=None):
                if path=='/api/chat':time.sleep(.005)
                return super().request(path,payload)
        r=self.runner(SlowClient());summary=r.run()
        self.assertGreaterEqual(summary['counters']['http_seconds'],.03)
        for case in summary['cases']:
            self.assertGreaterEqual(case['B_latency'],case['A_latency']+.005)
            self.assertGreaterEqual(case['pair_observed_seconds'],case['B_latency'])
        self.run=q.prepare(self.input,self.root/'runs');r=self.runner(FakeNet(fail='/api/chat'));summary=r.run()
        self.assertIsNone(summary['cases'][0]['B_latency'])

    def test_live_audit_required_no_network_on_prepare(self):
        with self.assertRaisesRegex(ValueError,'audit'):q.Runner(self.run,lambda client:FakeEngine(),self.net,live=True)
        self.assertEqual(self.net.calls,[])
        matrix=json.loads(self.input.read_text());audit={'approved':True,'cases_file_sha256':q.file_sha(self.input),
            'audit_kind':'independent_agent_source_audit','human_acceptance':False}
        path=self.root/'audit.json';core.save_private(path,audit);run=q.prepare(self.input,self.root/'runs',path)
        r=q.Runner(run,lambda client:FakeEngine(),self.net,live=True,lock_factory=nullcontext)
        self.assertIsNotNone(r);self.assertEqual(self.net.calls,[])

    def test_two_controllers_cannot_mutate_same_checkpoint(self):
        fd=open(self.run/'runner.lock','w')
        self.addCleanup(fd.close);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        before=(self.run/'checkpoint.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'controller_busy'):self.runner()
        self.assertEqual((self.run/'checkpoint.json').read_bytes(),before);self.assertEqual(self.net.calls,[])

    def test_incomplete_provider_response_pauses_before_independent_case(self):
        class Incomplete(FakeNet):
            def request(self,path,payload=None):
                raw=super().request(path,payload)
                if path=='/api/chat':raw['done']=False
                return raw
        r=self.runner(Incomplete());summary=r.run()
        self.assertTrue(summary['paused']);self.assertEqual(summary['counters']['generation_calls'],1)
        self.assertEqual(summary['counters']['ambiguous_http_calls'],1)
        self.assertEqual(summary['cases'][2]['status'],'pending')

    def test_frozen_five_subset_never_dispatches_unselected(self):
        matrix=q.mock_matrix();path=self.root/'matrix24.json';core.save_private(path,matrix)
        ids=['H03','H04','H05','H06','H07']
        run=q.prepare(path,self.root/'runs',case_ids=ids)
        r=q.Runner(run,lambda client:chat.ChatEngine([chunk()],{'synthetic':True},client),self.net,lock_factory=nullcontext)
        summary=r.run('holdout')
        self.assertEqual(summary['counters']['generation_calls'],10)
        self.assertEqual(summary['selected_case_ids'],ids)
        self.assertEqual(summary['completed_pairs'],5)
        self.assertEqual(summary['pending_unselected_holdout'],15)
        self.assertEqual(summary['counters']['generation_calls'],10)
        self.assertEqual(set(e['case_id'] for e in r.state['events']),set(ids))
        self.assertEqual(summary['holdout_claim'],'partial_selected_subset')

    def test_subset_missing_dependency_rejected_not_auto_added(self):
        with self.assertRaisesRegex(ValueError,'selection_dependency_missing'):
            q.prepare(self.input,self.root/'runs',case_ids=['P02'])

    def test_selection_mutation_resume_rejected_before_dispatch(self):
        run=q.prepare(self.input,self.root/'runs',case_ids=['P03'])
        selection=json.loads((run/'selection.json').read_text());selection['case_ids']=['P01']
        core.save_private(run/'selection.json',selection)
        with self.assertRaisesRegex(ValueError,'selection'):
            q.Runner(run,lambda client:FakeEngine(),self.net,lock_factory=nullcontext)
        self.assertEqual(self.net.calls,[])

    def test_seeded_selection_file_dataset_hash_and_closure(self):
        selection={'cases_file_sha256':q.file_sha(self.input),'case_ids':['P01','P02'],'seed':29011,'method':'seeded_random_independent_groups'}
        path=self.root/'selection.json';core.save_private(path,selection)
        run=q.prepare(self.input,self.root/'runs',selection_file=path)
        manifest=json.loads((run/'manifest.json').read_text())
        self.assertEqual(manifest['selection']['source_sha256'],q.file_sha(path))
        self.assertEqual(manifest['selection']['seed'],29011)
        self.assertEqual(manifest['selection']['case_ids'],['P01','P02'])
        selection['cases_file_sha256']='bad';core.save_private(path,selection)
        with self.assertRaisesRegex(ValueError,'dataset_mismatch'):q.prepare(self.input,self.root/'runs',selection_file=path)
        with self.assertRaisesRegex(ValueError,'conflict'):q.prepare(self.input,self.root/'runs',case_ids=['P03'],selection_file=path)
        core.save_private(path,{})
        with self.assertRaisesRegex(ValueError,'dataset_mismatch'):q.prepare(self.input,self.root/'runs',selection_file=path)


if __name__=='__main__':unittest.main()
