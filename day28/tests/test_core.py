"""Офлайн-контракт: провайдер подменён, сеть и исходный индекс не используются."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import nullcontext
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core

V = [1.0] + [0.0]*1023
def chunk(cid='a', source='assignment', day=18, text='Нужно сделать поиск.'):
    return dict(chunk_id=cid,document_id=f'{source}:{day}',source=source,day=day,text=text,vector=V)

class Fake:
    def __init__(self, response=None):
        self.calls=[];self.formats=[]
        self.response=response or {'model':core.MODEL,'done':True,'done_reason':'stop',
            'message':{'content':json.dumps({'answer':'Поиск.','source_refs':['S1']},ensure_ascii=False)},
            'prompt_eval_count':400,'eval_count':50}
    def verify(self): return {'generator_digest':'b'*64,'embedding_digest':core.EMBED_DIGEST}
    def embed(self, q): self.calls.append(('embed',q));return V
    def chat(self, messages,schema=core.SCHEMA): self.calls.append(('chat',messages));self.formats.append(schema);return self.response

class Contract(unittest.TestCase):
    def setUp(self):
        # Live-прогон родителя держит настоящий lock; offline не претендует на модель.
        self.lock_patch=patch.object(core,'generation_lock',return_value=nullcontext())
        self.lock_patch.start();self.addCleanup(self.lock_patch.stop)
    def test_scope_before_ranking_and_explicit_days(self):
        selected, messages, trace = core.retrieve([chunk(),chunk('b','discussion'),chunk('c',day=19)],
            'Чем отличаются задания дней 18 и 19?',V,'public')
        self.assertEqual({c['day'] for c in selected},{18,19})
        self.assertNotIn('discussion',json.dumps(messages))
    def test_public_explicit_days_exclude_neighbors(self):
        selected,messages,trace=core.retrieve([chunk(),chunk('b',day=19),chunk('neighbor',day=14)],
            'Чем отличаются требования заданий дней 18 и 19?',V,'public')
        self.assertEqual({c['day'] for c in selected},{18,19})
        self.assertEqual(trace['eligible_count'],2)
    def test_missing_explicit_day_is_empty(self):
        selected,messages,trace=core.retrieve([chunk()], 'Что нужно сделать в задании дня 29?',V,'public')
        self.assertEqual(selected,[])
        self.assertEqual(trace['eligible_count'],0)
    def test_general_and_all_queries_keep_vector_path(self):
        data=[chunk(),chunk('b',day=19),chunk('discussion','discussion')]
        selected,_,trace=core.retrieve(data,'Какие темы описаны в заданиях?',V,'public')
        self.assertEqual(len(selected),2)
        selected,_,trace=core.retrieve(data,'Что требуется в задании дня 18?',V,'all')
        self.assertEqual(len(selected),3)
    def test_bad_vectors(self):
        for v in ([1], [float('nan')]+V[1:], [0]*1024):
            with self.assertRaises(ValueError): core.vector(v)
    def test_quotes_and_sources(self):
        good={'answer':'Поиск','sources':[{'source':'assignment:18','chunk_id':'a'}],
              'quotes':[{'chunk_id':'a','text':'сделать поиск'}]}
        self.assertTrue(core.validate_answer(good,[chunk()]))
        for key,value in [('source','discussion:18'),('chunk_id','missing')]:
            bad=json.loads(json.dumps(good));bad['sources'][0][key]=value
            with self.assertRaises(ValueError):core.validate_answer(bad,[chunk()])
        good['quotes'][0]['text']='Несуществующая цитата'
        with self.assertRaises(ValueError):core.validate_answer(good,[chunk()])
    def test_empty_skips_generation(self):
        f=Fake();e=core.Engine([],{},f)
        r=e.ask('Какое задание?', 'public',run_id='offline')
        self.assertEqual(r['status'],'unknown');self.assertEqual(len(f.calls),1)
        self.assertFalse(r['generation_called']);self.assertIsNone(r['metrics']['prompt_eval_count'])
    def test_terminal_and_metrics(self):
        f=Fake();r=core.Engine([chunk()],{},f).ask('Что требуется в задании дня 18?')
        self.assertEqual(r['status'],'done');self.assertTrue(r['citations_valid'])
        self.assertIsNone(r['groundedness_semantic']);self.assertTrue(r['request_id'])
        self.assertEqual(r['metrics']['prompt_eval_count'],400)
    def test_incomplete_and_timeout(self):
        for change in ({'done':False},{'done_reason':'length'},{'model':'remote'}):
            f=Fake();f.response.update(change)
            self.assertEqual(core.Engine([chunk()],{},f).ask('Задание дня 18')['status'],'error')
        f=Fake();f.chat=lambda m,**kw: (_ for _ in ()).throw(TimeoutError('timeout'))
        self.assertEqual(core.Engine([chunk()],{},f).ask('Задание дня 18')['status'],'error')
    def test_input_limit(self):
        with self.assertRaises(ValueError):core.validate_question('а'*501)
        with self.assertRaises(ValueError):core.check_budget([{'role':'user','content':'x'*10000}])
    def test_fixed_transport(self):
        for url in ('http://example.org','http://localhost:11434','http://127.0.0.1:11434/x','https://127.0.0.1:11434'):
            with self.assertRaises(ValueError):core.Ollama(url)
    def test_private_files(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'private'/'run'/'receipt.json';core.save_private(p,{'a':1})
            self.assertEqual(p.stat().st_mode&0o777,0o600)
            self.assertEqual(p.parent.stat().st_mode&0o777,0o700)
    def test_ollama_payload_no_retry(self):
        o=core.Ollama();calls=[]
        def request(path,payload=None):
            calls.append((path,payload))
            return {'model':core.EMBED_MODEL,'embeddings':[V]} if path=='/api/embed' else Fake().response
        o.request=request
        o.embed('Вопрос');o.chat([{'role':'user','content':'Exact'}])
        self.assertEqual(len(calls),2)
        self.assertIs(calls[0][1]['truncate'],False)
        self.assertEqual(calls[0][1]['options'],core.EMBED_OPTIONS)
        self.assertEqual(calls[1][1]['messages'],[{'role':'user','content':'Exact'}])
        self.assertIs(calls[1][1]['think'],False)
        self.assertIs(calls[1][1]['stream'],False)
        self.assertEqual(calls[1][1]['format'],core.SCHEMA)
        self.assertEqual(calls[1][1]['options']['num_ctx'],8192)
    def test_tag_and_remote_identity(self):
        o=core.Ollama()
        def good(path,payload=None):
            if path=='/api/tags':return {'models':[{'name':core.MODEL,'digest':core.GEN_DIGEST},{'name':core.EMBED_MODEL,'digest':core.EMBED_DIGEST}]}
            return {'model_info':{'qwen3.context_length':32768}}
        o.request=good;self.assertEqual(o.verify()['generator_digest'],core.GEN_DIGEST)
        o.request=lambda path,payload=None:good(path,payload)|({'remote_host':'https://remote'} if path=='/api/show' else {})
        with self.assertRaises(ValueError):o.verify()
        o.request=lambda path,payload=None:{'models':[{'name':core.MODEL,'digest':'wrong'}]}
        with self.assertRaises(ValueError):o.verify()
    def test_mixed_cloud_capabilities_fail_closed(self):
        o=core.Ollama()
        o.request=lambda path,payload=None:({'models':[{'name':core.MODEL,'digest':core.GEN_DIGEST},
            {'name':core.EMBED_MODEL,'digest':core.EMBED_DIGEST}]} if path=='/api/tags' else
            {'model_info':{'qwen3.context_length':32768},'capabilities':['completion','cloud']})
        with self.assertRaisesRegex(ValueError,'remote_model'):o.verify()
    def test_missing_reported_embedding_model_fails(self):
        o=core.Ollama();o.request=lambda path,payload=None:{'embeddings':[V]}
        with self.assertRaisesRegex(ValueError,'embedding_response'):o.embed('Вопрос')
    def test_timeout_has_duration(self):
        f=Fake();f.chat=lambda m,**kw: (_ for _ in ()).throw(TimeoutError('timeout'))
        r=core.Engine([chunk()],{},f).ask('Задание дня 18')
        self.assertIsNotNone(r['times']['generation'])
    def test_index_mismatched_generation(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'current.json').write_text('{"generation":"wrong"}')
            with self.assertRaisesRegex(ValueError,'generation'):core.load_index(root)

if __name__=='__main__':unittest.main()
