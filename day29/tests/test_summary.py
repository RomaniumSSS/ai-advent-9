import contextlib,copy,io,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evaluate
class Summary(unittest.TestCase):
    def rows(self):
        return [{'run_id':run,'request_id':run+'-req','profile_id':'candidate','mode':'warm','case_id':'E02','status':'done','comparable':True,'times':{'generation':seconds},'resources':None} for run,seconds in [('run-one',10),('run-two',100)]]
    def test_distinct_runs_are_not_averaged_together(self):
        s=evaluate.summarize(self.rows());self.assertEqual(len(s['groups']),2);self.assertEqual({g['run_id'] for g in s['groups']},{'run-one','run-two'});self.assertEqual(sorted(g['generation_seconds']['median'] for g in s['groups']),[10,100])
    def test_cli_explicit_run_id_without_index_or_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            for r in self.rows():
                path=Path(directory)/r['run_id'];path.mkdir();(path/'receipt.json').write_text(json.dumps(r))
            stream=io.StringIO()
            with patch('evaluate.load_index',side_effect=AssertionError('summary must not load index')),contextlib.redirect_stdout(stream):
                self.assertEqual(evaluate.main(['summary','--output',directory,'--run-id','run-one']),0)
            result=json.loads(stream.getvalue());self.assertEqual(len(result['groups']),1);self.assertEqual(result['groups'][0]['run_id'],'run-one')
    def test_semantic_assessment_binds_actual_receipts(self):
        import core
        from test_comparison import series,Q
        runs=series('baseline',10)+series('candidate',8)
        for r in runs:r['run_id']='test-warm'
        assessment={'run_id':'test-warm','suite_sha256':core.sha(evaluate.read(core.HERE/'eval-suite.json')),'quality_gate':Q,
                    'rows':[{**{k:r[k] for k in ('request_id','profile_id','case_id','repeat')},'receipt_sha256':core.sha(r)} for r in runs]}
        self.assertTrue(evaluate.analyze(runs,assessment,'test-warm')['proven'])
        broken=copy.deepcopy(runs);broken[0]['answer']['answer']='Edited after assessment'
        with self.assertRaisesRegex(ValueError,'receipt_mismatch'):evaluate.analyze(broken,assessment,'test-warm')
        with self.assertRaisesRegex(ValueError,'run_id_mismatch'):evaluate.analyze(runs,assessment,'wrong-run')
    def test_explicit_run_id_selects_one_series(self):
        # Здесь проверяется действующий summary без нового API: явный CLI фильтр
        # добавляется после RED группировки в отдельном контрактном тесте.
        s=evaluate.summarize([r for r in self.rows() if r['run_id']=='run-one']);self.assertEqual(len(s['groups']),1);self.assertEqual(s['groups'][0]['run_id'],'run-one')
if __name__=='__main__':unittest.main()
