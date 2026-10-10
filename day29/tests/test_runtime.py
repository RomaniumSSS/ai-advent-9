import copy,json,sys,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,metrics,evaluate
P=core.load_profiles()
C={'document_id':'assignment:18','chunk_id':'c18','source':'assignment','day':18,'text':'Требование: сохранять оригинальный текст.','source_ref':'S1'}
I={'generation':core.GENERATION,'db_sha256':core.DB_SHA}
def snap():return core.make_snapshot('Что требуется сделать в задании дня 18?',[dict(C)],I)
class Client:
    def __init__(self,answer=None,reason='stop',loaded=True,load=100):self.calls=[];self.answer=answer or {'answer':'Нужно сохранять текст.','source_refs':['S1']};self.reason=reason;self.loaded=loaded;self.load=load
    def verify(self,p=None):return {'generator_digest':(p or P['baseline'])['digest'],'embedding_digest':core.EMBED_DIGEST}
    def request(self,path,payload=None):
        self.calls.append((path,payload))
        if path=='/api/ps':return {'models':[{'name':core.MODEL,'digest':core.GEN_DIGEST,'size':123,'size_vram':123,'expires_at':'future'}] if self.loaded else []}
        return {'model':core.MODEL,'done':True,'done_reason':self.reason,'prompt_eval_count':100,'eval_count':5,'eval_duration':1000000000,'load_duration':self.load,'message':{'content':json.dumps(self.answer)}}
class FakeSampler:
    def start(self):pass
    def stop(self):return {'observed_max_sum_rss_bytes':100,'comparison_eligible':True,'sample_interval_seconds':.5}
class Runtime(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.lockpatch=patch('core.tempfile.gettempdir',return_value=self.tmp.name);self.lockpatch.start()
        self.patch=patch('metrics.Sampler',FakeSampler);self.patch.start()
    def tearDown(self):self.patch.stop();self.lockpatch.stop();self.tmp.cleanup()
    def test_independent_baseline_parity(self):
        f=json.loads((core.HERE/'results/baseline-reference.json').read_text());self.assertEqual(f['system'],core.SYSTEM);self.assertEqual(f['generator_options'],P['baseline']['options'])
        for c in f['cases']:
            snapshot=core.make_snapshot(c['question'],c['selected'],I)
            self.assertEqual(core.snapshot_messages(snapshot,P['baseline']),c['messages'])
            self.assertEqual(core.profile_payload(P['baseline'],c['messages'])['format'],c['response_format'])
    def test_one_factor_profiles(self):
        b=P['baseline']
        for name,key in [('temperature','temperature'),('max-output','num_predict'),('context','num_ctx')]:
            self.assertEqual(P[name]['system'],b['system']);self.assertEqual([k for k in b['options'] if P[name]['options'][k]!=b['options'][k]],[key])
        self.assertEqual(P['prompt']['options'],b['options']);self.assertNotIn('Day19',P['prompt']['system'])
    def test_budget_reject_before_network_no_truncation(self):
        s=snap();before=copy.deepcopy(s);client=Client();p=copy.deepcopy(P['baseline']);p['options']['num_ctx']=50
        r=core.Engine([],I,client).generate(s,p,'tiny');self.assertEqual(r['status'],'rejected');self.assertEqual(client.calls,[]);self.assertEqual(s,before)
    def test_context_order_text_map_and_question_mutation(self):
        for field in ('question','selected','source_reference_map'):
            s=snap()
            if field=='question':s[field]+=' changed'
            elif field=='selected':s[field][0]['text']+=' changed'
            else:s[field]['S1']['chunk_id']='other'
            with self.assertRaises(ValueError):core.validate_snapshot(s)
    def test_actual_options_and_original_sources(self):
        client=Client();s=snap();r=core.Engine([],I,client).generate(s,P['temperature'],'temperature')
        self.assertEqual(r['status'],'done');self.assertEqual(client.calls[1][1]['options'],P['temperature']['options']);self.assertFalse(client.calls[1][1]['think']);self.assertEqual(r['answer']['quotes'][0]['text'],C['text'])
    def test_invalid_refs_unknown_and_length(self):
        for answer in ({'answer':'Ответ','source_refs':['S2']},{'answer':'Ответ','source_refs':['S1','S1']},{'answer':'Ответ','source_refs':[]},['invalid']):
            r=core.Engine([],I,Client(answer)).generate(snap(),P['baseline'],'baseline');self.assertEqual(r['status'],'error')
        r=core.Engine([],I,Client({'answer':'Не знаю по переданному контексту','source_refs':[]})).generate(snap(),P['baseline'],'baseline');self.assertEqual(r['status'],'unknown')
        r=core.Engine([],I,Client(reason='length')).generate(snap(),P['baseline'],'baseline');self.assertEqual(r['status'],'error')
    def test_empty_context_has_no_chat(self):
        client=Client();r=core.Engine([],I,client).generate(core.make_snapshot('q',[],I),P['baseline'],'baseline');self.assertEqual(r['status'],'unknown');self.assertFalse(any(p=='/api/chat' for p,_ in client.calls))
    def test_warm_cold_truth_and_unique_ids(self):
        engine=core.Engine([],I,Client());a=engine.generate(snap(),P['baseline'],'baseline',mode='warm');self.assertEqual(a['status'],'error')
        b=engine.generate(snap(),P['baseline'],'baseline',mode='cold');self.assertEqual(b['status'],'error');self.assertNotEqual(a['request_id'],b['request_id'])
        r=engine.generate(snap(),P['baseline'],'baseline',mode='warm',warmup={'request_id':'receipt','status':'done','mode':'warmup','profile_sha256':core.sha(P['baseline']),'model':core.MODEL,'digest':core.GEN_DIGEST,'finished_at':'observed'});self.assertEqual(r['status'],'done');self.assertTrue(r['comparable'])
        r=core.Engine([],I,Client(load=500000000)).generate(snap(),P['baseline'],'baseline',mode='warm',warmup={'request_id':'receipt','status':'done','mode':'warmup','profile_sha256':core.sha(P['baseline']),'model':core.MODEL,'digest':core.GEN_DIGEST,'finished_at':'observed'});self.assertFalse(r['comparable']);self.assertEqual(r['status'],'error')
    def test_arbitrary_warmup_id_not_proof(self):
        r=core.Engine([],I,Client()).generate(snap(),P['baseline'],'baseline',mode='warm',warmup='invented-id')
        self.assertEqual(r['status'],'error');self.assertFalse(r['comparable'])
    def test_missing_warm_load_metric_not_comparable(self):
        r=core.Engine([],I,Client(load=None)).generate(snap(),P['baseline'],'baseline',mode='warm',warmup={'request_id':'receipt','status':'done','mode':'warmup','profile_sha256':core.sha(P['baseline']),'model':core.MODEL,'digest':core.GEN_DIGEST,'finished_at':'observed'})
        self.assertEqual(r['status'],'error');self.assertFalse(r['comparable']);self.assertEqual(r['error']['message'],'warm_missing_load_metric')
    def test_lock_and_release_after_exception(self):
        with core.generation_lock():
            with self.assertRaisesRegex(ValueError,'busy'):
                with core.generation_lock():pass
        with core.generation_lock():pass
    def test_loopback_routes(self):
        with self.assertRaises(ValueError):core.Ollama('http://localhost:11434')
        with self.assertRaises(ValueError):core.Ollama().request('/evil')
    def test_public_filter_before_search(self):
        vec=[1.0]+[0.0]*1023
        selected,_,_=core.retrieve([{**C,'vector':vec},{**C,'source':'discussion','chunk_id':'private','vector':vec}], 'Что требуется в задании дня 18?',vec,'public')
        self.assertEqual([c['chunk_id'] for c in selected],['c18'])
    def test_metrics_null_and_units(self):
        m=metrics.ollama_metrics({'eval_count':10,'eval_duration':2000000000,'load_duration':-1});self.assertEqual(m['tokens_per_second'],5);self.assertEqual(m['seconds']['eval_duration'],2);self.assertIsNone(m['load_duration'])
        self.assertIsNone(metrics.ollama_metrics({'eval_count':1,'eval_duration':0})['tokens_per_second'])
        self.assertIsNone(metrics.summarize_samples([{'processes':None,'sum_rss_bytes':None}],.5)['observed_max_sum_rss_bytes'])
    def test_multiple_process_rss_pid_changes(self):
        processes=metrics.parse_processes('10 1 100 /usr/bin/ollama\n11 10 200 /usr/bin/llama-server\n12 1 999 /usr/bin/python')
        self.assertEqual(len(processes),2)
        samples=[{'processes':processes,'sum_rss_bytes':307200},{'processes':[dict(processes[1],pid=20),processes[0]],'sum_rss_bytes':500000}]
        result=metrics.summarize_samples(samples,.5);self.assertEqual(result['observed_max_sum_rss_bytes'],500000);self.assertEqual(result['pids'],[10,11,20]);self.assertFalse(result['comparison_eligible']);self.assertNotIn('size_vram',result)
    def test_statistics_and_no_false_optimization(self):
        self.assertEqual(evaluate.distribution([1,9,3])['median'],3);self.assertEqual(evaluate.distribution([1,9,3])['max'],9)
        self.assertFalse(evaluate.optimization_verdict([],[],{})['proven'])
        self.assertFalse(evaluate.optimization_verdict([],[],{'all_final_answers_assessed':True,'no_regression':True,'no_fabrication':True,'unknown_preserved':True})['proven'])
if __name__=='__main__':unittest.main()
