"""Readonly inspector corruption and privacy checks; synthetic only."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import index_pipeline as pipeline
import inspect_index

class Tokenizer:
    identity={'model':pipeline.TOKENIZER_MODEL,'revision':'synthetic'}
    def count(self,text):return len(text)
    def offsets(self,text):return [(i,i+1) for i in range(len(text))]
class Embedder:
    batch_size=8;calls=0;inputs=0;seconds=0;prompt_eval_count=0
    def embed(self,texts):return [[1.0]+[0.0]*1023 for _ in texts]
class InspectorTest(unittest.TestCase):
    def test_notready_without_current(self):
        with tempfile.TemporaryDirectory() as d:self.assertEqual(inspect_index.inspect(d)['status'],'notready')
    def test_readonly_private_and_corruptions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);doc={'document_id':'synthetic','source':'personal_note','title':'SECRET_TITLE','text':'SECRET_PRIVATE_TEXT','members':[{'source_key':'note:synthetic'}]}
            with redirect_stdout(io.StringIO()):report=pipeline.build_pair([doc],Tokenizer(),Embedder(),root,{'model':pipeline.MODEL,'digest':'synthetic'})
            directory=root/report['generation'];before={p.name:pipeline.file_hash(p) for p in directory.iterdir() if p.is_file()}
            result=inspect_index.inspect(root);self.assertEqual(result['status'],'ready');self.assertNotIn('SECRET',json.dumps(result))
            self.assertEqual(before,{p.name:pipeline.file_hash(p) for p in directory.iterdir() if p.is_file()})
            expected=directory/'expected-chunks.json';raw=expected.read_bytes();expected.write_bytes(raw+b' ')
            with self.assertRaises(ValueError):inspect_index.inspect(root)
            expected.write_bytes(raw);conn=sqlite3.connect(directory/'fixed.db');conn.execute('DELETE FROM chunks');conn.commit();conn.close()
            with self.assertRaises(ValueError):inspect_index.inspect(root)
    def test_pointer_path_escape(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'current.json').write_text('{"generation":"../escape"}')
            with self.assertRaises(ValueError):inspect_index.inspect(d)
if __name__=='__main__':unittest.main()
