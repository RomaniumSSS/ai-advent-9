import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evaluate,core
class FrozenManifest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'frozen.json'
        suite=evaluate.read(core.HERE/'eval-suite.json')
        self.data={'suite_sha256':core.sha(suite),'profiles_sha256':core.sha(core.load_profiles()),'source_manifest':evaluate.manifest(),
                   'contexts':[{'case_id':c['case_id'],'snapshot':core.make_snapshot(c['question'],[],{'generation':core.GENERATION,'db_sha256':core.DB_SHA})} for c in suite['cases']]}
    def tearDown(self):self.tmp.cleanup()
    def write(self,data):
        data=dict(data);data['freeze_sha256']=core.sha(data);self.path.write_text(json.dumps(data));return self.path
    def test_changed_source_not_implicitly_accepted(self):
        d=copy.deepcopy(self.data);d['source_manifest']['core.py']='old-version'
        with self.assertRaisesRegex(ValueError,'source'):evaluate.frozen_inputs(self.write(d))
    def test_changed_profiles_not_implicitly_accepted(self):
        d=copy.deepcopy(self.data);d['profiles_sha256']='old-profile'
        with self.assertRaisesRegex(ValueError,'profile'):evaluate.frozen_inputs(self.write(d))
    def test_bind_preserves_inputs_and_parent_without_inference(self):
        old=self.write(self.data);old_bytes=old.read_bytes();new=Path(self.tmp.name)/'bound.json'
        result=evaluate.bind_inputs(old,new,core.load_profiles())
        self.assertEqual(old.read_bytes(),old_bytes);self.assertEqual(result['contexts'],self.data['contexts'])
        self.assertEqual(result['parent_freeze_sha256'],json.loads(old_bytes)['freeze_sha256'])
        self.assertEqual(evaluate.frozen_inputs(new),result)
        with self.assertRaisesRegex(ValueError,'exists'):evaluate.bind_inputs(old,new,core.load_profiles())
    def test_current_manifest_valid(self):self.assertEqual(evaluate.frozen_inputs(self.write(self.data))['contexts'],self.data['contexts'])
if __name__=='__main__':unittest.main()
