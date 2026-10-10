from contextlib import closing
import hashlib,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
class Index(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'current.json').write_text(json.dumps({'generation':core.GENERATION}));self.path=self.root/core.GENERATION/'structure.db';self.path.parent.mkdir()
        with closing(sqlite3.connect(self.path)) as db:db.execute('CREATE TABLE metadata(key TEXT,value TEXT)');db.commit()
    def tearDown(self):self.tmp.cleanup()
    def test_generation_and_sha_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'index_sha_mismatch'):core.load_index(self.root)
        (self.root/'current.json').write_text(json.dumps({'generation':'foreign'}))
        with self.assertRaisesRegex(ValueError,'generation_mismatch'):core.load_index(self.root)
    def test_embedding_identity_fail_and_readonly(self):
        identity={'corpus_sha256':core.CORPUS_SHA,'strategy':'structure','config':{'model':{'model':core.EMBED_MODEL,'digest':'foreign','options':core.EMBED_OPTIONS,'truncate':False}}}
        with closing(sqlite3.connect(self.path)) as db:db.execute('INSERT INTO metadata VALUES (?,?)',('identity',json.dumps(identity)));db.commit()
        digest=hashlib.sha256(self.path.read_bytes()).hexdigest();connect=sqlite3.connect;observed=[]
        def inspect(database,**kwargs):
            self.assertIn('?mode=ro&immutable=1',database);db=connect(database,**kwargs)
            with self.assertRaisesRegex(sqlite3.OperationalError,'readonly'):db.execute('CREATE TABLE forbidden(x)')
            observed.append(database);return db
        with patch.object(core,'DB_SHA',digest),patch.object(core.sqlite3,'connect',side_effect=inspect):
            with self.assertRaisesRegex(ValueError,'incompatible_index_identity'):core.load_index(self.root)
        self.assertEqual(len(observed),1)
    def test_vector_dimension_and_finite(self):
        for value in ([1.0]*10,[float('nan')]+[0.0]*1023,[0.0]*1024):
            with self.assertRaises(ValueError):core.vector(value)
if __name__=='__main__':unittest.main()
