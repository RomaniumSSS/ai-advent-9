import contextlib,copy,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,evaluate
class Client:
    def __init__(self,refuse_unload=False):self.q4=True;self.q8=False;self.calls=[];self.refuse_unload=refuse_unload
    def verify(self,p):self.calls.append(('verify',p['model']));return {}
    def request(self,path,payload=None):
        self.calls.append((path,payload))
        if path=='/api/generate':
            with unittest.TestCase().assertRaisesRegex(ValueError,'busy'):
                with core.generation_lock():pass
            if not self.refuse_unload:self.q4=False
            return {'done':True}
        entries=[]
        if self.q4:entries.append({'name':core.MODEL,'digest':core.GEN_DIGEST})
        if self.q8:entries.append({'name':'qwen3:8b-q8_0','digest':core.Q8_DIGEST})
        return {'models':entries}
class Engine:
    def __init__(self,client):self.client=client;self.generations=[]
    def generate(self,snapshot,p,pid,**kw):
        self.generations.append(kw);self.client.q8=True
        return {'run_id':kw['run_id'],'request_id':str(len(self.generations)),'profile_id':pid,'case_id':'E02','mode':kw['mode'],'status':'done','times':{'generation':1},'profile_sha256':core.sha(p),'model':p['model'],'digest':p['digest'],'finished_at':'observed','generation_called':True}
class Quantization(unittest.TestCase):
    def test_isolated_q8_exactly_one_warmup_two_answers(self):
        with tempfile.TemporaryDirectory() as directory,patch('core.tempfile.gettempdir',return_value=directory),contextlib.redirect_stdout(io.StringIO()):
            p=copy.deepcopy(core.load_profiles()['candidate']);p.update(model='qwen3:8b-q8_0',digest=core.Q8_DIGEST,quantization='Q8_0');client=Client();engine=Engine(client)
            _,runs=evaluate.run_series(engine,{'contexts':[{'case_id':'E02','snapshot':{}}]},{'q8':p},'quant',Path(directory)/'runs',['q8'])
            self.assertEqual([g['mode'] for g in engine.generations],['warmup','warm','warm'])
            self.assertEqual(len(runs),2);self.assertTrue(all(r['quantization_isolation']['q4_absence_confirmed'] for r in runs))
            unload=[c for c in client.calls if c[0]=='/api/generate'];self.assertEqual(unload,[('/api/generate',{'model':core.MODEL,'keep_alive':0})])
            self.assertTrue(all(g['locked'] for g in engine.generations))
    def test_failed_first_warmup_saves_preparation_and_failed_series(self):
        class FailedEngine(Engine):
            def generate(self,*args,**kwargs):
                r=super().generate(*args,**kwargs);r.update(status='error',error={'phase':'generation','message':'incomplete_or_wrong_model_answer'},raw_response={'done_reason':'length'});return r
        with tempfile.TemporaryDirectory() as directory,patch('core.tempfile.gettempdir',return_value=directory),contextlib.redirect_stdout(io.StringIO()):
            p=copy.deepcopy(core.load_profiles()['candidate']);p.update(model='qwen3:8b-q8_0',digest=core.Q8_DIGEST,quantization='Q8_0');engine=FailedEngine(Client());output=Path(directory)/'runs'
            with self.assertRaisesRegex(ValueError,'warmup_failed'):evaluate.run_series(engine,{'contexts':[{'case_id':'E02','snapshot':{}}]},{'q8':p},'quant',output,['q8'])
            self.assertEqual(len(engine.generations),1);self.assertEqual(engine.generations[0]['mode'],'warmup')
            run=next(output.iterdir());self.assertTrue((run/'quant-preparation.json').exists());self.assertTrue((run/'series.json').exists())
            preparation=json.loads((run/'quant-preparation.json').read_text());series=json.loads((run/'series.json').read_text())
            self.assertTrue(preparation['quantization_isolation']['q4_absence_confirmed']);self.assertEqual(series['status'],'error');self.assertIn('warmup_failed',series['stop_reason']);self.assertEqual(series['request_ids'],[]);self.assertEqual(series['warmup_request_ids'],['1']);self.assertEqual(series['attempt_count'],1)
    def test_unconfirmed_unload_stops_before_generation(self):
        with tempfile.TemporaryDirectory() as directory,patch('core.tempfile.gettempdir',return_value=directory):
            p=copy.deepcopy(core.load_profiles()['candidate']);p.update(model='qwen3:8b-q8_0',digest=core.Q8_DIGEST,quantization='Q8_0');engine=Engine(Client(refuse_unload=True))
            with self.assertRaisesRegex(ValueError,'unload_not_confirmed'):evaluate.run_series(engine,{'contexts':[{'case_id':'E02','snapshot':{}}]},{'q8':p},'quant',directory,['q8'])
            self.assertEqual(engine.generations,[])
if __name__=='__main__':unittest.main()
