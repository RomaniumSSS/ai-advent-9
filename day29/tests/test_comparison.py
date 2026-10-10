import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evaluate,core

def series(pid,seconds):
    p=core.load_profiles()[pid]
    def inputs(cid):
        days=(18,) if cid!='E02' else (19,20)
        selected=[{'document_id':f'assignment:{d}','chunk_id':f'c{d}','source':'assignment','day':d,'text':'Подтверждённое требование.'} for d in days]
        snapshot=core.make_snapshot(cid,selected,{'generation':core.GENERATION,'db_sha256':core.DB_SHA})
        messages=core.snapshot_messages(snapshot,p)
        return {'selected':selected,'context_sha256':snapshot['context_sha256'],'messages':messages,'prompt_sha256':core.sha(messages),'payload':core.profile_payload(p,messages),'citations_valid':True}
    return [{'request_id':f'{pid}-{cid}-{rep}','profile_id':pid,'profile_sha256':core.sha(p),'profile':p,'scope':'public',
             'case_id':cid,'repeat':rep,'mode':'warm','comparable':True,'status':'unknown' if cid=='E03' else 'done',
             **inputs(cid),'question':cid,'index':{'generation':core.GENERATION,'db_sha256':core.DB_SHA},
             'model':core.MODEL,'digest':core.GEN_DIGEST,'times':{'generation':seconds},'timing_scope':'generator_replay',
             'answer':{'answer':'Не знаю по переданному контексту' if cid=='E03' else 'Подтверждённое требование.','sources':[] if cid=='E03' else [{'source':f'assignment:{d}','chunk_id':f'c{d}'} for d in ((19,20) if cid=='E02' else (18,))],'quotes':[] if cid=='E03' else [{'chunk_id':f'c{d}','text':'Подтверждённое требование.'} for d in ((19,20) if cid=='E02' else (18,))]},
             'resources':{'comparison_eligible':True,'observed_max_sum_rss_bytes':1000,'sample_interval_seconds':.5,
                          'observed_roles':['daemon','runner'],'missing_samples':0,'process_counts':[2], 'incomplete_process_samples':0},'placement_after':{'size':100,'size_vram':100}}
            for cid in ('E01','E02','E03') for rep in (1,2)]
Q={'all_final_answers_assessed':True,'no_regression':True,'no_fabrication':True,'unknown_preserved':True}
class Comparison(unittest.TestCase):
    def test_valid_speed_win(self):self.assertTrue(evaluate.optimization_verdict(series('baseline',10),series('candidate',8),Q)['proven'])
    def test_unfair_context_and_model_cannot_claim_win(self):
        for field in ('context_sha256','question','model','digest','index','timing_scope'):
            b=series('baseline',10);c=series('candidate',8);c[0][field]='mismatch'
            self.assertFalse(evaluate.optimization_verdict(b,c,Q)['proven'],field)
    def test_e03_receipts_override_false_manual_quality(self):
        for field,value in [('status','done'),('sources',[{'source':'invented'}]),('quotes',[{'text':'invented'}])]:
            c=series('candidate',8);e03=next(r for r in c if r['case_id']=='E03')
            if field=='status':e03[field]=value
            else:e03['answer'][field]=value
            self.assertFalse(evaluate.optimization_verdict(series('baseline',10),c,Q)['proven'])
    def test_baseline_and_candidate_group_identities(self):
        b=series('baseline',10);b[0]['profile_id']='candidate'
        self.assertFalse(evaluate.optimization_verdict(b,series('candidate',8),Q)['proven'])
        c=series('candidate',8);c[0]['profile_id']='prompt'
        self.assertFalse(evaluate.optimization_verdict(series('baseline',10),c,Q)['proven'])
    def test_fully_gpu_allocation_sizes_may_differ_for_rss(self):
        b=series('baseline',10);c=series('candidate',10)
        for r in c:r['placement_after']={'size':80,'size_vram':80};r['resources']['observed_max_sum_rss_bytes']=800
        result=evaluate.optimization_verdict(b,c,Q)
        self.assertTrue(result['proven']);self.assertTrue(result['resource_comparable']);self.assertIn('observed_RSS_median_10_percent',result['reasons'])
    def test_e01_e02_cannot_be_unknown_or_missing_required_sources(self):
        for cid in ('E01','E02'):
            for broken in ('unknown','missing-source','foreign-selected'):
                c=series('candidate',8);r=next(r for r in c if r['case_id']==cid)
                if broken=='unknown':r['status']='unknown';r['answer']['sources']=[];r['answer']['quotes']=[]
                elif broken=='missing-source':r['answer']['sources']=r['answer']['sources'][1:];r['answer']['quotes']=r['answer']['quotes'][1:]
                else:r['selected'][0]['document_id']='assignment:99'
                self.assertFalse(evaluate.optimization_verdict(series('baseline',10),c,Q)['proven'],(cid,broken))
    def test_duplicate_ids_cannot_claim_win(self):
        b=series('baseline',10);c=series('candidate',8);c[0]['request_id']=b[0]['request_id']
        self.assertFalse(evaluate.optimization_verdict(b,c,Q)['proven'])
if __name__=='__main__':unittest.main()
