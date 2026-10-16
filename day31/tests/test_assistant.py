"""Проверки общего обработчика с fake model/MCP, отдельно от live MCP."""
import json
import tempfile
import unittest
from pathlib import Path
from day31.assistant import Assistant
from day31.retrieval import RetrievalIndex
from day31.provider import ProviderResult, ProviderError
from day31.contracts import SourceChunk


class FakeMcp:
    last_discovery = {'protocol_version':'test','tools':['git_context']}
    def __init__(self, error=False): self.error = error; self.calls = 0
    def read(self):
        self.calls += 1
        if self.error: raise RuntimeError('SDK secret')
        return {'repository_id':'abc','branch':'test','detached':False,'head':'a'*40}


class FakeProvider:
    model = 'fake-model'; provider = 'fake'
    def __init__(self, response=None, error=False): self.response=response; self.error=error; self.calls=[]
    def generate(self, question, sources, git_context, trace_id):
        self.calls.append((question,sources,git_context,trace_id))
        if self.error: raise ProviderError('Безопасная ошибка модели')
        content=self.response if self.response is not None else json.dumps({'status':'ok','text':'Документированный ответ','source_ids':[sources[0]['id']]})
        return ProviderResult(content, {'cost_usd':None,'prompt_tokens':30,'completion_tokens':10})


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name); (root/'README.md').write_text('# Запуск\n\nPython запускает MCP сервер.\n')
        self.index=RetrievalIndex(root,root/'index.db')

    def make(self, provider=None, mcp=None):
        return Assistant(self.index,mcp or FakeMcp(),provider or FakeProvider())

    def test_help_same_handler_and_independent_runs(self):
        p=FakeProvider(); a=self.make(p)
        first=a.answer('/help Как запустить MCP?'); second=a.answer('Как запустить MCP?')
        self.assertEqual(first.status,'ok'); self.assertEqual(first.text,second.text)
        self.assertNotEqual(first.trace_id,second.trace_id)
        self.assertEqual(first.git_context['branch'],'test')
        self.assertEqual([s['name'] for s in first.stages],['search','mcp','model'])
        self.assertEqual(len(p.calls),2)
        self.assertNotIn('/help',p.calls[0][0])
        self.assertEqual(first.source_ids,[first.sources[0]['id']])

    def test_unknown_skips_provider_but_reads_mcp(self):
        p=FakeProvider(); m=FakeMcp(); result=self.make(p,m).answer('погода Барселона')
        self.assertEqual(result.status,'unknown'); self.assertEqual(p.calls,[]); self.assertEqual(m.calls,1)
        self.assertEqual(result.stages[-1]['status'],'skipped')

    def test_invalid_json_unknown_reference_missing_citation_empty_and_truncation(self):
        responses=['not JSON','{}','{"status":"ok","text":"ответ","source_ids":["fake"]}',
            '{"status":"ok","text":"ответ","source_ids":[]}',
            '{"status":"ok","text":" ","source_ids":[]}',
            '{"status":"unknown","text":"не знаю","source_ids":["fake"]}']
        for content in responses:
            with self.subTest(content=content):
                result=self.make(FakeProvider(content)).answer('MCP')
                self.assertEqual(result.status,'error')
                self.assertEqual(result.source_ids,[])
                self.assertNotIn('not JSON',result.text)

    def test_valid_inline_sources_are_normalized_for_unknown_and_ok(self):
        source=self.index.search('MCP')[0]
        for status in ('unknown','ok'):
            with self.subTest(status=status):
                text=f'Текст [{source.id}] без повторной генерации'
                provider=FakeProvider(json.dumps({'status':status,'text':text,'source_ids':[]}))
                result=self.make(provider).answer('MCP')
                self.assertEqual(result.status,status)
                self.assertEqual(result.text,text)
                self.assertEqual(result.source_ids,[source.id])
                self.assertEqual(len(provider.calls),1)
                self.assertEqual(result.stages[-1]['source_id_normalization'],{'method':'deterministic','added_from_inline':[source.id]})

    def test_normalization_keeps_declared_order_then_inline_order_and_deduplicates(self):
        ids=['1'*20,'2'*20,'3'*20]
        class Index:
            def search(self,question):
                return [SourceChunk(i,'README.md',1,1,'Раздел','Данные','h') for i in ids]
        text=f'[{ids[2]}] [{ids[0]}] [{ids[2]}] [{ids[1]}]'
        provider=FakeProvider(json.dumps({'status':'ok','text':text,'source_ids':[ids[1]]}))
        result=Assistant(Index(),FakeMcp(),provider).answer('MCP')
        self.assertEqual(result.status,'ok')
        self.assertEqual(result.text,text)
        self.assertEqual(result.source_ids,[ids[1],ids[2],ids[0]])
        self.assertEqual(result.stages[-1]['source_id_normalization']['added_from_inline'],[ids[2],ids[0]])

    def test_unknown_inline_declared_or_mixed_source_is_always_error(self):
        valid=self.index.search('MCP')[0].id
        unknown='f'*20
        for refs,text in [([unknown],'Текст'),([] ,f'[{unknown}]'),([valid],f'[{valid}] [{unknown}]'),([unknown],f'[{valid}]')]:
            for status in ('ok','unknown'):
                with self.subTest(status=status,refs=refs,text=text):
                    provider=FakeProvider(json.dumps({'status':status,'text':text,'source_ids':refs}))
                    result=self.make(provider).answer('MCP')
                    self.assertEqual(result.status,'error')
                    self.assertEqual(result.source_ids,[])
                    self.assertEqual(len(provider.calls),1)

    def test_schema_is_enforced_before_and_after_source_normalization(self):
        valid=self.index.search('MCP')[0].id
        for changed in [{'status':'bad'},{'extra':1},{'source_ids':'not-list'},{'text':' '},{'source_ids':[valid,valid]}]:
            with self.subTest(changed=changed):
                content={'status':'ok','text':f'[{valid}]','source_ids':[]}
                content.update(changed)
                self.assertEqual(self.make(FakeProvider(json.dumps(content))).answer('MCP').status,'error')
        ids=[f'{i:020x}' for i in range(9)]
        class Index:
            def search(self,question):
                return [SourceChunk(i,'README.md',1,1,'Раздел','Данные','h') for i in ids]
        provider=FakeProvider(json.dumps({'status':'ok','text':' '.join(f'[{i}]' for i in ids),'source_ids':[]}))
        self.assertEqual(Assistant(Index(),FakeMcp(),provider).answer('MCP').status,'error')

    def test_mcp_failure_blocks_generation_and_sanitizes(self):
        p=FakeProvider(); result=self.make(p,FakeMcp(error=True)).answer('MCP')
        self.assertEqual(result.status,'error'); self.assertEqual(p.calls,[])
        self.assertNotIn('SDK secret',json.dumps(result.to_dict()))
        self.assertEqual(result.stages[-1]['status'],'error')

    def test_provider_failure_is_error(self):
        result=self.make(FakeProvider(error=True)).answer('MCP')
        self.assertEqual(result.status,'error'); self.assertIn('модели',result.text)

    def test_bad_input_no_dependencies(self):
        for q in ('','/help','x'*4001,False):
            with self.subTest(q=str(q)[:20]):
                p=FakeProvider(); m=FakeMcp(); result=self.make(p,m).answer(q)
                self.assertEqual(result.status,'error'); self.assertEqual(m.calls,0); self.assertEqual(p.calls,[])


if __name__ == '__main__': unittest.main()
