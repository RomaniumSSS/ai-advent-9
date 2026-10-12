"""Регрессии profile09 с текущими лимитами: wire/budget и общие ожидания; моки/loopback."""
import asyncio
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import local,service,server,deploy,client
from test_service import Fake,chunk
from test_review_regressions import ImmediateFixture,SlowFixture

class Profile09Tests(unittest.TestCase):
    def test_actual_wire_stage_caps_trace_and_options_do_not_leak(self):
        calls=[];bounds=[]
        class Wire(Fake):
            def chat(self,m,s,options=None,think=False,native_format=True,deadline_seconds=None):
                response=super().chat(m,s,options,think,native_format)
                original=local.DeadlineConnection
                def record(host,port,deadline):
                    bounds.append(deadline-time.monotonic());return original(host,port,deadline)
                with ImmediateFixture(local.packed(response)) as fixture,patch('local.OLLAMA_URL',fixture.url),patch('local.DeadlineConnection',side_effect=record):
                    value=local.Ollama(fixture.url).chat(m,s,options=options,think=think,native_format=native_format,deadline_seconds=deadline_seconds)
                    calls.append(json.loads(fixture.calls[0]['body']));return value
        result=service.Engine([chunk()],Wire()).answer('Какие условия дня 30?',[])
        self.assertEqual([p['options']['num_predict'] for p in calls],[1024,1024])
        for observed,expected in zip(bounds,(300,300)):self.assertAlmostEqual(observed,expected,delta=.1)
        for phase,expected in (('selection',300),('synthesis',300)):
            self.assertEqual(result['trace']['generation_parameters'][phase]['deadline_seconds'],expected)
            self.assertEqual(result['trace']['budgets'][phase]['deadline_seconds'],expected)
        self.assertEqual(result['trace']['provider_deadlines']['embedding'],300)
        self.assertNotIn('deadline_seconds',calls[1]['options']);self.assertIn('format',calls[1]);self.assertFalse(calls[1]['think'])
        self.assertEqual(local.GEN_OPTIONS['num_predict'],1024);self.assertEqual(result['metrics']['generation_calls'],2)
    def test_default_routes_300_and_short_timeout_patch_still_applies_to_synthesis(self):
        observed=[];original=local.DeadlineConnection
        def record(host,port,deadline):observed.append(deadline-time.monotonic());return original(host,port,deadline)
        with ImmediateFixture(b'{}') as fixture,patch('local.OLLAMA_URL',fixture.url),patch('local.DeadlineConnection',side_effect=record):
            provider=local.Ollama(fixture.url);provider.request('/api/tags')
            provider.chat([],{},deadline_seconds=300)
            with patch('local.TIMEOUT',.2):provider.chat([],{},deadline_seconds=300)
        for actual,expected in zip(observed,(300,300,.2)):self.assertAlmostEqual(actual,expected,delta=.05)
    def test_output1024_fits_saved_bound_and_observed_cap_is_strict(self):
        class FixedCount:
            def count(self,text):return 5728 if text.startswith('[') else 0
        options=service.generation_options('synthesis');messages=[{'role':'user','content':'synthetic'}]
        budget=service.budget_for(messages,None,FixedCount(),options=options)
        self.assertEqual(budget['input_upper_bound'],6240);self.assertEqual(budget['output_reserved'],1024)
        self.assertEqual(budget['input_upper_bound']+budget['output_reserved'],7264)
        response={'model':local.MODEL,'done':True,'done_reason':'stop','message':{'content':'{}'},'prompt_eval_count':6656}
        self.assertEqual(service.parse_response(response,options=options,think=True),{})
        response['prompt_eval_count']=6657
        with self.assertRaisesRegex(ValueError,'observed_context_overflow_or_missing_count'):service.parse_response(response,options=options,think=True)
    def test_stalled_headers_and_body_use_short_absolute_cap_and_cancel_before_return(self):
        for phase in ('headers','body'):
            with self.subTest(phase=phase),SlowFixture(phase) as fixture,patch('local.OLLAMA_URL',fixture.url),patch('local.TIMEOUT',.12):
                provider=local.Ollama(fixture.url);started=time.monotonic()
                with self.assertRaises(local.ProviderTimeout) as caught:provider.chat([],{},think=True,native_format=False,deadline_seconds=300)
                self.assertLess(time.monotonic()-started,.3);self.assertTrue(fixture.cancelled.wait(.15))
                self.assertEqual(fixture.calls,1);self.assertFalse(hasattr(caught.exception,'response_text'))
    def test_timeout_closes_transport_before_application_releases_lock(self):
        connections=[];released=[];original=local.DeadlineConnection
        def record(host,port,deadline):
            connection=original(host,port,deadline);connections.append(connection);return connection
        @contextlib.contextmanager
        def lock():
            yield
            released.append([c.transport_socket.fileno() for c in connections])
        class Wire(Fake):
            def chat(self,*args,**kwargs):return provider.chat(*args,**kwargs)
        with SlowFixture('body') as fixture,patch('local.OLLAMA_URL',fixture.url),patch('local.TIMEOUT',.12),patch('local.DeadlineConnection',side_effect=record),tempfile.TemporaryDirectory() as d:
            provider=local.Ollama(fixture.url);app=server.Application(service.Engine([chunk()],Wire()),service.Store(Path(d)/'state'),'fixture-token')
            with patch('service.generation_lock',side_effect=lock),contextlib.redirect_stdout(io.StringIO()):
                accepted=app.submit({'question':'Какие условия дня 30?'});app.wait_workers()
            self.assertEqual(released,[[-1]]);self.assertFalse(app.active)
            receipt=app.store.receipt(accepted['request_id'],'all');self.assertEqual(receipt['status'],'error')
            self.assertEqual(receipt['error']['code'],'inference_timeout');self.assertEqual(fixture.calls,1)
    def test_coupled_worker_join_plist_and_legacy_plist_preservation(self):
        app=server.Application(object(),object(),'fixture-token');worker=Mock();app.workers.add(worker);app.wait_workers()
        worker.join.assert_called_once_with(910)
        with tempfile.TemporaryDirectory() as d:
            env=Path(d)/'.env';env.write_text('DAY30_TOKEN=fixture\nDAY30_PRIVATE='+d+'\n');env.chmod(0o600)
            path=deploy.prepare(env,'org.ai-advent.day30',sys.executable)
            self.assertEqual(plistlib.loads(path.read_bytes())['ExitTimeOut'],920);self.assertEqual(deploy.shutdown_timeout(path),925)
            path.write_bytes(plistlib.dumps({'ExitTimeOut':910}));self.assertEqual(deploy.shutdown_timeout(path),915)
    def test_client_accepts_completion_before930_not_old920(self):
        accepted={'status':'accepted','request_id':'a'*32};done={'status':'done','request_id':'a'*32}
        args=['client.py','--env','fake.env','--base-url','https://localhost','--cafile','fake.crt','--question','q','--wait']
        with patch.object(sys,'argv',args),patch('client.load_env',return_value={'DAY30_TOKEN':'fixture'}),patch('client.request',side_effect=[accepted,done]) as request,patch('client.time.monotonic',side_effect=[0,929]),patch('client.time.sleep'),contextlib.redirect_stdout(io.StringIO()):client.main()
        self.assertEqual(request.call_count,2)
    def test_video_terminal_wait_uses930_seconds(self):
        spec=importlib.util.spec_from_file_location('day30_video_test',Path(__file__).resolve().parents[1]/'video/run_demo.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        page=SimpleNamespace(wait_for_function=AsyncMock())
        asyncio.run(module.wait_for_terminal_turn(page))
        self.assertEqual(page.wait_for_function.call_args.kwargs['timeout'],930000)

if __name__=='__main__':unittest.main()
