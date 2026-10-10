import sys, unittest, copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
class Contracts(unittest.TestCase):
    def test_options_forwarded(self):
        p={'model':core.MODEL,'options':{'temperature':.2,'num_ctx':6144,'num_predict':384}}
        self.assertEqual(core.profile_payload(p,[{'role':'user','content':'x'}])['options'],p['options'])
    def test_mutated_snapshot_rejected(self):
        snapshot={'question':'q','selected':[],'index':{'generation':core.GENERATION,'db_sha256':core.DB_SHA},'source_reference_map':{},'context_sha256':'not-the-content-hash'}
        with self.assertRaisesRegex(ValueError,'snapshot'): core.validate_snapshot(snapshot)
if __name__=='__main__':unittest.main()
