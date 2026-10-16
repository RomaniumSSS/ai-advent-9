"""Бюджет и адаптер проверяются fake SDK, реальных запросов нет."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import threading
from day31.provider import OpenRouterProvider, ProviderError, BudgetLedger, check_endpoint


def completion(content='{}', finish='stop', usage=True):
    return NS(choices=[NS(finish_reason=finish, message=NS(content=content, refusal=None))], usage=NS(prompt_tokens=100, completion_tokens=20, cost=0.001) if usage else None)


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response or completion()
        self.error = error
        self.calls = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ledger = BudgetLedger(Path(self.tmp.name) / 'ledger.db', 0.1)

    def test_exactly_one_call_pinned_provider_schema_and_usage(self):
        client = FakeClient(completion('{"status":"ok","text":"Текст","source_ids":["a"]}'))
        provider = OpenRouterProvider('test', self.ledger, client=client)
        result = provider.generate('вопрос', [{'id': 'a', 'text': 'данные'}], {'branch':'demo'}, 't1')
        self.assertEqual(len(client.calls), 1)
        request = client.calls[0]
        self.assertEqual(request['model'],'deepseek/deepseek-v4.1-flash')
        self.assertEqual(provider.model,'deepseek/deepseek-v4.1-flash')
        self.assertEqual(provider.provider,'deepinfra/fp8')
        self.assertEqual(request['max_tokens'],1600)
        self.assertEqual(request['extra_body']['provider'], {'only':['deepinfra/fp8'], 'allow_fallbacks':False,'require_parameters':True})
        self.assertEqual(request['extra_body']['reasoning'],{'enabled':False})
        self.assertNotIn('tools', request)
        self.assertEqual(request['response_format']['type'], 'json_schema')
        self.assertIs(request['response_format']['json_schema']['strict'],True)
        self.assertEqual(result.usage['cost_usd'], 0.001)
        self.assertEqual(self.ledger.entries()[0]['state'], 'complete')

    def test_ambiguous_failure_holds_reserve_and_no_retry(self):
        client = FakeClient(error=TimeoutError('secret_from_sdk'))
        provider = OpenRouterProvider('test', self.ledger, client=client)
        with self.assertRaises(ProviderError) as caught:
            provider.generate('q', [{'id':'a'}], {}, 't2')
        self.assertNotIn('secret_from_sdk', str(caught.exception))
        self.assertEqual(len(client.calls), 1)
        entry = self.ledger.entries()[0]
        self.assertIsNone(entry['cost_usd'])
        self.assertEqual(entry['charged_usd'], entry['reserved_usd'])
        self.assertEqual(entry['state'], 'ambiguous')

    def test_unknown_usage_is_not_zero_and_truncation_fails(self):
        client = FakeClient(completion(finish='length', usage=False))
        with self.assertRaises(ProviderError):
            OpenRouterProvider('test', self.ledger, client=client).generate('q', [], {}, 't3')
        entry = self.ledger.entries()[0]
        self.assertIsNone(entry['cost_usd'])
        self.assertGreater(entry['charged_usd'], 0)

    def test_persistent_budget_atomic_reserve(self):
        ledger = BudgetLedger(Path(self.tmp.name) / 'small.db', 0.01)
        def reserve(i):
            try:
                ledger.reserve(str(i), 0.006)
                return True
            except ProviderError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(reserve, range(2))), 1)
        same = BudgetLedger(Path(self.tmp.name) / 'small.db', 0.01)
        with self.assertRaises(ProviderError):
            same.reserve('next', 0.006)
        with self.assertRaises(ValueError):
            BudgetLedger(Path(self.tmp.name) / 'small.db', 0.1)

    @staticmethod
    def endpoint(**changes):
        endpoint={'provider_name':'DeepInfra','status':0,'tag':'deepinfra/fp8',
            'supported_parameters':['reasoning','response_format','structured_outputs','max_tokens','temperature'],
            'pricing':{'prompt':'0.0000002','completion':'0.0000006','discount':0}}
        endpoint.update(changes)
        return endpoint

    def test_metadata_preflight_exact_route_and_price_ceiling(self):
        endpoint=self.endpoint()
        result=check_endpoint(lambda:{'data':{'endpoints':[endpoint]}})
        self.assertEqual(result['model'],'deepseek/deepseek-v4.1-flash')
        self.assertEqual(result['provider'],'deepinfra/fp8')
        self.assertEqual(result['endpoints'][0]['tag'],'deepinfra/fp8')
        self.assertAlmostEqual(result['endpoints'][0]['prompt_usd_per_m'],0.20)
        self.assertAlmostEqual(result['endpoints'][0]['completion_usd_per_m'],0.60)
        for field,value in [('prompt','0.000000201'),('completion','0.000000601'),('discount',0.25)]:
            with self.subTest(field=field):
                changed=self.endpoint()
                changed['pricing'][field]=value
                with self.assertRaises(ProviderError):
                    check_endpoint(lambda:{'data':{'endpoints':[changed]}})

    def test_preflight_absent_inactive_or_wrong_tag_cannot_fallback(self):
        cases=[[],[self.endpoint(status=1)],[self.endpoint(tag='venice')],
            [self.endpoint(tag='venice/fp16')],[self.endpoint(tag='deepinfra/bf16',provider_name='DeepInfra')],
            [self.endpoint(status=1),self.endpoint(tag='venice/fp16')]]
        for endpoints in cases:
            with self.subTest(endpoints=endpoints):
                with self.assertRaises(ProviderError):
                    check_endpoint(lambda:{'data':{'endpoints':endpoints}})
        with self.assertRaises(ProviderError): check_endpoint(lambda:{})

    def test_preflight_requires_all_request_parameters(self):
        supported=self.endpoint()['supported_parameters']
        for missing in supported:
            with self.subTest(missing=missing):
                endpoint=self.endpoint(supported_parameters=[p for p in supported if p!=missing])
                with self.assertRaises(ProviderError):
                    check_endpoint(lambda:{'data':{'endpoints':[endpoint]}})

    def test_sdk_has_no_automatic_retries(self):
        with patch('day31.provider.OpenAI') as factory:
            OpenRouterProvider('test-key',self.ledger)
        self.assertEqual(factory.call_count,1)
        self.assertEqual(factory.call_args.kwargs['max_retries'],0)
        self.assertEqual(factory.call_args.kwargs['base_url'],'https://openrouter.ai/api/v1')

    def test_explicit_profiles_are_immutable_and_share_request_builder(self):
        from dataclasses import FrozenInstanceError
        from day31.provider import ProviderProfile, build_request, request_reserve
        reasoning={'effort':'low','exclude':True}
        profile=ProviderProfile('test/model','test/fp8',2.0,6.0,8192,reasoning)
        reasoning['effort']='high'
        self.assertEqual(profile.reasoning['effort'],'low')
        with self.assertRaises(TypeError): profile.reasoning['effort']='high'
        with self.assertRaises(FrozenInstanceError): profile.model='other/model'
        request=build_request(profile,'Одинаковая инструкция','q',[{'id':'a'}],{'branch':'demo'})
        self.assertEqual(request['model'],'test/model')
        self.assertEqual(request['max_tokens'],8192)
        self.assertEqual(request['extra_body']['reasoning'],{'effort':'low','exclude':True})
        self.assertEqual(request['extra_body']['provider']['only'],['test/fp8'])
        client=FakeClient()
        provider=OpenRouterProvider('test',self.ledger,profile=profile,system='Одинаковая инструкция',client=client)
        provider.generate('q',[{'id':'a'}],{'branch':'demo'},'profile-test')
        self.assertEqual(client.calls,[request])
        self.assertAlmostEqual(self.ledger.entries()[0]['reserved_usd'],request_reserve(profile,request))

    def test_profile_preflight_uses_own_model_route_and_ceilings(self):
        from day31.provider import ProviderProfile
        profile=ProviderProfile('new/model','new/fp4',0.15,0.50,8192,{'effort':'low','exclude':True})
        endpoint=self.endpoint(tag='new/fp4',pricing={'prompt':'0.00000015','completion':'0.0000005','discount':0})
        result=check_endpoint(lambda:{'data':{'endpoints':[endpoint]}},profile=profile)
        self.assertEqual(result['model'],'new/model')
        self.assertEqual(result['provider'],'new/fp4')
        with self.assertRaises(ProviderError):
            check_endpoint(lambda:{'data':{'endpoints':[self.endpoint()]}},profile=profile)
        for change in ({'input_usd_per_m':float('nan')},{'max_output_tokens':0},{'reasoning':{'enabled':False,'effort':'low'}}):
            values=profile.to_dict(); values.update(change)
            with self.assertRaises(ValueError): ProviderProfile.from_dict(values)

    def test_observability_records_final_and_token_counts_without_hidden_reasoning(self):
        response=completion('{"status":"unknown","text":"Не знаю","source_ids":[]}')
        response.id='receipt'; response.model='returned/model'; response.provider='Returned'
        response.choices[0].message.reasoning_content='HIDDEN_REASONING_MUST_NOT_BE_SAVED'
        response.usage.completion_tokens_details=NS(reasoning_tokens=7)
        provider=OpenRouterProvider('test',self.ledger,client=FakeClient(response))
        provider.generate('q',[],{},'observe')
        self.assertEqual(provider.last_call['finish_reason'],'stop')
        self.assertEqual(provider.last_call['usage']['reasoning_tokens'],7)
        self.assertEqual(provider.last_call['receipt']['id'],'receipt')
        self.assertNotIn('HIDDEN_REASONING',json.dumps(provider.last_call))
        truncated=OpenRouterProvider('test',self.ledger,client=FakeClient(completion('partial',finish='length')))
        with self.assertRaises(ProviderError): truncated.generate('q',[],{},'truncated')
        self.assertEqual(truncated.last_call['finish_reason'],'length')
        self.assertEqual(truncated.last_call['content'],'partial')

    def test_comparison_reuses_context_and_stops_before_api_when_total_not_affordable(self):
        from day31.eval.compare_models import run_comparison
        from day31.provider import DEFAULT_PROFILE
        from day31.contracts import SourceChunk
        class Index:
            calls=0
            def search(self,question):
                self.calls+=1
                return [SourceChunk('a'*20,'README.md',1,1,'Раздел','Tool data','h')]
        class Mcp:
            calls=0; last_discovery={'protocol_version':'test','tools':['git_context']}
            def read(self):
                self.calls+=1
                return {'branch':'demo','head':'f'*40,'detached':False,'repository_id':'r'}
        clients=[]
        def factory(profile):
            client=FakeClient(completion('{"status":"ok","text":"Ответ","source_ids":["'+('a'*20)+'"]}'))
            clients.append(client); return client
        index=Index();mcp=Mcp();profiles={'one':DEFAULT_PROFILE,'two':DEFAULT_PROFILE,'three':DEFAULT_PROFILE}
        output=Path(self.tmp.name)/'compare'
        summary=run_comparison(profiles,index,mcp,self.ledger,'Одинаковая инструкция',output,execute=True,key='test',client_factory=factory,preflight=lambda profile:{'model':profile.model,'provider':profile.exact_route})
        self.assertEqual(summary['status'],'complete')
        self.assertEqual(index.calls,3);self.assertEqual(mcp.calls,3)
        self.assertEqual(sum(len(c.calls) for c in clients),9)
        for question_index in range(3):
            messages=[c.calls[question_index]['messages'] for c in clients]
            self.assertEqual(messages[0],messages[1]);self.assertEqual(messages[1],messages[2])
        tiny=BudgetLedger(Path(self.tmp.name)/'tiny.db',0.00001)
        before=len(clients)
        stopped=run_comparison(profiles,Index(),Mcp(),tiny,'same',Path(self.tmp.name)/'stop',execute=True,key='test',client_factory=factory,preflight=lambda profile:{})
        self.assertEqual(stopped['status'],'stopped_budget')
        self.assertEqual(len(clients),before)
        self.assertEqual(tiny.entries(),[])

    def test_three_profile_workers_overlap_and_keep_context_and_reservations_isolated(self):
        from dataclasses import replace
        from day31.eval.compare_models import run_comparison, QUESTIONS
        from day31.provider import DEFAULT_PROFILE
        from day31.contracts import SourceChunk
        class Context:
            last_discovery={}
            calls=0
            def search(self,question): return [SourceChunk('a'*20,'README.md',1,1,'Раздел','Данные','h')]
            def read(self): return {'branch':'demo','head':'f'*40}
        barrier=threading.Barrier(3,timeout=2)
        clients={};lock=threading.Lock()
        class ParallelClient(FakeClient):
            def create(self,**kwargs):
                if not self.calls: barrier.wait()
                self.worker=threading.get_ident()
                return super().create(**kwargs)
        def factory(profile):
            client=ParallelClient(completion('{"status":"ok","text":"Ответ","source_ids":["'+('a'*20)+'"]}'))
            with lock: clients[profile.model]=client
            return client
        profiles={name:replace(DEFAULT_PROFILE,model='test/'+name) for name in ('one','two','three')}
        output=Path(self.tmp.name)/'parallel'
        result=run_comparison(profiles,Context(),Context(),self.ledger,'same',output,execute=True,key='test',client_factory=factory,preflight=lambda profile:{})
        self.assertEqual(result['status'],'complete')
        self.assertEqual(len({client.worker for client in clients.values()}),3)
        for name,profile in profiles.items():
            requests=clients[profile.model].calls
            self.assertEqual([json.loads(request['messages'][1]['content'])['question'] for request in requests],[q for _,q in QUESTIONS])
            self.assertEqual(len(list((output/name).glob('*.json'))),3)
        for i in range(3):
            self.assertEqual(clients['test/one'].calls[i]['messages'],clients['test/two'].calls[i]['messages'])
            self.assertEqual(clients['test/one'].calls[i]['messages'],clients['test/three'].calls[i]['messages'])
        self.assertEqual(len(self.ledger.entries()),9)
        self.assertTrue(all(row['state']=='complete' for row in self.ledger.entries()))
        self.assertAlmostEqual(self.ledger.budget_state()['charged_usd'],0.009)

    def test_runner_stops_partial_when_concurrent_spend_exhausts_shared_budget(self):
        from day31.eval.compare_models import run_comparison
        from day31.provider import DEFAULT_PROFILE
        from day31.contracts import SourceChunk
        class Context:
            last_discovery={}
            def search(self,question): return [SourceChunk('a'*20,'README.md',1,1,'Раздел','Данные','h')]
            def read(self): return {'branch':'demo','head':'f'*40}
        clients=[];factory_lock=threading.Lock()
        def factory(profile):
            with factory_lock:
                if not clients:
                    # Другой процесс расходует бюджет после общего pre-check.
                    self.ledger.reserve('concurrent',0.099999)
                client=FakeClient();clients.append(client);return client
        result=run_comparison({'one':DEFAULT_PROFILE,'two':DEFAULT_PROFILE,'three':DEFAULT_PROFILE},Context(),Context(),self.ledger,'same',Path(self.tmp.name)/'partial',execute=True,key='test',client_factory=factory,preflight=lambda profile:{})
        self.assertEqual(result['status'],'partial_budget')
        self.assertGreaterEqual(len(result['calls']),1)
        self.assertLessEqual(len(result['calls']),3)
        self.assertTrue(all(call['error_code']=='budget_exceeded' for call in result['calls']))
        self.assertEqual(sum(len(c.calls) for c in clients),0)
        self.assertEqual(len(self.ledger.entries()),1)
        record=json.loads((Path(self.tmp.name)/'partial'/result['calls'][0]['file']).read_text())
        self.assertFalse(record['provider_final']['sent'])

    def test_runner_preflight_failure_sends_nothing_and_preserves_failure_summary(self):
        from day31.eval.compare_models import run_comparison
        from day31.provider import DEFAULT_PROFILE
        folder=Path(self.tmp.name)/'failed-preflight'
        def fail(profile): raise ProviderError('Метаданные недоступны')
        with self.assertRaises(ProviderError):
            run_comparison({'one':DEFAULT_PROFILE,'two':DEFAULT_PROFILE,'three':DEFAULT_PROFILE},None,None,self.ledger,'same',folder,execute=True,key='test',preflight=fail)
        self.assertEqual(json.loads((folder/'summary.json').read_text())['status'],'stopped_preflight')
        self.assertEqual(self.ledger.entries(),[])

    def test_real_sdk_http200_error_envelope_is_upstream_error_and_body_is_not_saved(self):
        import httpx2 as httpx
        from openai import OpenAI
        requests=[]
        def handle(request):
            requests.append(request)
            return httpx.Response(200,json={'id':'gen-error','error':{'code':429,'type':'rate_limit_error','status':429,'message':'SECRET_BODY_MUST_NOT_BE_SAVED','metadata':{'raw':'HIDDEN_REASONING'}}})
        with OpenAI(api_key='test-key',base_url='https://openrouter.invalid/api/v1',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handle))) as client:
            provider=OpenRouterProvider('test-key',self.ledger,client=client)
            with self.assertRaises(ProviderError) as caught:
                provider.generate('q',[],{},'http200-error')
        self.assertEqual(len(requests),1)
        self.assertEqual(caught.exception.code,'upstream_error')
        self.assertIn('Upstream',str(caught.exception))
        self.assertEqual(provider.last_call['error']['upstream'],{'code':429,'type':'rate_limit_error','status':429})
        self.assertEqual(provider.last_call['receipt']['id'],'gen-error')
        self.assertNotIn('SECRET_BODY',json.dumps(provider.last_call))
        self.assertNotIn('HIDDEN_REASONING',json.dumps(provider.last_call))
        self.assertIsNone(self.ledger.entries()[0]['cost_usd'])
        self.assertEqual(self.ledger.entries()[0]['charged_usd'],self.ledger.entries()[0]['reserved_usd'])

    def test_real_sdk_http_error_records_only_code_type_and_status_without_retry(self):
        import httpx2 as httpx
        from openai import OpenAI
        requests=[]
        def handle(request):
            requests.append(request)
            return httpx.Response(404,json={'error':{'code':'route_not_found','type':'routing_error','message':'PRIVATE_BODY_CONTENT','reasoning':'HIDDEN_REASONING'}})
        with OpenAI(api_key='test-key',base_url='https://openrouter.invalid/api/v1',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handle))) as client:
            provider=OpenRouterProvider('test-key',self.ledger,client=client)
            with self.assertRaises(ProviderError) as caught:
                provider.generate('q',[],{},'sdk404')
        self.assertEqual(len(requests),1)
        self.assertEqual(caught.exception.code,'upstream_error')
        self.assertEqual(provider.last_call['error']['upstream'],{'code':'route_not_found','type':'routing_error','status':404})
        self.assertNotIn('PRIVATE_BODY',json.dumps(provider.last_call))
        self.assertNotIn('HIDDEN_REASONING',json.dumps(provider.last_call))
        self.assertIsNone(self.ledger.entries()[0]['cost_usd'])

    def test_default_system_matches_tested_prompt_diagnostic(self):
        from day31.provider import SYSTEM
        tested=Path(__file__).resolve().parents[1]/'results/prompt-diagnostic-20261016/tested-system.txt'
        self.assertEqual(SYSTEM,tested.read_text())

    def test_wire_schema_omits_only_unique_items_and_local_schema_still_rejects_duplicates(self):
        import copy
        from jsonschema import Draft202012Validator, ValidationError
        from day31.provider import ANSWER_SCHEMA, DEFAULT_PROFILE, SYSTEM, build_request
        original=copy.deepcopy(ANSWER_SCHEMA)
        request=build_request(DEFAULT_PROFILE,SYSTEM,'q',[],{})
        wire=request['response_format']['json_schema']['schema']
        self.assertNotIn('uniqueItems',wire['properties']['source_ids'])
        expected=copy.deepcopy(original)
        del expected['properties']['source_ids']['uniqueItems']
        self.assertEqual(wire,expected)
        self.assertEqual(ANSWER_SCHEMA,original)
        self.assertIs(ANSWER_SCHEMA['properties']['source_ids']['uniqueItems'],True)
        duplicated={'status':'ok','text':'Ответ','source_ids':['a'*20,'a'*20]}
        with self.assertRaises(ValidationError):
            Draft202012Validator(ANSWER_SCHEMA).validate(duplicated)
        self.assertIs(request['response_format']['json_schema']['strict'],True)

    def test_budget_rejects_nonfinite_and_zero(self):
        for limit in (0, -1, float('inf'), float('nan')):
            with self.assertRaises(ValueError):
                BudgetLedger(Path(self.tmp.name) / 'x.db', limit)


if __name__ == '__main__': unittest.main()
