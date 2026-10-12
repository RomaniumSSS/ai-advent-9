"""Profile10: актуальный контекст каждой pruning-итерации и согласованные лимиты."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import local,service,limits
from test_protocol03 import UNIT
from test_service import Fake,chunk,context_body,embedded_schema
from test_review_regressions import ImmediateFixture

ASPECTS=[{'id':'Q1','text':'Какие варианты предложены?'},{'id':'Q2','text':'Какой результат подтверждён?'}]

def units():
    return [{**UNIT,'evidence_id':'S'+str(i)+'.U1','source_ref':'S'+str(i),'chunk_id':'synthetic-'+str(i),'text':'x'*600,
             'context_ids':['S5.U1'],'evidence_role':'proof'} for i in range(1,6)]

def coverage(items):
    ids=[u['evidence_id'] for u in items]
    return {'coverage':{'Q1':'full','Q2':'full'},'aspect_evidence_ids':{'Q1':ids,'Q2':[ids[-1]]},
            'proof_ids':ids,'evidence_to_aspect_ids':{eid:['Q1','Q2'] if eid==ids[-1] else ['Q1'] for eid in ids}}

class Profile10Tests(unittest.TestCase):
    def test_each_budget_uses_fresh_context_and_retains_earliest_fitting_three(self):
        for phase in ('selection','synthesis'):
            with self.subTest(phase=phase):
                original=units();before=copy.deepcopy(original);cov=coverage(original);cov_before=copy.deepcopy(cov)
                query={'intent':'followup'};prior={'status':'done','request_id':'prior','answer':{'source_refs':['S5.U1'],'sources':[original[-1]]}}
                def builder(current,history):
                    if phase=='selection':return service.selection_context(ASPECTS,current,[u['evidence_id'] for u in original],query,[prior])
                    return service.synthesis_context(ASPECTS,current,cov)
                initial=builder(original,[]);fresh=builder(original[:3],[])
                options=dict(local.GEN_OPTIONS);options['num_predict']=1408 if phase=='synthesis' else 1024
                def rendered(system,current,context):
                    body={'question':'synthetic question','history_for_dialogue_only':[],**context['extra']}
                    body['sources' if phase=='selection' else 'originals']=service.model_projection(current,phase)
                    content=local.packed(body).decode()
                    return [{'role':'system','content':system},{'role':'user','content':content}]
                fresh_messages=rendered('',original[:3],fresh)
                measured=service.budget_for(fresh_messages,fresh['wire_schema'],options=options)
                target=8192-options['num_predict']-30
                system='s'*(target-measured['input_upper_bound'])
                stale=service.fit_prompt(system,'synthetic question',[],original,initial['wire_schema'],extra=initial['extra'],phase=phase,options=options)
                self.assertEqual(len(stale[1]),2,'контроль действительно воспроизводит stale over-pruning')
                attempts=[];actual_budget=service.budget_for
                def inspect(messages,schema,*args,**kwargs):
                    body=context_body(messages[-1]['content']);sent=body['sources' if phase=='selection' else 'originals'];ids=[u['evidence_id'] for u in sent]
                    actual_schema=schema
                    self.assertTrue(all(set(u['context_ids'])<=set(ids) for u in sent))
                    if phase=='selection':
                        self.assertEqual(list(actual_schema['properties']['a_evidence']['properties']),ids)
                        self.assertEqual(body['evidence_admissibility']['allowed_evidence_ids'],ids)
                        self.assertEqual(body['dialogue_focus']['evidence_ids'],['S5.U1'] if len(ids)==5 else [])
                    else:
                        effective=service.retain_coverage(cov,original[:len(ids)])
                        self.assertEqual(body['coverage'],effective['coverage'])
                        self.assertEqual(body['aspect_evidence_ids'],effective['aspect_evidence_ids'])
                        self.assertEqual(body['evidence_to_aspect_ids'],effective['evidence_to_aspect_ids'])
                        self.assertEqual(actual_schema['properties']['a_points']['items']['properties']['evidence_id']['enum'],ids)
                    attempts.append((len(ids),len(body['history_for_dialogue_only'])))
                    return actual_budget(messages,schema,*args,**kwargs)
                with patch('service.budget_for',side_effect=inspect):
                    messages,kept,history,budget,context=service.fit_prompt(system,'synthetic question',['h'*9000],original,None,
                        phase=phase,options=options,context_builder=builder)
                self.assertEqual(attempts,[(5,1),(5,0),(4,0),(3,0)])
                self.assertEqual(kept,original[:3]);self.assertEqual(history,[])
                self.assertEqual(context,builder(kept,history));self.assertLessEqual(budget['input_upper_bound']+options['num_predict'],8192)
                self.assertEqual(original,before);self.assertEqual(cov,cov_before)
    def test_engine_sends_last_rebuilt_snapshot_once_per_stage(self):
        wire_bodies=[]
        class AllProof(Fake):
            def chat(self,*args,**kwargs):
                response=super().chat(*args,**kwargs);body=context_body(args[0][-1]['content'])
                if 'sources' in body:
                    response['message']['content']=json.dumps({'a_evidence':{u['evidence_id']:['Q1'] for u in body['sources']},'b_coverage':{'Q1':'full'}})
                with ImmediateFixture(local.packed(response)) as fixture,patch('local.OLLAMA_URL',fixture.url):
                    value=local.Ollama(fixture.url).chat(args[0],args[1],**kwargs)
                    wire_bodies.append(json.loads(fixture.calls[0]['body']));return value
        actual_budget=service.budget_for;seen=[]
        def inspect(messages,schema,*args,**kwargs):
            body=context_body(messages[-1]['content'])
            if 'originals' in body:
                ids=[u['evidence_id'] for u in body['originals']];seen.append(ids)
                if len(ids)>3:raise ValueError('input_exceeds_frozen_context_budget')
            return actual_budget(messages,schema,*args,**kwargs)
        fake=AllProof()
        with patch('service.budget_for',side_effect=inspect):result=service.Engine([chunk('c'+str(i)) for i in range(5)],fake).answer('Какие условия дня 30?',[])
        self.assertEqual([len(ids) for ids in seen],[5,4,3]);self.assertEqual(result['metrics']['generation_calls'],2)
        trace=result['trace'];wire=fake.calls[-1]
        self.assertEqual(wire[1],trace['synthesis_prompt']);self.assertEqual(wire[2],trace['synthesis_wire_schema'])
        self.assertEqual(trace['effective_coverage']['coverage'],{'Q1':'partial'})
        self.assertEqual(len(trace['synthesis_originals']),3);self.assertEqual(result['answer']['status'],'partial')
        self.assertEqual(wire_bodies[0]['format'],trace['selection_wire_schema'])
        self.assertEqual(wire_bodies[1]['messages'],trace['synthesis_prompt']);self.assertEqual(wire_bodies[1]['format'],trace['synthesis_wire_schema'])
        self.assertIsNone(embedded_schema(wire_bodies[1]['messages'][-1]['content']))
        self.assertEqual(wire_bodies[1]['options']['num_predict'],1024);self.assertFalse(wire_bodies[1]['think'])
    def test_current_capacity_and_lifecycle_bounds(self):
        self.assertEqual(service.generation_options('synthesis'),{'num_ctx':8192,'num_predict':1024,'temperature':.7,'top_p':.8})
        self.assertEqual(local.provider_deadline_seconds('synthesis'),300)
        self.assertEqual([local.provider_deadline_seconds(stage) for stage in ('embedding','selection','default')],[300]*3)
        self.assertEqual((limits.PROVIDER_TOTAL_BOUND_SECONDS,limits.WORKER_JOIN_SECONDS,limits.LAUNCHD_EXIT_TIMEOUT_SECONDS,limits.POLL_TIMEOUT_SECONDS),(900,910,920,930))

if __name__=='__main__':unittest.main()
