"""Profile11: строгий один пример, native wire и текущий pruning без inference."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evidence,local,protocol,service,limits
from test_protocol03 import UNIT,ASPECTS,metadata,synthesis
from test_service import Fake,chunk,context_body,embedded_schema
from test_review_regressions import ImmediateFixture

ONE={'max_proof_units':1,'max_points':1};ORDINARY={'max_proof_units':8,'max_points':4}

class Profile11Tests(unittest.TestCase):
    def test_explicit_current_question_detector_conservative_forms_and_guards(self):
        for q in ('Назови одну проблему в обсуждении','Пожалуйста, приведи мне один конкретный пример.',
                  'ПОКАЖИ пожалуйста 1 вопрос','пожалуйста,назови\nодно конкретное пример'):
            self.assertEqual(protocol.answer_limits(q),ONE)
        for q in ('Не назови один пример','Назови не один пример','Назови несколько примеров',
                  'Назови одну проблему каждого участника','Покажи один пример по одному на тему',
                  'Покажи один пример по1 на тему','Расскажи про один пример','А что с этим примером?',
                  'Назови одиночный пример','Приведи 11 примеров','Назови одну проблематику'):
            self.assertEqual(protocol.answer_limits(q),ORDINARY)
    def test_sentence_boundary_keeps_newlines_and_excludes_quoted_commands(self):
        for boundary in ('?','!','.',';','\n'):
            question='Какие варианты обсуждаются'+boundary+'  Назови один конкретный пример.'
            self.assertEqual(protocol.answer_limits(question),ONE)
        for question in ('Какие варианты? Не назови один пример.',
                         'Какие варианты? Назови не один пример.',
                         'Какие варианты? Назови два примера.',
                         'Какие варианты? Назови один пример для каждого участника.',
                         'Он написал: „Что случилось? Назови одну проблему“.',
                         'Он написал: «Что случилось; назови один пример».',
                         'Он написал: "Что случилось! Покажи один вопрос".',
                         'Он написал: “Что случилось. Приведи один пример”.',
                         'Что случилось? «Назови одну проблему».'):
            self.assertEqual(protocol.answer_limits(question),ORDINARY)
        question='Он написал: «Что случилось? Назови два примера». Назови один пример.'
        self.assertEqual(protocol.answer_limits(question),ONE)
    def test_ascii_single_quoted_command_is_not_request(self):
        self.assertEqual(protocol.answer_limits("Он написал: 'Что случилось? Назови один пример'."),ORDINARY)
    def test_nested_quoted_command_is_not_request(self):
        self.assertEqual(protocol.answer_limits('Он написал: «Цитата «слово»; Назови один пример».'),ORDINARY)
    def test_quote_escapes_mixed_nesting_and_intraword_apostrophe(self):
        for question in (r'Он написал: "Слово \"; Назови один пример".',
                         'Он написал: “Цитата ‘слово’; Назови один пример”.',
                         "Он написал: 'He can't? Назови один пример'.",
                         'Он написал: ‘He can’t? Назови один пример’.',
                         'Он написал: «Цитата «слово»; Назови один пример'):
            self.assertEqual(protocol.answer_limits(question),ORDINARY)
        for question in ("Прочитай l'amour. Назови один пример.",
                         'Прочитай l’amour. Назови один пример.',
                         'Он написал: «Цитата «слово»; Назови два примера». Назови один пример.'):
            self.assertEqual(protocol.answer_limits(question),ONE)
    def test_single_selection_schema_exact_union_and_backend_rejects_excess(self):
        other={**UNIT,'evidence_id':'S2.U1','source_ref':'S2'}
        schema=evidence.response_schema(ASPECTS,[UNIT,other],answer_limits=ONE)
        branch=schema['properties']['evidence'];self.assertEqual(set(branch),{'oneOf'})
        empty,first,second=branch['oneOf'];self.assertEqual(empty,{'type':'object','properties':{},'additionalProperties':False})
        for node,eid in ((first,'S1.U1'),(second,'S2.U1')):
            self.assertEqual(node['required'],[eid]);self.assertEqual(list(node['properties']),[eid]);self.assertFalse(node['additionalProperties'])
        raw={'evidence':{'S1.U1':['Q1'],'S2.U1':['Q2']},'coverage':{'Q1':'full','Q2':'full'}}
        with self.assertRaisesRegex(ValueError,'invalid_selection_quantity'):protocol.validate_selection(raw,ASPECTS,[UNIT,other],{'S1.U1','S2.U1'},answer_limits=ONE)
        self.assertEqual(evidence.response_schema(ASPECTS,[UNIT,other])['properties']['evidence']['maxProperties'],8)
        selected,cov=protocol.validate_selection(raw,ASPECTS,[UNIT,other],{'S1.U1','S2.U1'})
        self.assertEqual(len(cov['proof_ids']),2)
    def test_background_context_not_second_proof_or_point_unknown_retained(self):
        prior={**UNIT,'evidence_id':'S0.U1','source_ref':'S0'};proof={**UNIT,'context_ids':['S0.U1']}
        raw={'evidence':{'S1.U1':['Q1']},'coverage':{'Q1':'full','Q2':'none'}}
        chosen,cov=protocol.validate_selection(raw,ASPECTS,[prior,proof],{'S1.U1'},answer_limits=ONE)
        self.assertEqual([u['evidence_role'] for u in chosen],['background_context','proof']);self.assertEqual(cov['proof_ids'],['S1.U1'])
        schema=protocol.synthesis_schema(ASPECTS,chosen,cov,answer_limits=ONE)
        self.assertEqual(schema['properties']['points']['maxItems'],1)
        refs=schema['properties']['conclusion']['properties']['point_refs'];self.assertEqual(refs['maxItems'],1);self.assertEqual(refs['items']['enum'],['P1'])
        final=synthesis();answer=protocol.materialize_synthesis(final,ASPECTS,chosen,cov,answer_limits=ONE)
        self.assertEqual(len(answer['sources']),1);self.assertEqual(answer['source_refs'],['S1.U1'])
        final['points'].append(copy.deepcopy(final['points'][0]))
        with self.assertRaisesRegex(ValueError,'invalid_synthesis_quantity'):protocol.materialize_synthesis(final,ASPECTS,chosen,cov,answer_limits=ONE)
        final=synthesis();final['points'][0]['evidence_id']='S0.U1'
        with self.assertRaisesRegex(ValueError,'invalid_point_reference'):protocol.materialize_synthesis(final,ASPECTS,chosen,cov,answer_limits=ONE)
        final={'points':[],'doubtful_aspect_ids':[],'conclusion':{'text':protocol.UNKNOWN_CONCLUSION,'point_refs':[]}}
        self.assertEqual(protocol.materialize_synthesis(final,ASPECTS,chosen,cov,answer_limits=ONE)['status'],'unknown')
    def test_actual_native_wire_limits_budget_trace_and_followup_not_inherited(self):
        captured=[]
        class Wire(Fake):
            def chat(self,m,s,**kwargs):
                response=super().chat(m,s,**kwargs)
                with ImmediateFixture(local.packed(response)) as fixture,patch('local.OLLAMA_URL',fixture.url):
                    value=local.Ollama(fixture.url).chat(m,s,**kwargs);captured.append(json.loads(fixture.calls[0]['body']));return value
        first=service.Engine([chunk()],Wire()).answer('Назови одну проблему в задании дня 30',[])
        self.assertEqual(first['trace']['answer_limits'],ONE);self.assertEqual(first['metrics']['generation_calls'],2)
        for stage,sent in zip(('selection','synthesis'),captured):
            self.assertFalse(sent['think']);self.assertEqual(sent['format'],first['trace'][stage+'_wire_schema'])
            self.assertIsNone(embedded_schema(sent['messages'][-1]['content']))
            self.assertEqual(context_body(sent['messages'][-1]['content'])['answer_limits'],ONE)
            parameters=first['trace']['generation_parameters'][stage]
            self.assertEqual(parameters['format_mode'],'native');self.assertFalse(parameters['think']);self.assertEqual(parameters['deadline_seconds'],300)
            self.assertEqual(first['trace']['budgets'][stage],service.budget_for(sent['messages'],sent['format'],options=sent['options'],deadline_seconds=300))
            self.assertEqual(sent['options']['num_predict'],1024)
        next_turn={'status':'done','question':'Назови одну проблему в задании дня 30','query':first['query'],'answer':first['answer']}
        later=service.Engine([chunk()],Fake()).answer('А что именно там нужно проверить?',[next_turn])
        self.assertEqual(later['trace']['answer_limits'],ORDINARY)
        self.assertEqual((limits.PROVIDER_TOTAL_BOUND_SECONDS,limits.WORKER_JOIN_SECONDS,limits.LAUNCHD_EXIT_TIMEOUT_SECONDS,limits.POLL_TIMEOUT_SECONDS),(900,910,920,930))
    def test_ordinary_eight_proofs_four_points_and_single_multiple_aspects(self):
        items=[{**UNIT,'evidence_id':'S1.U'+str(i)} for i in range(1,9)]
        raw={'evidence':{u['evidence_id']:['Q1'] for u in items},'coverage':{'Q1':'full','Q2':'none'}}
        chosen,cov=protocol.validate_selection(raw,ASPECTS,items,{u['evidence_id'] for u in items})
        self.assertEqual(len(cov['proof_ids']),8)
        final=synthesis();final['points']*=4
        self.assertEqual(len(protocol.materialize_synthesis(final,ASPECTS,chosen,cov)['sources']),1)
        self.assertEqual(protocol.synthesis_schema(ASPECTS,chosen,cov)['properties']['points']['maxItems'],4)
        raw={'evidence':{'S1.U1':['Q1','Q2']},'coverage':{'Q1':'full','Q2':'full'}}
        chosen,cov=protocol.validate_selection(raw,ASPECTS,[UNIT],{'S1.U1'},answer_limits=ONE)
        self.assertEqual(cov['aspect_evidence_ids'],{'Q1':['S1.U1'],'Q2':['S1.U1']})
        final=synthesis();final['points'][0]['aspect_ids']=['Q1','Q2']
        self.assertEqual(protocol.materialize_synthesis(final,ASPECTS,chosen,cov,answer_limits=ONE)['status'],'supported')
    def test_excess_provider_outputs_fail_at_actual_stage_without_truncation_or_retry(self):
        for stage in ('selection','synthesis'):
            class Excess(Fake):
                def chat(self,m,s,**kwargs):
                    response=super().chat(m,s,**kwargs);body=context_body(m[-1]['content']);raw=json.loads(response['message']['content'])
                    if stage=='selection' and 'sources' in body:raw['a_evidence']={u['evidence_id']:['Q1'] for u in body['sources']}
                    if stage=='synthesis' and 'originals' in body:raw['a_points']*=2
                    response['message']['content']=json.dumps(raw);return response
            with self.subTest(stage=stage),self.assertRaises(service.InferenceFailure) as caught:
                service.Engine([chunk('a'),chunk('b')],Excess()).answer('Назови один пример в задании дня 30',[])
            result=caught.exception.partial_result
            self.assertEqual(result['trace']['validation_code'],'invalid_'+stage+'_quantity')
            self.assertEqual(result['metrics']['generation_calls'],1 if stage=='selection' else 2)
        result=service.Engine([chunk()],Fake('unknown')).answer('Назови один пример в задании дня 30',[])
        self.assertEqual(result['answer']['status'],'unknown');self.assertEqual(result['metrics']['generation_calls'],1)
    def test_unexpected_synthesis_thinking_rejected_and_private_snapshot_sanitized(self):
        import contextlib,io,tempfile,server
        sentinel='SYNTHETIC_REASONING_NOT_FOR_STORAGE'
        class Unexpected(Fake):
            def chat(self,m,s,**kwargs):
                response=super().chat(m,s,**kwargs)
                if 'originals' in context_body(m[-1]['content']):response['message']['thinking']=sentinel
                return response
        with tempfile.TemporaryDirectory() as d:
            app=server.Application(service.Engine([chunk()],Unexpected()),service.Store(Path(d)/'state'),'fixture-token')
            log=io.StringIO()
            with patch('service.generation_lock',side_effect=contextlib.nullcontext),contextlib.redirect_stdout(log):
                accepted=app.submit({'question':'Назови один пример в задании дня 30'});app.wait_workers()
            receipt=app.store.receipt(accepted['request_id'],'all')
            self.assertEqual(receipt['status'],'error');self.assertEqual(receipt['trace']['validation_code'],'unexpected_model_thinking')
            self.assertEqual(receipt['metrics']['generation_calls'],2)
            self.assertNotIn(sentinel,json.dumps(receipt));self.assertNotIn(sentinel,json.dumps(service.public_receipt(receipt)))
            self.assertNotIn(sentinel,log.getvalue())
            for p in Path(d).rglob('*.json'):self.assertNotIn(sentinel,p.read_text())
    def test_single_oneof_rebuilt_before_each_native_budget_and_earliest_fit(self):
        original=[{**UNIT,'evidence_id':'S'+str(i)+'.U1','source_ref':'S'+str(i),'text':'x'*600} for i in range(1,6)]
        allowed=[u['evidence_id'] for u in original]
        builder=lambda us,hs:service.selection_context(ASPECTS,us,allowed,{'intent':'new_topic'},[],ONE)
        context=builder(original[:3],[])
        body={'question':'synthetic','history_for_dialogue_only':[],**context['extra'],'sources':service.model_projection(original[:3],'selection')}
        messages=[{'role':'system','content':''},{'role':'user','content':local.packed(body).decode()}]
        b=service.budget_for(messages,context['wire_schema']);padding='s'*(8192-1024-30-b['input_upper_bound'])
        stale=builder(original,[])
        self.assertEqual(len(service.fit_prompt(padding,'synthetic',[],original,stale['wire_schema'],extra=stale['extra'],phase='selection')[1]),2)
        seen=[];actual=service.budget_for
        def inspect(ms,schema,*args,**kwargs):
            ids=[u['evidence_id'] for u in context_body(ms[-1]['content'])['sources']]
            self.assertEqual([node['required'][0] for node in schema['properties']['a_evidence']['oneOf'][1:]],ids);seen.append(len(ids))
            return actual(ms,schema,*args,**kwargs)
        with patch('service.budget_for',side_effect=inspect):fit=service.fit_prompt(padding,'synthetic',[],original,None,phase='selection',context_builder=builder)
        self.assertEqual(seen,[5,4,3]);self.assertEqual(fit[1],original[:3]);self.assertEqual(fit[4],builder(fit[1],[]))

if __name__=='__main__':unittest.main()
