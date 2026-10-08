"""T3: fault injection around durable phases and provider boundary, fully offline."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from common import MODEL, save
from service import Service, read
import test_context as context_fixture
CHUNK=context_fixture.CHUNK


class PowerLoss(BaseException):pass


class StatesTest(context_fixture.ContextTest):
    # Reuse the synthetic Service fixture, not the T2 test methods.
    def test_saved_phases_and_ledger_binding(self):
        observed=[]
        real_save=save
        def observe(path,data):
            if Path(path).name=='result-phases.json':observed.append(copy.deepcopy(data))
            real_save(path,data)
        with patch('service.save',side_effect=observe):
            item=self.service.ask(self.a,'phases','Объясни RAG','public')
        self.assertEqual(item['status'],'verified')
        self.assertEqual(item['stage'],'terminal')
        self.assertEqual([e['to'] for e in item['transitions']],
                         ['searching','selecting','generating','validating','terminal'])
        stages={entry['stage'] for entry in observed}
        self.assertEqual(stages,{'searching','selecting','generating','validating','terminal'})
        validating=[entry for entry in observed if entry['stage']=='validating'][0]
        self.assertEqual(validating['status'],'validating')
        self.assertNotIn('answer',validating)
        ledger=read(self.root/'ledger.json')['entries'][0]
        self.assertEqual(ledger['id'],'phases')
        self.assertEqual(ledger['chat_id'],self.a)
        self.assertEqual(ledger['task_state_version'],0)
        self.assertEqual(ledger['payload_sha256'],item['ledger']['payload_sha256'])
        self.assertEqual(item['generation']['transmitted_chunks'][0]['chunk_id'],'c1')
        restarted=Service(self.root,search_fn=lambda *_:self.fail('search repeated'),
                          generate_fn=lambda *_:self.fail('generation repeated'))
        self.assertEqual(restarted.get(self.a,'phases')['status'],'verified')
        self.assertEqual(restarted.ask(self.a,'phases','Объясни RAG','public')['status'],'verified')

    def test_illegal_transition_or_forged_success_cannot_generate(self):
        item=self.service.ask(self.a,'done','Объясни RAG','public')
        with self.assertRaisesRegex(ValueError,'invalid_request_transition'):
            self.service.advance(item,self.service.path('done'),'generating')
        with self.assertRaisesRegex(ValueError,'invalid_request_transition'):
            self.service.generate(item,self.service.path('done'),{},item['search']['trace'])
        self.assertEqual(len(self.generate_calls),1)
        fake=copy.deepcopy(item);fake.update(stage='validating',raw_answer='{}')
        with self.assertRaisesRegex(ValueError,'verified_invariant_failed'):
            self.service.advance(fake,self.service.path('done'),'terminal')
        self.assertEqual(self.service.get(self.a,'done')['status'],'verified')
        fake=copy.deepcopy(item);fake.update(stage='searching',status='searching')
        with self.assertRaisesRegex(ValueError,'invalid_request_transition'):
            self.service.advance(fake,self.service.path('done'),'validating')

    def test_invalid_answers_and_refusal(self):
        variants=[('{broken','unverified'),
                  (json.dumps({'answer':'Изобретённое','sources':[{'source':'assignment','chunk_id':'not-sent'}],
                   'quotes':[{'chunk_id':'not-sent','text':CHUNK['text']}]}),'unverified'),
                  (json.dumps({'answer':'Неточная цитата','sources':[{'source':'assignment','chunk_id':'c1'}],
                   'quotes':[{'chunk_id':'c1','text':'Fabricated quote'}]}),'unverified'),
                  (json.dumps({'answer':'Не знаю: уточни тему','sources':[],'quotes':[]}), 'model_refusal')]
        for index,(content,status) in enumerate(variants):
            self.service.generate_fn=lambda *_:{'model':MODEL,'provider':'DeepInfra','usage':{'cost':.00001},
                'choices':[{'finish_reason':'stop','message':{'content':content}}]}
            item=self.service.ask(self.a,'invalid'+str(index),'Вопрос','public')
            self.assertEqual(item['status'],status)
            self.assertEqual(item['stage'],'terminal')
            self.assertFalse(item['validation']['valid'])
            if status=='unverified':self.assertNotIn('answer',item)
            else:self.assertEqual(item['answer']['sources'],[])
        self.service.generate_fn=lambda *_:{'model':MODEL,'provider':'DeepInfra','usage':{'cost':.00001},
            'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
        truncated=self.service.ask(self.a,'truncated','Вопрос','public')
        self.assertEqual(truncated['status'],'unverified')
        self.assertEqual(truncated['validation']['errors'],['incomplete_answer'])

    def test_empty_search_and_search_failure_do_not_generate(self):
        self.service.search_fn=lambda *_:{'trace':{'empty':True,'selected':[]}}
        item=self.service.ask(self.a,'empty','Вопрос','public')
        self.assertEqual(item['status'],'no_context')
        self.assertEqual([e['to'] for e in item['transitions']],['searching','selecting','terminal'])
        self.assertEqual(item['answer']['sources'],[])
        self.assertEqual(item['cost'],0)
        def broken(*_):raise RuntimeError('search failure')
        self.service.search_fn=broken
        item=self.service.ask(self.a,'broken','Вопрос','public')
        self.assertEqual(item['status'],'error')
        self.assertEqual(item['stage'],'terminal')
        self.assertEqual(self.generate_calls,[])
        self.assertFalse((self.root/'ledger.json').exists())

    def test_crash_before_paid_boundary_and_after_transmission(self):
        def crash_search(*_):raise PowerLoss()
        original_search=self.service.search_fn
        self.service.search_fn=crash_search
        with self.assertRaises(PowerLoss):self.service.ask(self.a,'prepaid','Вопрос','public')
        self.assertEqual(read(self.service.path('prepaid'))['stage'],'searching')
        restarted=Service(self.root,search_fn=original_search,
                          generate_fn=lambda *_:self.fail('interrupted ID repeated'))
        self.assertEqual(restarted.get(self.a,'prepaid')['status'],'interrupted')
        self.assertEqual(restarted.ask(self.a,'prepaid','Вопрос','public')['status'],'interrupted')
        self.assertFalse((self.root/'ledger.json').exists())
        transmitted=[]
        def crash_provider(*_):transmitted.append(True);raise PowerLoss()
        restarted.generate_fn=crash_provider
        restarted.key_fn=lambda _:'synthetic-key'
        restarted.pricing_fn=lambda:{'prompt':.14/1e6,'completion':.42/1e6}
        with self.assertRaises(PowerLoss):restarted.ask(self.a,'paid','Вопрос','public')
        self.assertEqual(len(transmitted),1)
        next_service=Service(self.root,search_fn=original_search,generate_fn=lambda *_:self.fail('unknown repeated'))
        unknown=next_service.get(self.a,'paid')
        self.assertEqual(unknown['status'],'unknown')
        self.assertEqual(unknown['stage'],'terminal')
        self.assertEqual(unknown['generation']['transmission'],'unknown')
        self.assertEqual(read(self.root/'ledger.json')['entries'][-1]['status'],'unknown')
        self.assertEqual(next_service.ask(self.a,'paid','Вопрос','public')['status'],'unknown')
        next_service.pricing_fn=lambda:self.fail('pricing before recovery')
        blocked=next_service.ask(self.a,'blocked','Новый вопрос','public')
        self.assertEqual(blocked['error'],'explicit_recovery_required')
        self.assertFalse(next_service.cloud_state()['enabled'])

    def test_restart_from_selection_pre_reserve_and_saved_validation(self):
        real_save=save
        for phase in ('selecting','generating','validating'):
            ident='crash-'+phase
            def crash_phase(path,data):
                real_save(path,data)
                if Path(path).name=='result-'+ident+'.json' and data.get('stage')==phase:
                    raise PowerLoss()
            before=len(self.generate_calls)
            with patch('service.save',side_effect=crash_phase):
                with self.assertRaises(PowerLoss):self.service.ask(self.a,ident,'Вопрос','public')
            self.assertEqual(read(self.service.path(ident))['stage'],phase)
            self.assertEqual(len(self.generate_calls)-before,1 if phase=='validating' else 0)
            restored=Service(self.root,generate_fn=lambda *_:self.fail('restart repeated paid call'))
            result=restored.get(self.a,ident)
            self.assertEqual(result['status'],'interrupted')
            self.assertEqual(result['stage'],'terminal')
            self.assertNotIn('answer',result)
            restored.ask(self.a,ident,'Вопрос','public')

    def test_pending_save_failure_never_calls_provider_and_blocks_reserve(self):
        real_save=save
        def fail_pending(path,data):
            if Path(path).name=='result-pending.json' and data.get('generation',{}).get('transmission')=='pending':
                raise OSError('pending save')
            real_save(path,data)
        with patch('service.save',side_effect=fail_pending):
            item=self.service.ask(self.a,'pending','Вопрос','public')
        self.assertEqual(item['status'],'unknown')
        self.assertEqual(self.generate_calls,[])
        self.assertEqual(read(self.root/'ledger.json')['entries'][-1]['status'],'inflight')
        restored=Service(self.root,generate_fn=lambda *_:self.fail('pending call repeated'))
        self.assertEqual(restored.ask(self.a,'pending','Вопрос','public')['status'],'unknown')
        self.assertFalse(restored.cloud_state()['enabled'])

    def test_timeout_and_unknown_cost_block_retry(self):
        def timeout(*_):raise TimeoutError('provider timeout')
        self.service.generate_fn=timeout
        item=self.service.ask(self.a,'timeout','Вопрос','public')
        self.assertEqual(item['status'],'unknown')
        self.assertEqual(item['generation']['transmission'],'unknown')
        self.assertEqual(read(self.root/'ledger.json')['entries'][0]['status'],'unknown')
        self.assertEqual(self.service.ask(self.a,'timeout','Вопрос','public')['status'],'unknown')
        self.assertEqual(self.service.ask(self.a,'blocked','Новый вопрос','public')['error'],'explicit_recovery_required')

    def test_unknown_cost_preserves_answer_but_blocks_new_paid_calls(self):
        original=self.service.generate_fn
        def unknown_cost(body,key):
            raw=original(body,key);raw['usage']['cost']=None;return raw
        self.service.generate_fn=unknown_cost
        item=self.service.ask(self.a,'unknown-cost','Вопрос','public')
        self.assertEqual(item['status'],'verified')
        self.assertIsNone(item['cost'])
        self.assertTrue(read(self.root/'ledger.json')['entries'][-1]['cost_unknown'])
        count=len(self.generate_calls)
        self.service.ask(self.a,'unknown-cost','Вопрос','public')
        blocked=self.service.ask(self.a,'blocked-cost','Новый вопрос','public')
        self.assertEqual(blocked['error'],'explicit_recovery_required')
        self.assertEqual(len(self.generate_calls),count)

    def test_candidate_outside_transmitted_context_and_hidden_text_rejected(self):
        original_search=self.service.search_fn
        def search(*args):
            result=original_search(*args)
            selected=result['trace']['selected'][0]
            selected['message_parts']=[{'text':'VISIBLE', 'message_id':1,'author':'synthetic',
                                        'date':'2026-09-28','member_id':'synthetic','source_key':'synthetic','attribution':'explicit'}]
            selected['text']='HIDDEN VISIBLE'
            result['trace']['candidates'].append(dict(selected,chunk_id='candidate-only'))
            return result
        self.service.search_fn=search
        for index,(cid,quote) in enumerate((('candidate-only','VISIBLE'),('c1','HIDDEN'))):
            content=json.dumps({'answer':'Синтетический ответ','sources':[{'source':'assignment','chunk_id':cid}],
                                'quotes':[{'chunk_id':cid,'text':quote}]})
            self.service.generate_fn=lambda *_:{'model':MODEL,'provider':'DeepInfra','usage':{'cost':.00001},
                'choices':[{'finish_reason':'stop','message':{'content':content}}]}
            item=self.service.ask(self.a,'outside'+str(index),'Вопрос','public')
            self.assertEqual(item['status'],'unverified')
            self.assertEqual(item['generation']['transmitted_chunk_ids'],['c1'])
            if index==0:self.assertIn('source_not_in_context',item['validation']['errors'])
            else:self.assertIn('quote_not_in_transmitted_text',item['validation']['errors'])

    def test_storage_failures_no_false_success_or_paid_repeat(self):
        real_save=save
        def fail_initial(path,data):
            if Path(path).name=='result-initial.json':raise OSError('initial save')
            real_save(path,data)
        with patch('service.save',side_effect=fail_initial):
            with self.assertRaises(OSError):self.service.ask(self.a,'initial','Вопрос','public')
        self.assertEqual(len(self.search_calls),0)
        self.assertEqual(len(self.generate_calls),0)
        def fail_reserve(path,data):
            if Path(path).name=='ledger.json':raise OSError('reserve save')
            real_save(path,data)
        with patch('service.save',side_effect=fail_reserve):
            item=self.service.ask(self.a,'reserve','Вопрос','public')
        self.assertEqual(item['status'],'error')
        self.assertEqual(len(self.generate_calls),0)
        def fail_terminal(path,data):
            if Path(path).name=='result-terminal.json' and data.get('stage')=='terminal':raise OSError('terminal save')
            real_save(path,data)
        with patch('service.save',side_effect=fail_terminal):
            item=self.service.ask(self.a,'terminal','Вопрос','public')
        self.assertFalse(item['saved'])
        self.assertEqual(item['status'],'unverified')
        self.assertNotIn('answer',item)
        count=len(self.generate_calls)
        self.service.ask(self.a,'terminal','Вопрос','public')
        self.assertEqual(len(self.generate_calls),count)
        restarted=Service(self.root,generate_fn=lambda *_:self.fail('unsaved response repeated'))
        self.assertNotEqual(restarted.get(self.a,'terminal')['status'],'verified')
        self.assertEqual(restarted.ask(self.a,'terminal','Вопрос','public')['status'],'interrupted')

    def test_final_ledger_save_failure_blocks_all_new_calls(self):
        real_save=save
        def fail_final_ledger(path,data):
            if Path(path).name=='ledger.json' and data['entries'][-1]['status']=='completed':raise OSError('final ledger save')
            real_save(path,data)
        with patch('service.save',side_effect=fail_final_ledger):
            item=self.service.ask(self.a,'ledger-failure','Вопрос','public')
        self.assertEqual(item['status'],'unknown')
        self.assertIn('ledger_save_error',item)
        self.assertEqual(read(self.root/'ledger.json')['entries'][-1]['status'],'inflight')
        count=len(self.generate_calls)
        self.service.ask(self.a,'ledger-failure','Вопрос','public')
        blocked=self.service.ask(self.a,'new','Новый вопрос','public')
        self.assertEqual(blocked['error'],'explicit_recovery_required')
        self.assertEqual(len(self.generate_calls),count)


# Avoid rerunning inherited T2 cases in this suite while keeping its fixture.
for name in list(context_fixture.ContextTest.__dict__):
    if name.startswith('test_') and name not in StatesTest.__dict__:
        setattr(StatesTest,name,None)

if __name__=='__main__':unittest.main()
