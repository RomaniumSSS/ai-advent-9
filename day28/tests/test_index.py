"""Искусственный SQLite: несовместимые снимки отвергаются до запросов модели."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
from test_core import V

class IndexContract(unittest.TestCase):
    def fixture(self,root,bad_model=False,bad_vector=False):
        root=Path(root);(root/'current.json').write_text(json.dumps({'generation':core.GENERATION}))
        directory=root/core.GENERATION;directory.mkdir();path=directory/'structure.db'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE metadata (key TEXT,value TEXT)')
            db.execute('CREATE TABLE chunks (chunk_id TEXT,metadata_json TEXT,vector_json TEXT)')
            identity={'strategy':'structure','corpus_sha256':core.CORPUS_SHA,'config':{'model':{
                'model':core.EMBED_MODEL,'digest':'wrong' if bad_model else core.EMBED_DIGEST,
                'options':core.EMBED_OPTIONS,'truncate':False}}}
            db.execute('INSERT INTO metadata VALUES (?,?)',('identity',json.dumps(identity)))
            rows=[]
            for i in range(724):
                c={'chunk_id':str(i),'document_id':'doc:'+str(min(i,662)),'text':'Fixture public text',
                   'text_sha256':hashlib.sha256(b'Fixture public text').hexdigest(),'source':'assignment','day':18}
                rows.append((str(i),json.dumps(c),json.dumps([0]*1024 if bad_vector and i==0 else V)))
            db.executemany('INSERT INTO chunks VALUES (?,?,?)',rows)
        db.close()
        return path
    def test_read_only_and_full_identity(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.fixture(root);before=path.read_bytes();digest=hashlib.sha256(before).hexdigest()
            with patch.object(core,'DB_SHA',digest):identity,chunks=core.load_index(root)
            self.assertEqual(len(chunks),724);self.assertEqual(identity['corpus_sha256'],core.CORPUS_SHA)
            self.assertEqual(path.read_bytes(),before)
            self.assertFalse(path.with_name(path.name+'-journal').exists())
    def test_sha_model_vector_fail_closed(self):
        for model,vec,reason in [(False,False,'sha'),(True,False,'identity'),(False,True,'vector')]:
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as root:
                path=self.fixture(root,model,vec)
                digest='wrong' if reason=='sha' else hashlib.sha256(path.read_bytes()).hexdigest()
                with patch.object(core,'DB_SHA',digest),self.assertRaisesRegex(ValueError,reason):core.load_index(root)
    def test_loader_closes_connection(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.fixture(root);connection=sqlite3.connect(path)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(core,'DB_SHA',digest),patch.object(core.sqlite3,'connect',return_value=connection):core.load_index(root)
            try:
                with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
            finally:connection.close()

if __name__=='__main__':unittest.main()
